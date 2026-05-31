//! 主运行时编排：输入 → 移动 → 声呐 → 渲染 → UI。

use crate::audio;
use crate::bt::{self, BtSystem};
use crate::narrative::Narrative;
use crate::player::controller::Player;
use crate::render::renderer::Renderer;
use crate::ship;
use crate::sonar::system::{self, FireVisualState, Sonar};
use crate::ui::system::{Bio, CommsLine, LogLine, Ui, UiContext, Vitals, Warning, WarningCard};
use crate::world::geometry::World;
use macroquad::prelude::*;
use macroquad::text::{draw_text_ex, load_ttf_font_from_bytes, measure_text, Font, TextParams};
use std::sync::OnceLock;

/// UI 一致字体：DM Mono Regular。loop transition / 低电警告 / 坐标 HUD 都用它，
/// 不再走 macroquad 内置像素字体。
fn ui_font() -> &'static Font {
    static F: OnceLock<Font> = OnceLock::new();
    F.get_or_init(|| {
        load_ttf_font_from_bytes(include_bytes!("../../assets/fonts/DMMono-Regular.ttf"))
            .expect("DM Mono Regular 加载失败")
    })
}
fn ui_font_medium() -> &'static Font {
    static F: OnceLock<Font> = OnceLock::new();
    F.get_or_init(|| {
        load_ttf_font_from_bytes(include_bytes!("../../assets/fonts/DMMono-Medium.ttf"))
            .expect("DM Mono Medium 加载失败")
    })
}

const WARNING_LIFE: f32 = 4.0;
const LOG_MAX_LINES: usize = 8;

// 罗盘弹簧物理参数（FPS 游戏速度比 HTML 设计稿磁罗盘快得多）
const COMPASS_SPRING_K: f32 = 22.0; // 追目标的刚度（大→反应快）
const COMPASS_DAMPING: f32 = 4.8; // 阻尼（小→过冲多）
const COMPASS_TORQUE_CAP: f32 = 60.0; // delta 软限幅（大跳时给的初始加速度更猛）
const COMPASS_VEL_CAP: f32 = 1800.0; // 速度上限（基本=不限）

/// 飞船开场场景 GLB
const SHIP_GLB: &str = "content/levels/ship_room/scene.glb";

// ===== Ship→Earth 转场参数 =====
const STRETCH_DUR: f32 = 0.65; // POV 曲速折跃（FOV 扩到极限 + 画面放大冲出）
const BLACK_DUR: f32 = 0.22; // 全黑过渡
const BOOT_DUR: f32 = 1.15; // HUD 分段 CRT 启动（更快）

#[derive(Clone, Copy, PartialEq, Eq)]
enum TPhase {
    Idle,
    Stretching,
    BlackHold,
    HudBoot,
}

struct Transition {
    phase: TPhase,
    t: f32,
}

impl Transition {
    fn new() -> Self {
        Self {
            phase: TPhase::Idle,
            t: 0.0,
        }
    }
    fn start(&mut self) {
        if matches!(self.phase, TPhase::Idle) {
            self.phase = TPhase::Stretching;
            self.t = 0.0;
        }
    }
    fn stretch_t(&self) -> Option<f32> {
        if matches!(self.phase, TPhase::Stretching) {
            Some((self.t / STRETCH_DUR).clamp(0.0, 1.0))
        } else {
            None
        }
    }
    fn in_black(&self) -> bool {
        matches!(self.phase, TPhase::BlackHold)
    }
    fn hud_boot_t(&self) -> f32 {
        match self.phase {
            TPhase::HudBoot => (self.t / BOOT_DUR).clamp(0.0, 1.0),
            TPhase::Idle => 1.0,
            _ => 0.0,
        }
    }
}

// ===== 5→4→3→2→1 轮间转场参数（复用 Ship→Earth 的 FOV 曲速折跃风格）=====
const LT_WARN_DUR: f32 = 0.70; // 红警告布满视野
const LT_STRETCH_OUT_DUR: f32 = 0.75; // FOV 60°→178°，画面变暗
const LT_DARK_OLD_DUR: f32 = 0.50; // 全黑 + 旧数字
const LT_DARK_NEW_DUR: f32 = 0.60; // 旧数字交叉淡出 → 新数字淡入
const LT_STRETCH_IN_DUR: f32 = 0.75; // FOV 178°→60°，画面恢复
// world 切换在 StretchOut 末（DarkOld 起点）执行。

#[derive(Clone, Copy, PartialEq, Eq)]
enum LtPhase {
    Idle,
    WarnFlood,
    StretchOut,
    DarkOld,
    DarkNew,
    StretchIn,
}

struct LoopTransition {
    phase: LtPhase,
    t: f32,
    /// 显示用：旧 MD 段号 = 6 - engine_phase（进入 transition 时锁定）
    old_section: u32,
    new_section: u32,
    /// 警告气泡随机位置（U, V 屏占比，0..1）+ 触发延迟（秒）
    warnings: Vec<(f32, f32, f32)>,
    /// advance_phase 的实际世界切换是否已发生（在 ShowOld 开始时触发一次）
    switched: bool,
}

impl LoopTransition {
    fn new() -> Self {
        Self {
            phase: LtPhase::Idle,
            t: 0.0,
            old_section: 0,
            new_section: 0,
            warnings: Vec::new(),
            switched: false,
        }
    }
    fn active(&self) -> bool {
        !matches!(self.phase, LtPhase::Idle)
    }
    fn blocks_input(&self) -> bool {
        self.active()
    }
    /// FOV 拉伸系数 0..1（1=178°，0=正常）。在 StretchOut 上升，DarkOld/DarkNew 保持 1，StretchIn 回落。
    fn fov_warp(&self) -> f32 {
        match self.phase {
            LtPhase::StretchOut => ease_in_expo((self.t / LT_STRETCH_OUT_DUR).clamp(0.0, 1.0)),
            LtPhase::DarkOld | LtPhase::DarkNew => 1.0,
            LtPhase::StretchIn => {
                1.0 - ease_in_expo((self.t / LT_STRETCH_IN_DUR).clamp(0.0, 1.0))
            }
            _ => 0.0,
        }
    }
    /// 黑色覆盖 alpha 0..1。StretchOut 0→1，DarkOld/DarkNew 1，StretchIn 1→0。
    fn dark_alpha(&self) -> f32 {
        match self.phase {
            LtPhase::StretchOut => (self.t / LT_STRETCH_OUT_DUR).clamp(0.0, 1.0).powi(2),
            LtPhase::DarkOld | LtPhase::DarkNew => 1.0,
            LtPhase::StretchIn => (1.0 - self.t / LT_STRETCH_IN_DUR).clamp(0.0, 1.0).powi(2),
            _ => 0.0,
        }
    }
    /// 启动：传入当前 engine phase（advance 前）和下一 engine phase
    fn start(&mut self, from_engine: u32, to_engine: u32) {
        self.phase = LtPhase::WarnFlood;
        self.t = 0.0;
        self.old_section = 6u32.saturating_sub(from_engine.clamp(1, 5));
        self.new_section = 6u32.saturating_sub(to_engine.clamp(1, 5));
        self.switched = false;
        // 7 个红警告随机散布
        self.warnings.clear();
        let seed = (from_engine as f32 * 7.31).fract();
        for i in 0..7 {
            let u = ((i as f32 * 0.276 + seed) * 1.0).fract().clamp(0.06, 0.94);
            let v = ((i as f32 * 0.382 + seed * 1.3) * 1.0).fract().clamp(0.10, 0.86);
            let delay = i as f32 * 0.06;
            self.warnings.push((u, v, delay));
        }
    }
}

