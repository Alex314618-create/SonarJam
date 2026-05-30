//! 真实世界层：关卡几何 + 声呐 raycast 加速结构。
//!
//! 几何分层（"感知反转 / 镜山"架构，见 docs/L0-感知反转-镜山备忘.md）：
//!   · `R_*` Render 网格 = 真实几何（树、草、山等）。仅参与深度遮挡，不参与声呐 raycast。
//!   · `C_*` Collision 网格 = 系统所见（断壁残垣）。同时担当玩家碰撞 + 声呐 raycast 源。
//!     **这就是"工具有罪"的引擎本体——声呐看到的是 C_ 简化代理，不是真实世界。**
//!   · `P_*` Phantom 网格 = 过去回声 / 异常建构，按对象名颜色显形。仅参与 raycast，不碰撞。
//!
//! Raycast 加速：在 C_ + P_ 上各建一棵 BVH（bvh crate 0.12），单 ray 从 O(N) → O(log N)。

use crate::app::config::{
    PLAYER_HEIGHT, ROOM_CEILING_Y, ROOM_FLOOR_Y, ROOM_MAX_X, ROOM_MAX_Z, ROOM_MIN_X,
    ROOM_MIN_Z,
};
use bvh::aabb::{Aabb, Bounded};
use bvh::bounding_hierarchy::BHShape;
use bvh::bvh::Bvh;
use bvh::ray::Ray as BvhRay;
use macroquad::prelude::*;
use nalgebra::{Point3, Vector3};

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

/// 命中几何的语义标签，与 Surface（视觉分面）正交。
/// 由对象名识别（content::load 阶段在 C_ 几何上分类）。
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum HitTag {
    /// 普通几何，按 Surface 颜色显形、单点。
    Normal,
    /// 被识别为危险（C_*danger/hazard/corpse/threat/trap/blood*）。
    /// 显形锁红，beam 线随点色也红。
    Danger,
    /// 人类建筑/废墟/营地等"非地形"（C_*human/building/structure/ruin/camp/settlement/wreck/debris*）。
    /// 命中产生 3 倍粒子（探索优化），便于辨识。
    Structure,
}

impl HitTag {
    /// 从 Blender 对象名识别 tag。**Danger 优先于 Structure**（同名命中危险 token 即视为危险）。
    pub fn from_name(name: &str) -> Self {
        let n = name.to_lowercase();
        let danger_kw = [
            "danger", "hazard", "corpse", "threat", "trap", "blood",
        ];
        let structure_kw = [
            "human", "building", "structure", "ruin", "camp",
            "settlement", "wreck", "debris",
        ];
        if danger_kw.iter().any(|k| n.contains(k)) {
            HitTag::Danger
        } else if structure_kw.iter().any(|k| n.contains(k)) {
            HitTag::Structure
        } else {
            HitTag::Normal
        }
    }
}

#[derive(Clone, Copy)]
pub struct Hit {
    pub pos: Vec3,
    pub surface: Surface,
    pub tag: HitTag,
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
        Self {
            a,
            b,
            c,
            surface: surface_from_normal((b - a).cross(c - a).normalize_or_zero()),
        }
    }

    fn with_surface(a: Vec3, b: Vec3, c: Vec3, surface: Surface) -> Self {
        Self { a, b, c, surface }
    }
}

/// 按面法线方向把三角形分类：朝上=地面、朝下=天花板、其余=墙。
/// 同时被 `Tri::new` 和 BVH 包装层使用，保证两路一致。
fn surface_from_normal(n: Vec3) -> Surface {
    if n.y > 0.6 {
        Surface::Floor
    } else if n.y < -0.6 {
        Surface::Ceiling
    } else {
        Surface::Wall
    }
}

/// BVH 节点形状：包装 `Tri` + tag + bvh crate 要求的 node_index 字段。
struct BvhTri {
    tri: Tri,
    tag: HitTag,
    node_index: usize,
}

impl Bounded<f32, 3> for BvhTri {
    fn aabb(&self) -> Aabb<f32, 3> {
        let mn = self.tri.a.min(self.tri.b).min(self.tri.c);
        let mx = self.tri.a.max(self.tri.b).max(self.tri.c);
        Aabb::with_bounds(
            Point3::new(mn.x, mn.y, mn.z),
            Point3::new(mx.x, mx.y, mx.z),
        )
    }
}

impl BHShape<f32, 3> for BvhTri {
    fn set_bh_node_index(&mut self, i: usize) {
        self.node_index = i;
    }
    fn bh_node_index(&self) -> usize {
        self.node_index
    }
}

/// 把 `[Vec3;3]` + 自动分类 surface + 显式 tag 包装成 BvhTri。
fn bvh_tri_tagged(tag: HitTag, t: &[Vec3; 3]) -> BvhTri {
    let n = (t[1] - t[0]).cross(t[2] - t[0]).normalize_or_zero();
    BvhTri {
        tri: Tri::with_surface(t[0], t[1], t[2], surface_from_normal(n)),
        tag,
        node_index: 0,
    }
}

