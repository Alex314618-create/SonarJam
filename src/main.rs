mod app;
mod audio;
mod bt;
mod content;
mod narrative;
mod player;
mod render;
mod ship;
mod sonar;
mod ui;
mod world;

use app::game::GameApp;

fn window_conf() -> macroquad::prelude::Conf {
    app::config::window_conf()
}

#[macroquad::main(window_conf)]
async fn main() {
    audio::init();
    // 背景音乐已关 —— 开幕需要安静的星空
    let mut app = GameApp::new().await;
    app.run().await;
}