/// 缓动：指数 in（2^(10t-10)），前 70% 几乎不动、末段火箭。
/// 用于曲速折跃的视觉冲击：缓慢蓄势 → 暴裂收尾。
fn ease_in_expo(t: f32) -> f32 {
    if t <= 0.0 {
        0.0
    } else if t >= 1.0 {
        1.0
    } else {
        (2.0f32).powf(10.0 * t - 10.0)
    }
}

enum PendingHud {
    Warning(String),
    Comm(String, String),
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
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

// ===== Phase 3 树泄漏事件参数（L3-03）=====
const LEAK_TREE_TRIGGER_RADIUS: f32 = 8.0;
/// 红云显形到圆柱覆盖之间的时长。PA 验收反馈要"看清楚"，
/// 文档里写的 0.45s 太短，拉长到 3.5s 给玩家观察 + warning 读完。
const LEAK_TREE_REVEAL_DURATION: f32 = 3.5;
const LEAK_TREE_POINTS: usize = 5000;
const LEAK_TREE_MARKER: &str = "M_leak_tree_01";
const LEAK_TREE_MESH: &str = "R_leak_tree_01";
const LEAK_TREE_COVER: &str = "H_cover_tree_01";

#[derive(Clone, Copy)]
enum LeakTreeState {
    Idle,
    RedReveal { t: f32 },
    Covered,
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

    /// Phase 3 树泄漏事件状态机（L3-03）。
    leak_tree_state: LeakTreeState,

    /// 字幕/系统文本（L4 - Narrative）
    narrative: Narrative,

    /// 5→4→3→2→1 轮间转场状态机
    loop_transition: LoopTransition,

    /// 延迟入栈的 HUD 警告/通讯（MD 系统话从字幕剥离到这里走 banner / comms）
    pending_hud: std::collections::VecDeque<(f32, PendingHud)>,

    /// 低电警告节流计时（每 ~3s 推一次 banner，不会刷屏）
    low_energy_warn_t: f32,

    /// BT 系统 + 上身粒子模板
    bt_system: BtSystem,
    bt_upper_template: Vec<Vec3>,
    /// 是否已弹过"右键解离"首次教学提示
    bt_dissociation_hint_shown: bool,

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
        let mode = if ship_scene.is_some() {
            Mode::Ship
        } else {
            Mode::Earth
        };
        let (spawn, spawn_yaw) = compute_spawn(mode, &ship_world, ship_scene.as_ref(), &worlds[current_idx]);
        let mut player = Player::new(spawn);
        player.set_yaw(spawn_yaw);
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
                    who: "系统".into(),
                    msg: "意识同步完成".into(),
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
            leak_tree_state: LeakTreeState::Idle,
            narrative: {
                let mut n = Narrative::new();
                // Ship 模式开局立即排序章三连；Earth 直进模式由下面 enter_earth_silent 接管
                if mode == Mode::Ship {
                    n.queue_prologue();
                } else {
                    n.queue_phase_intro(1);
                }
                n
            },
            loop_transition: LoopTransition::new(),
            pending_hud: std::collections::VecDeque::new(),
            low_energy_warn_t: 0.0,
            bt_system: BtSystem::new(),
            bt_upper_template: bt::load_upper_template(
                "content/entities/bt_muddy_man.glb",
            ),
            bt_dissociation_hint_shown: false,
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

    /// 推入顶部红警告横幅 + 左下 COMMS（保证玩家能看到）。**不发声**——PA 反馈复活后滴滴嘟嘟太吵。
    pub fn push_warning(&mut self, text: impl Into<String>) {
        let s: String = text.into();
        self.warnings.push(Warning {
            text: s.clone(),
            age: 0.0,
            life: WARNING_LIFE,
        });
        self.comms.insert(
            0,
            CommsLine {
                who: "系统".into(),
                msg: s,
                age: 0.0,
            },
        );
        if self.comms.len() > 4 {
            self.comms.truncate(4);
        }
    }

    /// 推入一条 COMMS 短句。新条目插入栈顶（最新），多余的从尾部淡出。**不发声**。
    pub fn push_comm(&mut self, who: impl Into<String>, msg: impl Into<String>) {
        self.comms.insert(
            0,
            CommsLine {
                who: who.into(),
                msg: msg.into(),
                age: 0.0,
            },
        );
        if self.comms.len() > 4 {
            self.comms.truncate(4);
        }
    }

    /// 延迟入栈：delay 秒后 push_warning。
    fn enqueue_warning(&mut self, delay: f32, text: impl Into<String>) {
        self.pending_hud
            .push_back((delay, PendingHud::Warning(text.into())));
    }
    /// 延迟入栈：delay 秒后 push_comm。
    fn enqueue_comm(&mut self, delay: f32, who: impl Into<String>, msg: impl Into<String>) {
        self.pending_hud.push_back((
            delay,
            PendingHud::Comm(who.into(), msg.into()),
        ));
    }
    /// 每帧推进延迟队列：第一条 delay -= dt，归零则 fire。
    fn tick_pending_hud(&mut self, dt: f32) {
        if let Some((d, _)) = self.pending_hud.front_mut() {
            *d -= dt;
            if *d <= 0.0 {
                let (_, item) = self.pending_hud.pop_front().unwrap();
                match item {
                    PendingHud::Warning(t) => self.push_warning(t),
                    PendingHud::Comm(w, m) => self.push_comm(w, m),
                }
            }
        }
    }