fn bvh_tri_phantom(color: PhantomColor, t: &[Vec3; 3]) -> BvhTri {
    BvhTri {
        tri: Tri::with_surface(t[0], t[1], t[2], Surface::Phantom(color)),
        tag: HitTag::Normal, // phantom 自带颜色，不参与 Danger/Structure 通道
        node_index: 0,
    }
}

pub struct World {
    /// R_*：真实几何。仅参与深度遮挡（点云不穿墙）。**不参与声呐 raycast。**
    render_tris: Vec<Tri>,
    /// C_*：玩家碰撞用（resolve_player_movement → blocked()）。
    /// 声呐 raycast 不直接读这里，而是读 raycast_shapes 上的 BVH（同源数据）。
    collision_tris: Vec<Tri>,
    /// 出生点登陆仓预探明区采样源（C_*crashed* 几何）。
    crashed_tris: Vec<[Vec3; 3]>,
    /// 声呐 raycast 的 BVH 节点。
    /// 包含 C_（系统所见，与 collision_tris 同源）+ P_（phantom 显形）。
    /// C_ 为空时回退 R_（兼容旧地图）。
    raycast_shapes: Vec<BvhTri>,
    raycast_bvh: Option<Bvh<f32, 3>>,
    /// 物理地面查询专用：在 R_（真实山地几何）上建 BVH。
    /// 玩家身体落在真山表面（"工具有罪"的内核：你脚下是真山，但声呐让你以为是断壁）。
    physics_shapes: Vec<BvhTri>,
    physics_bvh: Option<Bvh<f32, 3>>,
    spawn: Vec3,
    spawn_yaw: f32,
}

impl World {
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
        // C_ 空则回退 R_：raycast **与玩家碰撞**都回退到 R_，全部 Normal tag。
        let raycast_src_tagged: Vec<(HitTag, [Vec3; 3])> = if level.collision_tris.is_empty() {
            println!(
                "[world] C_ 为空，raycast 与碰撞均回退到 R_（{} 三角）—— 建议补 C_ 简化代理避免玩家被装饰几何卡住",
                level.render_tris.len()
            );
            level.render_tris.iter().map(|t| (HitTag::Normal, *t)).collect()
        } else {
            level.collision_tris.clone()
        };
        // collision_tris 给 blocked()——不需要 tag，只要几何
        let collision_tris: Vec<Tri> = raycast_src_tagged
            .iter()
            .map(|(_, t)| Tri::new(t[0], t[1], t[2]))
            .collect();

        // 在 raycast_src（= C_ 或 R_ fallback）+ phantom 上建 BVH。
        let mut raycast_shapes: Vec<BvhTri> = raycast_src_tagged
            .iter()
            .map(|(tag, t)| bvh_tri_tagged(*tag, t))
            .collect();
        for (color, t) in &level.phantom_tris {
            raycast_shapes.push(bvh_tri_phantom(*color, t));
        }
        let raycast_bvh = build_bvh(&mut raycast_shapes);
        let bvh_tag_ok = raycast_bvh.is_some();

        // 统计 tag 分布（modeler 检查工具）
        let n_danger = raycast_src_tagged.iter().filter(|(t, _)| *t == HitTag::Danger).count();
        let n_struct = raycast_src_tagged.iter().filter(|(t, _)| *t == HitTag::Structure).count();
        println!(
            "[world] BVH: {} 节点形状 ({} C_/R_, 其中 {} Danger / {} Structure + {} P_) → {}",
            raycast_shapes.len(),
            raycast_src_tagged.len(),
            n_danger, n_struct,
            level.phantom_tris.len(),
            if bvh_tag_ok { "已加速" } else { "空场景跳过" }
        );

        // R_ 物理 BVH：地面查询专用（玩家"脚踏真山"）
        let mut physics_shapes: Vec<BvhTri> = level
            .render_tris
            .iter()
            .map(|t| bvh_tri_tagged(HitTag::Normal, t))
            .collect();
        let physics_bvh = build_bvh(&mut physics_shapes);
        println!(
            "[world] 物理 BVH: {} R_ 节点形状 → {}",
            physics_shapes.len(),
            if physics_bvh.is_some() { "已加速" } else { "空场景跳过" }
        );

        let spawn = level.spawn.unwrap_or_else(|| vec3(0.0, PLAYER_HEIGHT, 0.0));
        let spawn_yaw = level.spawn_yaw.unwrap_or(0.0);
        Self {
            render_tris,
            collision_tris,
            crashed_tris: level.crashed_tris,
            raycast_shapes,
            raycast_bvh,
            physics_shapes,
            physics_bvh,
            spawn,
            spawn_yaw,
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

        let mut raycast_shapes: Vec<BvhTri> = tris
            .iter()
            .map(|t| BvhTri { tri: *t, tag: HitTag::Normal, node_index: 0 })
            .collect();
        let raycast_bvh = build_bvh(&mut raycast_shapes);

        // code_room 下 R_ = collision tris；物理 BVH 也用它
        let mut physics_shapes: Vec<BvhTri> = tris
            .iter()
            .map(|t| BvhTri { tri: *t, tag: HitTag::Normal, node_index: 0 })
            .collect();
        let physics_bvh = build_bvh(&mut physics_shapes);

        Self {
            render_tris: tris.clone(),
            collision_tris: tris,
            crashed_tris: Vec::new(),
            raycast_shapes,
            raycast_bvh,
            physics_shapes,
            physics_bvh,
            spawn: v(0.0, PLAYER_HEIGHT, 0.0),
            spawn_yaw: 0.0,
        }
    }

