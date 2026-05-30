//! 渲染：近黑背景 + 声呐点云（miniquad GL_POINTS 底层管线，带深度遮挡）+ 枪口细线。
//!
//! 点云用 miniquad `PrimitiveType::Points` 绘制：vertex shader 写 `gl_PointSize`，
//! 得到“屏幕固定像素大小的干净方点”。为了让墙后的点被遮挡，先用真实几何做一个
//! 深度预通道（只写深度），再画点云时开启深度测试。
//!
//! 关键事实（已从 miniquad 0.4.10 源码确认）：
//! - Windows 走桌面 OpenGL（3.1 core, forward-compatible）。core profile 下
//!   `gl_PointSize` 仅在 `GL_PROGRAM_POINT_SIZE` 开启时生效；miniquad **从不**
//!   开启它，故渲染器初始化时我们自己 `glEnable(GL_PROGRAM_POINT_SIZE)`。
//!   该 GL 函数指针由 miniquad 启动时加载，可经 `macroquad::miniquad::gl` 调用。
//! - miniquad 的 `draw` 走 `glDrawElementsInstanced`，**必须**有 index buffer，
//!   故点云也用索引绘制（索引就是 0,1,2,…）。
//! - `buffer_update` 要求新数据字节数 <= 缓冲容量，且不能扩容；故按最大点数预分配，
//!   每帧只更新前 N 个点、只 draw N 个。
//! - miniquad `apply_pipeline` 用 `depth_write` 字段同时开关深度测试+写入
//!   （深度写掩码始终为 GL 默认 TRUE）；故两个管线都设 `depth_write: true`。

use crate::app::config::{
    CLEAR_COLOR, MAX_BEAM_LINES, POINT_DEPTH_BIAS, POINT_PIXEL_SIZE,
};
use crate::sonar::system::{Point, Sonar};
use crate::world::geometry::World;
use macroquad::camera::Camera;
use macroquad::miniquad::{
    Bindings, BufferId, BufferSource, BufferType, BufferUsage, Comparison, Pipeline,
    PipelineParams, PrimitiveType, ShaderMeta, ShaderSource, UniformBlockLayout,
    UniformDesc, UniformType, UniformsSource, VertexAttribute, VertexFormat,
};
use macroquad::prelude::*;
use macroquad::window::get_internal_gl;

use crate::app::config::SONAR_MAX_POINTS;

/// 点云顶点：位置 + 颜色。`#[repr(C)]` 保证与 GL 顶点布局字节对齐一致。
#[repr(C)]
#[derive(Clone, Copy)]
struct PointVertex {
    pos: [f32; 3],
    color: [f32; 4],
}

/// 上传给 shader 的 uniform 块。
/// miniquad GL 后端按 ShaderMeta 中 uniform 声明顺序、以 4 字节(float)为单位**紧密**读取，
/// 不做任何对齐填充；故此 #[repr(C)] 字段顺序与类型必须与 ShaderMeta 逐一对应：
/// mvp(16f) + cam_pos(3f) + point_size(1f) + depth_bias(1f)。
#[repr(C)]
struct PointUniforms {
    mvp: [f32; 16],
    cam_pos: [f32; 3],
    point_size: f32,
    depth_bias: f32,
}

#[repr(C)]
struct DepthUniforms {
    mvp: [f32; 16],
}

/// 初始化一次后缓存的全部 GL 资源。
struct Gpu {
    // 点云管线
    point_pipeline: Pipeline,
    point_vbo: BufferId,
    point_ibo: BufferId,
    point_capacity: usize,
    // 深度预通道（真实几何，只写深度）
    depth_pipeline: Pipeline,
    depth_vbo: BufferId,
    depth_ibo: BufferId,
    depth_index_count: i32,
    depth_capacity: usize, // 预分配的最大顶点数
}

pub struct Renderer {
    gpu: Option<Gpu>,
    // 切图时设 dirty，render 开头检测并 buffer_update 重传 depth 几何。
    world_dirty: bool,
}

impl Renderer {
    pub fn new() -> Self {
        // GL 资源延迟到首次 render 时创建：那时渲染上下文必定活跃。
        Self {
            gpu: None,
            world_dirty: false,
        }
    }

    /// 切换地图后调用：下一帧 render 时会用新 world 的几何重新填充 depth buffer。
    pub fn reload_world(&mut self) {
        self.world_dirty = true;
    }

