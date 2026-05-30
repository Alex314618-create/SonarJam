//! 主运行时编排：输入 → 移动 → 声呐 → 渲染 → UI。

use crate::player::controller::Player;
use crate::render::renderer::Renderer;
use crate::sonar::system::Sonar;
use crate::ui::system::{Bio, CommsLine, LogLine, Ui, UiContext, Vitals, Warning, WarningCard};
use crate::world::geometry::World;
use macroquad::prelude::*;

const WARNING_LIFE: f32 = 4.0;
const LOG_MAX_LINES: usize = 8;

// 罗盘弹簧物理参数（FPS 游戏速度比 HTML 设计稿磁罗盘快得多）
const COMPASS_SPRING_K: f32 = 22.0;     // 追目标的刚度（大→反应快）
const COMPASS_DAMPING: f32 = 4.8;       // 阻尼（小→过冲多）
const COMPASS_TORQUE_CAP: f32 = 60.0;   // delta 软限幅（大跳时给的初始加速度更猛）
const COMPASS_VEL_CAP: f32 = 1800.0;    // 速度上限（基本=不限）

/// 五轮 → 四张 GLB 映射（详见 docs/L2-03）：
/// 轮 1+2 共用 scene.glb，轮 3/4/5 各自 loop3/4/5.glb。
const PHASE_WORLD_PATHS: [&str; 4] = [
    "content/levels/earth_return_01/scene.glb",
    "content/levels/earth_return_01/scene_loop3.glb",
    "content/levels/earth_return_01/scene_loop4.glb",
    "content/levels/earth_return_01/scene_loop5.glb",
];

fn world_index_for_phase(phase: u32) -> usize {
    match phase {
        1 | 2 => 0,
        3 => 1,
        4 => 2,
        5 => 3,
        _ => 0,
    }
}

pub struct GameApp {
    worlds: Vec<World>,
    current_idx: usize,
    phase: u32,
    player: Player,
    sonar: Sonar,
    renderer: Renderer,
    ui: Ui,
    warnings: Vec<Warning>,
    system_log: Vec<LogLine>, // 最新条目在 [0]

    // HUD 状态（demo 占位值，未来由叙事/系统驱动）
    vitals: Vitals,
    bio: Bio,
    integrity_cell_pct: u32,
    comms: Vec<CommsLine>,
    warning_card: Option<WarningCard>,

    // 罗盘物理
    bearing_curr: f32, // 当前显示朝向（°）
    bearing_vel: f32,  // 角速度（°/s）

    // 玩家上一帧水平位置（算 DRIFT 用）
    last_player_xz: Option<Vec2>,
    /// 平滑后的水平速度（m/s），避免抖动
    drift_smooth: f32,

    time: f32, // 累计时间（动画用）
}

impl GameApp {
    pub async fn new() -> Self {
        // 启动时加载全部 GLB；缺失文件由 World::load 自动回退到代码盒子房间。
        let worlds: Vec<World> = PHASE_WORLD_PATHS.iter().map(|p| World::load(p)).collect();
        let current_idx = 0;
        let phase = 1;
        let player = Player::new(worlds[current_idx].spawn());
        Self {
            worlds,
            current_idx,
            phase,
            player,
            sonar: Sonar::new(),
            renderer: Renderer::new(),
            ui: Ui::new(),
            warnings: Vec::new(),
            system_log: Vec::new(),
            vitals: Vitals::default(),
            bio: Bio::default(),
            integrity_cell_pct: 42,
            comms: vec![
                CommsLine {
                    who: "ANCHOR".into(),
                    msg: "\"echo, your bio is spiking - slow down.\"".into(),
                    age: 99.0, // 初始几条直接稳定显示，不触发淡入
                },
                CommsLine {
                    who: "ECHO-3".into(),
                    msg: "\"...copy. lattice is humming in here.\"".into(),
                    age: 99.0,
                },
                CommsLine {
                    who: "ANCHOR".into(),
                    msg: "\"don't trust the optical. switch to acoustic.\"".into(),
                    age: 99.0,
                },
            ],
            warning_card: Some(WarningCard {
                tag: "CRITICAL . POWER".into(),
                msg: "EXTERNAL POWER LINK LOST.<br>SUIT NOW RUNNING ON INTERNAL CELL.".into(),
                sub: "EST. 11:48 REMAINING . LIFE SUPPORT WILL FAIL ON DEPLETION".into(),
            }),
            bearing_curr: 0.0,
            bearing_vel: 0.0,
            last_player_xz: None,
            drift_smooth: 0.0,
            time: 0.0,
        }
    }

