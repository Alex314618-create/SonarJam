//! BT 系统：会向玩家位移的实体（"过去的自己"重标记成的威胁）。
//!
//! 加载 muddy_man_by_tripo.glb 取顶点云 → BT 的上身粒子模板。
//! 下身（脚部已被 PA 在 Blender 删掉）→ 代码生成红色飘动粒子。
//!
//! 设计要点：
//! - 几何：直立胶囊体（高 BT_HEIGHT，半径 BT_RADIUS）。无 mesh、无 Blender 资产依赖
//! - 行为：声呐脉冲后 awareness 提升 → 转 Hunting → 朝玩家平移
//! - 击杀：右键绿激光持续命中 BT_KILL_DURATION 秒后死亡（淡出 BT_DESPAWN_FADE）
//! - 死亡：触碰玩家 = advance_phase（由 GameApp 检查）

use crate::world::geometry::World;
use macroquad::prelude::*;

/// 加载 BT 上身 mesh 顶点云。失败返回空——上身就只剩下身粒子，不至于崩。
pub fn load_upper_template(path: &str) -> Vec<Vec3> {
    let raw = match std::fs::read(path) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("[bt] 无法读取 {}：{}", path, e);
            return Vec::new();
        }
    };
    let patched = crate::ship::strip_extensions_required_for_glb(&raw);
    let (doc, buffers, _) = match gltf::import_slice(&patched) {
        Ok(t) => t,
        Err(e) => {
            eprintln!("[bt] GLB 解析失败 {}：{}", path, e);
            return Vec::new();
        }
    };
    let mut all = Vec::new();
    for mesh in doc.meshes() {
        for prim in mesh.primitives() {
            let reader = prim.reader(|b| buffers.get(b.index()).map(|d| d.0.as_slice()));
            if let Some(iter) = reader.read_positions() {
                for p in iter {
                    all.push(Vec3::from_array(p));
                }
            }
        }
    }
    // 取多一些（~400）能让人形显形；扫描时一次注入到 sonar Point，
    // 走深度遮挡管线，不穿墙，颜色用 Danger 红。
    const TARGET: usize = 400;
    if all.len() > TARGET {
        let step = (all.len() / TARGET).max(1);
        let mut down = Vec::with_capacity(TARGET);
        for i in (0..all.len()).step_by(step) {
            down.push(all[i]);
            if down.len() >= TARGET {
                break;
            }
        }
        println!("[bt] 上身模板：{} 顶点 → 下采样到 {}", all.len(), down.len());
        return down;
    }
    println!("[bt] 上身模板：{} 顶点", all.len());
    all
}

pub const BT_HEIGHT: f32 = 1.7;
pub const BT_RADIUS: f32 = 0.35;
/// 玩家按住左键时 BT 的位移速度（m/s）
const BT_HUNT_SPEED: f32 = 1.5;
/// 玩家放手时 BT 的"压迫蠕动"速度——慢，但持续给压力，不让你 10s 跑完地图
const BT_CREEP_SPEED: f32 = 0.4;
/// 蠕动只在玩家距离 BT < 此值时启用（远了 BT 不动）
const BT_CREEP_RANGE: f32 = 35.0;
/// 连续滋多久击杀（秒）
const BT_KILL_DURATION: f32 = 1.5;
/// 不被滋时累计计时器衰减速率（仅在放手 0.15s 后才开始衰减）
const BT_KILL_DECAY: f32 = 1.5;
/// 击杀计时器停滞缓冲：滋的最后一帧到现在 < 此值 → 不衰减
const BT_KILL_GRACE: f32 = 0.15;
/// 触碰距离（玩家中心到 BT 中心 < 这个 → 死亡）
const BT_TOUCH_DIST: f32 = 0.9;
/// 单次声呐脉冲给 BT 增加的 awareness（最大值）
const BT_AWARENESS_FROM_PULSE: f32 = 0.45;
/// 闲置时 awareness 衰减速率
const BT_AWARENESS_DECAY: f32 = 0.05;
/// awareness 超过这个 → 切到 Hunting
const BT_HUNT_THRESHOLD: f32 = 0.30;
/// 声呐脉冲影响 BT 的最大距离（远超此值 awareness 不增）
const BT_PULSE_REACH: f32 = 60.0;
/// 死亡淡出时长
const BT_DESPAWN_FADE: f32 = 0.30;

