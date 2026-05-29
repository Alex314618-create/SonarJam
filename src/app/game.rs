//! 主运行时编排：输入 → 移动 → 声呐 → 渲染 → UI。

use crate::player::controller::Player;
use crate::render::renderer::Renderer;
use crate::sonar::system::Sonar;
use crate::ui::system::{LogLine, Ui, UiContext, Warning};
use crate::world::geometry::World;
use macroquad::prelude::*;

const WARNING_LIFE: f32 = 4.0;
const LOG_MAX_LINES: usize = 8;

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
        }
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
            let ctx = UiContext::new(
                vec2(screen_width(), screen_height()),
                self.sonar.energy_ratio(),
                fire_state,
                self.phase,
                &self.warnings,
                &self.system_log,
            );
            self.ui.update(&ctx);
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
