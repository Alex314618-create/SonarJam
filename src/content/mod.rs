//! 内容管线：从 GLB 导入关卡。
//!
//! 按对象命名前缀分类（与 tools/generate_mvp_map.py 的输出约定一致）：
//! - `R_*` → Render 网格（真实层，仅参与深度遮挡，不参与声呐 raycast）
//! - `R_leak_*` → 真实层 + 按名分组保留，供事件采样（"系统泄漏"显形）
//! - `C_*` → Collision 网格（玩家碰撞代理 + 声呐 raycast 源）
//! - `P_*` → Phantoms 网格（人形等"过去回声"显形几何，
//!           只参与 raycast、命中显示为红色、不参与碰撞）
//! - `H_*` → Hidden / Hot-activated 网格（事件触发前完全隐形，
//!           运行时 World::activate_hidden_mesh 激活后才进入 raycast + 深度）
//! - `M_spawn*` → 出生点标记
//! - `M_*` → 通用标记点（按名查世界坐标，事件触发器用）
//! - `V_*` 及其它 → 跳过（体积/触发区不是物理几何）
//!
//! GLB 经 Blender 导出已转为 Y-up，直接对应本引擎坐标，无需手动换轴。

use crate::world::geometry::{HitTag, PhantomColor};
use macroquad::prelude::*;

#[derive(Clone)]
pub struct NamedMesh {
    pub name: String,
    pub tris: Vec<[Vec3; 3]>,
}

#[derive(Clone)]
pub struct Marker {
    pub name: String,
    pub position: Vec3,
}

pub struct LoadedLevel {
    pub render_tris: Vec<[Vec3; 3]>,
    /// 每个 collision 三角形携带从对象名识别出的 HitTag（Normal/Danger/Structure）。
    /// 同一对象的所有三角形共享同一 tag。
    pub collision_tris: Vec<(HitTag, [Vec3; 3])>,
    /// 每个 phantom 三角形携带从对象名解析出的颜色；同一对象的所有三角形共享同色。
    pub phantom_tris: Vec<(PhantomColor, [Vec3; 3])>,
    /// 名字含 `crashed` 的 C_ 对象的三角形——出生点登陆仓"预探明区"采样源。
    pub crashed_tris: Vec<[Vec3; 3]>,
    /// `R_leak_*` 三角形按对象名分组（同时已 push 进 render_tris）。
    /// 运行时通过 World::leak_mesh_triangles(name) 查询，用于事件泄漏采样。
    pub leak_meshes: Vec<NamedMesh>,
    /// `H_*` 三角形按对象名分组（未激活前完全隐形）。
    /// 运行时通过 World::activate_hidden_mesh(name) 激活后才生效。
    pub hidden_meshes: Vec<NamedMesh>,
    /// 通用 `M_*` 标记点（含 M_spawn）。按对象名查询世界坐标。
    pub markers: Vec<Marker>,
    pub spawn: Option<Vec3>,
    /// 出生 yaw（弧度）。从 M_spawn 的世界变换的 local +X 方向提取。
    /// engine yaw 约定：forward = (cos yaw, sin pitch, sin yaw)，即 yaw=atan2(local_X.z, local_X.x)。
    pub spawn_yaw: Option<f32>,
}

pub fn load(path: &str) -> Option<LoadedLevel> {
    // 读字节并清空 extensionsRequired（绕过 gltf crate 对 KHR_lights_punctual 等的硬拒）
    let raw = std::fs::read(path).ok()?;
    let patched = crate::ship::strip_extensions_required_for_glb(&raw);
    let (doc, buffers, _images) = gltf::import_slice(&patched).ok()?;
    let mut level = LoadedLevel {
        render_tris: Vec::new(),
        collision_tris: Vec::new(),
        phantom_tris: Vec::new(),
        crashed_tris: Vec::new(),
        leak_meshes: Vec::new(),
        hidden_meshes: Vec::new(),
        markers: Vec::new(),
        spawn: None,
        spawn_yaw: None,
    };
    for scene in doc.scenes() {
        for node in scene.nodes() {
            visit(&node, Mat4::IDENTITY, &buffers, &mut level);
        }
    }
    Some(level)
}

#[derive(Clone, Copy)]
enum Cat {
    Render,
    Collision,
    Phantom(PhantomColor),
    /// H_* 隐藏遮蔽物：导入时按名分组，激活前完全隐形。
    Hidden,
    Skip,
}