    /// 罗盘弹簧物理一帧：朝目标朝向（玩家 yaw）柔和过冲、回摆。
    fn tick_compass(&mut self, dt: f32, target_deg: f32) {
        let delta = shortest_delta(self.bearing_curr, target_deg);
        let soft = delta.signum() * delta.abs().min(COMPASS_TORQUE_CAP);
        let tail = if delta.abs() > COMPASS_TORQUE_CAP {
            delta.signum() * (delta.abs() - COMPASS_TORQUE_CAP) * 0.4
        } else {
            0.0
        };
        let accel = COMPASS_SPRING_K * soft + tail - COMPASS_DAMPING * self.bearing_vel;
        self.bearing_vel = (self.bearing_vel + accel * dt).clamp(-COMPASS_VEL_CAP, COMPASS_VEL_CAP);
        self.bearing_curr += self.bearing_vel * dt;
    }

    /// 推入顶部红警告横幅，自动 TTL 衰减消失。
    #[allow(dead_code)] // 公共 API，叙事系统稍后会调用
    pub fn push_warning(&mut self, text: impl Into<String>) {
        self.warnings.push(Warning {
            text: text.into(),
            age: 0.0,
            life: WARNING_LIFE,
        });
    }

    /// 推入一条 COMMS 短句。新条目插入栈顶（最新），多余的从尾部淡出。
    pub fn push_comm(&mut self, who: impl Into<String>, msg: impl Into<String>) {
        self.comms.insert(0, CommsLine {
            who: who.into(),
            msg: msg.into(),
            age: 0.0,
        });
        // 允许 4 条同时存在（最后一条本帧 alpha≈0），下一帧由 tick 移除。
        if self.comms.len() > 4 {
            self.comms.truncate(4);
        }
    }

    /// 推入左下系统日志一条；最旧的会在超出 LOG_MAX_LINES 时被裁掉。
    #[allow(dead_code)] // 公共 API，叙事系统稍后会调用
    pub fn push_log(&mut self, text: impl Into<String>) {
        self.system_log.insert(
            0,
            LogLine {
                text: text.into(),
                age: 0.0,
            },
        );
        self.system_log.truncate(LOG_MAX_LINES);
    }

    fn tick_ui_state(&mut self, dt: f32) {
        for w in self.warnings.iter_mut() {
            w.age += dt;
        }
        self.warnings.retain(|w| w.age < w.life);
        for l in self.system_log.iter_mut() {
            l.age += dt;
        }
        for c in self.comms.iter_mut() {
            c.age += dt;
        }
        // 第 4 条（被挤出的）出现一帧后即移除——它在 UI 层 alpha≈0。
        if self.comms.len() > 3 {
            let extra_age = self.comms[3].age;
            if extra_age > 0.05 {
                self.comms.truncate(3);
            }
        }
    }

    /// 推进一轮：染银当前点云、phase+1（5→1 循环）、若需切图则切、玩家 respawn。
    fn advance_phase(&mut self) {
        self.sonar.advance_loop();
        self.phase = if self.phase >= 5 { 1 } else { self.phase + 1 };
        let new_idx = world_index_for_phase(self.phase);
        if new_idx != self.current_idx {
            self.current_idx = new_idx;
            self.renderer.reload_world();
            println!(
                "[game] phase {} → 切换至地图 {}",
                self.phase, PHASE_WORLD_PATHS[new_idx]
            );
        } else {
            println!("[game] phase {} → 沿用当前地图", self.phase);
        }
        let spawn = self.worlds[self.current_idx].spawn();
        self.player.respawn(spawn);

        // 进入新一轮的通讯回音（占位文案；正式叙事接入后替换）。
        let msg = match self.phase {
            2 => "\"again? echo, you just did this loop.\"",
            3 => "\"lattice is shifting. don't trust the walls.\"",
            4 => "\"you've been here too long.\"",
            5 => "\"...is anyone else seeing this?\"",
            _ => "\"reset. sample anchor confirms position.\"",
        };
        self.push_comm("ANCHOR", msg);
    }


