//! 感知结果层：声呐发射射线、命中生成持久点、能量管理。
//!
//! 只读消费 world 的 raycast，从不修改世界几何（保持感知层 / 几何层分离）。

use crate::app::config::{
    CONTINUOUS_COST_PER_SEC, CONTINUOUS_RAYS_PER_SEC, CONTINUOUS_SPREAD_DEG, ENERGY_MAX,
    ENERGY_REGEN_PER_SEC, GREEN_COST_PER_SEC, GREEN_RANGE, GREEN_RAYS_PER_SEC, GREEN_SPREAD_DEG,
    PULSE_COOLDOWN, PULSE_COST, PULSE_RAYS, PULSE_SPREAD_DEG, SONAR_MAX_POINTS, SONAR_RANGE,
};
use crate::bt::BtSystem;
use crate::world::geometry::{HitTag, Surface, World};
use macroquad::prelude::*;
use macroquad::rand::gen_range;
use std::collections::HashSet;

const GOLDEN_ANGLE: f32 = 2.399_963_2;

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum PointOrigin {
    World,
    /// 来自 BT 轮廓（u32 = BT id；BT 死亡时按 id 清掉对应点）
    BtSilhouette(u32),
}

#[derive(Clone, Copy)]
pub struct Point {
    pub pos: Vec3,
    pub color: Color,
    pub origin: PointOrigin,
}

#[derive(Clone, Copy, Default)]
pub struct FireVisualState {
    #[allow(dead_code)]
    pub muzzle_flash: f32,
}

pub struct Sonar {
    points: Vec<Point>, // 环形缓冲
    head: usize,
    new_this_frame: Vec<usize>,
    energy: f32,
    cooldown: f32,
    cont_accum: f32,
    muzzle_flash: f32,
    was_down: bool,
    /// 右键绿激光：本帧命中端点（renderer 画 beam）
    new_green_beam_ends: Vec<Vec3>,
    green_accum: f32,
    /// 本帧是否首次扫到 BT（首次扫描触发"右键解离"警告）
    pub just_scanned_bt_first_time: bool,
}

impl Sonar {
    pub fn new() -> Self {
        Self {
            points: Vec::with_capacity(SONAR_MAX_POINTS),
            head: 0,
            new_this_frame: Vec::new(),
            energy: ENERGY_MAX,
            cooldown: 0.0,
            cont_accum: 0.0,
            muzzle_flash: 0.0,
            was_down: false,
            new_green_beam_ends: Vec::new(),
            green_accum: 0.0,
            just_scanned_bt_first_time: false,
        }
    }

    pub fn new_green_beams(&self) -> &[Vec3] {
        &self.new_green_beam_ends
    }

    /// BT 死亡后清掉它的轮廓点。
    pub fn clear_silhouettes_for(&mut self, ids: &[u32]) {
        if ids.is_empty() {
            return;
        }
        self.points.retain(|p| match p.origin {
            PointOrigin::BtSilhouette(id) => !ids.contains(&id),
            _ => true,
        });
        self.head = self.points.len() % SONAR_MAX_POINTS;
    }

    pub fn energy_ratio(&self) -> f32 {
        self.energy / ENERGY_MAX
    }

    pub fn points(&self) -> &[Point] {
        &self.points
    }

    /// 灌入一次性事件点云（如 phase 3 树泄漏的红色显形）。
    /// 不触发枪口细线、不消耗能量、走环形缓冲推进（用 push 走 head 游标）。
    pub fn seed_event_points(&mut self, cloud: &[Point]) {
        for p in cloud {
            self.push(p.pos, p.color);
        }
        // 事件点不应被本帧的 new_this_frame 误判成"刚扫到"
        self.new_this_frame.clear();
    }

    /// 灌入预探明区静态点云（不触发枪口细线、不计入 head 环形游标）。
    /// 用于 Earth 出生点登陆仓的"已探明态"。
    pub fn seed_static(&mut self, cloud: &[Point]) {
        for p in cloud {
            if self.points.len() >= SONAR_MAX_POINTS {
                break;
            }
            self.points.push(*p);
        }
        // 环形游标推进到当前末尾，让后续玩家发射在剩余容量里循环覆盖
        self.head = self.points.len() % SONAR_MAX_POINTS;
        self.new_this_frame.clear();
    }

