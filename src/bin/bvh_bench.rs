//! BVH 性能基准：合成 N 个三角形，对比 BVH 加速 vs 暴力线性扫描。
//! 用法：`cargo run --release --bin bvh_bench`
//!
//! 目标：在静态几何 370k 三角 + 每次 864 射线（PULSE_RAYS）的负载下
//! 验证 BVH 单 ray 平均 < 5 µs。

use bvh::aabb::{Aabb, Bounded};
use bvh::bounding_hierarchy::BHShape;
use bvh::bvh::Bvh;
use bvh::ray::Ray as BvhRay;
use macroquad::prelude::Vec3;
use nalgebra::{Point3, Vector3};
use std::time::Instant;

// === 与 World 等价的 BvhTri 与 ray_tri，独立这里以保持 bench 闭环 ===

struct BvhTri {
    v: [Vec3; 3],
    node_index: usize,
}

impl Bounded<f32, 3> for BvhTri {
    fn aabb(&self) -> Aabb<f32, 3> {
        let mn = self.v[0].min(self.v[1]).min(self.v[2]);
        let mx = self.v[0].max(self.v[1]).max(self.v[2]);
        Aabb::with_bounds(
            Point3::new(mn.x, mn.y, mn.z),
            Point3::new(mx.x, mx.y, mx.z),
        )
    }
}

impl BHShape<f32, 3> for BvhTri {
    fn set_bh_node_index(&mut self, i: usize) {
        self.node_index = i;
    }
    fn bh_node_index(&self) -> usize {
        self.node_index
    }
}

fn ray_tri(origin: Vec3, dir: Vec3, a: Vec3, b: Vec3, c: Vec3) -> Option<f32> {
    const EPS: f32 = 1e-6;
    let e1 = b - a;
    let e2 = c - a;
    let p = dir.cross(e2);
    let det = e1.dot(p);
    if det.abs() < EPS {
        return None;
    }
    let inv = 1.0 / det;
    let tv = origin - a;
    let u = tv.dot(p) * inv;
    if !(0.0..=1.0).contains(&u) {
        return None;
    }
    let q = tv.cross(e1);
    let vv = dir.dot(q) * inv;
    if vv < 0.0 || u + vv > 1.0 {
        return None;
    }
    let t = e2.dot(q) * inv;
    (t > EPS).then_some(t)
}

// === 合成几何：用 sin/cos 生成"球壳样片状"分布的伪关卡 ===
//
// 选这种分布是为了让射线既可能近距离命中、也可能远距离命中、还可能 miss，
// 拿到接近真实关卡的命中率（≈ 70-90%）。

fn generate_scene(n: usize) -> Vec<[Vec3; 3]> {
    let mut tris = Vec::with_capacity(n);
    // 黄金角散布：均匀覆盖球面
    let golden = 2.399_963_2_f32;
    for i in 0..n {
        let t = i as f32 / n as f32;
        let phi = (1.0 - 2.0 * t).acos();
        let theta = golden * i as f32;
        let r = 25.0 + (i as f32 * 0.13).sin() * 8.0;
        let cx = r * phi.sin() * theta.cos();
        let cy = r * phi.cos();
        let cz = r * phi.sin() * theta.sin();
        let s = 0.6;
        let v0 = Vec3::new(cx, cy, cz);
        let v1 = Vec3::new(cx + s, cy, cz);
        let v2 = Vec3::new(cx, cy + s, cz);
        tris.push([v0, v1, v2]);
    }
    tris
}

fn rays_for_pulse(_eye: Vec3, fwd: Vec3, count: usize, spread_deg: f32) -> Vec<Vec3> {
    // 斐波那契圆盘 + 锥角偏转
    let right = fwd.cross(Vec3::Y).normalize_or_zero();
    let up = right.cross(fwd).normalize_or_zero();
    let spread = spread_deg.to_radians();
    let golden = 2.399_963_2_f32;
    (0..count)
        .map(|i| {
            let t = i as f32 / count as f32;
            let angle = i as f32 * golden;
            let radius = spread * t.sqrt();
            let off_x = angle.cos() * radius;
            let off_y = angle.sin() * radius;
            (fwd + right * off_x + up * off_y).normalize()
        })
        .collect()
}

// === BVH 路径：build 一次，traverse 多次 ===

