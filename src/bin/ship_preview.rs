//! 飞船房间预览工具（独立 bin）。
//!
//! 用法：`cargo run --release --bin ship_preview`
//! 读取 `content/levels/ship_room/scene.glb`，CPU Lambert + base color texture，
//! 第一人称走动（WASD + 鼠标），不走主游戏的声呐黑暗管线。
//!
//! 目的：让 PA 在不动主游戏架构的前提下，对飞船 GLB 的美术效果做反馈迭代。
//! 视觉满意后再接入 GameApp 的 Mode::Ship 路径。

use macroquad::models::{Mesh, Vertex};
use macroquad::prelude::*;

const GLB_PATH: &str = "content/levels/ship_room/scene.glb";

// ===== 灯光（CPU Lambert） =====
const LIGHT_DIR: Vec3 = Vec3::new(0.45, 0.95, 0.30); // 主灯方向（指向光源）
const LIGHT_COLOR: Vec3 = Vec3::new(1.00, 0.96, 0.88); // 暖白主灯
const AMBIENT: Vec3 = Vec3::new(0.32, 0.36, 0.44);   // 冷蓝环境光（夜航舱基调）
const DIFFUSE_GAIN: f32 = 0.75;                       // 主灯强度
/// 单 drawcall 索引上限（gotchas memory：macroquad 0.4.15 ~5000）
const MAX_IDX_PER_BATCH: usize = 4992; // 5000 取 3 的倍数

// ===== 相机参数 =====
const EYE_HEIGHT: f32 = 1.65;
const WALK_SPEED: f32 = 3.2;
const SPRINT_MUL: f32 = 2.2;
const LOOK_SENS: f32 = 0.0025;
const FOV_DEG: f32 = 65.0;

struct Batch {
    mesh: Mesh,
    /// unlit 模式下的顶点颜色（= base_color_factor，texture 全亮显示）
    color_unlit: Vec<[u8; 4]>,
    /// Lambert 模式下的顶点颜色（= base_factor * lambert）
    color_lit: Vec<[u8; 4]>,
    /// true = emissive overlay（在 base batch 之后再画一遍，模拟自发光叠加）
    is_emissive: bool,
}

fn window_conf() -> Conf {
    Conf {
        window_title: "SonarJam · Ship Preview".to_owned(),
        window_width: 1600,
        window_height: 900,
        high_dpi: true,
        window_resizable: false,
        ..Default::default()
    }
}

