//! Sonar firing logic, energy consumption, ray sampling, and persistent point cloud storage.

use crate::app::config::{
    CONTINUOUS_ENERGY_PER_SECOND, CONTINUOUS_HOLD_THRESHOLD, CONTINUOUS_RAYS_PER_SECOND,
    CONTINUOUS_SPREAD_DEGREES, ENERGY_MAX, PULSE_COOLDOWN, PULSE_COST, PULSE_RAYS,
    PULSE_SPREAD_DEGREES, SONAR_BUFFER_CAPACITY, SONAR_RANGE,
};
use crate::world::geometry::{Hit, SurfaceKind, World};
use macroquad::prelude::*;
use macroquad::rand::gen_range;

const GOLDEN_ANGLE: f32 = 2.399_963_1;

#[derive(Clone, Copy)]
pub struct SonarPoint {
    pub position: Vec3,
    pub color: Color,
    pub surface_kind: SurfaceKind,
}

#[derive(Clone, Copy, Default)]
pub struct FireVisualState {
    pub firing: bool,
    pub muzzle_flash: f32,
}

pub struct SonarSystem {
    points: Vec<SonarPoint>,
    write_head: usize,
    live_count: usize,
    frame_new_points: Vec<usize>,
    energy: f32,
    cooldown: f32,
    continuous_accumulator: f32,
    held_time: f32,
    hold_consumed_pulse: bool,
    muzzle_flash: f32,
}

impl SonarSystem {
    pub fn new() -> Self {
        let seed_point = SonarPoint {
            position: Vec3::ZERO,
            color: BLACK,
            surface_kind: SurfaceKind::Wall,
        };

        Self {
            points: vec![seed_point; SONAR_BUFFER_CAPACITY],
            write_head: 0,
            live_count: 0,
            frame_new_points: Vec::new(),
            energy: ENERGY_MAX,
            cooldown: 0.0,
            continuous_accumulator: 0.0,
            held_time: 0.0,
            hold_consumed_pulse: false,
            muzzle_flash: 0.0,
        }
    }

    pub fn update(
        &mut self,
        dt: f32,
        world: &World,
        origin: Vec3,
        forward: Vec3,
    ) -> FireVisualState {
        self.frame_new_points.clear();
        self.cooldown = (self.cooldown - dt).max(0.0);
        self.muzzle_flash = (self.muzzle_flash - dt * 5.0).max(0.0);

        let up = Vec3::Y;
        let right = forward.cross(up).normalize_or_zero();
        let corrected_up = right.cross(forward).normalize_or_zero();

        let pressed = is_mouse_button_pressed(MouseButton::Left);
        let down = is_mouse_button_down(MouseButton::Left);
        let released = is_mouse_button_released(MouseButton::Left);

        if pressed {
            self.held_time = 0.0;
            self.hold_consumed_pulse = false;
        }

        let mut firing = false;

        if down {
            self.held_time += dt;
            if self.held_time >= CONTINUOUS_HOLD_THRESHOLD
                && self.fire_continuous(dt, world, origin, forward, corrected_up, right)
            {
                firing = true;
            }
        }

        if released {
            if self.held_time < CONTINUOUS_HOLD_THRESHOLD && !self.hold_consumed_pulse {
                firing = self.try_fire_pulse(world, origin, forward, corrected_up, right) || firing;
            }
            self.held_time = 0.0;
            self.hold_consumed_pulse = false;
        }

        FireVisualState {
            firing,
            muzzle_flash: self.muzzle_flash,
        }
    }

    pub fn energy_ratio(&self) -> f32 {
        self.energy / ENERGY_MAX
    }

    pub fn points(&self) -> &[SonarPoint] {
        &self.points
    }

    pub fn iter_points(&self) -> impl Iterator<Item = &SonarPoint> {
        let start = if self.live_count == SONAR_BUFFER_CAPACITY {
            self.write_head
        } else {
            0
        };

        (0..self.live_count).map(move |i| &self.points[(start + i) % SONAR_BUFFER_CAPACITY])
    }

    pub fn frame_new_points(&self) -> impl Iterator<Item = &SonarPoint> {
        self.frame_new_points
            .iter()
            .map(move |&index| &self.points[index])
    }

    fn try_fire_pulse(
        &mut self,
        world: &World,
        origin: Vec3,
        forward: Vec3,
        up: Vec3,
        right: Vec3,
    ) -> bool {
        if self.cooldown > 0.0 || self.energy < PULSE_COST {
            return false;
        }

        self.energy -= PULSE_COST;
        self.cooldown = PULSE_COOLDOWN;
        self.muzzle_flash = 1.0;
        self.emit_fibonacci_cone(world, origin, forward, up, right, PULSE_RAYS, PULSE_SPREAD_DEGREES);
        true
    }