#[derive(Clone, Copy, PartialEq)]
pub enum BtState {
    Idle,
    Hunting,
    /// 剩余淡出时间（秒）
    Dying(f32),
}

pub struct Bt {
    pub pos: Vec3, // 脚底位置
    pub state: BtState,
    pub awareness: f32,
    pub kill_progress: f32,
    pub id: u32,               // 全局唯一 ID（清除 BT 轮廓点用）
    pub last_snap_t: f32,      // 上次"轮廓定格"时间戳，1.0s 限流用
    pub last_green_hit_t: f32, // 上次绿激光命中时间戳；0.15s 内不衰减 kill_progress
    /// 自主留痕时间戳：每 1.0s BT 自己往 sonar 喷一次身影（不依赖玩家扫描）
    pub last_auto_snap_t: f32,
    /// 是否已被声呐扫到过（用于第一次扫到时触发"右键解离"警告）
    pub ever_scanned: bool,
    /// 身体粒子偏移（相对 pos）：上身贴 muddy_man mesh 顶点，下身飘红粒子。
    pub body_particles: Vec<Vec3>,
    /// 每个粒子的相位（用于 sin 漂浮）
    pub body_phases: Vec<f32>,
}

pub struct CapsuleHit {
    pub bt_idx: usize,
    pub pos: Vec3,
    pub distance: f32,
}

/// BT 死亡时的红色蒸发粒子
pub struct DeathParticle {
    pub pos: Vec3,
    pub vel: Vec3,
    pub life: f32,     // 剩余存活时间
    pub life_max: f32, // 初始存活时间（用于 alpha 计算）
}

pub struct BtSystem {
    pub bts: Vec<Bt>,
    /// 玩家当前是否在按住左键发射声呐——BT 仅在此为 true 时才靠近玩家
    pub firing: bool,
    /// 累计游戏时间（用于 BT 限流时间戳）
    pub now: f32,
    next_id: u32,
    /// 死亡蒸发粒子（独立于点云，用屏幕空间投影绘制）
    pub particles: Vec<DeathParticle>,
}

impl BtSystem {
    pub fn new() -> Self {
        Self {
            bts: Vec::new(),
            firing: false,
            now: 0.0,
            next_id: 1,
            particles: Vec::new(),
        }
    }

    /// 玩家是否在按住左键。BtSystem.tick 只在 firing == true 时让 Hunting BT 位移。
    pub fn set_firing(&mut self, firing: bool) {
        self.firing = firing;
    }

    /// 在脚底位置 spawn 一只 BT。upper_verts 是 muddy_man mesh 的顶点采样
    /// （相对 BT 脚底原点）；下身用算法生成红粒子。
    pub fn spawn(&mut self, pos: Vec3, upper_template: &[Vec3]) {
        let id = self.next_id;
        self.next_id += 1;
        let mut body_particles = Vec::with_capacity(upper_template.len() + 40);
        let mut body_phases = Vec::with_capacity(upper_template.len() + 40);
        // 上身：直接用 mesh 顶点采样（脚底原点）
        for v in upper_template {
            body_particles.push(*v);
            body_phases.push(macroquad::rand::gen_range(0.0_f32, std::f32::consts::TAU));
        }
        // 下身：脚底到上身底（y=0 到 -1.0m 下方？mesh 已删脚部，所以从 mesh.min.y 往下）
        // 这里在脚底以下 1.0m 范围内撒 40 个红粒子，圆柱半径 0.25m
        for _ in 0..40 {
            let theta = macroquad::rand::gen_range(0.0_f32, std::f32::consts::TAU);
            let r = macroquad::rand::gen_range(0.0_f32, 1.0).sqrt() * 0.28;
            let y = macroquad::rand::gen_range(-1.0_f32, 0.05);
            body_particles.push(vec3(theta.cos() * r, y, theta.sin() * r));
            body_phases.push(macroquad::rand::gen_range(0.0_f32, std::f32::consts::TAU));
        }
        self.bts.push(Bt {
            pos,
            state: BtState::Idle,
            awareness: 0.0,
            kill_progress: 0.0,
            id,
            last_snap_t: -100.0,
            last_green_hit_t: -100.0,
            last_auto_snap_t: -100.0,
            ever_scanned: false,
            body_particles,
            body_phases,
        });
    }

