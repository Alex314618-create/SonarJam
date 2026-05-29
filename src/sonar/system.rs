//! 感知结果层：声呐发射射线、命中生成持久点、能量管理。
//!
//! 只读消费 world 的 raycast，从不修改世界几何（保持感知层 / 几何层分离）。

use crate::app::config::{
    CONTINUOUS_COST_PER_SEC, CONTINUOUS_RAYS_PER_SEC, CONTINUOUS_SPREAD_DEG, ENERGY_MAX,
    ENERGY_REGEN_PER_SEC, PULSE_COOLDOWN, PULSE_COST, PULSE_RAYS, PULSE_SPREAD_DEG,
    SONAR_MAX_POINTS, SONAR_RANGE,
};
use crate::world::geometry::{Surface, World};
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
            let jitter = vec3(
                gen_range(-0.035f32, 0.035),
                gen_range(-0.035f32, 0.035),
                gen_range(-0.035f32, 0.035),
            );
            self.push(hit.pos + jitter, color_for(hit.surface));
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

fn color_for(surface: Surface) -> Color {
    match surface {
        Surface::Wall => Color::new(0.25, gen_range(0.75f32, 1.0), gen_range(0.85f32, 1.0), 1.0),
        Surface::Floor => Color::new(0.10, gen_range(0.70f32, 0.9), gen_range(0.55f32, 0.75), 1.0),
        Surface::Ceiling => Color::new(0.30, gen_range(0.60f32, 0.8), gen_range(0.90f32, 1.0), 1.0),
    }
}