    pub fn render(&mut self, camera: &Camera3D, sonar: &Sonar, world: &World) {
        let mvp = camera.matrix();

        // ---- 1. 用 miniquad 自己开一个默认 pass，同时清色 + 清深度 ----
        // macroquad 的 clear_background 只清颜色不清深度；这里直接用 begin_default_pass
        // 的 Clear 动作把 color 与 depth 一起清掉，确保点云/几何共享的是同一张刚清空的
        // 深度缓冲（默认帧缓冲）。
        unsafe {
            let mut gl = get_internal_gl();
            // 先冲刷 macroquad 此前可能积累的 2D 批次（本帧渲染器最先调用，通常为空，保险起见）。
            gl.flush();
            let ctx = gl.quad_context;

            // 懒初始化 GL 资源（含开启 GL_PROGRAM_POINT_SIZE）。
            if self.gpu.is_none() {
                self.gpu = Some(Gpu::new(ctx, world));
                self.world_dirty = false;
            }
            let gpu = self.gpu.as_mut().unwrap();

            // 地图切换后：用新 world 的几何重传 depth buffer。
            if self.world_dirty {
                gpu.depth_index_count =
                    upload_world_depth(ctx, gpu.depth_vbo, world, gpu.depth_capacity);
                self.world_dirty = false;
            }

            ctx.begin_default_pass(macroquad::miniquad::PassAction::Clear {
                color: Some((CLEAR_COLOR.r, CLEAR_COLOR.g, CLEAR_COLOR.b, CLEAR_COLOR.a)),
                depth: Some(1.0),
                stencil: None,
            });

            // ---- 2. 深度预通道：真实几何只写深度（颜色写掩码关闭）----
            let depth_uniforms = DepthUniforms {
                mvp: mvp.to_cols_array(),
            };
            ctx.apply_pipeline(&gpu.depth_pipeline);
            ctx.apply_bindings(&Bindings {
                vertex_buffers: vec![gpu.depth_vbo],
                index_buffer: gpu.depth_ibo,
                images: vec![],
            });
            ctx.apply_uniforms(UniformsSource::table(&depth_uniforms));
            ctx.draw(0, gpu.depth_index_count, 1);

            // ---- 3. 点云：上传本帧点，开启深度测试，画 GL_POINTS ----
            let points = sonar.points();
            let count = points.len().min(gpu.point_capacity);
            if count > 0 {
                // 重建顶点数据（位置 + 颜色）。
                let mut verts: Vec<PointVertex> = Vec::with_capacity(count);
                for p in &points[..count] {
                    verts.push(PointVertex {
                        pos: [p.pos.x, p.pos.y, p.pos.z],
                        color: [p.color.r, p.color.g, p.color.b, 0.9],
                    });
                }
                ctx.buffer_update(gpu.point_vbo, BufferSource::slice(&verts));

                let point_uniforms = PointUniforms {
                    mvp: mvp.to_cols_array(),
                    cam_pos: [camera.position.x, camera.position.y, camera.position.z],
                    point_size: POINT_PIXEL_SIZE,
                    depth_bias: POINT_DEPTH_BIAS,
                };
                ctx.apply_pipeline(&gpu.point_pipeline);
                ctx.apply_bindings(&Bindings {
                    vertex_buffers: vec![gpu.point_vbo],
                    index_buffer: gpu.point_ibo,
                    images: vec![],
                });
                ctx.apply_uniforms(UniformsSource::table(&point_uniforms));
                ctx.draw(0, count as i32, 1);
            }

            ctx.end_render_pass();
        }

        // ---- 4. 枪口细线：2D 屏幕空间，从右下枪口连到本帧新生点 ----
        // muzzle 位置与 UI 里 sonar gun 贴图共用同一公式（ui::system::muzzle_screen_pos）。
        let muzzle = crate::ui::system::muzzle_screen_pos(vec2(screen_width(), screen_height()));
        let beams: Vec<&Point> = sonar.new_points().collect();
        if !beams.is_empty() {
            let step = (beams.len() / MAX_BEAM_LINES).max(1);
            for p in beams.iter().step_by(step).take(MAX_BEAM_LINES) {
                if let Some(sp) = project(mvp, p.pos) {
                    let c = p.color;
                    draw_line(muzzle.x, muzzle.y, sp.x, sp.y, 1.0, Color::new(c.r, c.g, c.b, 0.4));
                }
            }
        }
    }
}