#[macroquad::main(window_conf)]
async fn main() {
    println!("[ship_preview] 加载 {}", GLB_PATH);
    let mut batches = match load_ship(GLB_PATH) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("[ship_preview] 加载失败：{}", e);
            return;
        }
    };
    let tri_count: usize = batches.iter().map(|b| b.mesh.indices.len() / 3).sum();
    println!(
        "[ship_preview] 共 {} 个 batch，{} 三角形",
        batches.len(),
        tri_count
    );

    // 初始位置：场景中心略偏后方，朝里看
    let aabb = compute_aabb(&batches);
    let center = (aabb.0 + aabb.1) * 0.5;
    let size = aabb.1 - aabb.0;
    println!(
        "[ship_preview] AABB min={:?} max={:?} size={:?}",
        aabb.0, aabb.1, size
    );

    // 出生点：水平 AABB 中心，站在地板（AABB.min.y）+ 眼高
    let mut cam_pos = vec3(center.x, aabb.0.y + EYE_HEIGHT, center.z);
    let mut yaw: f32 = 0.0;
    let mut pitch: f32 = 0.0;
    let mut last_mouse: Option<Vec2> = None;
    let mut mouse_grabbed = false;
    let mut unlit = true; // 默认 fullbright（= Blender viewport 看到的颜色）

    println!("[ship_preview] 控制：WASD 移动，Shift 加速，Space/Ctrl 上下飞，L 切 Unlit/Lambert，鼠标看向（点击锁，Esc 释放）");

    loop {
        let dt = get_frame_time().min(1.0 / 20.0);

        // L 切 unlit/Lambert
        if is_key_pressed(KeyCode::L) {
            unlit = !unlit;
            for b in batches.iter_mut() {
                let src = if unlit { &b.color_unlit } else { &b.color_lit };
                for (v, c) in b.mesh.vertices.iter_mut().zip(src.iter()) {
                    v.color = *c;
                }
            }
            println!("[ship_preview] shading = {}", if unlit { "unlit" } else { "lambert" });
        }

        // 鼠标抓取切换：点击进入 look，Esc 退出
        if is_mouse_button_pressed(MouseButton::Left) && !mouse_grabbed {
            mouse_grabbed = true;
            set_cursor_grab(true);
            show_mouse(false);
            last_mouse = Some(Vec2::from(mouse_position()));
        }
        if is_key_pressed(KeyCode::Escape) {
            if mouse_grabbed {
                mouse_grabbed = false;
                set_cursor_grab(false);
                show_mouse(true);
            } else {
                break;
            }
        }

        // 鼠标看向
        if mouse_grabbed {
            let m = Vec2::from(mouse_position());
            let d = m - last_mouse.unwrap_or(m);
            yaw += d.x * LOOK_SENS;
            pitch =
                (pitch - d.y * LOOK_SENS).clamp(-1.5, 1.5);
            last_mouse = Some(m);
        }

        let forward = vec3(yaw.cos() * pitch.cos(), pitch.sin(), yaw.sin() * pitch.cos()).normalize();
        let flat = vec3(forward.x, 0.0, forward.z).normalize_or_zero();
        let right = flat.cross(Vec3::Y).normalize_or_zero();

        let sprint = is_key_down(KeyCode::LeftShift) || is_key_down(KeyCode::RightShift);
        let speed = WALK_SPEED * if sprint { SPRINT_MUL } else { 1.0 };
        let mut mv = Vec3::ZERO;
        if is_key_down(KeyCode::W) { mv += flat; }
        if is_key_down(KeyCode::S) { mv -= flat; }
        if is_key_down(KeyCode::D) { mv += right; }
        if is_key_down(KeyCode::A) { mv -= right; }
        if is_key_down(KeyCode::Space) { mv += Vec3::Y; }
        if is_key_down(KeyCode::LeftControl) { mv -= Vec3::Y; }
        if mv.length_squared() > 1e-6 {
            cam_pos += mv.normalize() * speed * dt;
        }

        // 清屏（深蓝舱内调）
        clear_background(Color::new(0.025, 0.030, 0.040, 1.0));

        set_camera(&Camera3D {
            position: cam_pos,
            target: cam_pos + forward,
            up: Vec3::Y,
            fovy: FOV_DEG.to_radians(),
            aspect: Some(screen_width() / screen_height()),
            z_near: 0.05,
            z_far: 300.0,
            ..Default::default()
        });

        // 先画 base（可能受光），再画 emissive overlay（始终全亮）。
        for b in batches.iter().filter(|b| !b.is_emissive) {
            draw_mesh(&b.mesh);
        }
        for b in batches.iter().filter(|b| b.is_emissive) {
            draw_mesh(&b.mesh);
        }

        // HUD：状态
        set_default_camera();
        draw_text(
            &format!(
                "pos {:.1},{:.1},{:.1}  yaw {:.0}°  fps {:.0}  tri {}",
                cam_pos.x, cam_pos.y, cam_pos.z,
                yaw.to_degrees(),
                1.0 / dt.max(1e-4),
                tri_count
            ),
            12.0,
            22.0,
            18.0,
            Color::new(0.85, 0.95, 1.0, 0.9),
        );
        if !mouse_grabbed {
            draw_text(
                "Click to capture mouse · WASD move · Shift run · Space/Ctrl up/down · Esc release",
                12.0,
                screen_height() - 14.0,
                18.0,
                Color::new(0.7, 0.85, 0.9, 0.85),
            );
        }

        next_frame().await;
    }
}

