//! 主运行时编排：输入 → 移动 → 声呐 → 渲染 → UI。

use crate::player::controller::Player;
use crate::render::renderer::Renderer;
use crate::sonar::system::Sonar;
use crate::ui::system::{Ui, UiContext};
use crate::world::geometry::World;
use macroquad::prelude::*;

pub struct GameApp {
    world: World,
    player: Player,
    sonar: Sonar,
    renderer: Renderer,
    ui: Ui,
}

impl GameApp {
    pub async fn new() -> Self {
        let world = World::new();
        let player = Player::new(world.spawn());
        Self {
            world,
            player,
            sonar: Sonar::new(),
            renderer: Renderer::new(),
            ui: Ui::new(),
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

            // N：进入下一轮——当前点云固化为银色“过去”，玩家回到起点重走。
            if is_key_pressed(KeyCode::N) {
                self.sonar.advance_loop();
                self.player.respawn(self.world.spawn());
            }

            self.player.update(dt, &self.world, true);
            let fire_state =
                self.sonar
                    .update(dt, &self.world, self.player.eye(), self.player.forward());

            self.renderer
                .render(&self.player.camera(), &self.sonar, &self.world);

            let ctx = UiContext::new(
                vec2(screen_width(), screen_height()),
                self.sonar.energy_ratio(),
                fire_state,
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
