//! 第一人称控制器：鼠标看向 + WASD 移动 + Shift 跑步 + headbob + FOV 平滑。

use crate::app::config::{
    BOB_AMP_LERP, FOV_LERP, LOOK_SENSITIVITY, MAX_PITCH, SPRINT_BOB_AMP, SPRINT_BOB_FREQ,
    SPRINT_FOV_DEG, SPRINT_MULTIPLIER, WALK_BOB_AMP, WALK_BOB_FREQ, WALK_FOV_DEG, WALK_SPEED,
};
use crate::world::geometry::World;
use macroquad::prelude::*;

pub struct Player {
    pos: Vec3,
    yaw: f32,
    pitch: f32,
    last_mouse: Option<Vec2>,

    // --- headbob / FOV 状态 ---
    /// 连续累积的摆动相位；移动时 += freq * dt，永不归零（避免突变）。
    bob_phase: f32,
    /// 当前生效的摆动幅度，平滑 lerp 到目标（移动→amp、静止→0）。
    bob_amp: f32,
    /// 当前生效的 FOV（弧度），平滑 lerp 到走 / 跑目标。
    current_fov_rad: f32,
}

impl Player {
    pub fn new(spawn: Vec3) -> Self {
        Self {
            pos: spawn,
            yaw: 0.0,
            pitch: 0.0,
            last_mouse: None,
            bob_phase: 0.0,
            bob_amp: 0.0,
            current_fov_rad: WALK_FOV_DEG.to_radians(),
        }
    }

    pub fn update(&mut self, dt: f32, world: &World, capture_mouse: bool) {
        // --- 视角（鼠标）---
        let mouse = Vec2::from(mouse_position());
        if capture_mouse {
            let delta = mouse - self.last_mouse.unwrap_or(mouse);
            self.yaw += delta.x * LOOK_SENSITIVITY;
            self.pitch = (self.pitch - delta.y * LOOK_SENSITIVITY).clamp(-MAX_PITCH, MAX_PITCH);
        }
        self.last_mouse = Some(mouse);

        // --- 输入 ---
        let sprinting = is_key_down(KeyCode::LeftShift) || is_key_down(KeyCode::RightShift);

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

        let moving = motion.length_squared() > 1e-6;
        let speed = if sprinting {
            WALK_SPEED * SPRINT_MULTIPLIER
        } else {
            WALK_SPEED
        };
        let step = motion.normalize_or_zero() * speed * dt;
        self.pos = world.resolve_player_movement(self.pos, self.pos + step);

        // --- headbob：相位持续累积，幅度向目标平滑 ---
        let (target_amp, freq) = if moving {
            if sprinting {
                (SPRINT_BOB_AMP, SPRINT_BOB_FREQ)
            } else {
                (WALK_BOB_AMP, WALK_BOB_FREQ)
            }
        } else {
            (0.0, WALK_BOB_FREQ) // 静止时幅度归零，相位继续走但 amp=0 → 无可见摆动
        };
        self.bob_phase += freq * dt;
        self.bob_amp = lerp_f32(self.bob_amp, target_amp, BOB_AMP_LERP * dt);

        // --- FOV：跑步轻微拉远，平滑过渡 ---
        let target_fov = if sprinting {
            SPRINT_FOV_DEG.to_radians()
        } else {
            WALK_FOV_DEG.to_radians()
        };
        self.current_fov_rad = lerp_f32(self.current_fov_rad, target_fov, FOV_LERP * dt);
    }

    /// 眼睛位置 = 物理位置 + headbob 在 Y 上的偏移。
    pub fn eye(&self) -> Vec3 {
        let bob_y = self.bob_phase.sin() * self.bob_amp;
        self.pos + Vec3::Y * bob_y
    }

    /// 回到起点开始新一轮（朝向归零、bob/FOV 重置）。
    pub fn respawn(&mut self, spawn: Vec3) {
        self.pos = spawn;
        self.yaw = 0.0;
        self.pitch = 0.0;
        self.bob_phase = 0.0;
        self.bob_amp = 0.0;
        self.current_fov_rad = WALK_FOV_DEG.to_radians();
    }

    /// 物理位置（不含 headbob）。
    pub fn position(&self) -> Vec3 {
        self.pos
    }

    pub fn forward(&self) -> Vec3 {
        let cp = self.pitch.cos();
        vec3(self.yaw.cos() * cp, self.pitch.sin(), self.yaw.sin() * cp).normalize()
    }

    /// 当前朝向转为罗盘度数（0..360°，0=N）。
    pub fn forward_yaw_deg(&self) -> f32 {
        let d = self.yaw.to_degrees();
        ((d % 360.0) + 360.0) % 360.0
    }

    pub fn camera(&self) -> Camera3D {
        let eye = self.eye();
        Camera3D {
            position: eye,
            target: eye + self.forward(),
            up: Vec3::Y,
            fovy: self.current_fov_rad,
            aspect: Some(screen_width() / screen_height()),
            z_near: 0.1,
            z_far: 200.0,
            ..Default::default()
        }
    }
}

fn lerp_f32(a: f32, b: f32, t: f32) -> f32 {
    a + (b - a) * t.clamp(0.0, 1.0)
}
