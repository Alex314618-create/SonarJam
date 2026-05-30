mod app;
mod audio;
mod content;
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
    // 背景音乐永久 loop，ducking 由 audio::update 自动管理
    audio::music_start("background_music");
    let mut app = GameApp::new().await;
    app.run().await;
}
