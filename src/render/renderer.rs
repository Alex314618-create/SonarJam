//! 渲染：近黑背景 + 声呐点云 + 枪口细线。
//!
//! 凸盒房间从内部看无遮挡，故把每个 3D 点手动投影成屏幕空间小方块直接绘制
//! （draw_rectangle，与 UI 同一套必定渲染的 2D API），彻底绕开 3D mesh/材质路径。

use crate::app::config::{CLEAR_COLOR, MAX_BEAM_LINES, POINT_PIXEL_SIZE};
use crate::sonar::system::{Point, Sonar};
use macroquad::camera::Camera;
use macroquad::prelude::*;

pub struct Renderer;

impl Renderer {
    pub fn new() -> Self {
        Self
    }

    pub fn render(&self, camera: &Camera3D, sonar: &Sonar) {
        clear_background(CLEAR_COLOR);

        let mat = camera.matrix();
        let half = POINT_PIXEL_SIZE * 0.5;

        // 持久点云：投影为屏幕空间小方块。
        for p in sonar.points() {
            if let Some(sp) = project(mat, p.pos) {
                let c = p.color;
                draw_rectangle(
                    sp.x - half,
                    sp.y - half,
                    POINT_PIXEL_SIZE,
                    POINT_PIXEL_SIZE,
                    Color::new(c.r, c.g, c.b, 0.9),
                );
            }
        }

        // 枪口细线：右下角枪口连到本帧新生点（采样上限）。
        let muzzle = vec2(screen_width() - 74.0, screen_height() - 64.0);
        let beams: Vec<&Point> = sonar.new_points().collect();
        if !beams.is_empty() {
            let step = (beams.len() / MAX_BEAM_LINES).max(1);
            for p in beams.iter().step_by(step).take(MAX_BEAM_LINES) {
                if let Some(sp) = project(mat, p.pos) {
                    let c = p.color;
                    draw_line(muzzle.x, muzzle.y, sp.x, sp.y, 1.0, Color::new(c.r, c.g, c.b, 0.4));
                }
            }
        }
    }
}

/// 把世界坐标投影到屏幕像素坐标；相机背后或视野外返回 None。
fn project(mat: Mat4, world: Vec3) -> Option<Vec2> {
    let clip = mat * world.extend(1.0);
    if clip.w <= 0.0 {
        return None;
    }
    let ndc = clip.truncate() / clip.w;
    if ndc.x.abs() > 1.0 || ndc.y.abs() > 1.0 {
        return None;
    }
    Some(vec2(
        (ndc.x * 0.5 + 0.5) * screen_width(),
        (0.5 - ndc.y * 0.5) * screen_height(),
    ))
}
