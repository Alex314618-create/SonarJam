//! 内容管线：从 GLB 导入关卡。
//!
//! 按对象命名前缀分类（与 tools/generate_mvp_map.py 的输出约定一致）：
//! - `R_*` → Render 网格（声呐 raycast 的视觉几何）
//! - `C_*` → Collision 网格（玩家碰撞代理）
//! - `M_spawn*` → 出生点标记
//! - `V_*` 及其它 → 跳过（体积/触发区不是物理几何）
//!
//! GLB 经 Blender 导出已转为 Y-up，直接对应本引擎坐标，无需手动换轴。

use crate::app::config::PLAYER_HEIGHT;
use macroquad::prelude::*;

pub struct LoadedLevel {
    pub render_tris: Vec<[Vec3; 3]>,
    pub collision_tris: Vec<[Vec3; 3]>,
    pub spawn: Option<Vec3>,
}

pub fn load(path: &str) -> Option<LoadedLevel> {
    let (doc, buffers, _images) = gltf::import(path).ok()?;
    let mut level = LoadedLevel {
        render_tris: Vec::new(),
        collision_tris: Vec::new(),
        spawn: None,
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
    Skip,
}

fn visit(node: &gltf::Node, parent: Mat4, buffers: &[gltf::buffer::Data], level: &mut LoadedLevel) {
    let local = Mat4::from_cols_array_2d(&node.transform().matrix());
    let world = parent * local;
    let name = node.name().unwrap_or("");

    if name.starts_with("M_spawn") && level.spawn.is_none() {
        let p = world.transform_point3(Vec3::ZERO);
        level.spawn = Some(vec3(p.x, PLAYER_HEIGHT, p.z));
    }

    if let Some(mesh) = node.mesh() {
        let cat = if name.starts_with("C_") {
            Cat::Collision
        } else if name.starts_with("R_") {
            Cat::Render
        } else {
            Cat::Skip
        };

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
                let target = match cat {
                    Cat::Collision => &mut level.collision_tris,
                    _ => &mut level.render_tris,
                };
                for tri in indices.chunks(3) {
                    if tri.len() == 3 {
                        target.push([
                            positions[tri[0] as usize],
                            positions[tri[1] as usize],
                            positions[tri[2] as usize],
                        ]);
                    }
                }
            }
        }
    }

    for child in node.children() {
        visit(&child, world, buffers, level);
    }
}
