//! Rendering pipeline for dark scene, depth-only world, additive sonar points, and muzzle beams.

use crate::app::config::{
    CLEAR_COLOR, MUZZLE_ANCHOR_OFFSET, POINT_FAR_SIZE, POINT_NEAR_SIZE, POINT_SIZE_FAR_DISTANCE,
    POINT_SIZE_NEAR_DISTANCE,
};
use crate::sonar::system::{SonarPoint, SonarSystem};
use crate::world::geometry::{RenderBox, World};
use macroquad::camera::Camera;
use macroquad::material::{gl_use_default_material, gl_use_material, load_material, Material, MaterialParams};
use macroquad::miniquad::{BlendFactor, BlendState, BlendValue, Comparison, Equation, PipelineParams};
use macroquad::prelude::*;

const SHARED_VERTEX: &str = r#"#version 100
attribute vec3 position;
attribute vec2 texcoord;
attribute vec4 color0;
attribute vec4 normal;

varying lowp vec2 uv;
varying lowp vec4 color;

uniform mat4 Model;
uniform mat4 Projection;

void main() {
    gl_Position = Projection * Model * vec4(position, 1.0);
    uv = texcoord;
    color = color0 / 255.0;
}
"#;

const DEPTH_FRAGMENT: &str = r#"#version 100
precision mediump float;
void main() {
    gl_FragColor = vec4(0.0, 0.0, 0.0, 0.0);
}
"#;

const POINT_FRAGMENT: &str = r#"#version 100
precision mediump float;
varying lowp vec2 uv;
varying lowp vec4 color;

void main() {
    vec2 coord = uv * 2.0 - 1.0;
    float dist = dot(coord, coord);
    if (dist > 1.0) {
        discard;
    }

    float glow = pow(1.0 - dist, 1.9);
    gl_FragColor = vec4(color.rgb * (0.55 + glow * 0.85), glow);
}
"#;

const COLOR_FRAGMENT: &str = r#"#version 100
precision mediump float;
varying lowp vec2 uv;
varying lowp vec4 color;

void main() {
    gl_FragColor = color;
}
"#;

pub struct Renderer {
    depth_material: Material,
    point_material: Material,
    additive_overlay_material: Material,
}

impl Renderer {
    pub fn new() -> Self {
        let depth_material = load_material(
            ShaderSource::Glsl {
                vertex: SHARED_VERTEX,
                fragment: DEPTH_FRAGMENT,
            },
            MaterialParams {
                pipeline_params: PipelineParams {
                    depth_test: Comparison::LessOrEqual,
                    depth_write: true,
                    color_write: (false, false, false, false),
                    ..Default::default()
                },
                ..Default::default()
            },
        )
        .expect("depth-only material");

        let point_material = load_material(
            ShaderSource::Glsl {
                vertex: SHARED_VERTEX,
                fragment: POINT_FRAGMENT,
            },
            MaterialParams {
                pipeline_params: PipelineParams {
                    depth_test: Comparison::LessOrEqual,
                    depth_write: false,
                    color_blend: Some(BlendState::new(
                        Equation::Add,
                        BlendFactor::Value(BlendValue::SourceAlpha),
                        BlendFactor::One,
                    )),
                    alpha_blend: Some(BlendState::new(
                        Equation::Add,
                        BlendFactor::One,
                        BlendFactor::One,
                    )),
                    ..Default::default()
                },
                ..Default::default()
            },
        )
        .expect("point material");

        let additive_overlay_material = load_material(
            ShaderSource::Glsl {
                vertex: SHARED_VERTEX,
                fragment: COLOR_FRAGMENT,
            },
            MaterialParams {
                pipeline_params: PipelineParams {
                    depth_test: Comparison::Always,
                    depth_write: false,
                    color_blend: Some(BlendState::new(
                        Equation::Add,
                        BlendFactor::Value(BlendValue::SourceAlpha),
                        BlendFactor::One,
                    )),
                    alpha_blend: Some(BlendState::new(
                        Equation::Add,
                        BlendFactor::One,
                        BlendFactor::One,
                    )),
                    ..Default::default()
                },
                ..Default::default()
            },
        )
        .expect("overlay material");

        Self {
            depth_material,
            point_material,
            additive_overlay_material,
        }
    }