    pub fn new_points(&self) -> impl Iterator<Item = &Point> + '_ {
        self.new_this_frame.iter().map(move |&i| &self.points[i])
    }

    /// 进入下一轮：BtSilhouette **整批删除**（PA 要求）；World 点染银保留。
    pub fn advance_loop(&mut self) {
        let silver = Color::new(0.74, 0.78, 0.82, 1.0);
        self.points
            .retain(|p| !matches!(p.origin, PointOrigin::BtSilhouette(_)));
        for p in &mut self.points {
            p.color = silver;
        }
        self.head = self.points.len() % SONAR_MAX_POINTS;
        self.energy = ENERGY_MAX;
        self.new_this_frame.clear();
    }

    /// 公开：BT 自主每秒留痕用。外部传 BT id + 当前脚底位置 + 身体粒子模板。
    pub fn inject_bt_silhouette(&mut self, id: u32, base: Vec3, body_offsets: &[Vec3]) {
        for off in body_offsets {
            let jit = vec3(
                gen_range(-0.02_f32, 0.02),
                gen_range(-0.02_f32, 0.02),
                gen_range(-0.02_f32, 0.02),
            );
            let color = Color::new(jitter10(1.00), jitter10(0.15), jitter10(0.15), 1.0);
            self.push_with_origin(base + *off + jit, color, PointOrigin::BtSilhouette(id));
        }
    }

    /// `regen_enabled`：true=能量自动回充（DEV 模式专用），false=不回充（正式游戏：能量只减不加）。
    pub fn update(
        &mut self,
        dt: f32,
        world: &World,
        eye: Vec3,
        forward: Vec3,
        regen_enabled: bool,
        bt: &mut BtSystem,
    ) -> FireVisualState {
        self.new_this_frame.clear();
        self.new_green_beam_ends.clear();
        self.just_scanned_bt_first_time = false;
        self.cooldown = (self.cooldown - dt).max(0.0);
        self.muzzle_flash = (self.muzzle_flash - dt * 5.0).max(0.0);

        let right = forward.cross(Vec3::Y).normalize_or_zero();
        let up = right.cross(forward).normalize_or_zero();

        let down = mouse_left_down();
        let right_down = mouse_right_down();
        bt.set_firing(down);

        // 左键：声呐脉冲
        if down {
            if !self.was_down {
                bt.on_sonar_pulse(eye);
                self.fire_pulse(world, eye, forward, right, up, bt);
            } else {
                self.fire_continuous(dt, world, eye, forward, right, up, bt);
            }
        } else if regen_enabled && !right_down {
            self.energy = (self.energy + ENERGY_REGEN_PER_SEC * dt).min(ENERGY_MAX);
        }

        // 右键：绿激光（吃电，不显形 BT 点）
        if right_down && self.energy > 0.0 {
            self.fire_green(dt, world, eye, forward, right, up, bt);
        }
        self.was_down = down;

        FireVisualState {
            muzzle_flash: self.muzzle_flash,
        }
    }

    fn fire_pulse(
        &mut self,
        world: &World,
        eye: Vec3,
        fwd: Vec3,
        right: Vec3,
        up: Vec3,
        bt: &mut BtSystem,
    ) -> bool {
        if self.cooldown > 0.0 || self.energy < PULSE_COST {
            return false;
        }
        self.energy -= PULSE_COST;
        self.cooldown = PULSE_COOLDOWN;
        self.muzzle_flash = 1.0;
        crate::audio::play("gun");

        let spread = PULSE_SPREAD_DEG.to_radians();
        for i in 0..PULSE_RAYS {
            let t = i as f32 / PULSE_RAYS as f32;
            let angle = i as f32 * GOLDEN_ANGLE;
            let radius = spread * t.sqrt();
            self.cast(
                world,
                eye,
                fwd,
                right,
                up,
                angle.cos() * radius,
                angle.sin() * radius,
                bt,
            );
        }
        true
    }

    fn fire_continuous(
        &mut self,
        dt: f32,
        world: &World,
        eye: Vec3,
        fwd: Vec3,
        right: Vec3,
        up: Vec3,
        bt: &mut BtSystem,
    ) -> bool {
        let cost = CONTINUOUS_COST_PER_SEC * dt;
        if self.energy < cost {
            return false;
        }
        self.energy -= cost;
        self.muzzle_flash = 1.0;

        self.cont_accum += CONTINUOUS_RAYS_PER_SEC * dt;
        let count = self.cont_accum.floor() as usize;
        self.cont_accum -= count as f32;

        let spread = CONTINUOUS_SPREAD_DEG.to_radians();
        for _ in 0..count {
            let theta = gen_range(0.0, std::f32::consts::TAU);
            let radius = gen_range(0.0f32, 1.0).sqrt() * spread;
            self.cast(
                world,
                eye,
                fwd,
                right,
                up,
                theta.cos() * radius,
                theta.sin() * radius,
                bt,
            );
        }
        count > 0
    }

    /// 右键绿激光：每秒固定射线数密集发射；命中 BT 胶囊 → on_green_hit 累计击杀。
    fn fire_green(
        &mut self,
        dt: f32,
        world: &World,
        eye: Vec3,
        fwd: Vec3,
        right: Vec3,
        up: Vec3,
        bt: &mut BtSystem,
    ) {
        let cost = GREEN_COST_PER_SEC * dt;
        if self.energy < cost {
            return;
        }
        self.energy -= cost;
        self.muzzle_flash = 1.0;
        self.green_accum += GREEN_RAYS_PER_SEC * dt;
        let count = self.green_accum.floor() as usize;
        self.green_accum -= count as f32;

        let spread = GREEN_SPREAD_DEG.to_radians();
        let mut hit_bts: HashSet<usize> = HashSet::new();
        for _ in 0..count {
            let theta = gen_range(0.0, std::f32::consts::TAU);
            let radius = gen_range(0.0f32, 1.0).sqrt() * spread;
            let dir =
                (fwd + right * (theta.cos() * radius) + up * (theta.sin() * radius)).normalize();
            if let Some(hit) = bt.raycast(eye, dir, GREEN_RANGE) {
                hit_bts.insert(hit.bt_idx);
                self.new_green_beam_ends.push(hit.pos);
            } else if let Some(world_hit) = world.raycast(eye, dir, GREEN_RANGE) {
                self.new_green_beam_ends.push(world_hit.pos);
            } else {
                self.new_green_beam_ends.push(eye + dir * GREEN_RANGE);
            }
        }
        for idx in hit_bts {
            bt.on_green_hit(idx, dt);
        }
    }

    fn cast(
        &mut self,
        world: &World,
        eye: Vec3,
        fwd: Vec3,
        right: Vec3,
        up: Vec3,
        off_x: f32,
        off_y: f32,
        bt: &mut BtSystem,
    ) {
        let dir = (fwd + right * off_x + up * off_y).normalize();
        let w_hit = world.raycast(eye, dir, SONAR_RANGE);
        let b_hit = bt.raycast(eye, dir, SONAR_RANGE);
        let (pos, surface, tag, bt_id, bt_idx) = match (w_hit, b_hit) {
            (Some(w), Some(b)) if b.distance < w.distance => {
                let try_snap = bt.try_snap(b.bt_idx);
                let fresh_snap = try_snap.is_some();
                if bt.snap_open(b.bt_idx) || fresh_snap {
                    let bt_obj = &mut bt.bts[b.bt_idx];
                    if !bt_obj.ever_scanned {
                        bt_obj.ever_scanned = true;
                        self.just_scanned_bt_first_time = true;
                    }
                    let idx = if fresh_snap { Some(b.bt_idx) } else { None };
                    (b.pos, Surface::Wall, HitTag::Danger, Some(bt_obj.id), idx)
                } else {
                    return;
                }
            }
            (Some(w), _) => (w.pos, w.surface, w.tag, None, None),
            (None, Some(b)) => {
                let try_snap = bt.try_snap(b.bt_idx);
                let fresh_snap = try_snap.is_some();
                if bt.snap_open(b.bt_idx) || fresh_snap {
                    let bt_obj = &mut bt.bts[b.bt_idx];
                    if !bt_obj.ever_scanned {
                        bt_obj.ever_scanned = true;
                        self.just_scanned_bt_first_time = true;
                    }
                    let idx = if fresh_snap { Some(b.bt_idx) } else { None };
                    (b.pos, Surface::Wall, HitTag::Danger, Some(bt_obj.id), idx)
                } else {
                    return;
                }
            }
            (None, None) => return,
        };
        let color = color_for(surface, tag);
        let origin = match bt_id {
            Some(id) => PointOrigin::BtSilhouette(id),
            None => PointOrigin::World,
        };
        let jitter = vec3(
            gen_range(-0.035f32, 0.035),
            gen_range(-0.035f32, 0.035),
            gen_range(-0.035f32, 0.035),
        );
        self.push_with_origin(pos + jitter, color, origin);
        if tag == HitTag::Structure {
            for _ in 0..2 {
                let extra = vec3(
                    gen_range(-0.12f32, 0.12),
                    gen_range(-0.12f32, 0.12),
                    gen_range(-0.12f32, 0.12),
                );
                self.push_with_origin(pos + extra, color, origin);
            }
        }
        if tag == HitTag::Danger {
            for _ in 0..2 {
                let extra = vec3(
                    gen_range(-0.08f32, 0.08),
                    gen_range(-0.10f32, 0.10),
                    gen_range(-0.08f32, 0.08),
                );
                self.push_with_origin(pos + extra, color, origin);
            }
        }

        // 新鲜 snap：把 BT 的 mesh 顶点云作为身体轮廓灌进 sonar。
        // **不清旧的**——PA 要求"每秒钟留下自己的残影，身影一直被定格"。
        // 走深度遮挡管线（不穿墙）。
        if let Some(idx) = bt_idx {
            let bt_obj = &bt.bts[idx];
            let id = bt_obj.id;
            let base_pos = bt_obj.pos;
            for off in &bt_obj.body_particles {
                let jit = vec3(
                    gen_range(-0.02_f32, 0.02),
                    gen_range(-0.02_f32, 0.02),
                    gen_range(-0.02_f32, 0.02),
                );
                let p_color = Color::new(
                    jitter10(1.00),
                    jitter10(0.15),
                    jitter10(0.15),
                    1.0,
                );
                self.push_with_origin(base_pos + *off + jit, p_color, PointOrigin::BtSilhouette(id));
            }
        }
    }

    fn push(&mut self, pos: Vec3, color: Color) {
        self.push_with_origin(pos, color, PointOrigin::World);
    }

    fn push_with_origin(&mut self, pos: Vec3, color: Color, origin: PointOrigin) {
        let idx = if self.points.len() < SONAR_MAX_POINTS {
            self.points.push(Point { pos, color, origin });
            self.points.len() - 1
        } else {
            let i = self.head;
            self.points[i] = Point { pos, color, origin };
            i
        };
        self.head = (self.head + 1) % SONAR_MAX_POINTS;
        self.new_this_frame.push(idx);
    }
}

