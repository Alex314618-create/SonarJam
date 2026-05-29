//! 真实世界层：一个凸盒子房间（四面墙 + 地板 + 天花板），四面墙距离各不相同。
//!
//! 这是真实几何，永远干净、不被篡改——“工具有罪”的偏差将来叠加在感知层，
//! 不在这里。提供：射线求交（声呐用）与玩家碰撞（盒内 clamp）。

use crate::app::config::{
    PLAYER_HEIGHT, PLAYER_RADIUS, ROOM_CEILING_Y, ROOM_FLOOR_Y, ROOM_MAX_X, ROOM_MAX_Z, ROOM_MIN_X,
    ROOM_MIN_Z,
};
use macroquad::prelude::*;

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

struct Tri {
    a: Vec3,
    b: Vec3,
    c: Vec3,
    surface: Surface,
}

pub struct World {
    tris: Vec<Tri>,
    spawn: Vec3,
}

impl World {
    pub fn new() -> Self {
        let mut tris = Vec::new();
        let (x0, x1) = (ROOM_MIN_X, ROOM_MAX_X);
        let (z0, z1) = (ROOM_MIN_Z, ROOM_MAX_Z);
        let (y0, y1) = (ROOM_FLOOR_Y, ROOM_CEILING_Y);

        // 地板与天花板
        push_quad(&mut tris, v(x0, y0, z0), v(x1, y0, z0), v(x1, y0, z1), v(x0, y0, z1), Surface::Floor);
        push_quad(&mut tris, v(x0, y1, z0), v(x0, y1, z1), v(x1, y1, z1), v(x1, y1, z0), Surface::Ceiling);

        // 四面墙（内壁）——绕序无所谓，射线求交不剔除背面
        push_quad(&mut tris, v(x0, y0, z0), v(x0, y0, z1), v(x0, y1, z1), v(x0, y1, z0), Surface::Wall); // 左 x0
        push_quad(&mut tris, v(x1, y0, z1), v(x1, y0, z0), v(x1, y1, z0), v(x1, y1, z1), Surface::Wall); // 右 x1
        push_quad(&mut tris, v(x1, y0, z0), v(x0, y0, z0), v(x0, y1, z0), v(x1, y1, z0), Surface::Wall); // 后 z0
        push_quad(&mut tris, v(x0, y0, z1), v(x1, y0, z1), v(x1, y1, z1), v(x0, y1, z1), Surface::Wall); // 前 z1

        Self {
            tris,
            spawn: v(0.0, PLAYER_HEIGHT, 0.0),
        }
    }

    pub fn spawn(&self) -> Vec3 {
        self.spawn
    }

    /// 最近正向命中。射线从房间内部射出，命中内壁。
    pub fn raycast(&self, origin: Vec3, dir: Vec3, max_range: f32) -> Option<Hit> {
        let mut best: Option<Hit> = None;
        for t in &self.tris {
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

    /// 凸盒房间：把玩家位置 clamp 在内壁以内即为碰撞。
    pub fn clamp_position(&self, mut p: Vec3) -> Vec3 {
        p.x = p.x.clamp(ROOM_MIN_X + PLAYER_RADIUS, ROOM_MAX_X - PLAYER_RADIUS);
        p.z = p.z.clamp(ROOM_MIN_Z + PLAYER_RADIUS, ROOM_MAX_Z - PLAYER_RADIUS);
        p.y = PLAYER_HEIGHT;
        p
    }
}

fn v(x: f32, y: f32, z: f32) -> Vec3 {
    vec3(x, y, z)
}

fn push_quad(tris: &mut Vec<Tri>, a: Vec3, b: Vec3, c: Vec3, d: Vec3, surface: Surface) {
    tris.push(Tri { a, b, c, surface });
    tris.push(Tri { a, b: c, c: d, surface });
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
