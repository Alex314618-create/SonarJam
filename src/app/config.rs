//! 全局配置与可调参数（手感调参集中于此）。

use macroquad::prelude::{Color, Conf};

pub const CLEAR_COLOR: Color = Color::new(0.01, 0.01, 0.02, 1.0);

// --- 玩家 ---
pub const PLAYER_HEIGHT: f32 = 2.0;
pub const PLAYER_RADIUS: f32 = 0.3;
pub const MOVE_SPEED: f32 = 4.0;
pub const LOOK_SENSITIVITY: f32 = 0.0025;
pub const MAX_PITCH: f32 = 1.5;

// --- 房间：四面墙距离各不相同（玩家 spawn 在原点）---
// 左墙 x=-3、右墙 x=+8、后墙 z=-2、前墙 z=+12 → 四面距离 3 / 8 / 2 / 12。
pub const ROOM_MIN_X: f32 = -3.0;
pub const ROOM_MAX_X: f32 = 8.0;
pub const ROOM_MIN_Z: f32 = -2.0;
pub const ROOM_MAX_Z: f32 = 12.0;
pub const ROOM_FLOOR_Y: f32 = 0.0;
pub const ROOM_CEILING_Y: f32 = 3.0;

// --- 声呐 ---
pub const SONAR_RANGE: f32 = 40.0;
pub const SONAR_MAX_POINTS: usize = 200_000; // 持久点云环形缓冲容量（含多轮残留）
pub const PULSE_RAYS: usize = 864;
pub const PULSE_SPREAD_DEG: f32 = 32.64;
pub const PULSE_COST: f32 = 6.0;
pub const PULSE_COOLDOWN: f32 = 0.12;
pub const CONTINUOUS_RAYS_PER_SEC: f32 = 2016.0;
pub const CONTINUOUS_SPREAD_DEG: f32 = 32.64;
pub const CONTINUOUS_COST_PER_SEC: f32 = 1.5;
pub const ENERGY_MAX: f32 = 100.0;
// 完全松开鼠标时才回充（spike 可玩性用，正式平衡待定）
pub const ENERGY_REGEN_PER_SEC: f32 = 30.0;

// --- 点云渲染 ---
// 点云走 miniquad GL_POINTS 底层管线：屏幕固定像素大小的方点 + 真实深度遮挡。
// gl_PointSize 直接控制点的屏幕像素边长（需 GL_PROGRAM_POINT_SIZE，渲染器启动时开启）。
pub const POINT_PIXEL_SIZE: f32 = 1.4;
// 点沿“指向相机”方向的偏移量，避免点与墙面 z-fighting（世界单位）。
pub const POINT_DEPTH_BIAS: f32 = 0.02;
// 每帧枪口细线采样上限
pub const MAX_BEAM_LINES: usize = 12;

pub fn window_conf() -> Conf {
    Conf {
        window_title: "Sonar".to_owned(),
        window_width: 1280,
        window_height: 720,
        window_resizable: false,
        ..Default::default()
    }
}