    pub fn render(&self, world: &World, camera: &Camera3D, sonar: &SonarSystem) {
        clear_background(CLEAR_COLOR);

        set_camera(camera);
        gl_use_material(&self.depth_material);
        for box_shape in world.depth_boxes() {
            self.draw_depth_box(*box_shape);
        }
        gl_use_default_material();

        let mut point_mesh = Mesh {
            vertices: Vec::new(),
            indices: Vec::new(),
            texture: None,
        };

        for point in sonar.iter_points() {
            self.append_point_billboard(&mut point_mesh, point, camera.position);
        }

        if !point_mesh.vertices.is_empty() {
            gl_use_material(&self.point_material);
            draw_mesh(&point_mesh);
            gl_use_default_material();
        }

        set_default_camera();
        gl_use_material(&self.additive_overlay_material);
        let muzzle = vec2(
            screen_width() + MUZZLE_ANCHOR_OFFSET.x,
            screen_height() + MUZZLE_ANCHOR_OFFSET.y,
        );
        for point in sonar.frame_new_points() {
            if let Some(screen_pos) = world_to_screen(camera, point.position) {
                let bright = Color::new(point.color.r, point.color.g, point.color.b, 0.85);
                let dim = Color::new(point.color.r * 0.2, point.color.g * 0.2, point.color.b * 0.2, 0.2);
                draw_line(muzzle.x, muzzle.y, screen_pos.x, screen_pos.y, 1.05, bright);
                draw_circle(screen_pos.x, screen_pos.y, 1.35, dim);
                draw_circle(muzzle.x, muzzle.y, 2.8, bright);
            }
        }
        gl_use_default_material();
    }

    fn draw_depth_box(&self, render_box: RenderBox) {
        draw_cube(
            render_box.center,
            render_box.size,
            None,
            Color::new(0.0, 0.0, 0.0, 0.0),
        );
    }

    fn append_point_billboard(&self, mesh: &mut Mesh, point: &SonarPoint, eye: Vec3) {
        if mesh.vertices.len() > (u16::MAX as usize).saturating_sub(4) {
            return;
        }

        let to_camera = eye - point.position;
        let distance = to_camera.length().max(0.001);
        let forward = to_camera / distance;
        let mut right = Vec3::Y.cross(forward);
        if right.length_squared() < 0.0001 {
            right = Vec3::X;
        }
        right = right.normalize();
        let up = forward.cross(right).normalize();

        let t = ((distance - POINT_SIZE_NEAR_DISTANCE)
            / (POINT_SIZE_FAR_DISTANCE - POINT_SIZE_NEAR_DISTANCE))
            .clamp(0.0, 1.0);
        let half_size = (POINT_NEAR_SIZE + (POINT_FAR_SIZE - POINT_NEAR_SIZE) * t) * 0.5;

        let corners = [
            point.position - right * half_size - up * half_size,
            point.position + right * half_size - up * half_size,
            point.position + right * half_size + up * half_size,
            point.position - right * half_size + up * half_size,
        ];
        let uvs = [vec2(0.0, 1.0), vec2(1.0, 1.0), vec2(1.0, 0.0), vec2(0.0, 0.0)];

        let start = mesh.vertices.len() as u16;
        for (corner, uv) in corners.into_iter().zip(uvs) {
            mesh.vertices.push(Vertex::new2(corner, uv, point.color));
        }

        mesh.indices
            .extend_from_slice(&[start, start + 1, start + 2, start, start + 2, start + 3]);
    }
}

fn world_to_screen(camera: &Camera3D, world: Vec3) -> Option<Vec2> {
    let clip = camera.matrix() * world.extend(1.0);
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