fn load_ship(path: &str) -> Result<Vec<Batch>, String> {
    // 读字节并把 extensionsRequired 清空（绕过 gltf crate 对未识别扩展的硬拒）。
    // 这样不影响数据：扩展自身（如 KHR_lights_punctual）的字段仍可读，仅去掉"必须支持"标记。
    let raw = std::fs::read(path).map_err(|e| format!("读文件失败：{}", e))?;
    let patched = strip_extensions_required(&raw);
    let (doc, buffers, images) =
        gltf::import_slice(&patched).map_err(|e| e.to_string())?;
    println!("[ship_preview] GLB images = {}", images.len());
    for (i, img) in images.iter().enumerate() {
        println!(
            "[ship_preview]   image[{}] {}x{} {:?}",
            i, img.width, img.height, img.format
        );
    }
    // 全部 image 一次性烘成 Texture2D（Rgb8 转 Rgba8）
    let textures: Vec<Texture2D> = images
        .iter()
        .map(|img| {
            let rgba = to_rgba8(img);
            let t = Texture2D::from_rgba8(img.width as u16, img.height as u16, &rgba);
            t.set_filter(FilterMode::Linear);
            t
        })
        .collect();

    // KHR_lights_punctual 诊断
    let extensions: Vec<&str> = doc.extensions_used().collect();
    println!("[ship_preview] glTF extensions used = {:?}", extensions);

    // 顶点色诊断：统计有 COLOR_0 的 primitive 数
    let mut prim_with_vc = 0usize;
    let mut prim_total = 0usize;
    for mesh in doc.meshes() {
        for prim in mesh.primitives() {
            prim_total += 1;
            let r = prim.reader(|b| buffers.get(b.index()).map(|d| d.0.as_slice()));
            if r.read_colors(0).is_some() { prim_with_vc += 1; }
        }
    }
    println!("[ship_preview] primitives with COLOR_0 = {}/{}", prim_with_vc, prim_total);

    // 材质诊断：列出每个材质用到哪些通道
    println!("[ship_preview] materials:");
    for (i, m) in doc.materials().enumerate() {
        let pbr = m.pbr_metallic_roughness();
        let base_tex = pbr.base_color_texture().map(|t| t.texture().source().index());
        let em_tex = m.emissive_texture().map(|t| t.texture().source().index());
        let em_f = m.emissive_factor();
        let bc = pbr.base_color_factor();
        println!(
            "  mat[{}] {:?}: base_tex={:?} base_factor={:.2?} em_tex={:?} em_factor={:?}",
            i,
            m.name().unwrap_or("(unnamed)"),
            base_tex, bc, em_tex, em_f
        );
    }

    let mut batches: Vec<Batch> = Vec::new();
    for scene in doc.scenes() {
        for node in scene.nodes() {
            walk(&node, Mat4::IDENTITY, &buffers, &textures, &mut batches);
        }
    }
    println!("[ship_preview] built {} batches ({} base, {} emissive)",
        batches.len(),
        batches.iter().filter(|b| !b.is_emissive).count(),
        batches.iter().filter(|b| b.is_emissive).count(),
    );
    Ok(batches)
}

fn walk(
    node: &gltf::Node,
    parent: Mat4,
    buffers: &[gltf::buffer::Data],
    textures: &[Texture2D],
    batches: &mut Vec<Batch>,
) {
    let local = Mat4::from_cols_array_2d(&node.transform().matrix());
    let world = parent * local;
    let name = node.name().unwrap_or("");
    // 只渲染 R_ 几何；C_/M_/P_ 跳过
    let is_render = name.starts_with("R_");
    if let Some(mesh) = node.mesh() {
        if is_render {
            for prim in mesh.primitives() {
                process_primitive(&prim, world, buffers, textures, batches);
            }
        }
    }
    for c in node.children() {
        walk(&c, world, buffers, textures, batches);
    }
}