    /// 给 sonar 用：尝试为 bt_idx 申请一次"轮廓定格"。
    /// 间隔 < 1.0s 返回 None；可以则返回 BT 的 id（轮廓点 origin 用）+ 更新时间戳。
    pub fn try_snap(&mut self, bt_idx: usize) -> Option<u32> {
        if let Some(bt) = self.bts.get_mut(bt_idx) {
            if self.now - bt.last_snap_t >= 1.0 {
                bt.last_snap_t = self.now;
                return Some(bt.id);
            }
        }
        None
    }

    /// 不重置时间戳的简单查询：本帧此 BT 是否在"已开启的快照窗口"内。
    /// 用于本帧多条 ray 命中同一 BT 时统一判定。
    pub fn snap_open(&self, bt_idx: usize) -> bool {
        self.bts
            .get(bt_idx)
            .map_or(false, |bt| self.now - bt.last_snap_t < 0.05)
    }

    pub fn clear(&mut self) {
        self.bts.clear();
    }

    /// 声呐脉冲触发：所有 BT 的 awareness 按距离衰减地增长。
    pub fn on_sonar_pulse(&mut self, player_pos: Vec3) {
        for bt in &mut self.bts {
            if matches!(bt.state, BtState::Dying(_)) {
                continue;
            }
            let d = (bt.pos - player_pos).length();
            if d < BT_PULSE_REACH {
                let scale = (1.0 - d / BT_PULSE_REACH).max(0.0);
                bt.awareness = (bt.awareness + BT_AWARENESS_FROM_PULSE * scale).min(1.0);
                if bt.awareness >= BT_HUNT_THRESHOLD && !matches!(bt.state, BtState::Dying(_)) {
                    bt.state = BtState::Hunting;
                }
            }
        }
    }

    /// 绿激光命中：累计击杀进度。同一帧多条射线命中同一 BT，外层去重后调一次。
    pub fn on_green_hit(&mut self, bt_idx: usize, dt: f32) {
        let now = self.now;
        if let Some(bt) = self.bts.get_mut(bt_idx) {
            if matches!(bt.state, BtState::Dying(_)) {
                return;
            }
            bt.kill_progress += dt;
            bt.last_green_hit_t = now;
            if bt.kill_progress >= BT_KILL_DURATION {
                bt.state = BtState::Dying(BT_DESPAWN_FADE);
                // 触发死亡蒸发：在胶囊体积内随机撒 60 个红粒子，
                // 速度全部朝上但有快慢之分，寿命 1.5~3.5s
                let center = bt.pos + vec3(0.0, BT_HEIGHT * 0.5, 0.0);
                for _ in 0..60 {
                    // 圆柱体积内均匀采样
                    let theta = macroquad::rand::gen_range(0.0_f32, std::f32::consts::TAU);
                    let r = macroquad::rand::gen_range(0.0_f32, 1.0).sqrt() * BT_RADIUS * 0.95;
                    let y_off = macroquad::rand::gen_range(-BT_HEIGHT * 0.45, BT_HEIGHT * 0.45);
                    let pos = vec3(
                        center.x + theta.cos() * r,
                        center.y + y_off,
                        center.z + theta.sin() * r,
                    );
                    let up_speed = macroquad::rand::gen_range(0.4_f32, 2.5);
                    let drift = 0.15_f32;
                    let vel = vec3(
                        macroquad::rand::gen_range(-drift, drift),
                        up_speed,
                        macroquad::rand::gen_range(-drift, drift),
                    );
                    let life = macroquad::rand::gen_range(1.5_f32, 3.5);
                    self.particles.push(DeathParticle {
                        pos,
                        vel,
                        life,
                        life_max: life,
                    });
                }
            }
        }
    }