impl Gpu {
    fn new(ctx: &mut dyn macroquad::miniquad::RenderingBackend, world: &World) -> Self {
        // === 关键：开启 GL_PROGRAM_POINT_SIZE，否则桌面 core profile 下 gl_PointSize 被忽略 ===
        // miniquad 已在启动时加载该函数指针；此处直接调用其暴露的 GL 绑定。
        unsafe {
            use macroquad::miniquad::gl::{glEnable, GL_PROGRAM_POINT_SIZE};
            glEnable(GL_PROGRAM_POINT_SIZE);
        }

        // ---------- 点云管线 ----------
        let point_shader = ctx
            .new_shader(
                ShaderSource::Glsl {
                    vertex: POINT_VERTEX,
                    fragment: POINT_FRAGMENT,
                },
                ShaderMeta {
                    images: vec![],
                    uniforms: UniformBlockLayout {
                        uniforms: vec![
                            UniformDesc::new("mvp", UniformType::Mat4),
                            UniformDesc::new("cam_pos", UniformType::Float3),
                            UniformDesc::new("point_size", UniformType::Float1),
                            UniformDesc::new("depth_bias", UniformType::Float1),
                        ],
                    },
                },
            )
            .expect("point shader compile/link failed");

        let point_pipeline = ctx.new_pipeline(
            &[macroquad::miniquad::BufferLayout::default()],
            &[
                VertexAttribute::new("in_pos", VertexFormat::Float3),
                VertexAttribute::new("in_color", VertexFormat::Float4),
            ],
            point_shader,
            PipelineParams {
                primitive_type: PrimitiveType::Points,
                depth_test: Comparison::LessOrEqual,
                depth_write: true,
                color_blend: Some(macroquad::miniquad::BlendState::new(
                    macroquad::miniquad::Equation::Add,
                    macroquad::miniquad::BlendFactor::Value(
                        macroquad::miniquad::BlendValue::SourceAlpha,
                    ),
                    macroquad::miniquad::BlendFactor::OneMinusValue(
                        macroquad::miniquad::BlendValue::SourceAlpha,
                    ),
                )),
                ..Default::default()
            },
        );

        // 点云缓冲按最大点数预分配（Stream：每帧更新）。
        let point_capacity = SONAR_MAX_POINTS;
        let point_vbo = ctx.new_buffer(
            BufferType::VertexBuffer,
            BufferUsage::Stream,
            BufferSource::empty::<PointVertex>(point_capacity),
        );
        // 点云索引恒为 0,1,2,…，一次性建好（u32：20 万点超过 u16 上限）。
        let point_indices: Vec<u32> = (0..point_capacity as u32).collect();
        let point_ibo = ctx.new_buffer(
            BufferType::IndexBuffer,
            BufferUsage::Immutable,
            BufferSource::slice(&point_indices),
        );

        // ---------- 深度预通道管线（真实几何，只写深度）----------
        let depth_shader = ctx
            .new_shader(
                ShaderSource::Glsl {
                    vertex: DEPTH_VERTEX,
                    fragment: DEPTH_FRAGMENT,
                },
                ShaderMeta {
                    images: vec![],
                    uniforms: UniformBlockLayout {
                        uniforms: vec![UniformDesc::new("mvp", UniformType::Mat4)],
                    },
                },
            )
            .expect("depth shader compile/link failed");

        let depth_pipeline = ctx.new_pipeline(
            &[macroquad::miniquad::BufferLayout::default()],
            &[VertexAttribute::new("in_pos", VertexFormat::Float3)],
            depth_shader,
            PipelineParams {
                primitive_type: PrimitiveType::Triangles,
                depth_test: Comparison::LessOrEqual,
                depth_write: true,
                // 关闭颜色写入：只产生深度。
                color_write: (false, false, false, false),
                ..Default::default()
            },
        );

        // 深度几何按上限预分配（Stream），切换 GLB 时 buffer_update 重传。
        // 50k 三角形 = 150k 顶点 × 12B ≈ 1.8MB，覆盖所有手工地图。
        const DEPTH_MAX_VERTS: usize = 150_000;
        let depth_vbo = ctx.new_buffer(
            BufferType::VertexBuffer,
            BufferUsage::Stream,
            BufferSource::empty::<[f32; 3]>(DEPTH_MAX_VERTS),
        );
        // 索引一次性 0..MAX 建好（不画的部分靠 draw count 控制）。
        let depth_indices: Vec<u32> = (0..DEPTH_MAX_VERTS as u32).collect();
        let depth_ibo = ctx.new_buffer(
            BufferType::IndexBuffer,
            BufferUsage::Immutable,
            BufferSource::slice(&depth_indices),
        );
        let depth_index_count = upload_world_depth(ctx, depth_vbo, world, DEPTH_MAX_VERTS);
        let depth_capacity = DEPTH_MAX_VERTS;

        Self {
            point_pipeline,
            point_vbo,
            point_ibo,
            point_capacity,
            depth_pipeline,
            depth_vbo,
            depth_ibo,
            depth_index_count,
            depth_capacity,
        }
    }
}

