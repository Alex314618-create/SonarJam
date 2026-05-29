//! Immutable level geometry, triangle raycast, and wall collision queries.

use crate::app::config::{PLAYER_HEIGHT, PLAYER_RADIUS};
use macroquad::prelude::*;

const FLOOR_Y: f32 = 0.0;
const CEILING_Y: f32 = 3.0;
const EPSILON: f32 = 0.0001;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SurfaceKind {
    Wall,
    Floor,
    Ceiling,
}

#[derive(Clone, Copy, Debug)]
pub struct Hit {
    pub pos: Vec3,
    pub normal: Vec3,
    pub distance: f32,
    pub surface_kind: SurfaceKind,
}

#[derive(Clone, Copy, Debug)]
struct Triangle {
    a: Vec3,
    b: Vec3,
    c: Vec3,
    normal: Vec3,
    surface_kind: SurfaceKind,
}

#[derive(Clone, Copy, Debug)]
struct WallBox {
    min: Vec2,
    max: Vec2,
}

#[derive(Clone, Copy, Debug)]
pub struct RenderBox {
    pub center: Vec3,
    pub size: Vec3,
}

pub struct World {
    triangles: Vec<Triangle>,
    walls: Vec<WallBox>,
    depth_boxes: Vec<RenderBox>,
    spawn: Vec3,
}

impl World {
    pub fn new() -> Self {
        let mut world = Self {
            triangles: Vec::new(),
            walls: Vec::new(),
            depth_boxes: Vec::new(),
            spawn: vec3(0.0, PLAYER_HEIGHT, 0.0),
        };

        world.add_floor_and_ceiling(vec2(-2.0, -2.0), vec2(14.0, 18.0));
        world.depth_boxes.push(RenderBox {
            center: vec3(6.0, -0.025, 8.0),
            size: vec3(16.0, 0.05, 20.0),
        });
        world.depth_boxes.push(RenderBox {
            center: vec3(6.0, CEILING_Y + 0.025, 8.0),
            size: vec3(16.0, 0.05, 20.0),
        });
        world.add_wall_rect(vec2(-2.0, -2.0), vec2(4.0, 0.0));
        world.add_wall_rect(vec2(2.6, -2.0), vec2(14.0, 0.0));
        world.add_wall_rect(vec2(-2.0, 0.0), vec2(-1.6, 18.0));
        world.add_wall_rect(vec2(1.6, 0.0), vec2(2.0, 7.0));
        world.add_wall_rect(vec2(1.6, 11.0), vec2(2.0, 18.0));
        world.add_wall_rect(vec2(8.0, 0.0), vec2(8.4, 10.5));
        world.add_wall_rect(vec2(8.0, 13.0), vec2(8.4, 18.0));
        world.add_wall_rect(vec2(2.0, 17.6), vec2(14.0, 18.0));
        world.add_wall_rect(vec2(13.6, 8.0), vec2(14.0, 18.0));
        world.add_wall_rect(vec2(8.4, 7.0), vec2(12.5, 7.4));
        world.add_wall_rect(vec2(10.0, 10.5), vec2(10.4, 14.5));
        world.add_wall_rect(vec2(4.8, 13.2), vec2(9.2, 13.6));
        world.add_pillar(vec2(5.6, 4.2), vec2(6.5, 5.4));
        world.add_pillar(vec2(11.0, 15.0), vec2(12.0, 16.2));

        world
    }

    pub fn player_spawn(&self) -> Vec3 {
        self.spawn
    }

    pub fn depth_boxes(&self) -> &[RenderBox] {
        &self.depth_boxes
    }

    pub fn raycast(&self, origin: Vec3, dir: Vec3, max_range: f32) -> Option<Hit> {
        let mut best_hit: Option<Hit> = None;

        for tri in &self.triangles {
            if let Some(distance) = ray_triangle(origin, dir, tri) {
                if distance <= max_range {
                    let replace = best_hit
                        .map(|current| distance < current.distance)
                        .unwrap_or(true);
                    if replace {
                        best_hit = Some(Hit {
                            pos: origin + dir * distance,
                            normal: tri.normal,
                            distance,
                            surface_kind: tri.surface_kind,
                        });
                    }
                }
            }
        }

        best_hit
    }

    pub fn resolve_player_movement(&self, current: Vec3, desired: Vec3) -> Vec3 {
        let mut resolved = current;
        let try_x = vec3(desired.x, current.y, current.z);
        if !self.collides_cylinder(try_x, PLAYER_RADIUS, PLAYER_HEIGHT) {
            resolved.x = try_x.x;
        }

        let try_z = vec3(resolved.x, current.y, desired.z);
        if !self.collides_cylinder(try_z, PLAYER_RADIUS, PLAYER_HEIGHT) {
            resolved.z = try_z.z;
        }

        resolved
    }