    fn fire_continuous(
        &mut self,
        dt: f32,
        world: &World,
        origin: Vec3,
        forward: Vec3,
        up: Vec3,
        right: Vec3,
    ) -> bool {
        let drain = CONTINUOUS_ENERGY_PER_SECOND * dt;
        if self.energy <= 0.0 || self.energy < drain {
            return false;
        }

        self.energy -= drain;
        self.continuous_accumulator += CONTINUOUS_RAYS_PER_SECOND * dt;
        let ray_count = self.continuous_accumulator.floor() as usize;
        self.continuous_accumulator -= ray_count as f32;

        if ray_count == 0 {
            self.muzzle_flash = self.muzzle_flash.max(0.45);
            return true;
        }

        self.muzzle_flash = 1.0;
        let spread = CONTINUOUS_SPREAD_DEGREES.to_radians();
        for _ in 0..ray_count {
            let theta = gen_range(0.0, std::f32::consts::TAU);
            let radius = gen_range(0.0, 1.0f32).sqrt() * spread;
            let offset_x = theta.cos() * radius;
            let offset_y = theta.sin() * radius;
            let dir = (forward + right * offset_x + up * offset_y).normalize();
            self.cast_and_scatter(world, origin, dir);
        }

        true
    }

    fn emit_fibonacci_cone(
        &mut self,
        world: &World,
        origin: Vec3,
        forward: Vec3,
        up: Vec3,
        right: Vec3,
        ray_count: usize,
        spread_degrees: f32,
    ) {
        let spread = spread_degrees.to_radians();
        for index in 0..ray_count {
            let t = index as f32 / ray_count as f32;
            let angle = index as f32 * GOLDEN_ANGLE;
            let radius = spread * t.sqrt();
            let offset_x = angle.cos() * radius;
            let offset_y = angle.sin() * radius;
            let dir = (forward + right * offset_x + up * offset_y).normalize();
            self.cast_and_scatter(world, origin, dir);
        }
    }

    fn cast_and_scatter(&mut self, world: &World, origin: Vec3, dir: Vec3) {
        if let Some(hit) = world.raycast(origin, dir, SONAR_RANGE) {
            self.spawn_hit_cluster(hit);
        }
    }

    fn spawn_hit_cluster(&mut self, hit: Hit) {
        let tangent_seed = if hit.normal.y.abs() > 0.8 { Vec3::X } else { Vec3::Y };
        let tangent = hit.normal.cross(tangent_seed).normalize_or_zero();
        let bitangent = hit.normal.cross(tangent).normalize_or_zero();

        self.push_point(
            hit.pos
                + tangent * gen_range(-0.04f32, 0.04f32)
                + bitangent * gen_range(-0.04f32, 0.04f32),
            hit.surface_kind,
        );

        if hit.surface_kind == SurfaceKind::Wall {
            if gen_range(0.0f32, 1.0f32) < 0.7 {
                self.push_point(
                    vec3(
                        hit.pos.x + gen_range(-0.16f32, 0.16f32),
                        0.03,
                        hit.pos.z + gen_range(-0.16f32, 0.16f32),
                    ),
                    SurfaceKind::Floor,
                );
            }

            if gen_range(0.0f32, 1.0f32) < 0.55 {
                self.push_point(
                    vec3(
                        hit.pos.x + gen_range(-0.16f32, 0.16f32),
                        2.97,
                        hit.pos.z + gen_range(-0.16f32, 0.16f32),
                    ),
                    SurfaceKind::Ceiling,
                );
            }
        }

        let extra_count = match hit.surface_kind {
            SurfaceKind::Wall => 4,
            SurfaceKind::Floor | SurfaceKind::Ceiling => 3,
        };
        for _ in 0..extra_count {
            let jitter =
                tangent * gen_range(-0.08f32, 0.08f32) + bitangent * gen_range(-0.08f32, 0.08f32);
            self.push_point(hit.pos + jitter, hit.surface_kind);
        }
    }

    fn push_point(&mut self, position: Vec3, surface_kind: SurfaceKind) {
        let color = match surface_kind {
            SurfaceKind::Wall => Color::new(
                0.05,
                gen_range(0.72f32, 1.0f32),
                gen_range(0.7f32, 0.95f32),
                1.0,
            ),
            SurfaceKind::Floor => Color::new(
                0.0,
                gen_range(0.68f32, 0.96f32),
                gen_range(0.48f32, 0.72f32),
                1.0,
            ),
            SurfaceKind::Ceiling => Color::new(
                gen_range(0.14f32, 0.28f32),
                gen_range(0.7f32, 0.9f32),
                1.0,
                1.0,
            ),
        };

        let index = self.write_head;
        self.points[index] = SonarPoint {
            position,
            color,
            surface_kind,
        };
        self.frame_new_points.push(index);
        self.write_head = (self.write_head + 1) % SONAR_BUFFER_CAPACITY;
        self.live_count = (self.live_count + 1).min(SONAR_BUFFER_CAPACITY);
    }
}
