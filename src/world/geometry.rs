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
    /// P_* 几何：人形/按钮/提示/标识等"过去的回声/异常建构"，
    /// 显形颜色由对象名编码（见 PhantomColor）。
    Phantom(PhantomColor),
}

/// 通过 Blender 对象名前缀 `P_<kind>_<color>_<id>` 编码的显形颜色。
/// 命中时点云颜色 = base ± 10%。
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum PhantomColor {
    Red,
    Yellow,
    Silver,
    Cyan,
    Purple,
    Orange,
    Green,
    White,
}

impl PhantomColor {
    /// 从对象名中识别颜色 token。匹配规则：用 `_` 分割后查找已知颜色单词。
    /// 没找到返回 None，调用者决定默认（当前默认 Red）。
    pub fn parse(name: &str) -> Option<Self> {
        for token in name.split('_') {
            match token {
                "red" => return Some(Self::Red),
                "yellow" => return Some(Self::Yellow),
                "silver" => return Some(Self::Silver),
                "cyan" => return Some(Self::Cyan),
                "purple" => return Some(Self::Purple),
                "orange" => return Some(Self::Orange),
                "green" => return Some(Self::Green),
                "white" => return Some(Self::White),
                _ => {}
            }
        }
        None
    }

    /// 基色 (r, g, b)；声呐 color_for 在此基础上 ±10% 抖动。
    pub fn base_rgb(self) -> (f32, f32, f32) {
        match self {
            Self::Red => (0.95, 0.18, 0.22),
            Self::Yellow => (0.98, 0.85, 0.18),
            Self::Silver => (0.78, 0.80, 0.84),
            Self::Cyan => (0.18, 0.92, 0.95),
            Self::Purple => (0.62, 0.20, 0.85),
            Self::Orange => (0.98, 0.55, 0.15),
            Self::Green => (0.20, 0.92, 0.40),
            Self::White => (0.95, 0.95, 0.95),
        }
    }
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
    phantom_tris: Vec<Tri>,   // 人形等"过去回声"——只参与 raycast，不参与碰撞
    spawn: Vec3,
}

impl World {
    pub fn new() -> Self {
        Self::load(DEFAULT_LEVEL)
    }

    /// 按路径加载一张 GLB；失败则回退代码盒子房间。
    pub fn load(path: &str) -> Self {
        if let Some(level) = crate::content::load(path) {
            if !level.render_tris.is_empty() {
                println!(
                    "[world] GLB 加载 {}: render {} / collision {} / phantom {} 三角形",
                    path,
                    level.render_tris.len(),
                    level.collision_tris.len(),
                    level.phantom_tris.len()
                );
                return Self::from_level(level);
            }
        }
        println!("[world] 未找到 GLB ({})，回退到代码盒子房间", path);
        Self::code_room()
    }

    fn from_level(level: crate::content::LoadedLevel) -> Self {
        let render_tris: Vec<Tri> = level
            .render_tris
            .iter()
            .map(|t| Tri::new(t[0], t[1], t[2]))
            .collect();
        let collision_src = if level.collision_tris.is_empty() {
            &level.render_tris
        } else {
            &level.collision_tris
        };
        let collision_tris: Vec<Tri> = collision_src
            .iter()
            .map(|t| Tri::new(t[0], t[1], t[2]))
            .collect();
        let phantom_tris: Vec<Tri> = level
            .phantom_tris
            .iter()
            .map(|(color, t)| Tri::with_surface(t[0], t[1], t[2], Surface::Phantom(*color)))
            .collect();
        let spawn = level.spawn.unwrap_or_else(|| vec3(0.0, PLAYER_HEIGHT, 0.0));
        Self {
            render_tris,
            collision_tris,
            phantom_tris,
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
            phantom_tris: Vec::new(),
            spawn: v(0.0, PLAYER_HEIGHT, 0.0),
        }
    }

    pub fn spawn(&self) -> Vec3 {
        self.spawn
    }

    /// 声呐能打到的真实渲染几何，按三角形给出（用于点云渲染的深度预通道）。
    /// 几何是静态的，渲染器可缓存一次即可。
    pub fn render_triangles(&self) -> impl Iterator<Item = [Vec3; 3]> + '_ {
        self.render_tris.iter().map(|t| [t.a, t.b, t.c])
    }

    /// 声呐射线对 Render + Phantom 几何求最近正向命中。
    /// 两套几何竞争同一条射线的最近距离——phantom 在玩家与墙之间会先被命中。
    pub fn raycast(&self, origin: Vec3, dir: Vec3, max_range: f32) -> Option<Hit> {
        let mut best: Option<Hit> = None;
        let consider = |tris: &[Tri], best: &mut Option<Hit>| {
            for t in tris {
                if let Some(dist) = ray_tri(origin, dir, t.a, t.b, t.c) {
                    if dist <= max_range && best.map_or(true, |h: Hit| dist < h.distance) {
                        *best = Some(Hit {
                            pos: origin + dir * dist,
                            surface: t.surface,
                            distance: dist,
                        });
                    }
                }
            }
        };
        consider(&self.render_tris, &mut best);
        consider(&self.phantom_tris, &mut best);
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