    pub async fn run(&mut self) {
        loop {
            let dt = get_frame_time().min(1.0 / 20.0);

            // 每帧重新断言抓取：在 run() 开头一次性调用常因窗口尚未获得焦点而失效，
            // 逐帧断言可确保鼠标被稳定锁定、不跑出窗口。
            set_cursor_grab(true);
            show_mouse(false);
            // 双保险：macroquad/ClipCursor 在某些焦点切换中会被释放，故每帧再用
            // SetCursorPos 把物理光标钉到窗口客户区中心，无论如何都跑不出去。
            // grab 模式下 macroquad 走 raw input 累积，与 SetCursorPos 产生的
            // WM_MOUSEMOVE 是两条独立路径，转视角不受影响。
            pin_cursor_to_window_center();

            if is_key_pressed(KeyCode::Escape) {
                set_cursor_grab(false);
                show_mouse(true);
                break;
            }

            // N：进入下一轮——当前点云固化为银色"过去"，玩家回到起点重走（可能切图）。
            if is_key_pressed(KeyCode::N) {
                self.advance_phase();
            }

            let world = &self.worlds[self.current_idx];
            self.player.update(dt, world, true);
            let fire_state =
                self.sonar
                    .update(dt, world, self.player.eye(), self.player.forward());

            self.renderer
                .render(&self.player.camera(), &self.sonar, world);

            self.tick_ui_state(dt);

            // 罗盘目标朝向 = 玩家 yaw 转成 0..360°（约定：yaw=0 → N=0°）
            let yaw_deg = self.player.forward_yaw_deg();
            self.tick_compass(dt, yaw_deg);

            self.time += dt;

            // DRIFT = 玩家真实水平速度（m/s），按 dt 差分 + 一阶低通平滑。
            let pos = self.player.position();
            let xz = vec2(pos.x, pos.z);
            let instant = match self.last_player_xz {
                Some(prev) if dt > 1e-4 => (xz - prev).length() / dt,
                _ => 0.0,
            };
            self.last_player_xz = Some(xz);
            // 0.18 ≈ 时间常数 ~50ms，跑停瞬切清晰但去掉单帧噪声
            let alpha = (dt / 0.05).clamp(0.0, 1.0);
            self.drift_smooth = self.drift_smooth + (instant - self.drift_smooth) * alpha;
            let drift = self.drift_smooth;
            let energy_ratio = self.sonar.energy_ratio();
            let energy_segments = (energy_ratio * 5.0).ceil().clamp(0.0, 5.0) as u32;
            // CELL 联动声呐能量（电池条 = 当前能量百分比）。
            self.integrity_cell_pct = (energy_ratio * 100.0).round().clamp(0.0, 100.0) as u32;
            let sprinting = is_key_down(KeyCode::LeftShift) || is_key_down(KeyCode::RightShift);
            let walking = drift > 0.5 && !sprinting; // 走路阈值 0.5 m/s

            let ctx = UiContext {
                viewport: vec2(screen_width(), screen_height()),
                time: self.time,
                energy_segments,
                energy_ratio,
                phase: self.phase,
                fire_state,
                bearing_deg: self.bearing_curr,
                drift_mps: drift,
                vitals: &self.vitals,
                bio: &self.bio,
                integrity_cell_pct: self.integrity_cell_pct,
                comms: &self.comms,
                warning_card: self.warning_card.as_ref(),
                warnings: &self.warnings,
                system_log: &self.system_log,
                sprinting,
                walking,
            };
            self.ui.update(&ctx, dt);
            self.ui.draw(&ctx);

            next_frame().await;
        }
    }
}

/// 把光标物理钉到当前前台窗口客户区中心。直接调 user32，绕开 macroquad/ClipCursor
/// 在焦点切换中可能短暂失效的问题。失焦时窗口不在前台，这函数会作用到别的窗口
/// 中心——玩家失焦时反正也不操作游戏，可接受。
#[cfg(target_os = "windows")]
fn pin_cursor_to_window_center() {
    #[repr(C)]
    struct RECT {
        left: i32,
        top: i32,
        right: i32,
        bottom: i32,
    }
    #[repr(C)]
    struct POINT {
        x: i32,
        y: i32,
    }
    type HWND = *mut core::ffi::c_void;

    #[link(name = "user32")]
    extern "system" {
        fn GetForegroundWindow() -> HWND;
        fn GetClientRect(hwnd: HWND, rect: *mut RECT) -> i32;
        fn ClientToScreen(hwnd: HWND, point: *mut POINT) -> i32;
        fn SetCursorPos(x: i32, y: i32) -> i32;
    }

    unsafe {
        let hwnd = GetForegroundWindow();
        if hwnd.is_null() {
            return;
        }
        let mut rect = RECT {
            left: 0,
            top: 0,
            right: 0,
            bottom: 0,
        };
        if GetClientRect(hwnd, &mut rect) == 0 {
            return;
        }
        let mut pt = POINT {
            x: (rect.right - rect.left) / 2,
            y: (rect.bottom - rect.top) / 2,
        };
        if ClientToScreen(hwnd, &mut pt) == 0 {
            return;
        }
        SetCursorPos(pt.x, pt.y);
    }
}

#[cfg(not(target_os = "windows"))]
fn pin_cursor_to_window_center() {}

/// 取两个角度之间的最短旋转方向（±180°）。
fn shortest_delta(from: f32, to: f32) -> f32 {
    let mut d = (to - from) % 360.0;
    if d > 180.0 {
        d -= 360.0;
    }
    if d < -180.0 {
        d += 360.0;
    }
    d
}