    /// 每帧推进：状态机 + 位移 + 贴山 + 衰减。
    /// 返回 (本帧死亡 IDs, 本帧需要自主留痕的 BT 索引)。
    /// 自主留痕：每 1.0s，存活 BT 在当前位置把身影喷一次到 sonar（不依赖玩家扫描）。
    pub fn tick(&mut self, dt: f32, player_pos: Vec3, world: &World) -> (Vec<u32>, Vec<usize>) {
        self.now += dt;
        let firing = self.firing; // 先取出，避免和 iter_mut 的借用冲突
        let now = self.now;
        let mut despawn: Vec<usize> = Vec::new();
        for (i, bt) in self.bts.iter_mut().enumerate() {
            match bt.state {
                BtState::Dying(remain) => {
                    let r = remain - dt;
                    if r <= 0.0 {
                        despawn.push(i);
                    } else {
                        bt.state = BtState::Dying(r);
                    }
                }
                BtState::Hunting => {
                    let to = player_pos - bt.pos;
                    let horiz = vec3(to.x, 0.0, to.z);
                    let dist = horiz.length();
                    // 速度：按住左键 → 快；否则 → 蠕动（仅在近距离）；远了不动
                    let speed = if firing {
                        BT_HUNT_SPEED
                    } else if dist < BT_CREEP_RANGE {
                        BT_CREEP_SPEED
                    } else {
                        0.0
                    };
                    if dist > 1e-3 && speed > 0.0 {
                        bt.pos += horiz.normalize() * speed * dt;
                    }
                    if let Some(gy) = world.ground_y_at(bt.pos.x, bt.pos.z) {
                        bt.pos.y = gy;
                    }
                    // 击杀计时：被滋最近 0.15s 内不衰减；否则 1.5×/s 衰减
                    if now - bt.last_green_hit_t > BT_KILL_GRACE {
                        bt.kill_progress = (bt.kill_progress - BT_KILL_DECAY * dt).max(0.0);
                    }
                }
                BtState::Idle => {
                    if let Some(gy) = world.ground_y_at(bt.pos.x, bt.pos.z) {
                        bt.pos.y = gy;
                    }
                    bt.awareness = (bt.awareness - BT_AWARENESS_DECAY * dt).max(0.0);
                    if now - bt.last_green_hit_t > BT_KILL_GRACE {
                        bt.kill_progress = (bt.kill_progress - BT_KILL_DECAY * dt).max(0.0);
                    }
                }
            }
        }
        // 倒序移除，收集死亡 IDs
        despawn.sort_unstable();
        despawn.reverse();
        let mut dead_ids = Vec::with_capacity(despawn.len());
        for i in despawn {
            dead_ids.push(self.bts[i].id);
            self.bts.remove(i);
        }
        // 蒸发粒子推进 + 清理
        for p in self.particles.iter_mut() {
            p.life -= dt;
            p.pos += p.vel * dt;
            p.vel.y -= 0.3 * dt;
        }
        self.particles.retain(|p| p.life > 0.0);

        // 自主留痕：必须曾经被玩家扫描过（ever_scanned）才会持续在 sonar 里留痕——
        // 没被扫过的 BT 玩家根本不知道存在，自然不该看到红粒子。
        let mut auto_snap: Vec<usize> = Vec::new();
        for (i, bt) in self.bts.iter_mut().enumerate() {
            if matches!(bt.state, BtState::Dying(_)) {
                continue;
            }
            if !bt.ever_scanned {
                continue;
            }
            if now - bt.last_auto_snap_t > 1.0 {
                bt.last_auto_snap_t = now;
                auto_snap.push(i);
            }
        }
        (dead_ids, auto_snap)
    }

    /// 玩家是否触碰任何 BT。
    pub fn check_contact(&self, player_pos: Vec3) -> bool {
        for bt in &self.bts {
            if matches!(bt.state, BtState::Dying(_)) {
                continue;
            }
            let center = bt.pos + vec3(0.0, BT_HEIGHT * 0.5, 0.0);
            let d = (center - player_pos).length();
            if d < BT_TOUCH_DIST + BT_RADIUS {
                return true;
            }
        }
        false
    }