    /// 进入某 phase 时把 MD 的系统话（方括号 / 协议）排到 HUD warning/comm 通道。
    fn queue_phase_system_hud(&mut self, phase: u32) {
        let section = 6u32.saturating_sub(phase.clamp(1, 5));
        match section {
            5 => {
                self.enqueue_warning(0.4, "外部供电已断 · 仅内部电池 · 不会自动回充");
                self.enqueue_comm(0.5, "套装", "\"生命维持仍在。电池在掉。\"");
                self.enqueue_warning(0.8, "声呐能量 100% · 省着用");
                self.enqueue_warning(1.4, "黄色信号 · 前人类残骸 · 潜在威胁");
                self.enqueue_comm(1.5, "套装", "\"黄色回响 = 古代遗迹。小心。\"");
                self.enqueue_warning(2.0, "前方未分类几何 · 潜在危险区");
            }
            4 => {
                self.enqueue_warning(0.5, "RED OUTLINE · FIRST CONTACT · 12m · APPROACHING");
                self.enqueue_comm(
                    0.6,
                    "SYS",
                    "\"silver afterimage detected. source: unknown.\"",
                );
                self.enqueue_warning(1.0, "ECHO RESIDUE · CLASSIFIED HARMLESS");
            }
            3 => {
                self.enqueue_warning(0.5, "RESIDUE LAYER · MULTIPLE TRAJECTORIES");
                self.enqueue_warning(
                    1.0,
                    "RED OUTLINE · SECOND CONTACT · 9m · TRAJECTORY MATCH PREV LOOP",
                );
                self.enqueue_comm(
                    1.0,
                    "SYS",
                    "\"hostile residue uncleared. threat level raised.\"",
                );
                self.enqueue_warning(1.4, "STRUCTURE DRIFT +12° · RECALIBRATION ADVISED");
                self.enqueue_comm(
                    1.4,
                    "SYS",
                    "\"cognitive map deviation. follow sonar.\"",
                );
                self.enqueue_warning(
                    1.8,
                    "RED OUTLINE PATH · 96% MATCH WITH PLAYER LAST 11s",
                );
            }
            2 => {
                self.enqueue_warning(0.5, "RED ENTITY APPROACHING · THREAT MEDIUM");
                self.enqueue_warning(
                    1.0,
                    "UNAUTHORIZED CONSCIOUSNESS · HIGHLY SIMILAR TO PLAYER",
                );
                self.enqueue_warning(1.4, "RED OUTLINE LOCKED · 7m · CLOSING");
                self.enqueue_comm(
                    1.4,
                    "SYS",
                    "\"perception request denied. quota will drop on retry.\"",
                );
                self.enqueue_warning(1.8, "ARCHIVE · TRAJECTORY 0247 TERMINATED");
            }
            1 => {
                self.enqueue_warning(0.5, "HISTORICAL TRAJECTORY DENSITY · ANOMALOUS");
                self.enqueue_warning(1.0, "RED OUTLINE · SIGNAL CORRUPTED · TRYING TO APPROACH");
                self.enqueue_warning(1.5, "DO NOT SYNC WITH RED OUTLINE · COGNITION HAZARD");
                self.enqueue_warning(2.0, "SCAN VS ARCHIVE · MISMATCH —");
                self.enqueue_warning(2.5, "CONSCIOUSNESS STATE ERROR · CORRECTING");
            }
            _ => {}
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

    /// 切到 Earth：重置玩家到 Earth 起点、重置声呐能量、重传 depth buffer。
    /// 不推 comm——由转场完成时统一推。
    fn enter_earth_silent(&mut self) {
        self.mode = Mode::Earth;
        self.current_idx = 0;
        self.phase = 1;
        self.sonar = Sonar::new();
        seed_crashed_cloud(&mut self.sonar, &self.worlds[self.current_idx]);
        self.renderer.reload_world();
        let (spawn, yaw) = compute_spawn(
            Mode::Earth,
            &self.ship_world,
            self.ship_scene.as_ref(),
            &self.worlds[self.current_idx],
        );
        self.player.respawn(spawn);
        self.player.set_yaw(yaw);
        // 字幕：进入 Earth 第一轮内心独白
        self.narrative.clear_all();
        self.narrative.queue_phase_intro(self.phase);
        // HUD：MD 系统话进 warning/comm 通道
        self.pending_hud.clear();
        self.queue_phase_system_hud(self.phase);
        self.respawn_bts_for_phase(self.phase);
        self.bt_dissociation_hint_shown = false;
        println!("[game] Ship → Earth：进入声呐世界（phase 1）");
    }

    /// 直接跳到指定 phase（开发用：按 3 进入树泄漏关）。
    /// 不染银点云、不灌登陆仓；清空 sonar + 重置事件状态 + 切图 + respawn。
    fn jump_to_phase(&mut self, phase: u32) {
        self.phase = phase.clamp(1, 5);
        let new_idx = world_index_for_phase(self.phase);
        if new_idx != self.current_idx {
            self.current_idx = new_idx;
            self.renderer.reload_world();
        }
        self.sonar = Sonar::new();
        let (spawn, yaw) = compute_spawn(
            Mode::Earth,
            &self.ship_world,
            self.ship_scene.as_ref(),
            &self.worlds[self.current_idx],
        );
        self.player.respawn(spawn);
        self.player.set_yaw(yaw);
        self.leak_tree_state = LeakTreeState::Idle;
        self.narrative.clear_all();
        self.narrative.queue_phase_intro(self.phase);
        self.pending_hud.clear();
        self.queue_phase_system_hud(self.phase);
        self.respawn_bts_for_phase(self.phase);
        self.bt_dissociation_hint_shown = false;
        let world = &self.worlds[self.current_idx];
        println!(
            "[game] JUMP → phase {} (地图 {}) spawn={:?} yaw={:.2}°",
            self.phase,
            PHASE_WORLD_PATHS[self.current_idx],
            spawn,
            world.spawn_yaw().to_degrees()
        );
        // 事件诊断：报告 phase 3 三件套的实际位置（PA 排查 spawn/cover 不对位时用）
        if self.phase == 3 {
            for n in [LEAK_TREE_MARKER, LEAK_TREE_COVER] {
                match world.marker_position(n) {
                    Some(p) => println!(
                        "[leak-tree] {} @ ({:.2}, {:.2}, {:.2})  距 spawn {:.2}m",
                        n,
                        p.x,
                        p.y,
                        p.z,
                        (spawn - p).length()
                    ),
                    None => println!("[leak-tree] {} 缺失", n),
                }
            }
            match world.leak_mesh_triangles(LEAK_TREE_MESH) {
                Some(tris) if !tris.is_empty() => {
                    let mut mn = tris[0][0];
                    let mut mx = mn;
                    for t in tris {
                        for v in t {
                            mn = mn.min(*v);
                            mx = mx.max(*v);
                        }
                    }
                    let c = (mn + mx) * 0.5;
                    println!(
                        "[leak-tree] {} {} 三角形 中心 ({:.2}, {:.2}, {:.2})  距 spawn {:.2}m",
                        LEAK_TREE_MESH,
                        tris.len(),
                        c.x,
                        c.y,
                        c.z,
                        (spawn - c).length()
                    );
                }
                _ => println!("[leak-tree] {} 缺失", LEAK_TREE_MESH),
            }
        }
    }

    /// Phase 3 树泄漏事件：靠近 marker → 红云显形 → 系统圆柱覆盖。
    /// 只在 phase==3 + Earth 模式生效；状态机由 advance_phase / jump_to_phase 重置。
    fn tick_phase3_tree_leak(&mut self, dt: f32) {
        if self.phase != 3 || self.mode != Mode::Earth {
            return;
        }
        match self.leak_tree_state {
            LeakTreeState::Idle => {
                let world = &self.worlds[self.current_idx];
                let Some(marker) = world.marker_position(LEAK_TREE_MARKER) else {
                    return;
                };
                let d = (self.player.position() - marker).length();
                if d > LEAK_TREE_TRIGGER_RADIUS {
                    return;
                }
                let Some(tris) = world.leak_mesh_triangles(LEAK_TREE_MESH) else {
                    println!(
                        "[leak-tree] marker {} 触发但找不到 {}，跳过事件",
                        LEAK_TREE_MARKER, LEAK_TREE_MESH
                    );
                    self.leak_tree_state = LeakTreeState::Covered;
                    return;
                };
                let tris: Vec<[Vec3; 3]> = tris.to_vec();
                let alert = Color::new(1.0, 0.12, 0.10, 1.0);
                let points =
                    crate::sonar::system::sample_leak_cloud(&tris, LEAK_TREE_POINTS, alert);
                self.sonar.seed_event_points(&points);
                self.push_warning("意识模式错误");
                self.push_comm("系统", "\"检测到视觉异象，正在修正。\"");
                self.leak_tree_state = LeakTreeState::RedReveal { t: 0.0 };
                println!(
                    "[leak-tree] 触发：距 {} = {:.2}m，{} 采样点已注入",
                    LEAK_TREE_MARKER,
                    d,
                    points.len()
                );
            }
            LeakTreeState::RedReveal { mut t } => {
                t += dt;
                if t >= LEAK_TREE_REVEAL_DURATION {
                    if self.worlds[self.current_idx].activate_hidden_mesh(LEAK_TREE_COVER) {
                        self.renderer.reload_world();
                        self.push_warning("未授权视觉轨迹已抑制");
                    } else {
                        println!(
                            "[leak-tree] 未找到 {}，覆盖跳过（红云保留）",
                            LEAK_TREE_COVER
                        );
                    }
                    self.leak_tree_state = LeakTreeState::Covered;
                } else {
                    self.leak_tree_state = LeakTreeState::RedReveal { t };
                }
            }
            LeakTreeState::Covered => {}
        }
    }

    /// 推进一轮：启动转场动画（红警告→闪→数字翻转），世界在转场中段才真正切。
    fn advance_phase(&mut self) {
        if self.loop_transition.active() {
            return; // 转场中再按 N 无效
        }
        audio::play("rebirth");
        // 劫后余生：吉他音乐随转场（在新一轮起始时奏起，奏完即停）
        audio::play("music_relief");
        // 威胁音乐先停掉（新 phase 里如果再扫到 BT 再开）
        audio::loop_stop("music_threat");
        let from = self.phase;
        let to = if from >= 5 { 1 } else { from + 1 };
        self.loop_transition.start(from, to);
        // 触发"电量耗尽"视觉感：警告布满期间逐张弹红警告（实际不动 energy）
        for (i, w) in self.loop_transition.warnings.clone().into_iter().enumerate() {
            let _ = w; // 警告位置在 draw 阶段读 self.loop_transition.warnings
            // 顶部红 banner 也叠一波（短寿命），让横向警告条同步爆出
            if i < 3 {
                let banner = match i {
                    0 => "记忆锚点丢失",
                    1 => "意识崩塌",
                    _ => "协议覆盖 · 重置中",
                };
                self.push_warning(banner);
            }
        }
    }

    /// 实际执行 phase 切换（转场动画推进到 ShowOld 时由 run() 调用）。
    fn actually_switch_phase(&mut self, to_phase: u32) {
        self.sonar.advance_loop();
        self.phase = to_phase;
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
        let (spawn, yaw) = compute_spawn(
            Mode::Earth,
            &self.ship_world,
            self.ship_scene.as_ref(),
            &self.worlds[self.current_idx],
        );
        self.player.respawn(spawn);
        self.player.set_yaw(yaw);
        self.leak_tree_state = LeakTreeState::Idle;
        // 字幕：清掉残留 → 排新 phase 的内心独白
        self.narrative.clear_all();
        self.narrative.queue_phase_intro(self.phase);
        // HUD：旧 pending 清掉，排新 phase 系统话
        self.pending_hud.clear();
        self.queue_phase_system_hud(self.phase);
        // BT：清掉旧的 + 按新 phase 重新 spawn
        self.respawn_bts_for_phase(self.phase);
        self.bt_dissociation_hint_shown = false;
    }

    /// 按 phase 重新生成 BT。phase 1 用 M_leak_phantom_0X 标记位置；
    /// 后续 phase 暂时不刷（PA 后续设计）。
    fn respawn_bts_for_phase(&mut self, phase: u32) {
        self.bt_system.clear();
        if phase == 1 {
            let world = &self.worlds[self.current_idx];
            let mut spawned = 0;
            for name in ["M_leak_phantom_01", "M_leak_phantom_02"] {
                if let Some(pos) = world.marker_position(name) {
                    // 让脚底贴 R_ 真山
                    let foot_y = world.ground_y_at(pos.x, pos.z).unwrap_or(pos.y);
                    let foot = vec3(pos.x, foot_y, pos.z);
                    self.bt_system.spawn(foot, &self.bt_upper_template);
                    spawned += 1;
                    println!("[bt] spawn {} @ ({:.1}, {:.1}, {:.1})", name, foot.x, foot.y, foot.z);
                }
            }
            println!("[bt] phase 1 共 spawn {} 只", spawned);
        }
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

            // 模式相关输入（Ship→Earth 转场或轮间转场进行中禁用 F/N/1..5）
            let in_transition = !matches!(self.transition.phase, TPhase::Idle)
                || self.loop_transition.active();
            match self.mode {
                Mode::Ship => {
                    // 空格跳过当前开幕卡（持续提示除外）
                    if is_key_pressed(KeyCode::Space) {
                        self.narrative.skip_current();
                    }
                    // F：只在开幕卡放完后触发 Ship→Earth 转场
                    if !in_transition
                        && !self.narrative.cards_active()
                        && is_key_pressed(KeyCode::F)
                    {
                        self.transition.start();
                        audio::play("warp_charge");
                        self.narrative.clear_persistent();
                    }
                }
                Mode::Earth => {
                    // N：进入下一轮——当前点云固化为银色"过去"，玩家回到起点重走（可能切图）。
                    if !in_transition && is_key_pressed(KeyCode::N) {
                        self.advance_phase();
                    }
                    // 1..=5：直接跳到对应 phase（开发热键；按 3 测试树泄漏事件）
                    if !in_transition {
                        if is_key_pressed(KeyCode::Key1) {
                            self.jump_to_phase(1);
                        } else if is_key_pressed(KeyCode::Key2) {
                            self.jump_to_phase(2);
                        } else if is_key_pressed(KeyCode::Key3) {
                            self.jump_to_phase(3);
                        } else if is_key_pressed(KeyCode::Key4) {
                            self.jump_to_phase(4);
                        } else if is_key_pressed(KeyCode::Key5) {
                            self.jump_to_phase(5);
                        }
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
                    self.push_comm("系统", "信号锁定 · 你接入了");
                }
                _ => {}
            }

            // ===== 5→4→3→2→1 轮间转场推进 =====
            if self.loop_transition.active() {
                self.loop_transition.t += dt;
                match self.loop_transition.phase {
                    LtPhase::WarnFlood if self.loop_transition.t >= LT_WARN_DUR => {
                        self.loop_transition.phase = LtPhase::StretchOut;
                        self.loop_transition.t = 0.0;
                    }
                    LtPhase::StretchOut if self.loop_transition.t >= LT_STRETCH_OUT_DUR => {
                        // FOV 已拉到 178°、屏幕全黑——这里切 phase（玩家看不到突变）
                        if !self.loop_transition.switched {
                            let to = if self.phase >= 5 { 1 } else { self.phase + 1 };
                            self.actually_switch_phase(to);
                            self.loop_transition.switched = true;
                        }
                        self.loop_transition.phase = LtPhase::DarkOld;
                        self.loop_transition.t = 0.0;
                    }
                    LtPhase::DarkOld if self.loop_transition.t >= LT_DARK_OLD_DUR => {
                        self.loop_transition.phase = LtPhase::DarkNew;
                        self.loop_transition.t = 0.0;
                    }
                    LtPhase::DarkNew if self.loop_transition.t >= LT_DARK_NEW_DUR => {
                        self.loop_transition.phase = LtPhase::StretchIn;
                        self.loop_transition.t = 0.0;
                    }
                    LtPhase::StretchIn if self.loop_transition.t >= LT_STRETCH_IN_DUR => {
                        self.loop_transition.phase = LtPhase::Idle;
                        self.loop_transition.t = 0.0;
                    }
                    _ => {}
                }
            }

            // Per-mode 更新 + 渲染
            let fire_state: FireVisualState = match self.mode {
                Mode::Ship => {
                    // 开幕卡片序列期间冻结输入与渲染——画面就是黑底卡片
                    let in_opening = self.narrative.cards_active();
                    if !in_transition && !in_opening {
                        self.player.update(
                            dt,
                            &self.ship_world,
                            true,
                            crate::app::config::SHIP_WALK_SPEED_MUL,
                            crate::app::config::SHIP_PLAYER_RADIUS,
                        );
                    }
                    if in_opening {
                        // 完全黑屏，让 narrative.draw() 负责画卡片
                        clear_background(BLACK);
                    } else {
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
                    }
                    // 末段加速黑屏（最后 18%）
                    if let Some(st) = self.transition.stretch_t() {
                        let blackout = ((st - 0.82) / 0.18).max(0.0).powi(2);
                        if blackout > 0.0 {
                            draw_rectangle(
                                0.0,
                                0.0,
                                screen_width(),
                                screen_height(),
                                Color::new(0.0, 0.0, 0.0, blackout),
                            );
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
                        use crate::app::config::{
                            EARTH_EYE_HEIGHT, MAX_WALK_SLOPE, PLAYER_RADIUS, Y_LERP_RATE,
                        };
                        // 记录本帧水平移动前的位置，用来在陡崖处撤销
                        let p_before = self.player.position();
                        // Earth 走 / 跑速度倍率 0.5（PA 要求小人感觉）
                        {
                            let world = &self.worlds[self.current_idx];
                            self.player.update(dt, world, true, 0.5, PLAYER_RADIUS);
                        }
                        let p_after = self.player.position();
                        let (gy_before, gy_after) = {
                            let world = &self.worlds[self.current_idx];
                            (
                                world.ground_y_at(p_before.x, p_before.z),
                                world.ground_y_at(p_after.x, p_after.z),
                            )
                        };
                        let target_y = match (gy_before, gy_after) {
                            (Some(gb), Some(ga)) => {
                                let dx_h = ((p_after.x - p_before.x).powi(2)
                                    + (p_after.z - p_before.z).powi(2))
                                .sqrt();
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

                        // L3-03：phase 3 树泄漏事件（在 sonar 更新前注入红云）
                        self.tick_phase3_tree_leak(dt);

                        let world = &self.worlds[self.current_idx];
                        let fs =
                            self.sonar
                                .update(dt, world, self.player.eye(), self.player.forward(), self.dev_mode, &mut self.bt_system);

                        let player_pos = self.player.position();
                        let (dead_ids, auto_snap_indices) =
                            self.bt_system.tick(dt, player_pos, world);
                        if !dead_ids.is_empty() {
                            self.sonar.clear_silhouettes_for(&dead_ids);
                        }
                        // BT 自主留痕：不依赖玩家扫描，每秒一发自动喷身影到 sonar
                        for idx in auto_snap_indices {
                            if let Some(b) = self.bt_system.bts.get(idx) {
                                self.sonar
                                    .inject_bt_silhouette(b.id, b.pos, &b.body_particles);
                            }
                        }
                        let touched = self.bt_system.check_contact(player_pos);

                        // 轮间转场：FOV 拉伸应用到 Earth 渲染相机
                        let mut cam = self.player.camera();
                        let fov_t = self.loop_transition.fov_warp();
                        if fov_t > 0.001 {
                            let max_fovy: f32 = 178.0_f32.to_radians();
                            cam.fovy = cam.fovy + (max_fovy - cam.fovy) * fov_t;
                        }
                        self.renderer.render(&cam, &self.sonar, world);

                        // BT 死亡蒸发粒子（仅濒死阶段红粒子飘升）+ 绿激光 beam
                        draw_bt_death_particles(&self.bt_system, &cam);
                        draw_green_beams(&self.sonar, &cam);

                        // BT 第一次被扫到 → 系统弹窗 + 威胁压迫音乐
                        if self.sonar.just_scanned_bt_first_time && !self.bt_dissociation_hint_shown {
                            self.bt_dissociation_hint_shown = true;
                            self.narrative.popup_override(
                                "系统提示：检测到威胁！\n长按右键解离威胁！\n不要暴露自己！",
                                6.5,
                            );
                            self.push_warning("检测到红色信号 · 长按右键解离威胁");
                            // 管风琴压迫感音乐：BT 一旦被发现就响起
                            audio::play("music_threat");
                        }

                        // 死亡条件：能量耗尽 OR 被 BT 触碰
                        let drained = self.sonar.energy_ratio() <= 0.001;
                        if (drained || touched) && !self.loop_transition.active() {
                            let cause = if touched {
                                "被红色信号触碰"
                            } else {
                                "电量耗尽"
                            };
                            self.push_warning(format!("{} · 记忆崩塌", cause));
                            self.advance_phase();
                        }
                        fs
                    }
                }
            };

            self.tick_ui_state(dt);
            self.tick_pending_hud(dt);
            // 字幕：推进队列 + 监测能量阈值（Earth 模式才看能量；Ship 模式不消耗）
            self.narrative.tick(dt);
            if self.mode == Mode::Earth {
                self.narrative.check_energy(self.sonar.energy_ratio());
            }

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
            // 随机恐怖 stinger 暂时全关 —— PA 说"刚到 Earth 的音乐"碍事
            audio::set_stingers_active(false);
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
            // 临时调试 HUD（坐标 + yaw）：左上小字，方便 PA 排查 spawn / marker 位置
            draw_coord_hud(&self.player);
            // 低电量红色视野闪烁（< 30% Earth 模式）+ 周期警告
            if self.mode == Mode::Earth
                && energy_ratio < 0.30
                && !matches!(self.transition.phase, TPhase::BlackHold)
                && !self.loop_transition.active()
            {
                draw_low_energy_vignette(energy_ratio, self.time);
                self.low_energy_warn_t += dt;
                if self.low_energy_warn_t >= 3.5 {
                    self.low_energy_warn_t = 0.0;
                    let pct = (energy_ratio * 100.0).round() as i32;
                    self.push_warning(format!("电量危急 · {}% · 寻找补给", pct));
                }
            } else {
                self.low_energy_warn_t = 0.0;
            }
            // 字幕在 HUD 之上：BlackHold / 轮间转场黑屏期不画
            let suppress_subtitle = matches!(self.transition.phase, TPhase::BlackHold)
                || matches!(
                    self.loop_transition.phase,
                    LtPhase::DarkOld | LtPhase::DarkNew
                );
            if !suppress_subtitle {
                self.narrative
                    .draw(vec2(screen_width(), screen_height()));
            }
            // 轮间转场覆盖层（红警告→白闪→黑+数字→淡出）
            if self.loop_transition.active() {
                draw_loop_transition(&self.loop_transition);
            }

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
    let header = format!(
        "[DEV MODE]   mode: {}   yaw {:.0}°   fps {:.0}",
        mode_label,
        yaw,
        1.0 / get_frame_time().max(1e-4)
    );
    let coord = format!(
        "X {:>+8.2}    Y {:>+8.2}    Z {:>+8.2}",
        pos.x, pos.y, pos.z
    );
    let hint = "WASD 视线方向移动   Space 升   LeftCtrl 降   Shift 加速   T 退出";

    let bg = Color::new(0.0, 0.0, 0.0, 0.60);
    let fg_dim = Color::new(0.75, 0.85, 0.95, 0.85);
    let fg_coord = Color::new(0.62, 1.0, 0.85, 1.0); // 鲜青绿，突出
    let fg_hint = Color::new(0.70, 0.80, 0.88, 0.75);

    draw_rectangle(8.0, 12.0, 760.0, 110.0, bg);
    draw_text(&header, 18.0, 36.0, 20.0, fg_dim);
    draw_text(&coord, 18.0, 78.0, 36.0, fg_coord);
    draw_text(hint, 18.0, 110.0, 18.0, fg_hint);
}

/// 统一的 spawn 计算 —— 优先 config 覆盖，否则 GLB M_spawn / floor_center 兜底。
/// Earth 模式额外做 robust ground-snap：M_spawn 哪怕摆在地形孔洞里，玩家也落实地。
fn compute_spawn(
    mode: Mode,
    ship_world: &World,
    ship_scene: Option<&ship::Scene>,
    earth_world: &World,
) -> (Vec3, f32) {
    use crate::app::config::{
        EARTH_EYE_HEIGHT, EARTH_SPAWN_OVERRIDE, SHIP_EYE_HEIGHT, SHIP_FLOOR_Y_OFFSET,
        SHIP_SPAWN_OVERRIDE,
    };
    let (mut spawn, mut yaw, source);
    match mode {
        Mode::Ship => {
            if let Some((x, y, z, yd)) = SHIP_SPAWN_OVERRIDE {
                spawn = vec3(x, y, z);
                yaw = yd.to_radians();
                source = "OVERRIDE";
            } else {
                let ms = ship_world.spawn();
                let yaw_g = ship_world.spawn_yaw();
                if ms.length_squared() > 0.01 {
                    spawn = vec3(ms.x, ms.y + SHIP_EYE_HEIGHT, ms.z);
                    yaw = yaw_g;
                    source = "M_spawn_main";
                } else if let Some(s) = ship_scene {
                    let c = s.floor_center();
                    let floor_y = c.y + SHIP_FLOOR_Y_OFFSET;
                    spawn = vec3(c.x, floor_y + SHIP_EYE_HEIGHT, c.z);
                    yaw = yaw_g; // 通常 0
                    source = "floor_center (M_spawn_main 在原点)";
                } else {
                    spawn = vec3(ms.x, ms.y + SHIP_EYE_HEIGHT, ms.z);
                    yaw = yaw_g;
                    source = "fallback origin";
                }
            }
        }
        Mode::Earth => {
            if let Some((x, y, z, yd)) = EARTH_SPAWN_OVERRIDE {
                spawn = vec3(x, y, z);
                yaw = yd.to_radians();
                source = "OVERRIDE";
            } else {
                let m = earth_world.spawn();
                let yaw_g = earth_world.spawn_yaw();
                // robust ground snap：M_spawn.y 可能高高悬在空中，强行贴山
                let snap_y = earth_world
                    .ground_y_at_robust(m.x, m.z)
                    .map(|gy| gy + EARTH_EYE_HEIGHT);
                if let Some(sy) = snap_y {
                    spawn = vec3(m.x, sy, m.z);
                    source = "M_spawn + ground_snap";
                } else {
                    spawn = vec3(m.x, m.y, m.z);
                    source = "M_spawn (无地形可贴!)";
                }
                yaw = yaw_g;
            }
        }
    }
    println!(
        "[spawn] {:?} via {} → ({:.2}, {:.2}, {:.2}) yaw {:.1}°",
        mode,
        source,
        spawn.x,
        spawn.y,
        spawn.z,
        yaw.to_degrees()
    );
    (spawn, yaw)
}

/// 5→4 轮间转场覆盖层渲染（FOV 曲速折跃风格，复用 Ship→Earth 视感）。
/// FOV 拉伸由 game.rs 在 Earth 渲染时应用（draw_loop_transition 只画顶层效果）：
///   - WarnFlood：散布红警告气泡（在被拉伸的世界视图上方）
///   - StretchOut：黑色覆盖 alpha 0→1（已被 FOV 拉伸的世界从可见变全黑）
///   - DarkOld：全黑 + "5"（保持稳定，玩家眼里一沉一震）
///   - DarkNew：全黑 + "5" 交叉淡出到 "4"
///   - StretchIn：黑色覆盖 alpha 1→0（新世界从黑里浮出，FOV 从 178° 回拉）
fn draw_loop_transition(lt: &LoopTransition) {
    let w = screen_width();
    let h = screen_height();

    // === WarnFlood：散布红警告气泡 ===
    if matches!(lt.phase, LtPhase::WarnFlood) {
        let t_norm = lt.t / LT_WARN_DUR;
        for (i, (u, v, delay)) in lt.warnings.iter().enumerate() {
            let local_t = (lt.t - delay).max(0.0);
            if local_t <= 0.0 {
                continue;
            }
            let alpha = (local_t / 0.18).clamp(0.0, 1.0);
            let cx = u * w;
            let cy = v * h;
            let bw = w * 0.22;
            let bh = h * 0.052;
            draw_rectangle(
                cx - bw * 0.5,
                cy - bh * 0.5,
                bw,
                bh,
                Color::new(0.6, 0.04, 0.04, 0.78 * alpha),
            );
            let bord = Color::new(1.0, 0.18, 0.18, 0.95 * alpha);
            draw_rectangle(cx - bw * 0.5, cy - bh * 0.5, bw, 2.0, bord);
            draw_rectangle(cx - bw * 0.5, cy + bh * 0.5 - 2.0, bw, 2.0, bord);
            draw_rectangle(cx - bw * 0.5, cy - bh * 0.5, 2.0, bh, bord);
            draw_rectangle(cx + bw * 0.5 - 2.0, cy - bh * 0.5, 2.0, bh, bord);
            let labels = [
                "电量危急", "锚点丢失", "协议覆盖", "记忆崩塌",
                "意识漂移", "信号丢失", "系统重置",
            ];
            let label = labels[i % labels.len()];
            let font = ui_font_medium();
            let fs = (h * 0.022) as u16;
            let dim = measure_text(label, Some(font), fs, 1.0);
            draw_text_ex(
                label,
                (cx - dim.width * 0.5).round(),
                (cy + fs as f32 * 0.35).round(),
                TextParams {
                    font: Some(font),
                    font_size: fs,
                    font_scale: 1.0,
                    color: Color::new(1.0, 0.96, 0.96, alpha),
                    ..Default::default()
                },
            );
        }
        let v_alpha = (t_norm * 0.55).min(0.55);
        draw_rectangle(0.0, 0.0, w, h * 0.08, Color::new(0.8, 0.05, 0.05, v_alpha));
        draw_rectangle(0.0, h * 0.92, w, h * 0.08, Color::new(0.8, 0.05, 0.05, v_alpha));
        return;
    }

    // === StretchOut / DarkOld / DarkNew / StretchIn：黑色覆盖（alpha 由 dark_alpha 控制） ===
    let dark_a = lt.dark_alpha();
    if dark_a > 0.001 {
        draw_rectangle(0.0, 0.0, w, h, Color::new(0.0, 0.0, 0.0, dark_a));
    }

    // === DarkOld / DarkNew：PPT 翻页瞬切（不淡入不淡出）===
    let fs = (h * 0.30) as u16;
    let (old_a, new_a) = match lt.phase {
        // 旧数字：DarkOld 全程满 alpha，DarkNew 后瞬间消失
        LtPhase::DarkOld => (1.0, 0.0),
        // 新数字：DarkNew 起瞬间满 alpha，StretchIn 跟着黑底一起退场
        LtPhase::DarkNew => (0.0, 1.0),
        LtPhase::StretchIn => {
            // 黑底淡出过程里数字也直接挂在那不淡——黑底退出后玩家就看不到了
            let dark = lt.dark_alpha();
            (0.0, if dark > 0.5 { 1.0 } else { 0.0 })
        }
        _ => (0.0, 0.0),
    };
    if old_a > 0.001 {
        draw_big_number(
            lt.old_section,
            w * 0.5,
            h * 0.5,
            fs,
            1.0,
            Color::new(1.0, 1.0, 1.0, old_a),
        );
    }
    if new_a > 0.001 {
        draw_big_number(
            lt.new_section,
            w * 0.5,
            h * 0.5,
            fs,
            1.0,
            Color::new(1.0, 1.0, 1.0, new_a),
        );
    }
}

fn draw_big_number(n: u32, cx: f32, cy: f32, base_fs: u16, scale: f32, color: Color) {
    let font = ui_font_medium();
    let fs = ((base_fs as f32) * scale).round() as u16;
    let text = n.to_string();
    let dim = measure_text(&text, Some(font), fs, 1.0);
    let x = (cx - dim.width * 0.5).round();
    let y = (cy + dim.offset_y * 0.5).round();
    // PPT 翻页：单层实笔画，不发光不淡入
    draw_text_ex(
        &text,
        x,
        y,
        TextParams {
            font: Some(font),
            font_size: fs,
            font_scale: 1.0,
            color,
            ..Default::default()
        },
    );
}

/// BT 死亡蒸发粒子：CPU 投影后 draw_circle 红点；按 life 比例淡出。
fn draw_bt_death_particles(bt: &BtSystem, cam: &Camera3D) {
    if bt.particles.is_empty() {
        return;
    }
    let w = screen_width();
    let h = screen_height();
    let mvp = cam.matrix();
    for p in &bt.particles {
        let life_t = (p.life / p.life_max).clamp(0.0, 1.0);
        let alpha = life_t.powf(0.6);
        let clip = mvp * vec4(p.pos.x, p.pos.y, p.pos.z, 1.0);
        if clip.w <= 0.0 {
            continue;
        }
        let ndc_x = clip.x / clip.w;
        let ndc_y = clip.y / clip.w;
        let ndc_z = clip.z / clip.w;
        if ndc_z < -1.0 || ndc_z > 1.0 || ndc_x.abs() > 1.0 || ndc_y.abs() > 1.0 {
            continue;
        }
        let sx = (ndc_x * 0.5 + 0.5) * w;
        let sy = (1.0 - (ndc_y * 0.5 + 0.5)) * h;
        let r = (4.0 / clip.w.max(0.001)).clamp(1.0, 5.0);
        draw_circle(sx, sy, r, Color::new(1.0, 0.15, 0.15, 0.95 * alpha));
    }
}

/// 绿激光 beam：从枪口（屏幕中下方）到每个命中端点连一根细绿线。
fn draw_green_beams(sonar: &crate::sonar::system::Sonar, cam: &Camera3D) {
    let ends = sonar.new_green_beams();
    if ends.is_empty() {
        return;
    }
    let w = screen_width();
    let h = screen_height();
    let mvp = cam.matrix();
    // 枪口投影点（用屏幕中下方代替）
    let muzzle = vec2(w * 0.78, h * 0.85);
    let beam_c = Color::new(0.30, 1.0, 0.45, 0.55);
    for e in ends.iter().take(40) {
        let clip = mvp * vec4(e.x, e.y, e.z, 1.0);
        if clip.w <= 0.0 {
            continue;
        }
        let sx = (clip.x / clip.w * 0.5 + 0.5) * w;
        let sy = (1.0 - (clip.y / clip.w * 0.5 + 0.5)) * h;
        draw_line(muzzle.x, muzzle.y, sx, sy, 1.2, beam_c);
    }
}

/// 低电量红色视野渐变：贴边平滑红 vignette + 心跳脉冲 alpha。
/// 120 条细带 + ease-out 平方曲线 → 肉眼无梯阶，纯流体渐变。
fn draw_low_energy_vignette(energy_ratio: f32, time: f32) {
    let w = screen_width();
    let h = screen_height();
    let danger = ((0.30 - energy_ratio.max(0.0)) / 0.30).clamp(0.0, 1.0);
    let bpm = 60.0 + 100.0 * danger;
    let pulse = 0.5 + 0.5 * (time * bpm * std::f32::consts::TAU / 60.0).sin();
    let a_max = 0.62 * danger * (0.45 + 0.55 * pulse);
    let thick = h * 0.30; // 厚度拉大让渐变更柔
    const STEPS: usize = 120;
    let band = thick / STEPS as f32; // ~2.7px @1080p
    for i in 0..STEPS {
        let t = i as f32 / STEPS as f32;
        let a = (1.0 - t).powf(2.6) * a_max;
        if a < 0.0015 {
            continue;
        }
        let c = Color::new(0.97, 0.08, 0.10, a);
        let y_top = i as f32 * band;
        let y_bot = h - (i as f32 + 1.0) * band;
        draw_rectangle(0.0, y_top, w, band + 0.7, c);
        draw_rectangle(0.0, y_bot, w, band + 0.7, c);
        let x_l = i as f32 * band;
        let x_r = w - (i as f32 + 1.0) * band;
        draw_rectangle(x_l, 0.0, band + 0.7, h, c);
        draw_rectangle(x_r, 0.0, band + 0.7, h, c);
    }
}

/// 临时调试 HUD：左上角小字显示玩家坐标 + yaw（°），用于 PA 验证 spawn / marker。
/// 正式版应该藏到 DEV 模式或调试按键后。
fn draw_coord_hud(player: &Player) {
    let pos = player.position();
    let yaw = player.forward_yaw_deg();
    let font = ui_font();
    let bg = Color::new(0.0, 0.0, 0.0, 0.55);
    let txt = format!(
        "X {:>+8.2}   Y {:>+8.2}   Z {:>+8.2}   yaw {:>+6.1}",
        pos.x, pos.y, pos.z, yaw
    );
    let fs = 16u16;
    let dim = measure_text(&txt, Some(font), fs, 1.0);
    draw_rectangle(8.0, 8.0, dim.width + 16.0, fs as f32 + 12.0, bg);
    draw_text_ex(
        &txt,
        16.0,
        22.0,
        TextParams {
            font: Some(font),
            font_size: fs,
            font_scale: 1.0,
            color: Color::new(0.7, 1.0, 0.85, 1.0),
            ..Default::default()
        },
    );
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
