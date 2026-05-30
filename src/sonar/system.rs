//! 感知结果层：声呐发射射线、命中生成持久点、能量管理。
//!
//! 只读消费 world 的 raycast，从不修改世界几何（保持感知层 / 几何层分离）。

use crate::app::config::{
    CONTINUOUS_COST_PER_SEC, CONTINUOUS_RAYS_PER_SEC, CONTINUOUS_SPREAD_DEG, ENERGY_MAX,
    ENERGY_REGEN_PER_SEC, PULSE_COOLDOWN, PULSE_COST, PULSE_RAYS, PULSE_SPREAD_DEG,
    SONAR_MAX_POINTS, SONAR_RANGE,
};
use crate::world::geometry::{HitTag, Surface, World};
use macroquad::prelude::*;
use macroquad::rand::gen_range;

const GOLDEN_ANGLE: f32 = 2.399_963_2;

#[derive(Clone, Copy)]
pub struct Point {
    pub pos: Vec3,
    pub color: Color,
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
        }
    }

    pub fn energy_ratio(&self) -> f32 {
        self.energy / ENERGY_MAX
    }

    pub fn points(&self) -> &[Point] {
        &self.points
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

    /// 进入下一轮：把当前所有点固化为“过去”（染银，保留原位），能量充满。
    pub fn advance_loop(&mut self) {
        let silver = Color::new(0.74, 0.78, 0.82, 1.0);
        for p in &mut self.points {
            p.color = silver;
        }
        self.energy = ENERGY_MAX;
        self.new_this_frame.clear();
    }

    pub fn update(&mut self, dt: f32, world: &World, eye: Vec3, forward: Vec3) -> FireVisualState {
        self.new_this_frame.clear();
        self.cooldown = (self.cooldown - dt).max(0.0);
        self.muzzle_flash = (self.muzzle_flash - dt * 5.0).max(0.0);

        let right = forward.cross(Vec3::Y).normalize_or_zero();
        let up = right.cross(forward).normalize_or_zero();

        // 直接查询物理鼠标状态（见文件底部 mouse_left_down）。macroquad 在 grab +
        // raw input 下偶发丢失释放事件、导致 down 卡死、firing 卡 1，故绕开其事件层。
        let down = mouse_left_down();

        if down {
            if !self.was_down {
                // 按下第一帧立即发一发 pulse —— 零延迟反馈。
                self.fire_pulse(world, eye, forward, right, up);
            } else {
                // 持续按住 → 连续扫描。
                self.fire_continuous(dt, world, eye, forward, right, up);
            }
        } else {
            // 完全松开才回充，避免耗尽后边回血边断续发射的抖动。
            self.energy = (self.energy + ENERGY_REGEN_PER_SEC * dt).min(ENERGY_MAX);
        }
        self.was_down = down;

        FireVisualState {
            muzzle_flash: self.muzzle_flash,
        }
    }

    fn fire_pulse(&mut self, world: &World, eye: Vec3, fwd: Vec3, right: Vec3, up: Vec3) -> bool {
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
            self.cast(world, eye, fwd, right, up, angle.cos() * radius, angle.sin() * radius);
        }
        true
    }

    fn fire_continuous(&mut self, dt: f32, world: &World, eye: Vec3, fwd: Vec3, right: Vec3, up: Vec3) -> bool {
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
            self.cast(world, eye, fwd, right, up, theta.cos() * radius, theta.sin() * radius);
        }
        count > 0
    }

    fn cast(&mut self, world: &World, eye: Vec3, fwd: Vec3, right: Vec3, up: Vec3, off_x: f32, off_y: f32) {
        let dir = (fwd + right * off_x + up * off_y).normalize();
        if let Some(hit) = world.raycast(eye, dir, SONAR_RANGE) {
            let color = color_for(hit.surface, hit.tag);
            let jitter = vec3(
                gen_range(-0.035f32, 0.035),
                gen_range(-0.035f32, 0.035),
                gen_range(-0.035f32, 0.035),
            );
            self.push(hit.pos + jitter, color);
            // Structure tag：再添 2 个散布点（3× 总量）便于辨识"非地形"
            if hit.tag == HitTag::Structure {
                for _ in 0..2 {
                    let extra = vec3(
                        gen_range(-0.12f32, 0.12),
                        gen_range(-0.12f32, 0.12),
                        gen_range(-0.12f32, 0.12),
                    );
                    self.push(hit.pos + extra, color);
                }
            }
        }
    }

    fn push(&mut self, pos: Vec3, color: Color) {
        let idx = if self.points.len() < SONAR_MAX_POINTS {
            self.points.push(Point { pos, color });
            self.points.len() - 1
        } else {
            let i = self.head;
            self.points[i] = Point { pos, color };
            i
        };
        self.head = (self.head + 1) % SONAR_MAX_POINTS;
        self.new_this_frame.push(idx);
    }
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
            out.push(Point { pos: p + jitter, color: color_for(surface, HitTag::Normal) });
        }
    }
    out
}

fn color_for(surface: Surface, tag: HitTag) -> Color {
    // Danger tag 覆盖一切 surface 色——锁红（带点橙调以匹配青白点的感知亮度）。
    // 纯红 (0.95, 0.18, 0.22) 实测在 sonar 暗底里亮度感只有青白点的 60%；
    // 抬 G/B 把感知亮度拉回同档，保留 danger 红味。beam 线随点色也红。
    if tag == HitTag::Danger {
        return Color::new(jitter10(1.00), jitter10(0.42), jitter10(0.32), 1.0);
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