fn process_primitive(
    prim: &gltf::Primitive,
    world: Mat4,
    buffers: &[gltf::buffer::Data],
    textures: &[Texture2D],
    batches: &mut Vec<Batch>,
) {
    let reader = prim.reader(|b| buffers.get(b.index()).map(|d| d.0.as_slice()));
    let positions: Vec<Vec3> = match reader.read_positions() {
        Some(it) => it.map(Vec3::from_array).collect(),
        None => return,
    };
    let normals: Option<Vec<Vec3>> = reader
        .read_normals()
        .map(|it| it.map(Vec3::from_array).collect());
    let uvs: Vec<Vec2> = reader
        .read_tex_coords(0)
        .map(|tc| tc.into_f32().map(Vec2::from_array).collect())
        .unwrap_or_else(|| vec![Vec2::ZERO; positions.len()]);
    // COLOR_0：Blender 顶点色/烘焙色常通过这个通道走（base_factor 仅是 tint 乘子）
    let vcolors: Option<Vec<Vec3>> = reader
        .read_colors(0)
        .map(|c| c.into_rgb_f32().map(Vec3::from_array).collect());
    let indices: Vec<u32> = reader
        .read_indices()
        .map(|i| i.into_u32().collect())
        .unwrap_or_else(|| (0..positions.len() as u32).collect());

    // 材质：base color + emissive
    let mat = prim.material();
    let pbr = mat.pbr_metallic_roughness();
    let base_factor = pbr.base_color_factor();
    let base_tint = vec3(base_factor[0], base_factor[1], base_factor[2]);
    let base_texture = pbr.base_color_texture().and_then(|info| {
        let src = info.texture().source().index();
        textures.get(src).cloned()
    });
    let em_factor_arr = mat.emissive_factor();
    let em_factor = vec3(em_factor_arr[0], em_factor_arr[1], em_factor_arr[2]);
    let em_texture = mat.emissive_texture().and_then(|info| {
        let src = info.texture().source().index();
        textures.get(src).cloned()
    });
    let has_emissive = em_factor.length_squared() > 1e-6 || em_texture.is_some();

    // 法线变换：用 world 3x3 的逆转置（无非均匀缩放时近似为旋转部分）。
    // 这里取上 3x3 + 单位化，足够 GameJam 用。
    let nm = Mat3::from_cols(world.x_axis.truncate(), world.y_axis.truncate(), world.z_axis.truncate());

    // 双路径：base / emissive 各一份累积，独立 flush。
    let mut base_v: Vec<Vertex> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut base_i: Vec<u16> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut base_unlit: Vec<[u8; 4]> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut base_lit: Vec<[u8; 4]> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut em_v: Vec<Vertex> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut em_i: Vec<u16> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut em_unlit: Vec<[u8; 4]> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut em_lit: Vec<[u8; 4]> = Vec::with_capacity(MAX_IDX_PER_BATCH);

    fn flush(
        v: &mut Vec<Vertex>, i: &mut Vec<u16>,
        cu: &mut Vec<[u8; 4]>, cl: &mut Vec<[u8; 4]>,
        batches: &mut Vec<Batch>, tex: Option<Texture2D>, is_em: bool,
    ) {
        if i.is_empty() { return; }
        batches.push(Batch {
            mesh: Mesh { vertices: std::mem::take(v), indices: std::mem::take(i), texture: tex },
            color_unlit: std::mem::take(cu),
            color_lit: std::mem::take(cl),
            is_emissive: is_em,
        });
    }

    // emissive vertex color：HDR factor 截到 0..1；若 factor=0 而有贴图则视为 1（让贴图全亮显示）
    let em_color: [u8; 4] = if em_texture.is_some() && em_factor.length_squared() < 1e-6 {
        [255, 255, 255, 255]
    } else {
        [
            (em_factor.x.clamp(0.0, 1.0) * 255.0) as u8,
            (em_factor.y.clamp(0.0, 1.0) * 255.0) as u8,
            (em_factor.z.clamp(0.0, 1.0) * 255.0) as u8,
            255,
        ]
    };

    for tri in indices.chunks_exact(3) {
        if base_i.len() + 3 > MAX_IDX_PER_BATCH {
            flush(&mut base_v, &mut base_i, &mut base_unlit, &mut base_lit, batches, base_texture.clone(), false);
        }
        if has_emissive && em_i.len() + 3 > MAX_IDX_PER_BATCH {
            flush(&mut em_v, &mut em_i, &mut em_unlit, &mut em_lit, batches, em_texture.clone(), true);
        }

        let i0 = tri[0] as usize;
        let i1 = tri[1] as usize;
        let i2 = tri[2] as usize;

        let p_local = [positions[i0], positions[i1], positions[i2]];
        let p_world = [
            world.transform_point3(p_local[0]),
            world.transform_point3(p_local[1]),
            world.transform_point3(p_local[2]),
        ];

        let n_world = match &normals {
            Some(ns) => [
                nm.mul_vec3(ns[i0]).normalize_or_zero(),
                nm.mul_vec3(ns[i1]).normalize_or_zero(),
                nm.mul_vec3(ns[i2]).normalize_or_zero(),
            ],
            None => {
                let fn_ = (p_world[1] - p_world[0]).cross(p_world[2] - p_world[0]).normalize_or_zero();
                [fn_, fn_, fn_]
            }
        };

        for k in 0..3 {
            let vi = [i0, i1, i2][k];
            let uv_k = uvs[vi];
            let n_k = n_world[k];
            // 顶点色：若存在则乘进 base_tint（PBR 工作流的标准做法）
            let vc = vcolors.as_ref().map(|v| v[vi]).unwrap_or(Vec3::ONE);
            let tint = vec3(base_tint.x * vc.x, base_tint.y * vc.y, base_tint.z * vc.z);
            let unlit_k: [u8; 4] = [
                (tint.x.clamp(0.0, 1.0) * 255.0) as u8,
                (tint.y.clamp(0.0, 1.0) * 255.0) as u8,
                (tint.z.clamp(0.0, 1.0) * 255.0) as u8,
                255,
            ];
            let lit = lambert(n_k, tint);
            let lit_color = [
                (lit.x.clamp(0.0, 1.0) * 255.0) as u8,
                (lit.y.clamp(0.0, 1.0) * 255.0) as u8,
                (lit.z.clamp(0.0, 1.0) * 255.0) as u8,
                255,
            ];
            let base_idx = base_v.len() as u16;
            base_v.push(Vertex {
                position: p_world[k],
                uv: uv_k,
                color: unlit_k,
                normal: Vec4::new(n_k.x, n_k.y, n_k.z, 0.0),
            });
            base_unlit.push(unlit_k);
            base_lit.push(lit_color);
            base_i.push(base_idx);

            if has_emissive {
                let em_idx = em_v.len() as u16;
                em_v.push(Vertex {
                    position: p_world[k],
                    uv: uv_k,
                    color: em_color,
                    normal: Vec4::new(n_k.x, n_k.y, n_k.z, 0.0),
                });
                em_unlit.push(em_color);
                em_lit.push(em_color); // emissive 不受光影响
                em_i.push(em_idx);
            }
        }
    }
    flush(&mut base_v, &mut base_i, &mut base_unlit, &mut base_lit, batches, base_texture, false);
    if has_emissive {
        flush(&mut em_v, &mut em_i, &mut em_unlit, &mut em_lit, batches, em_texture, true);
    }
}

