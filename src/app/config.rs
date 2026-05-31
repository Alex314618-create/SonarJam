//! 全局配置与可调参数（手感调参集中于此）。

use macroquad::prelude::{Color, Conf};

pub const CLEAR_COLOR: Color = Color::new(0.01, 0.01, 0.02, 1.0);

// --- 玩家 ---
pub const PLAYER_HEIGHT: f32 = 2.0;
/// Earth 模式眼高：玩家身体落在 R_ 真山表面后，眼睛距地面的高度。
/// 0.85 ≈ 半个真人，匍匐前进/小人感觉。
pub const EARTH_EYE_HEIGHT: f32 = 0.85;
/// 玩家可步行斜率上限（dy/dx_水平）。0.70 ≈ tan(35°)，超过 = 悬崖，水平移动被拒。
pub const MAX_WALK_SLOPE: f32 = 0.70;
/// Y 向地面 lerp 速率（1/秒）。12.0 ≈ 80ms 半衰期；缓坡丝滑，无传送感。
pub const Y_LERP_RATE: f32 = 12.0;
pub const PLAYER_RADIUS: f32 = 0.3;
pub const WALK_SPEED: f32 = 5.0;
pub const SPRINT_MULTIPLIER: f32 = 1.8; // 按住 Shift 跑步速度倍率（→ 9 m/s）
pub const LOOK_SENSITIVITY: f32 = 0.0025;
pub const MAX_PITCH: f32 = 1.5;

// --- 头部摆动（headbob）---
// 移动时眼睛 y 做正弦摆动；幅度按当前是否在跑/走/静止平滑过渡。
pub const WALK_BOB_FREQ: f32 = 9.0; // 走路摆动角速度（rad/s）
pub const WALK_BOB_AMP: f32 = 0.035; // 走路摆动半幅（m）
pub const SPRINT_BOB_FREQ: f32 = 13.0;
pub const SPRINT_BOB_AMP: f32 = 0.06;
pub const BOB_AMP_LERP: f32 = 9.0; // 幅度平滑速率（值越大反应越快）

// --- 相机 FOV ---
pub const WALK_FOV_DEG: f32 = 60.0;
pub const SPRINT_FOV_DEG: f32 = 65.0; // 跑步轻微拉远，营造速度感
pub const FOV_LERP: f32 = 6.0;

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
pub const SONAR_MAX_POINTS: usize = 1_120_000; // 翻倍（PA 要求） // 持久点云环形缓冲容量（含 crashed 静态云 + 多轮残留）
/// 出生点登陆仓预探明区静态采样点数（占 SONAR_MAX_POINTS 约 37%，留出 60% 给玩家发射）
pub const CRASHED_CLOUD_POINTS: usize = 150_000;
pub const PULSE_RAYS: usize = 864;
// 圆形发射范围缩小 30%（32.64 → 22.85）
pub const PULSE_SPREAD_DEG: f32 = 22.85;
pub const PULSE_COST: f32 = 6.0;
// --- 右键绿激光（解离 BT 用）---
pub const GREEN_COST_PER_SEC: f32 = 1.2;
pub const GREEN_RAYS_PER_SEC: f32 = 3000.0;
pub const GREEN_SPREAD_DEG: f32 = 6.0;
pub const GREEN_RANGE: f32 = 50.0;
// 发射速度提升 40%（cooldown ÷ 1.4：0.12 → 0.086）
pub const PULSE_COOLDOWN: f32 = 0.086;
// 连续扫描发射率提升 40%（2016 → 2822）
pub const CONTINUOUS_RAYS_PER_SEC: f32 = 2822.0;
pub const CONTINUOUS_SPREAD_DEG: f32 = 22.85;
pub const CONTINUOUS_COST_PER_SEC: f32 = 1.5;
pub const ENERGY_MAX: f32 = 100.0;
// 完全松开鼠标时才回充（spike 可玩性用，正式平衡待定）
pub const ENERGY_REGEN_PER_SEC: f32 = 30.0;

// --- 点云渲染 ---
// 点云走 miniquad GL_POINTS 底层管线：屏幕固定像素大小的方点 + 真实深度遮挡。
// gl_PointSize 直接控制点的屏幕像素边长（需 GL_PROGRAM_POINT_SIZE，渲染器启动时开启）。
pub const POINT_PIXEL_SIZE: f32 = 1.68;
// 点沿“指向相机”方向的偏移量，避免点与墙面 z-fighting（世界单位）。
pub const POINT_DEPTH_BIAS: f32 = 0.02;
// 每帧枪口细线采样上限
pub const MAX_BEAM_LINES: usize = 12;

// --- Sonar Gun（右下手持枪 sprite + 激光起点）---
// 在 1920×1080 设计空间里：以右下角为锚，gun 图片宽度 + 偏移让它斜插进画面。
// 调这几个参数即可对齐"激光从枪口出"。
// --- Ship 模式（开场飞船舱）---
/// 走路速度倍率（相对 Earth 模式）。Ship 模式 = 真实人类舱内步速。
pub const SHIP_WALK_SPEED_MUL: f32 = 0.50;
/// Ship 模式眼睛距 spawn 地面的高度（相对参考；Earth 用 EARTH_EYE_HEIGHT）
pub const SHIP_EYE_HEIGHT: f32 = 0.9;
/// Ship spawn y 微调：在 AABB.min.y 之上抬高这么多再加 SHIP_EYE_HEIGHT，
/// 用于补偿 GLB 里地板不在 y=0 的情况（默认 0；PA 觉得人浮空就调正）。
pub const SHIP_FLOOR_Y_OFFSET: f32 = 0.0;
/// Ship 模式玩家碰撞半径（窄过道用；Earth 仍用 PLAYER_RADIUS=0.3）
pub const SHIP_PLAYER_RADIUS: f32 = 0.08;

// ===== 出生点强制覆盖（开发期 PA 拨数字，正式发布前可清回 None）=====
// 写 Some((x, y, z, yaw_deg)) → 完全无视 GLB 里的 M_spawn，强制用这组坐标和朝向。
// 写 None → 走 GLB M_spawn / floor_center 兜底。
pub const SHIP_SPAWN_OVERRIDE: Option<(f32, f32, f32, f32)> = Some((0.56, 0.98, 1.32, 259.3));
pub const EARTH_SPAWN_OVERRIDE: Option<(f32, f32, f32, f32)> = Some((82.26, 6.25, 69.6, 63.1));

/// 枪图设计宽度（设计像素，1920×1080 基准）
pub const GUN_DESIGN_W: f32 = 280.0;
/// 枪图相对右下角的偏移（设计像素，负数=向画内移；0=右下角贴角）
pub const GUN_ANCHOR_OFFSET_X: f32 = 0.0;
pub const GUN_ANCHOR_OFFSET_Y: f32 = 0.0;
/// 枪口（激光起点）在贴图里的归一化位置（0..1，0=左上）。需要按图调。
pub const GUN_MUZZLE_U: f32 = 0.18;
pub const GUN_MUZZLE_V: f32 = 0.22;

pub fn window_conf() -> Conf {
    Conf {
        window_title: "Sonar".to_owned(),
        // 全屏占满显示器；Scale 自动按实际分辨率把 design 1920×1080 映射上去。
        // 这是 borderless fullscreen——Alt-Tab、Esc 退出都正常工作。
        window_width: 1920,
        window_height: 1080,
        fullscreen: true,
        window_resizable: false,
        // 高 DPI 显示器下，screen_width 返回物理像素 → pixel-perfect TTF。
        high_dpi: true,
        ..Default::default()
    }
}