/// 物理查询右键是否按下。
#[cfg(target_os = "windows")]
fn mouse_right_down() -> bool {
    #[link(name = "user32")]
    extern "system" {
        fn GetAsyncKeyState(vkey: i32) -> i16;
    }
    const VK_RBUTTON: i32 = 0x02;
    unsafe { (GetAsyncKeyState(VK_RBUTTON) as u16 & 0x8000) != 0 }
}
#[cfg(not(target_os = "windows"))]
fn mouse_right_down() -> bool {
    is_mouse_button_down(MouseButton::Right)
}

/// 物理查询左键是否按下，绕开 macroquad 在 grab 下偶发丢失释放事件的问题。
#[cfg(target_os = "windows")]
fn mouse_left_down() -> bool {
    #[link(name = "user32")]
    extern "system" {
        fn GetAsyncKeyState(vkey: i32) -> i16;
    }
    const VK_LBUTTON: i32 = 0x01;
    unsafe { (GetAsyncKeyState(VK_LBUTTON) as u16 & 0x8000) != 0 }
}

#[cfg(not(target_os = "windows"))]
fn mouse_left_down() -> bool {
    is_mouse_button_down(MouseButton::Left)
}

/// 按面积加权在三角形集合上均匀采样 `target_count` 个点，给每个点 sonar 标志色 ± 抖动。
/// 用于 Earth 起步时把 crashed lander 的几何"预灌"成已探明的密集点云。
pub fn sample_static_cloud(tris: &[[Vec3; 3]], target_count: usize) -> Vec<Point> {
    if tris.is_empty() || target_count == 0 {
        return Vec::new();
    }
    let mut areas: Vec<f32> = Vec::with_capacity(tris.len());
    let mut total = 0.0_f32;
    for t in tris {
        let a = (t[1] - t[0]).cross(t[2] - t[0]).length() * 0.5;
        areas.push(a);
        total += a;
    }
    if total < 1e-6 {
        return Vec::new();
    }
    let density = target_count as f32 / total;
    let mut out: Vec<Point> = Vec::with_capacity(target_count);
    for (t, a) in tris.iter().zip(areas.iter()) {
        let n = (a * density).round() as usize;
        for _ in 0..n {
            let mut u = gen_range(0.0_f32, 1.0);
            let mut v = gen_range(0.0_f32, 1.0);
            if u + v > 1.0 {
                u = 1.0 - u;
                v = 1.0 - v;
            }
            let p = t[0] + (t[1] - t[0]) * u + (t[2] - t[0]) * v;
            // 用面法线推断 surface 让颜色和玩家自己扫的一致
            let normal = (t[1] - t[0]).cross(t[2] - t[0]).normalize_or_zero();
            let surface = if normal.y > 0.6 {
                Surface::Floor
            } else if normal.y < -0.6 {
                Surface::Ceiling
            } else {
                Surface::Wall
            };
            // 加点亚像素抖动让密集云不至于"网格化"
            let jitter = vec3(
                gen_range(-0.025_f32, 0.025),
                gen_range(-0.025_f32, 0.025),
                gen_range(-0.025_f32, 0.025),
            );
            // 预探明云在采样阶段无 tag 信息（C_*crashed* 都按 Normal 处理）
            out.push(Point {
                pos: p + jitter,
                color: color_for(surface, HitTag::Normal),
                origin: PointOrigin::World,
            });
        }
    }
    out
}