/// 把 world 的真实几何扁平化为顶点数组，写入 depth vbo。返回索引数（= 顶点数）。
fn upload_world_depth(
    ctx: &mut dyn macroquad::miniquad::RenderingBackend,
    vbo: BufferId,
    world: &World,
    capacity: usize,
) -> i32 {
    let mut verts: Vec<[f32; 3]> = Vec::new();
    for tri in world.render_triangles() {
        if verts.len() + 3 > capacity {
            eprintln!(
                "[render] 警告：地图三角形超过 depth buffer 上限 {} 顶点，已截断",
                capacity
            );
            break;
        }
        for v in tri {
            verts.push([v.x, v.y, v.z]);
        }
    }
    ctx.buffer_update(vbo, BufferSource::slice(&verts));
    verts.len() as i32
}

/// 把世界坐标投影到屏幕像素坐标；相机背后或视野外返回 None。
fn project(mat: Mat4, world: Vec3) -> Option<Vec2> {
    let clip = mat * world.extend(1.0);
    if clip.w <= 0.0 {
        return None;
    }
    let ndc = clip.truncate() / clip.w;
    if ndc.x.abs() > 1.0 || ndc.y.abs() > 1.0 {
        return None;
    }
    Some(vec2(
        (ndc.x * 0.5 + 0.5) * screen_width(),
        (0.5 - ndc.y * 0.5) * screen_height(),
    ))
}

// ============ Shaders（GLSL #version 100，兼容 miniquad 全后端）============

// 点云 vertex：沿“指向相机”方向略微前移以避免与墙面 z-fighting，并写 gl_PointSize。
const POINT_VERTEX: &str = r#"#version 100
attribute vec3 in_pos;
attribute vec4 in_color;
uniform mat4 mvp;
uniform vec3 cam_pos;
uniform float point_size;
uniform float depth_bias;
varying lowp vec4 color;
void main() {
    vec3 to_cam = normalize(cam_pos - in_pos);
    vec3 biased = in_pos + to_cam * depth_bias;
    gl_Position = mvp * vec4(biased, 1.0);
    gl_PointSize = point_size;
    color = in_color;
}
"#;

// 圆形裁切：用 GL_POINTS 内建的 gl_PointCoord（[0,1]² 点精灵局部坐标），
// 把方点裁成圆点。圆是各向同性的——驱动对点的形变（裁切/拉伸）作用在圆上
// 比作用在方块上视觉上柔和得多，"歪斜方向"消失，毛病变得不显眼。
// 软边圆形：硬 discard 改成 smoothstep 衰减——亚像素位移时边缘像素亮度连续过渡，
// 消除相机轻微移动时的"逐像素跳变"闪烁感。
const POINT_FRAGMENT: &str = r#"#version 100
precision mediump float;
varying lowp vec4 color;
void main() {
    vec2 d = gl_PointCoord - vec2(0.5);
    float r2 = dot(d, d);
    if (r2 > 0.25) discard;
    float a = 1.0 - smoothstep(0.16, 0.25, r2);
    gl_FragColor = vec4(color.rgb, color.a * a);
}
"#;

// 深度预通道：仅变换位置，片元颜色无所谓（颜色写入已被管线关闭）。
const DEPTH_VERTEX: &str = r#"#version 100
attribute vec3 in_pos;
uniform mat4 mvp;
void main() {
    gl_Position = mvp * vec4(in_pos, 1.0);
}
"#;

const DEPTH_FRAGMENT: &str = r#"#version 100
precision mediump float;
void main() {
    gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
}
"#;
