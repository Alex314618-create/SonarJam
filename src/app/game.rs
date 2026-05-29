//! Main runtime composition: update input, emit sonar, render frame, draw UI.

use crate::player::controller::PlayerController;
use crate::render::renderer::Renderer;
use crate::sonar::system::SonarSystem;
use crate::ui::system::{Ui, UiContext};
use crate::world::geometry::World;
use macroquad::prelude::*;

pub struct GameApp {
    world: World,
    player: PlayerController,
    sonar: SonarSystem,
    renderer: Renderer,
    ui: Ui,
    mouse_captured: bool,
}

impl GameApp {
    pub async fn new() -> Self {
        let world = World::new();
        let player = PlayerController::new(world.player_spawn());
        let sonar = SonarSystem::new();
        let renderer = Renderer::new();
        let ui = Ui::new();

        Self {
            world,
            player,
            sonar,
            renderer,
            ui,
            mouse_captured: false,
        }
    }

    pub async fn run(&mut self) {
        loop {
            let dt = get_frame_time().min(1.0 / 20.0);
            if is_key_pressed(KeyCode::Escape) {
                if self.mouse_captured {
                    set_cursor_grab(false);
                    show_mouse(true);
                    self.mouse_captured = false;
                } else {
                    break;
                }
            }

            if !self.mouse_captured && is_mouse_button_pressed(MouseButton::Left) {
                set_cursor_grab(true);
                show_mouse(false);
                self.mouse_captured = true;
            }

            self.player.update(dt, &self.world, self.mouse_captured);
            let fire_state = self
                .sonar
                .update(dt, &self.world, self.player.eye_position(), self.player.forward());

            self.renderer.render(
                &self.world,
                &self.player.camera(),
                &self.sonar,
            );

            let ui_context = UiContext::new(
                vec2(screen_width(), screen_height()),
                self.sonar.energy_ratio(),
                fire_state,
            );
            self.ui.update(&ui_context);
            self.ui.draw(&ui_context);

            next_frame().await;
        }
    }
}