/// 顶点 Lambert：ambient + diffuse*N·L，乘 base_color_factor 作 tint。
fn lambert(n: Vec3, base_tint: Vec3) -> Vec3 {
    let l = LIGHT_DIR.normalize_or_zero();
    let ndl = n.dot(l).max(0.0);
    let lit = AMBIENT + LIGHT_COLOR * (DIFFUSE_GAIN * ndl);
    vec3(lit.x * base_tint.x, lit.y * base_tint.y, lit.z * base_tint.z)
}

fn to_rgba8(img: &gltf::image::Data) -> Vec<u8> {
    use gltf::image::Format;
    match img.format {
        Format::R8G8B8A8 => img.pixels.clone(),
        Format::R8G8B8 => {
            let mut out = Vec::with_capacity(img.pixels.len() / 3 * 4);
            for chunk in img.pixels.chunks_exact(3) {
                out.extend_from_slice(chunk);
                out.push(255);
            }
            out
        }
        Format::R8 => {
            let mut out = Vec::with_capacity(img.pixels.len() * 4);
            for &v in &img.pixels {
                out.extend_from_slice(&[v, v, v, 255]);
            }
            out
        }
        Format::R8G8 => {
            let mut out = Vec::with_capacity(img.pixels.len() * 2);
            for chunk in img.pixels.chunks_exact(2) {
                out.extend_from_slice(&[chunk[0], chunk[1], 0, 255]);
            }
            out
        }
        other => {
            eprintln!("[ship_preview] 不支持的纹理格式 {:?}，用占位灰", other);
            vec![160, 160, 160, 255]
        }
    }
}

