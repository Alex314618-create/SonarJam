//! 真实世界层：关卡几何。优先从 GLB 导入，缺失则回退到代码盒子房间。
//!
//! Render 网格供声呐 raycast（玩家“看见”的视觉几何），Collision 网格供玩家碰撞。
//! 真实几何永远干净、不被篡改——“工具有罪”的偏差将来叠加在感知层。

use crate::app::config::{
    PLAYER_HEIGHT, PLAYER_RADIUS, ROOM_CEILING_Y, ROOM_FLOOR_Y, ROOM_MAX_X, ROOM_MAX_Z, ROOM_MIN_X,
    ROOM_MIN_Z,
};
use macroquad::prelude::*;

const DEFAULT_LEVEL: &str = "content/levels/earth_return_01/scene.glb";

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Surface {
    Wall,
    Floor,
    Ceiling,
}

#[derive(Clone, Copy)]
pub struct Hit {
    pub pos: Vec3,
    pub surface: Surface,
    pub distance: f32,
}

#[derive(Clone, Copy)]
struct Tri {
    a: Vec3,
    b: Vec3,
    c: Vec3,
    surface: Surface,
}

impl Tri {
    fn new(a: Vec3, b: Vec3, c: Vec3) -> Self {
        // 按法线方向自动分面：朝上=地面、朝下=天花板、其余=墙。
        let n = (b - a).cross(c - a).normalize_or_zero();
        let surface = if n.y > 0.6 {
            Surface::Floor
        } else if n.y < -0.6 {
            Surface::Ceiling
        } else {
            Surface::Wall
        };
        Self { a, b, c, surface }
    }

    fn with_surface(a: Vec3, b: Vec3, c: Vec3, surface: Surface) -> Self {
        Self { a, b, c, surface }
    }
}

pub struct World {
    render_tris: Vec<Tri>,    // 声呐 raycast
    collision_tris: Vec<Tri>, // 玩家碰撞
    spawn: Vec3,
}

impl World {
    pub fn new() -> Self {
        if let Some(level) = crate::content::load(DEFAULT_LEVEL) {
            if !level.render_tris.is_empty() {
                println!(
                    "[world] GLB 关卡已加载：render {} 三角形，collision {} 三角形",
                    level.render_tris.len(),
                    level.collision_tris.len()
                );
                return Self::from_level(level);
            }
        }
        println!("[world] 未找到 GLB 关卡，回退到代码盒子房间");
        Self::code_room()
    }

    fn from_level(level: crate::content::LoadedLevel) -> Self {
        let render_tris: Vec<Tri> = level
            .render_tris
            .iter()
            .map(|t| Tri::new(t[0], t[1], t[2]))
            .collect();
        // 没有 Collision 网格时退而用 Render 几何兜底碰撞。
        let collision_src = if level.collision_tris.is_empty() {
            &level.render_tris
        } else {
            &level.collision_tris
        };
        let collision_tris: Vec<Tri> = collision_src
            .iter()
            .map(|t| Tri::new(t[0], t[1], t[2]))
            .collect();
        let spawn = level.spawn.unwrap_or_else(|| vec3(0.0, PLAYER_HEIGHT, 0.0));
        Self {
            render_tris,
            collision_tris,
            spawn,
        }
    }

    fn code_room() -> Self {
        let mut tris = Vec::new();
        let (x0, x1) = (ROOM_MIN_X, ROOM_MAX_X);
        let (z0, z1) = (ROOM_MIN_Z, ROOM_MAX_Z);
        let (y0, y1) = (ROOM_FLOOR_Y, ROOM_CEILING_Y);

        push_quad(&mut tris, v(x0, y0, z0), v(x1, y0, z0), v(x1, y0, z1), v(x0, y0, z1), Surface::Floor);
        push_quad(&mut tris, v(x0, y1, z0), v(x0, y1, z1), v(x1, y1, z1), v(x1, y1, z0), Surface::Ceiling);
        push_quad(&mut tris, v(x0, y0, z0), v(x0, y0, z1), v(x0, y1, z1), v(x0, y1, z0), Surface::Wall);
        push_quad(&mut tris, v(x1, y0, z1), v(x1, y0, z0), v(x1, y1, z0), v(x1, y1, z1), Surface::Wall);
        push_quad(&mut tris, v(x1, y0, z0), v(x0, y0, z0), v(x0, y1, z0), v(x1, y1, z0), Surface::Wall);
        push_quad(&mut tris, v(x0, y0, z1), v(x1, y0, z1), v(x1, y1, z1), v(x0, y1, z1), Surface::Wall);

        Self {
            render_tris: tris.clone(),
            collision_tris: tris,
            spawn: v(0.0, PLAYER_HEIGHT, 0.0),
        }
    }

    pub fn spawn(&self) -> Vec3 {
        self.spawn
    }

    /// 声呐射线对 Render 几何求最近正向命中。
    pub fn raycast(&self, origin: Vec3, dir: Vec3, max_range: f32) -> Option<Hit> {
        let mut best: Option<Hit> = None;
        for t in &self.render_tris {
            if let Some(dist) = ray_tri(origin, dir, t.a, t.b, t.c) {
                if dist <= max_range && best.map_or(true, |h| dist < h.distance) {
                    best = Some(Hit {
                        pos: origin + dir * dist,
                        surface: t.surface,
                        distance: dist,
                    });
                }
            }
        }
        best
    }

    /// 分轴推进，对 Collision 几何做射线阻挡（够用的近似碰撞）。
    pub fn resolve_player_movement(&self, current: Vec3, desired: Vec3) -> Vec3 {
        let mut pos = current;
        let dx = desired.x - current.x;
        if dx.abs() > 1e-5 && !self.blocked(pos, vec3(dx.signum(), 0.0, 0.0), dx.abs()) {
            pos.x = desired.x;
        }
        let dz = desired.z - current.z;
        if dz.abs() > 1e-5 && !self.blocked(pos, vec3(0.0, 0.0, dz.signum()), dz.abs()) {
            pos.z = desired.z;
        }
        pos.y = PLAYER_HEIGHT;
        pos
    }

    fn blocked(&self, origin: Vec3, dir: Vec3, dist: f32) -> bool {
        let reach = dist + PLAYER_RADIUS;
        for t in &self.collision_tris {
            if let Some(d) = ray_tri(origin, dir, t.a, t.b, t.c) {
                if d <= reach {
                    return true;
                }
            }
        }
        false
    }
}

fn v(x: f32, y: f32, z: f32) -> Vec3 {
    vec3(x, y, z)
}

fn push_quad(tris: &mut Vec<Tri>, a: Vec3, b: Vec3, c: Vec3, d: Vec3, surface: Surface) {
    tris.push(Tri::with_surface(a, b, c, surface));
    tris.push(Tri::with_surface(a, c, d, surface));
}

/// Möller–Trumbore，不剔除背面。
fn ray_tri(origin: Vec3, dir: Vec3, a: Vec3, b: Vec3, c: Vec3) -> Option<f32> {
    const EPS: f32 = 1e-6;
    let e1 = b - a;
    let e2 = c - a;
    let p = dir.cross(e2);
    let det = e1.dot(p);
    if det.abs() < EPS {
        return None;
    }
    let inv = 1.0 / det;
    let tv = origin - a;
    let u = tv.dot(p) * inv;
    if !(0.0..=1.0).contains(&u) {
        return None;
    }
    let q = tv.cross(e1);
    let vv = dir.dot(q) * inv;
    if vv < 0.0 || u + vv > 1.0 {
        return None;
    }
    let t = e2.dot(q) * inv;
    (t > EPS).then_some(t)
}
