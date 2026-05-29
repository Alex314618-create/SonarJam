mod app;
mod player;
mod render;
mod sonar;
mod ui;
mod world;

use app::game::GameApp;

fn window_conf() -> macroquad::prelude::Conf {
    app::config::window_conf()
}

#[macroquad::main(window_conf)]
async fn main() {
    let mut app = GameApp::new().await;
    app.run().await;
}