/// 把 GLB JSON chunk 的 `"extensionsRequired": [...]` 改为 `"extensionsRequired":[]`，
/// 多余字节用空格补齐（JSON 允许空白），保持 chunk 长度不变。
fn strip_extensions_required(bytes: &[u8]) -> Vec<u8> {
    if bytes.len() < 28 || &bytes[0..4] != b"glTF" {
        return bytes.to_vec();
    }
    let json_len = u32::from_le_bytes(bytes[12..16].try_into().unwrap()) as usize;
    if &bytes[16..20] != b"JSON" || 20 + json_len > bytes.len() {
        return bytes.to_vec();
    }
    let json_start = 20;
    let json_end = json_start + json_len;
    let Ok(s) = std::str::from_utf8(&bytes[json_start..json_end]) else {
        return bytes.to_vec();
    };
    let modified = replace_array_value(s, "\"extensionsRequired\"", "[]");
    let mut new_json: Vec<u8> = modified.into_bytes();
    if new_json.len() > json_len {
        // 永远不会变长（只是清空数组），出现就跳过 patch
        return bytes.to_vec();
    }
    new_json.resize(json_len, b' ');
    let mut out = bytes.to_vec();
    out[json_start..json_end].copy_from_slice(&new_json);
    out
}

fn replace_array_value(s: &str, key: &str, new_value: &str) -> String {
    let Some(key_pos) = s.find(key) else { return s.to_string() };
    let bytes = s.as_bytes();
    let after_key = key_pos + key.len();
    let mut i = after_key;
    while i < bytes.len() && matches!(bytes[i], b' ' | b':' | b'\t' | b'\n' | b'\r') {
        i += 1;
    }
    if i >= bytes.len() || bytes[i] != b'[' {
        return s.to_string();
    }
    let array_start = i;
    let mut depth: i32 = 1;
    let mut j = i + 1;
    while j < bytes.len() && depth > 0 {
        match bytes[j] {
            b'[' => depth += 1,
            b']' => depth -= 1,
            _ => {}
        }
        j += 1;
    }
    if depth != 0 {
        return s.to_string();
    }
    let array_end = j;
    let mut out = String::with_capacity(s.len());
    out.push_str(&s[..array_start]);
    out.push_str(new_value);
    out.push_str(&s[array_end..]);
    out
}

fn compute_aabb(batches: &[Batch]) -> (Vec3, Vec3) {
    let mut mn = Vec3::splat(f32::INFINITY);
    let mut mx = Vec3::splat(f32::NEG_INFINITY);
    for b in batches {
        for v in &b.mesh.vertices {
            mn = mn.min(v.position);
            mx = mx.max(v.position);
        }
    }
    if !mn.is_finite() {
        return (Vec3::ZERO, Vec3::ONE);
    }
    (mn, mx)
}