fn visit(node: &gltf::Node, parent: Mat4, buffers: &[gltf::buffer::Data], level: &mut LoadedLevel) {
    let local = Mat4::from_cols_array_2d(&node.transform().matrix());
    let world = parent * local;
    let name = node.name().unwrap_or("");

    if name.starts_with("M_") {
        let p = world.transform_point3(Vec3::ZERO);
        if name.starts_with("M_spawn") && level.spawn.is_none() {
            // 直接尊重 M_spawn 的世界坐标——之前 .max(PLAYER_HEIGHT) 让低于 2m 的
            // marker 被强行抬高，造成"出生点偏移"。PA 在 Blender 放哪儿就用哪儿，
            // Earth 主循环每帧 ground_y_at + EARTH_EYE_HEIGHT 会自动贴地，无需提前抬。
            level.spawn = Some(vec3(p.x, p.y, p.z));
            // 从 M_spawn 的 local +X 方向提取 yaw（玩家面朝方向）
            let lx = world.transform_vector3(Vec3::X);
            // forward = (cos yaw, _, sin yaw) → yaw = atan2(lx.z, lx.x)
            level.spawn_yaw = Some(lx.z.atan2(lx.x));
            println!(
                "[content] M_spawn @ ({:.2}, {:.2}, {:.2})  yaw={:.1}°",
                p.x,
                p.y,
                p.z,
                lx.z.atan2(lx.x).to_degrees()
            );
        }
        // 所有 M_* 都进 markers（含 M_spawn，方便事件按名统一查询）
        level.markers.push(Marker {
            name: name.to_string(),
            position: p,
        });
    }

    if let Some(mesh) = node.mesh() {
        let cat = if name.starts_with("C_") {
            Cat::Collision
        } else if name.starts_with("R_") {
            Cat::Render
        } else if name.starts_with("P_") {
            // 从对象名解析颜色；不指定颜色 token 时默认红色。
            Cat::Phantom(PhantomColor::parse(name).unwrap_or(PhantomColor::Red))
        } else if name.starts_with("H_") {
            Cat::Hidden
        } else {
            Cat::Skip
        };
        // C_*crashed* 的几何额外进入 crashed_tris（不影响碰撞与 raycast 的正常工作）
        let is_crashed = matches!(cat, Cat::Collision) && name.to_lowercase().contains("crashed");
        // R_leak_* 额外按名分组进 leak_meshes
        let is_leak = matches!(cat, Cat::Render) && name.starts_with("R_leak");

        if !matches!(cat, Cat::Skip) {
            // 本节点累积的三角形（用于 R_leak_* / H_* 的 named 分组）
            let mut grouped: Vec<[Vec3; 3]> = Vec::new();
            for prim in mesh.primitives() {
                let reader = prim.reader(|b| buffers.get(b.index()).map(|d| d.0.as_slice()));
                let positions: Vec<Vec3> = match reader.read_positions() {
                    Some(iter) => iter
                        .map(|p| world.transform_point3(Vec3::from_array(p)))
                        .collect(),
                    None => continue,
                };
                let indices: Vec<u32> = match reader.read_indices() {
                    Some(i) => i.into_u32().collect(),
                    None => (0..positions.len() as u32).collect(),
                };
                for tri in indices.chunks(3) {
                    if tri.len() != 3 {
                        continue;
                    }
                    let pts = [
                        positions[tri[0] as usize],
                        positions[tri[1] as usize],
                        positions[tri[2] as usize],
                    ];
                    match cat {
                        Cat::Collision => {
                            let tag = HitTag::from_name(name);
                            level.collision_tris.push((tag, pts));
                            if is_crashed {
                                level.crashed_tris.push(pts);
                            }
                        }
                        Cat::Phantom(color) => level.phantom_tris.push((color, pts)),
                        Cat::Render => {
                            level.render_tris.push(pts);
                            if is_leak {
                                grouped.push(pts);
                            }
                        }
                        Cat::Hidden => {
                            // 隐藏遮蔽物：当前不进入任何 list；只按 named 分组保留三角形。
                            grouped.push(pts);
                        }
                        Cat::Skip => {}
                    }
                }
            }
            if !grouped.is_empty() {
                match cat {
                    Cat::Render if is_leak => level.leak_meshes.push(NamedMesh {
                        name: name.to_string(),
                        tris: grouped,
                    }),
                    Cat::Hidden => level.hidden_meshes.push(NamedMesh {
                        name: name.to_string(),
                        tris: grouped,
                    }),
                    _ => {}
                }
            }
        }
    }

    for child in node.children() {
        visit(&child, world, buffers, level);
    }
}