    /// 物理地面查询：从 (x, z) 顶上往下打一道射线，返回最近 R_ 表面的 y。
    /// 用来把玩家身体"贴"到真山上，让玩家感受到坡度、不会浮空/钻地。
    pub fn ground_y_at(&self, x: f32, z: f32) -> Option<f32> {
        let bvh = self.physics_bvh.as_ref()?;
        let origin = vec3(x, 10_000.0, z);
        let dir = vec3(0.0, -1.0, 0.0);
        let ray = BvhRay::new(
            Point3::new(origin.x, origin.y, origin.z),
            Vector3::new(dir.x, dir.y, dir.z),
        );
        let mut best_dist: Option<f32> = None;
        for shape in bvh.traverse(&ray, &self.physics_shapes) {
            let t = &shape.tri;
            if let Some(dist) = ray_tri(origin, dir, t.a, t.b, t.c) {
                if best_dist.map_or(true, |b| dist < b) {
                    best_dist = Some(dist);
                }
            }
        }
        best_dist.map(|d| origin.y - d)
    }

    /// 出生点登陆仓预探明区采样源三角形（按面积分配静态点云）
    pub fn crashed_triangles(&self) -> &[[Vec3; 3]] {
        &self.crashed_tris
    }

    pub fn spawn_yaw(&self) -> f32 {
        self.spawn_yaw
    }

    pub fn spawn(&self) -> Vec3 {
        self.spawn
    }

    /// 用于深度预通道：R_（真实几何）+ C_（系统所见简化代理）都写深度，
    /// 才能正确遮挡点云（C_ 墙也要挡住后方点云，否则玩家会"穿墙看见"）。
    /// 几何是静态的，渲染器一次性缓存即可。
    pub fn render_triangles(&self) -> impl Iterator<Item = [Vec3; 3]> + '_ {
        self.render_tris
            .iter()
            .chain(self.collision_tris.iter())
            .map(|t| [t.a, t.b, t.c])
    }

    /// 声呐 raycast：BVH 加速、单 ray O(log N)。
    /// 命中源 = C_（系统所见，主要墙体）+ P_（phantom 显形）；R_ 不参与（=真实几何对声呐隐形）。
    /// 同一 BVH 容纳两类几何，统一最近命中比较。
    ///
    /// **方向归一化**：bvh 的 slab test 是尺度无关的，但我们自己跑 Möller-Trumbore 算 t
    /// 时 t = 真实距离需要 dir 归一化才有意义（后续 max_range 比较）。
    /// 入口处兜底归一一次。
    pub fn raycast(&self, origin: Vec3, dir: Vec3, max_range: f32) -> Option<Hit> {
        let Some(bvh) = self.raycast_bvh.as_ref() else {
            return None;
        };
        let dir = dir.normalize_or_zero();
        if dir.length_squared() < 1e-12 {
            return None;
        }
        let ray = BvhRay::new(
            Point3::new(origin.x, origin.y, origin.z),
            Vector3::new(dir.x, dir.y, dir.z),
        );
        let mut best: Option<Hit> = None;
        for shape in bvh.traverse(&ray, &self.raycast_shapes) {
            let t = &shape.tri;
            if let Some(dist) = ray_tri(origin, dir, t.a, t.b, t.c) {
                if dist <= max_range && best.map_or(true, |h: Hit| dist < h.distance) {
                    best = Some(Hit {
                        pos: origin + dir * dist,
                        surface: t.surface,
                        tag: shape.tag,
                        distance: dist,
                    });
                }
            }
        }
        best
    }

    /// 分轴推进，对 Collision 几何做射线阻挡（够用的近似碰撞）。
    pub fn resolve_player_movement(&self, current: Vec3, desired: Vec3, radius: f32) -> Vec3 {
        let mut pos = current;
        let dx = desired.x - current.x;
        if dx.abs() > 1e-5 && !self.blocked(pos, vec3(dx.signum(), 0.0, 0.0), dx.abs(), radius) {
            pos.x = desired.x;
        }
        let dz = desired.z - current.z;
        if dz.abs() > 1e-5 && !self.blocked(pos, vec3(0.0, 0.0, dz.signum()), dz.abs(), radius) {
            pos.z = desired.z;
        }
        pos.y = current.y;
        pos
    }

    fn blocked(&self, origin: Vec3, dir: Vec3, dist: f32, radius: f32) -> bool {
        let reach = dist + radius;
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

/// 在给定形状集合上构建 BVH；空集返回 None。
fn build_bvh(shapes: &mut Vec<BvhTri>) -> Option<Bvh<f32, 3>> {
    if shapes.is_empty() {
        None
    } else {
        Some(Bvh::build(shapes))
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