fn bvh_raycast(
    bvh: &Bvh<f32, 3>,
    shapes: &[BvhTri],
    origin: Vec3,
    dir: Vec3,
    max_range: f32,
) -> Option<f32> {
    let ray = BvhRay::new(
        Point3::new(origin.x, origin.y, origin.z),
        Vector3::new(dir.x, dir.y, dir.z),
    );
    let mut best: Option<f32> = None;
    for shape in bvh.traverse(&ray, shapes) {
        if let Some(d) = ray_tri(origin, dir, shape.v[0], shape.v[1], shape.v[2]) {
            if d <= max_range && best.map_or(true, |b: f32| d < b) {
                best = Some(d);
            }
        }
    }
    best
}

fn brute_raycast(tris: &[[Vec3; 3]], origin: Vec3, dir: Vec3, max_range: f32) -> Option<f32> {
    let mut best: Option<f32> = None;
    for t in tris {
        if let Some(d) = ray_tri(origin, dir, t[0], t[1], t[2]) {
            if d <= max_range && best.map_or(true, |b: f32| d < b) {
                best = Some(d);
            }
        }
    }
    best
}

fn main() {
    // === 三档负载 ===
    for n_tri in [30_000usize, 100_000, 370_000] {
        println!("\n=== {} 三角形 ===", n_tri);
        let scene = generate_scene(n_tri);

        // 构建 BVH
        let mut shapes: Vec<BvhTri> = scene
            .iter()
            .map(|t| BvhTri { v: *t, node_index: 0 })
            .collect();
        let t_build = Instant::now();
        let bvh = Bvh::build(&mut shapes);
        let build_ms = t_build.elapsed().as_secs_f64() * 1000.0;
        println!("  BVH 构建：{:.1} ms", build_ms);

        // 生成 864 射线（与一次声呐脉冲一致）
        let eye = Vec3::new(0.0, 0.0, 0.0);
        let fwd = Vec3::new(0.0, 0.0, 1.0);
        let rays = rays_for_pulse(eye, fwd, 864, 22.85);

        // === BVH 路径 ===
        let t_bvh = Instant::now();
        let mut bvh_hits = 0usize;
        for &dir in &rays {
            if bvh_raycast(&bvh, &shapes, eye, dir, 40.0).is_some() {
                bvh_hits += 1;
            }
        }
        let bvh_ms = t_bvh.elapsed().as_secs_f64() * 1000.0;
        let bvh_us_per_ray = bvh_ms * 1000.0 / rays.len() as f64;
        println!(
            "  BVH 864 ray：{:.2} ms  ({:.2} µs/ray, {} hits)",
            bvh_ms, bvh_us_per_ray, bvh_hits
        );

        // === 暴力路径（仅在 ≤100k 跑，370k 时几秒钟太慢）===
        if n_tri <= 100_000 {
            let t_brute = Instant::now();
            let mut brute_hits = 0usize;
            for &dir in &rays {
                if brute_raycast(&scene, eye, dir, 40.0).is_some() {
                    brute_hits += 1;
                }
            }
            let brute_ms = t_brute.elapsed().as_secs_f64() * 1000.0;
            let brute_us_per_ray = brute_ms * 1000.0 / rays.len() as f64;
            println!(
                "  Brute 864 ray：{:.2} ms  ({:.2} µs/ray, {} hits)",
                brute_ms, brute_us_per_ray, brute_hits
            );
            if bvh_hits != brute_hits {
                println!(
                    "  ⚠️  hit 数不一致！BVH={} Brute={}（射线-三角检测路径有差异）",
                    bvh_hits, brute_hits
                );
            }
            let speedup = brute_ms / bvh_ms.max(1e-3);
            println!("  加速比：×{:.0}", speedup);
        } else {
            println!("  Brute 跳过（370k 暴力跑要几秒）");
        }

        // === 连续扫描负载：2822 ray/s 一帧 = ~47 ray ===
        // 对 BVH 跑 60 帧的负载、看 frame-time 影响
        let cont_per_frame = (2822.0_f32 / 60.0).ceil() as usize;
        let t_cont = Instant::now();
        for _frame in 0..60 {
            for i in 0..cont_per_frame {
                let dir = rays[i % rays.len()];
                let _ = bvh_raycast(&bvh, &shapes, eye, dir, 40.0);
            }
        }
        let cont_ms = t_cont.elapsed().as_secs_f64() * 1000.0;
        println!(
            "  连续扫描 60 帧 × {} ray：{:.2} ms  ({:.3} ms/frame)",
            cont_per_frame,
            cont_ms,
            cont_ms / 60.0
        );
    }

    println!("\n完成。");
}
