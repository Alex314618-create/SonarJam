//! 主运行时编排：输入 → 移动 → 声呐 → 渲染 → UI。

use crate::audio;
use crate::player::controller::Player;
use crate::render::renderer::Renderer;
use crate::ship;
use crate::sonar::system::{self, FireVisualState, Sonar};
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

/// 飞船开场场景 GLB
const SHIP_GLB: &str = "content/levels/ship_room/scene.glb";

// ===== Ship→Earth 转场参数 =====
const STRETCH_DUR: f32 = 0.65;  // POV 曲速折跃（FOV 扩到极限 + 画面放大冲出）
const BLACK_DUR: f32 = 0.22;    // 全黑过渡
const BOOT_DUR: f32 = 1.15;     // HUD 分段 CRT 启动（更快）

#[derive(Clone, Copy, PartialEq, Eq)]
enum TPhase { Idle, Stretching, BlackHold, HudBoot }

struct Transition {
    phase: TPhase,
    t: f32,
}

impl Transition {
    fn new() -> Self { Self { phase: TPhase::Idle, t: 0.0 } }
    fn start(&mut self) {
        if matches!(self.phase, TPhase::Idle) {
            self.phase = TPhase::Stretching;
            self.t = 0.0;
        }
    }
    fn stretch_t(&self) -> Option<f32> {
        if matches!(self.phase, TPhase::Stretching) {
            Some((self.t / STRETCH_DUR).clamp(0.0, 1.0))
        } else { None }
    }
    fn in_black(&self) -> bool { matches!(self.phase, TPhase::BlackHold) }
    fn hud_boot_t(&self) -> f32 {
        match self.phase {
            TPhase::HudBoot => (self.t / BOOT_DUR).clamp(0.0, 1.0),
            TPhase::Idle => 1.0,
            _ => 0.0,
        }
    }
}

/// 缓动：指数 in（2^(10t-10)），前 70% 几乎不动、末段火箭。
/// 用于曲速折跃的视觉冲击：缓慢蓄势 → 暴裂收尾。
fn ease_in_expo(t: f32) -> f32 {
    if t <= 0.0 { 0.0 }
    else if t >= 1.0 { 1.0 }
    else { (2.0f32).powf(10.0 * t - 10.0) }
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    /// 开场飞船舱：第一人称走动 + 实景渲染（带纹理/灯/emissive）。无声呐 HUD。
    Ship,
    /// 声呐黑暗世界：第一人称 + 点云感知 + HUD 满血。
    Earth,
}

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
    mode: Mode,
    /// 飞船舱 World：仅取 C_ 碰撞 + spawn 标记。视觉走 ship_scene。
    ship_world: World,
    /// 飞船舱视觉 batches（base + emissive overlay）
    ship_scene: Option<ship::Scene>,
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

    /// Ship→Earth 转场状态机
    transition: Transition,

    /// DEV 模式开关（T 切换）：自由飞行 + 真实贴图渲染，断声呐/碰撞/贴山
    dev_mode: bool,
    /// DEV 模式下 Earth 用的"真实"渲染（含贴图，从 Earth GLB 加载 R_ 网格）
    dev_earth_scene: Option<ship::Scene>,

    time: f32, // 累计时间（动画用）
}

