//! 第一人称控制器：鼠标看向 + WASD 移动 + 凸盒房间碰撞。

use crate::app::config::{LOOK_SENSITIVITY, MAX_PITCH, MOVE_SPEED};
use crate::world::geometry::World;
use macroquad::prelude::*;

pub struct Player {
    pos: Vec3,
    yaw: f32,
    pitch: f32,
    last_mouse: Option<Vec2>,
}

impl Player {
    pub fn new(spawn: Vec3) -> Self {
        Self {
            pos: spawn,
            yaw: 0.0,
            pitch: 0.0,
            last_mouse: None,
        }
    }

    pub fn update(&mut self, dt: f32, world: &World, capture_mouse: bool) {
        let mouse = Vec2::from(mouse_position());
        if capture_mouse {
            let delta = mouse - self.last_mouse.unwrap_or(mouse);
            self.yaw += delta.x * LOOK_SENSITIVITY;
            self.pitch = (self.pitch - delta.y * LOOK_SENSITIVITY).clamp(-MAX_PITCH, MAX_PITCH);
        }
        self.last_mouse = Some(mouse);

        let forward = self.forward();
        let flat = vec3(forward.x, 0.0, forward.z).normalize_or_zero();
        let right = flat.cross(Vec3::Y).normalize_or_zero();

        let mut motion = Vec3::ZERO;
        if is_key_down(KeyCode::W) {
            motion += flat;
        }
        if is_key_down(KeyCode::S) {
            motion -= flat;
        }
        if is_key_down(KeyCode::D) {
            motion += right;
        }
        if is_key_down(KeyCode::A) {
            motion -= right;
        }

        let step = motion.normalize_or_zero() * MOVE_SPEED * dt;
        self.pos = world.clamp_position(self.pos + step);
    }

    pub fn eye(&self) -> Vec3 {
        self.pos
    }

    /// 回到起点开始新一轮（朝向归零）。
    pub fn respawn(&mut self, spawn: Vec3) {
        self.pos = spawn;
        self.yaw = 0.0;
        self.pitch = 0.0;
    }

    pub fn forward(&self) -> Vec3 {
        let cp = self.pitch.cos();
        vec3(self.yaw.cos() * cp, self.pitch.sin(), self.yaw.sin() * cp).normalize()
    }

    pub fn camera(&self) -> Camera3D {
        Camera3D {
            position: self.pos,
            target: self.pos + self.forward(),
            up: Vec3::Y,
            fovy: 60.0f32.to_radians(),
            aspect: Some(screen_width() / screen_height()),
            ..Default::default()
        }
    }
}
