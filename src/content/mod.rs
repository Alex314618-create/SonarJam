//! 内容管线：从 GLB 导入关卡。
//!
//! 按对象命名前缀分类（与 tools/generate_mvp_map.py 的输出约定一致）：
//! - `R_*` → Render 网格（声呐 raycast 的视觉几何）
//! - `C_*` → Collision 网格（玩家碰撞代理）
//! - `P_*` → Phantoms 网格（人形等"过去回声"显形几何，
//!           只参与 raycast、命中显示为红色、不参与碰撞）
//! - `M_spawn*` → 出生点标记
//! - `V_*` 及其它 → 跳过（体积/触发区不是物理几何）
//!
//! GLB 经 Blender 导出已转为 Y-up，直接对应本引擎坐标，无需手动换轴。

use crate::app::config::PLAYER_HEIGHT;
use crate::world::geometry::{HitTag, PhantomColor};
use macroquad::prelude::*;

pub struct LoadedLevel {
    pub render_tris: Vec<[Vec3; 3]>,
    /// 每个 collision 三角形携带从对象名识别出的 HitTag（Normal/Danger/Structure）。
    /// 同一对象的所有三角形共享同一 tag。
    pub collision_tris: Vec<(HitTag, [Vec3; 3])>,
    /// 每个 phantom 三角形携带从对象名解析出的颜色；同一对象的所有三角形共享同色。
    pub phantom_tris: Vec<(PhantomColor, [Vec3; 3])>,
    /// 名字含 `crashed` 的 C_ 对象的三角形——出生点登陆仓"预探明区"采样源。
    pub crashed_tris: Vec<[Vec3; 3]>,
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
    Skip,
}

fn visit(node: &gltf::Node, parent: Mat4, buffers: &[gltf::buffer::Data], level: &mut LoadedLevel) {
    let local = Mat4::from_cols_array_2d(&node.transform().matrix());
    let world = parent * local;
    let name = node.name().unwrap_or("");

    if name.starts_with("M_spawn") && level.spawn.is_none() {
        let p = world.transform_point3(Vec3::ZERO);
        level.spawn = Some(vec3(p.x, PLAYER_HEIGHT, p.z));
        // 从 M_spawn 的 local +X 方向提取 yaw（玩家面朝方向）
        let lx = world.transform_vector3(Vec3::X);
        // forward = (cos yaw, _, sin yaw) → yaw = atan2(lx.z, lx.x)
        level.spawn_yaw = Some(lx.z.atan2(lx.x));
    }

    if let Some(mesh) = node.mesh() {
        let cat = if name.starts_with("C_") {
            Cat::Collision
        } else if name.starts_with("R_") {
            Cat::Render
        } else if name.starts_with("P_") {
            // 从对象名解析颜色；不指定颜色 token 时默认红色。
            Cat::Phantom(PhantomColor::parse(name).unwrap_or(PhantomColor::Red))
        } else {
            Cat::Skip
        };
        // C_*crashed* 的几何额外进入 crashed_tris（不影响碰撞与 raycast 的正常工作）
        let is_crashed = matches!(cat, Cat::Collision) && name.to_lowercase().contains("crashed");

        if !matches!(cat, Cat::Skip) {
            for prim in mesh.primitives() {
                let reader = prim.reader(|b| buffers.get(b.index()).map(|d| d.0.as_slice()));
                let positions: Vec<Vec3> = match reader.read_positions() {
                    Some(iter) => iter.map(|p| world.transform_point3(Vec3::from_array(p))).collect(),
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
                        Cat::Render => level.render_tris.push(pts),
                        Cat::Skip => {}
                    }
                }
            }
        }
    }

    for child in node.children() {
        visit(&child, world, buffers, level);
    }
}