/// 按面积加权采样 `count` 个点，每个点固定颜色 + 轻微抖动。
/// 用于事件层"系统泄漏"显形（如 phase 3 树红云）。
pub fn sample_leak_cloud(tris: &[[Vec3; 3]], count: usize, base: Color) -> Vec<Point> {
    if tris.is_empty() || count == 0 {
        return Vec::new();
    }
    let mut areas: Vec<f32> = Vec::with_capacity(tris.len());
    let mut total = 0.0_f32;
    for t in tris {
        let a = (t[1] - t[0]).cross(t[2] - t[0]).length() * 0.5;
        areas.push(a);
        total += a;
    }
    if total < 1e-6 {
        return Vec::new();
    }
    let density = count as f32 / total;
    let mut out = Vec::with_capacity(count);
    for (t, a) in tris.iter().zip(areas.iter()) {
        let n = (a * density).round() as usize;
        for _ in 0..n {
            let mut u = gen_range(0.0_f32, 1.0);
            let mut v = gen_range(0.0_f32, 1.0);
            if u + v > 1.0 {
                u = 1.0 - u;
                v = 1.0 - v;
            }
            let p = t[0] + (t[1] - t[0]) * u + (t[2] - t[0]) * v;
            // 系统异常显形：轻微抖动让红云脱离"贴图感"
            let jitter = vec3(
                gen_range(-0.04_f32, 0.04),
                gen_range(-0.04_f32, 0.04),
                gen_range(-0.04_f32, 0.04),
            );
            let color = Color::new(
                (base.r + gen_range(-0.05_f32, 0.05)).clamp(0.0, 1.0),
                (base.g + gen_range(-0.03_f32, 0.03)).clamp(0.0, 1.0),
                (base.b + gen_range(-0.03_f32, 0.03)).clamp(0.0, 1.0),
                base.a,
            );
            out.push(Point {
                pos: p + jitter,
                color,
                origin: PointOrigin::World,
            });
        }
    }
    out
}