    /// 射线-胶囊求交（声呐/绿激光命中检测）。返回最近正向命中。
    pub fn raycast(&self, origin: Vec3, dir: Vec3, max_dist: f32) -> Option<CapsuleHit> {
        let mut best: Option<CapsuleHit> = None;
        for (i, bt) in self.bts.iter().enumerate() {
            if matches!(bt.state, BtState::Dying(_)) {
                continue;
            }
            // 胶囊：底半球中心 a，顶半球中心 b
            let a = bt.pos + vec3(0.0, BT_RADIUS, 0.0);
            let b = bt.pos + vec3(0.0, BT_HEIGHT - BT_RADIUS, 0.0);
            if let Some((t, hit)) = ray_capsule(origin, dir, a, b, BT_RADIUS) {
                if t <= max_dist && best.as_ref().map_or(true, |h| t < h.distance) {
                    best = Some(CapsuleHit {
                        bt_idx: i,
                        pos: hit,
                        distance: t,
                    });
                }
            }
        }
        best
    }

    /// 最近 BT 到玩家的距离（音频/HUD 用）。无 BT 返回 None。
    #[allow(dead_code)]
    pub fn nearest_distance(&self, player_pos: Vec3) -> Option<f32> {
        let mut best: Option<f32> = None;
        for bt in &self.bts {
            if matches!(bt.state, BtState::Dying(_)) {
                continue;
            }
            let d = (bt.pos - player_pos).length();
            if best.map_or(true, |b| d < b) {
                best = Some(d);
            }
        }
        best
    }
}

// ===== 射线-胶囊几何 =====

/// 把胶囊拆成 (顶半球, 底半球, 沿 Y 轴的圆柱) 三段做相交，取最近正向命中。
fn ray_capsule(origin: Vec3, dir: Vec3, a: Vec3, b: Vec3, r: f32) -> Option<(f32, Vec3)> {
    let mut best: Option<(f32, Vec3)> = None;
    // 底半球（y <= a.y 一侧）
    if let Some((t, h)) = ray_sphere(origin, dir, a, r) {
        if h.y <= a.y + 1e-3 {
            best = better(best, t, h);
        }
    }
    // 顶半球（y >= b.y 一侧）
    if let Some((t, h)) = ray_sphere(origin, dir, b, r) {
        if h.y >= b.y - 1e-3 {
            best = better(best, t, h);
        }
    }
    // Y 轴圆柱（y 在 [a.y, b.y] 之间）
    if let Some((t, h)) = ray_cylinder_y(origin, dir, a, b, r) {
        best = better(best, t, h);
    }
    best
}

fn better(best: Option<(f32, Vec3)>, t: f32, h: Vec3) -> Option<(f32, Vec3)> {
    if t < 0.0 {
        return best;
    }
    match best {
        Some((bt, _)) if bt <= t => best,
        _ => Some((t, h)),
    }
}

fn ray_sphere(origin: Vec3, dir: Vec3, center: Vec3, r: f32) -> Option<(f32, Vec3)> {
    let oc = origin - center;
    let b = oc.dot(dir);
    let c = oc.dot(oc) - r * r;
    let disc = b * b - c;
    if disc < 0.0 {
        return None;
    }
    let sd = disc.sqrt();
    let t = -b - sd;
    if t > 0.0 {
        return Some((t, origin + dir * t));
    }
    let t2 = -b + sd;
    if t2 > 0.0 {
        return Some((t2, origin + dir * t2));
    }
    None
}

fn ray_cylinder_y(origin: Vec3, dir: Vec3, a: Vec3, b: Vec3, r: f32) -> Option<(f32, Vec3)> {
    let cx = a.x;
    let cz = a.z;
    let dx = dir.x;
    let dz = dir.z;
    let ox = origin.x - cx;
    let oz = origin.z - cz;
    let aa = dx * dx + dz * dz;
    if aa.abs() < 1e-9 {
        return None; // 射线沿 Y 轴
    }
    let bb = 2.0 * (ox * dx + oz * dz);
    let cc = ox * ox + oz * oz - r * r;
    let disc = bb * bb - 4.0 * aa * cc;
    if disc < 0.0 {
        return None;
    }
    let sd = disc.sqrt();
    let t_candidates = [(-bb - sd) / (2.0 * aa), (-bb + sd) / (2.0 * aa)];
    let y_min = a.y.min(b.y);
    let y_max = a.y.max(b.y);
    for &t in &t_candidates {
        if t > 0.0 {
            let py = origin.y + dir.y * t;
            if py >= y_min && py <= y_max {
                return Some((t, origin + dir * t));
            }
        }
    }
    None
}
