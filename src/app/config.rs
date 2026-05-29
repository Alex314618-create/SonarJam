//! Shared app configuration and tuning values used across modules.

use macroquad::prelude::{vec2, Color, Conf, Vec2};

pub const CLEAR_COLOR: Color = Color::new(0.008, 0.008, 0.02, 1.0);
pub const PLAYER_HEIGHT: f32 = 1.6;
pub const PLAYER_RADIUS: f32 = 0.24;
pub const MOVE_SPEED: f32 = 4.25;
pub const LOOK_SENSITIVITY: f32 = 0.0022;
pub const MAX_PITCH: f32 = 1.52;
pub const SONAR_RANGE: f32 = 24.0;
pub const SONAR_BUFFER_CAPACITY: usize = 65_536;
pub const PULSE_RAYS: usize = 120;
pub const PULSE_SPREAD_DEGREES: f32 = 30.0;
pub const PULSE_COST: f32 = 16.0;
pub const PULSE_COOLDOWN: f32 = 0.32;
pub const CONTINUOUS_SPREAD_DEGREES: f32 = 30.0;
pub const CONTINUOUS_RAYS_PER_SECOND: f32 = 300.0;
pub const CONTINUOUS_ENERGY_PER_SECOND: f32 = 18.0;
pub const ENERGY_MAX: f32 = 100.0;
pub const POINT_NEAR_SIZE: f32 = 0.13;
pub const POINT_FAR_SIZE: f32 = 0.045;
pub const POINT_SIZE_NEAR_DISTANCE: f32 = 2.0;
pub const POINT_SIZE_FAR_DISTANCE: f32 = 22.0;
pub const MUZZLE_ANCHOR_OFFSET: Vec2 = vec2(-84.0, -94.0);
pub const CONTINUOUS_HOLD_THRESHOLD: f32 = 0.12;

pub fn window_conf() -> Conf {
    Conf {
        window_title: "Sonar Spike".to_owned(),
        window_width: 1280,
        window_height: 720,
        window_resizable: true,
        sample_count: 4,
        high_dpi: true,
        ..Default::default()
    }
}