    fn collides_cylinder(&self, position: Vec3, radius: f32, height: f32) -> bool {
        if position.y < FLOOR_Y || position.y > CEILING_Y || position.y - PLAYER_HEIGHT > EPSILON {
            return true;
        }

        if position.y - height < FLOOR_Y + 0.05 || position.y > CEILING_Y - 0.05 {
            return true;
        }

        let point = vec2(position.x, position.z);
        self.walls.iter().any(|wall| circle_intersects_aabb(point, radius, wall.min, wall.max))
    }

    fn add_floor_and_ceiling(&mut self, min: Vec2, max: Vec2) {
        let floor_a = vec3(min.x, FLOOR_Y, min.y);
        let floor_b = vec3(max.x, FLOOR_Y, min.y);
        let floor_c = vec3(max.x, FLOOR_Y, max.y);
        let floor_d = vec3(min.x, FLOOR_Y, max.y);
        self.push_triangle(floor_a, floor_c, floor_b, SurfaceKind::Floor);
        self.push_triangle(floor_a, floor_d, floor_c, SurfaceKind::Floor);

        let ceil_a = vec3(min.x, CEILING_Y, min.y);
        let ceil_b = vec3(max.x, CEILING_Y, min.y);
        let ceil_c = vec3(max.x, CEILING_Y, max.y);
        let ceil_d = vec3(min.x, CEILING_Y, max.y);
        self.push_triangle(ceil_a, ceil_b, ceil_c, SurfaceKind::Ceiling);
        self.push_triangle(ceil_a, ceil_c, ceil_d, SurfaceKind::Ceiling);
    }

    fn add_pillar(&mut self, min: Vec2, max: Vec2) {
        self.add_wall_rect(min, max);
    }

    fn add_wall_rect(&mut self, min: Vec2, max: Vec2) {
        self.walls.push(WallBox { min, max });
        self.depth_boxes.push(RenderBox {
            center: vec3((min.x + max.x) * 0.5, CEILING_Y * 0.5, (min.y + max.y) * 0.5),
            size: vec3(max.x - min.x, CEILING_Y, max.y - min.y),
        });

        let x0 = min.x;
        let x1 = max.x;
        let z0 = min.y;
        let z1 = max.y;
        let y0 = FLOOR_Y;
        let y1 = CEILING_Y;

        self.push_quad(
            vec3(x0, y0, z0),
            vec3(x1, y0, z0),
            vec3(x1, y1, z0),
            vec3(x0, y1, z0),
            SurfaceKind::Wall,
        );
        self.push_quad(
            vec3(x1, y0, z1),
            vec3(x0, y0, z1),
            vec3(x0, y1, z1),
            vec3(x1, y1, z1),
            SurfaceKind::Wall,
        );
        self.push_quad(
            vec3(x0, y0, z1),
            vec3(x0, y0, z0),
            vec3(x0, y1, z0),
            vec3(x0, y1, z1),
            SurfaceKind::Wall,
        );
        self.push_quad(
            vec3(x1, y0, z0),
            vec3(x1, y0, z1),
            vec3(x1, y1, z1),
            vec3(x1, y1, z0),
            SurfaceKind::Wall,
        );
    }

    fn push_quad(&mut self, a: Vec3, b: Vec3, c: Vec3, d: Vec3, surface_kind: SurfaceKind) {
        self.push_triangle(a, b, c, surface_kind);
        self.push_triangle(a, c, d, surface_kind);
    }

    fn push_triangle(&mut self, a: Vec3, b: Vec3, c: Vec3, surface_kind: SurfaceKind) {
        let normal = (b - a).cross(c - a).normalize();
        self.triangles.push(Triangle {
            a,
            b,
            c,
            normal,
            surface_kind,
        });
    }
}

fn ray_triangle(origin: Vec3, dir: Vec3, tri: &Triangle) -> Option<f32> {
    let edge1 = tri.b - tri.a;
    let edge2 = tri.c - tri.a;
    let p = dir.cross(edge2);
    let det = edge1.dot(p);
    if det.abs() < EPSILON {
        return None;
    }

    let inv_det = 1.0 / det;
    let tvec = origin - tri.a;
    let u = tvec.dot(p) * inv_det;
    if !(0.0..=1.0).contains(&u) {
        return None;
    }

    let q = tvec.cross(edge1);
    let v = dir.dot(q) * inv_det;
    if v < 0.0 || u + v > 1.0 {
        return None;
    }

    let distance = edge2.dot(q) * inv_det;
    (distance > EPSILON).then_some(distance)
}

fn circle_intersects_aabb(center: Vec2, radius: f32, min: Vec2, max: Vec2) -> bool {
    let closest = vec2(center.x.clamp(min.x, max.x), center.y.clamp(min.y, max.y));
    center.distance_squared(closest) < radius * radius
}