fn color_for(surface: Surface, tag: HitTag) -> Color {
    // Danger tag = 真红。PA 说之前那个橘色不对。
    if tag == HitTag::Danger {
        return Color::new(jitter10(1.00), jitter10(0.15), jitter10(0.15), 1.0);
    }
    // Structure：人造建筑/残骸/尸骨——黄色，区别于地形 + 登陆仓的青色。
    if tag == HitTag::Structure {
        return Color::new(jitter10(1.00), jitter10(0.82), jitter10(0.12), 1.0);
    }
    match surface {
        Surface::Wall => Color::new(0.25, gen_range(0.75f32, 1.0), gen_range(0.85f32, 1.0), 1.0),
        Surface::Floor => Color::new(0.10, gen_range(0.70f32, 0.9), gen_range(0.55f32, 0.75), 1.0),
        Surface::Ceiling => Color::new(0.30, gen_range(0.60f32, 0.8), gen_range(0.90f32, 1.0), 1.0),
        // Phantom：基色由 Blender 对象名编码（P_<kind>_<color>_<id>），±10% 抖动。
        Surface::Phantom(c) => {
            let (r, g, b) = c.base_rgb();
            Color::new(jitter10(r), jitter10(g), jitter10(b), 1.0)
        }
    }
}

/// 在 base 值上做 ±10% 抖动，并 clamp 到 [0,1]。
fn jitter10(base: f32) -> f32 {
    (base + gen_range(-0.1f32, 0.1) * base).clamp(0.0, 1.0)
}
