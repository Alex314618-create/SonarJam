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

            self.renderer.render(&self.player.camera(), &self.sonar);

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