impl GameApp {
    pub async fn new() -> Self {
        // 加载飞船舱（碰撞 + 视觉）
        let ship_world = World::load(SHIP_GLB);
        let ship_scene = ship::Scene::load(SHIP_GLB);
        // 启动时加载全部 GLB；缺失文件由 World::load 自动回退到代码盒子房间。
        let worlds: Vec<World> = PHASE_WORLD_PATHS.iter().map(|p| World::load(p)).collect();
        let current_idx = 0;
        let phase = 1;
        // 默认从 Ship 模式开局；如果 ship 加载失败则直接进 Earth
        let mode = if ship_scene.is_some() { Mode::Ship } else { Mode::Earth };
        let spawn = match mode {
            Mode::Ship => {
                if let Some(s) = ship_scene.as_ref() {
                    let c = s.floor_center();
                    let floor_y = c.y + crate::app::config::SHIP_FLOOR_Y_OFFSET;
                    vec3(c.x, floor_y + crate::app::config::SHIP_EYE_HEIGHT, c.z)
                } else {
                    ship_world.spawn()
                }
            }
            Mode::Earth => worlds[current_idx].spawn(),
        };
        let mut player = Player::new(spawn);
        // 注入 M_spawn 的朝向（仅 Earth；Ship 没 M_spawn 时 spawn_yaw=0 不影响）
        if mode == Mode::Earth {
            player.set_yaw(worlds[current_idx].spawn_yaw());
        }
        // 出生点登陆仓预探明云：只 Earth 模式开局需要灌（Ship 模式 enter_earth 时也会灌）
        let mut sonar = Sonar::new();
        if mode == Mode::Earth {
            seed_crashed_cloud(&mut sonar, &worlds[current_idx]);
        }
        Self {
            mode,
            ship_world,
            ship_scene,
            worlds,
            current_idx,
            phase,
            player,
            sonar,
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
            transition: Transition::new(),
            dev_mode: false,
            dev_earth_scene: ship::Scene::load(PHASE_WORLD_PATHS[0]),
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
        audio::play("system_notification");
    }

    /// 推入一条 COMMS 短句。新条目插入栈顶（最新），多余的从尾部淡出。
    pub fn push_comm(&mut self, who: impl Into<String>, msg: impl Into<String>) {
        self.comms.insert(0, CommsLine {
            who: who.into(),
            msg: msg.into(),
            age: 0.0,
        });
        if self.comms.len() > 4 {
            self.comms.truncate(4);
        }
        audio::play("comm_blip");
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

    /// 切到 Earth：重置玩家到 Earth 起点、重置声呐能量、重传 depth buffer。
    /// 不推 comm——由转场完成时统一推。
    fn enter_earth_silent(&mut self) {
        self.mode = Mode::Earth;
        self.current_idx = 0;
        self.phase = 1;
        self.sonar = Sonar::new();
        seed_crashed_cloud(&mut self.sonar, &self.worlds[self.current_idx]);
        self.renderer.reload_world();
        let spawn = self.worlds[self.current_idx].spawn();
        self.player.respawn(spawn);
        self.player.set_yaw(self.worlds[self.current_idx].spawn_yaw());
        // 进 Earth 时立刻贴山，避免第一帧腾空 / 钻地
        let pos = self.player.position();
        if let Some(gy) = self.worlds[self.current_idx].ground_y_at(pos.x, pos.z) {
            self.player.set_y(gy + crate::app::config::EARTH_EYE_HEIGHT);
        }
        println!("[game] Ship → Earth：进入声呐世界（phase 1）");
    }

    /// 推进一轮：染银当前点云、phase+1（5→1 循环）、若需切图则切、玩家 respawn。
    fn advance_phase(&mut self) {
        audio::play("rebirth");
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
        self.player.set_yaw(self.worlds[self.current_idx].spawn_yaw());

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

            // T：DEV 模式切换。开发时看真山样貌、自由飞、断 sonar/碰撞/贴山。
            if is_key_pressed(KeyCode::T) {
                self.dev_mode = !self.dev_mode;
                println!(
                    "[game] DEV mode = {}（{}）",
                    self.dev_mode,
                    if self.dev_mode {
                        "WASD 视线方向, Space 升 Ctrl 降, Shift 加速"
                    } else {
                        "回到正常游戏"
                    }
                );
                // 退出 dev 前提下若回 Earth，立刻贴山，避免悬空
                if !self.dev_mode && self.mode == Mode::Earth {
                    let pos = self.player.position();
                    if let Some(gy) = self.worlds[self.current_idx].ground_y_at(pos.x, pos.z) {
                        self.player.set_y(gy + crate::app::config::EARTH_EYE_HEIGHT);
                    }
                }
            }

            // ===== DEV 模式渲染分支：跳过所有正常逻辑 =====
            if self.dev_mode {
                self.player.update_fly(dt, true);
                clear_background(Color::new(0.04, 0.07, 0.12, 1.0)); // 深夜空
                let cam = self.player.camera();
                set_camera(&cam);
                // Earth 用 dev_earth_scene；Ship 用 ship_scene
                match self.mode {
                    Mode::Earth => {
                        if let Some(s) = self.dev_earth_scene.as_ref() {
                            ship::render(s);
                        }
                    }
                    Mode::Ship => {
                        if let Some(s) = self.ship_scene.as_ref() {
                            ship::render(s);
                        }
                    }
                }
                set_default_camera();
                draw_dev_hud(&self.player, self.mode);
                self.time += dt;
                next_frame().await;
                continue;
            }

            // 模式相关输入（转场进行中禁用 F/N）
            let in_transition = !matches!(self.transition.phase, TPhase::Idle);
            match self.mode {
                Mode::Ship => {
                    if !in_transition && is_key_pressed(KeyCode::F) {
                        self.transition.start();
                        audio::play("warp_charge");
                    }
                }
                Mode::Earth => {
                    // N：进入下一轮——当前点云固化为银色"过去"，玩家回到起点重走（可能切图）。
                    if !in_transition && is_key_pressed(KeyCode::N) {
                        self.advance_phase();
                    }
                }
            }

            // 转场状态机推进
            self.transition.t += dt;
            match self.transition.phase {
                TPhase::Stretching if self.transition.t >= STRETCH_DUR => {
                    // 拉伸结束 → 黑屏一瞬，并在此切到 Earth
                    self.enter_earth_silent();
                    self.transition.phase = TPhase::BlackHold;
                    self.transition.t = 0.0;
                }
                TPhase::BlackHold if self.transition.t >= BLACK_DUR => {
                    self.transition.phase = TPhase::HudBoot;
                    self.transition.t = 0.0;
                }
                TPhase::HudBoot if self.transition.t >= BOOT_DUR => {
                    self.transition.phase = TPhase::Idle;
                    self.transition.t = 0.0;
                    audio::play("prompt_tone");
                    self.push_comm("ANCHOR", "\"...signal lock. you're in.\"");
                }
                _ => {}
            }

            // Per-mode 更新 + 渲染
            let fire_state: FireVisualState = match self.mode {
                Mode::Ship => {
                    // 转场拉伸阶段：保持玩家位置不变；FOV 扩到极限鱼眼。
                    if !in_transition {
                        self.player.update(
                            dt,
                            &self.ship_world,
                            true,
                            crate::app::config::SHIP_WALK_SPEED_MUL,
                            crate::app::config::SHIP_PLAYER_RADIUS,
                        );
                    }
                    // 飞船舱独立渲染（macroquad 标准 3D + draw_mesh），不走点云黑暗管线。
                    clear_background(Color::new(0.020, 0.025, 0.035, 1.0));
                    let mut cam = self.player.camera();
                    if let Some(st) = self.transition.stretch_t() {
                        let max_fovy: f32 = 175.0_f32.to_radians();
                        cam.fovy = cam.fovy + (max_fovy - cam.fovy) * ease_in_expo(st);
                    }
                    set_camera(&cam);
                    if let Some(scene) = self.ship_scene.as_ref() {
                        ship::render(scene);
                    }
                    set_default_camera();
                    // 末段加速黑屏（最后 18%）
                    if let Some(st) = self.transition.stretch_t() {
                        let blackout = ((st - 0.82) / 0.18).max(0.0).powi(2);
                        if blackout > 0.0 {
                            draw_rectangle(0.0, 0.0, screen_width(), screen_height(),
                                Color::new(0.0, 0.0, 0.0, blackout));
                        }
                    }
                    FireVisualState::default()
                }
                Mode::Earth => {
                    if self.transition.in_black() {
                        // 全黑：跳过 Earth 渲染
                        clear_background(BLACK);
                        FireVisualState::default()
                    } else {
                        use crate::app::config::{EARTH_EYE_HEIGHT, MAX_WALK_SLOPE, Y_LERP_RATE, PLAYER_RADIUS};
                        let world = &self.worlds[self.current_idx];
                        // 记录本帧水平移动前的位置，用来在陡崖处撤销
                        let p_before = self.player.position();
                        // Earth 走 / 跑速度倍率 0.5（PA 要求小人感觉）
                        self.player.update(dt, world, true, 0.5, PLAYER_RADIUS);
                        let p_after = self.player.position();
                        let gy_before = world.ground_y_at(p_before.x, p_before.z);
                        let gy_after = world.ground_y_at(p_after.x, p_after.z);
                        let target_y = match (gy_before, gy_after) {
                            (Some(gb), Some(ga)) => {
                                let dx_h = ((p_after.x - p_before.x).powi(2)
                                    + (p_after.z - p_before.z).powi(2)).sqrt();
                                let slope = if dx_h > 1e-4 { (ga - gb) / dx_h } else { 0.0 };
                                if slope > MAX_WALK_SLOPE {
                                    // 陡崖：撤销 XZ，y 维持原地面
                                    self.player.set_xz(p_before.x, p_before.z);
                                    gb + EARTH_EYE_HEIGHT
                                } else {
                                    ga + EARTH_EYE_HEIGHT
                                }
                            }
                            (Some(gb), None) => gb + EARTH_EYE_HEIGHT,
                            (None, Some(ga)) => ga + EARTH_EYE_HEIGHT,
                            (None, None) => self.player.position().y,
                        };
                        // Y 向 target lerp，去掉传送感
                        let cur_y = self.player.position().y;
                        let k = (Y_LERP_RATE * dt).min(1.0);
                        self.player.set_y(cur_y + (target_y - cur_y) * k);

                        let fs = self.sonar
                            .update(dt, world, self.player.eye(), self.player.forward());
                        self.renderer
                            .render(&self.player.camera(), &self.sonar, world);
                        fs
                    }
                }
            };

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
            // 脚步循环：Earth 模式走/跑触发，停下立停。Ship 模式不响。
            let want_steps = self.mode == Mode::Earth && (walking || sprinting);
            if want_steps {
                audio::loop_start("steps");
            } else {
                audio::loop_stop("steps");
            }
            // 心跳：Earth 模式 + 能量 < 25% → loop
            let want_heartbeat = self.mode == Mode::Earth && energy_ratio < 0.25;
            if want_heartbeat {
                audio::loop_start("heartbeat");
            } else {
                audio::loop_stop("heartbeat");
            }
            // 随机恐怖 stinger：Earth 模式开 / Ship 关
            audio::set_stingers_active(self.mode == Mode::Earth);
            // 每帧推进 ducking + stinger 调度
            audio::update(dt);

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
                in_ship: self.mode == Mode::Ship,
                hud_boot_t: self.transition.hud_boot_t(),
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

/// 把 world 里 R_*crashed* 几何按面积均匀采样成密集点云，灌进 sonar。
fn seed_crashed_cloud(sonar: &mut Sonar, world: &World) {
    let tris = world.crashed_triangles();
    if tris.is_empty() {
        println!("[game/earth] 当前地图无 R_*crashed* 几何，跳过预探明云");
        return;
    }
    let cloud = system::sample_static_cloud(tris, crate::app::config::CRASHED_CLOUD_POINTS);
    println!(
        "[game/earth] crashed 预探明云：{} 三角形 → {} 采样点",
        tris.len(),
        cloud.len()
    );
    sonar.seed_static(&cloud);
}

/// DEV 模式简易 HUD：大字号坐标 + 模式/朝向/控制提示。
fn draw_dev_hud(player: &Player, mode: Mode) {
    let pos = player.position();
    let yaw = player.forward_yaw_deg();
    let mode_label = match mode {
        Mode::Ship => "Ship",
        Mode::Earth => "Earth",
    };
    let header = format!("[DEV MODE]   mode: {}   yaw {:.0}°   fps {:.0}",
        mode_label, yaw, 1.0 / get_frame_time().max(1e-4));
    let coord = format!("X {:>+8.2}    Y {:>+8.2}    Z {:>+8.2}", pos.x, pos.y, pos.z);
    let hint = "WASD 视线方向移动   Space 升   LeftCtrl 降   Shift 加速   T 退出";

    let bg = Color::new(0.0, 0.0, 0.0, 0.60);
    let fg_dim = Color::new(0.75, 0.85, 0.95, 0.85);
    let fg_coord = Color::new(0.62, 1.0, 0.85, 1.0); // 鲜青绿，突出
    let fg_hint = Color::new(0.70, 0.80, 0.88, 0.75);

    draw_rectangle(8.0, 12.0, 760.0, 110.0, bg);
    draw_text(&header, 18.0, 36.0, 20.0, fg_dim);
    draw_text(&coord,  18.0, 78.0, 36.0, fg_coord);
    draw_text(hint,    18.0, 110.0, 18.0, fg_hint);
}

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
