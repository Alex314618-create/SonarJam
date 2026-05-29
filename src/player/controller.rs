//! First-person controller with yaw/pitch look, WASD movement, and collision-aware camera.

use crate::app::config::{LOOK_SENSITIVITY, MAX_PITCH, MOVE_SPEED, PLAYER_HEIGHT};
use crate::world::geometry::World;
use macroquad::prelude::*;

pub struct PlayerController {
    position: Vec3,
    yaw: f32,
    pitch: f32,
    last_mouse_position: Option<Vec2>,
}

impl PlayerController {
    pub fn new(spawn: Vec3) -> Self {
        Self {
            position: spawn,
            yaw: 0.0,
            pitch: 0.0,
            last_mouse_position: None,
        }
    }

    pub fn update(&mut self, dt: f32, world: &World, capture_mouse: bool) {
        let mouse_now = {
            let (x, y) = mouse_position();
            vec2(x, y)
        };

        if capture_mouse {
            let mouse_delta = mouse_now - self.last_mouse_position.unwrap_or(mouse_now);
            self.yaw += mouse_delta.x * LOOK_SENSITIVITY;
            self.pitch = (self.pitch - mouse_delta.y * LOOK_SENSITIVITY).clamp(-MAX_PITCH, MAX_PITCH);
        }
        self.last_mouse_position = Some(mouse_now);

        let forward = self.forward();
        let flat_forward = vec3(forward.x, 0.0, forward.z).normalize_or_zero();
        let right = Vec3::Y.cross(flat_forward).normalize_or_zero();

        let mut move_input = Vec3::ZERO;
        if is_key_down(KeyCode::W) {
            move_input += flat_forward;
        }
        if is_key_down(KeyCode::S) {
            move_input -= flat_forward;
        }
        if is_key_down(KeyCode::D) {
            move_input += right;
        }
        if is_key_down(KeyCode::A) {
            move_input -= right;
        }

        let desired = self.position
            + move_input.normalize_or_zero() * MOVE_SPEED * dt;
        self.position = world.resolve_player_movement(self.position, desired);
        self.position.y = PLAYER_HEIGHT;
    }

    pub fn eye_position(&self) -> Vec3 {
        self.position
    }

    pub fn forward(&self) -> Vec3 {
        let cp = self.pitch.cos();
        vec3(self.yaw.cos() * cp, self.pitch.sin(), self.yaw.sin() * cp).normalize()
    }

    pub fn right(&self) -> Vec3 {
        self.forward().cross(Vec3::Y).normalize_or_zero()
    }

    pub fn up(&self) -> Vec3 {
        self.right().cross(self.forward()).normalize_or_zero()
    }

    pub fn camera(&self) -> Camera3D {
        Camera3D {
            position: self.eye_position(),
            up: self.up(),
            target: self.eye_position() + self.forward(),
            fovy: 66.0f32.to_radians(),
            aspect: Some(screen_width() / screen_height()),
            ..Default::default()
        }
    }
}
