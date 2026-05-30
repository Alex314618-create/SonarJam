//! GLB 诊断工具：报告几何规模与对象分类，帮助定位"加载不出来"。
//!
//! 用法：cargo run --release --bin glb_inspect content/levels/earth_return_01/scene.glb

use std::collections::BTreeMap;

fn main() {
    let path = std::env::args()
        .nth(1)
        .expect("用法：cargo run --release --bin glb_inspect <path-to-glb>");

    println!("=== 解析 {} ===", path);
    let (doc, buffers, _images) = match gltf::import(&path) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("❌ 解析失败：{}", e);
            std::process::exit(1);
        }
    };
    println!("✓ 解析成功");

    let mut total_tris = 0usize;
    let mut by_prefix: BTreeMap<&str, (usize, usize)> = BTreeMap::new(); // prefix → (object_count, tri_count)
    let mut nameless = 0usize;

    for scene in doc.scenes() {
        for node in scene.nodes() {
            walk(&node, &buffers, &mut total_tris, &mut by_prefix, &mut nameless);
        }
    }

    println!();
    println!("--- 几何统计 ---");
    println!("总三角形数：{}", total_tris);
    println!("未命名对象：{}", nameless);
    println!();
    println!("按前缀分类：");
    println!("  {:<10} {:>10} {:>15}", "前缀", "对象数", "三角形数");
    for (prefix, (objs, tris)) in &by_prefix {
        println!("  {:<10} {:>10} {:>15}", prefix, objs, tris);
    }

    println!();
    println!("--- 运行时容量判定 ---");
    let depth_cap = 150_000usize / 3; // upload_world_depth 上限 50k tri
    if total_tris > depth_cap {
        println!(
            "⚠️  R_ 三角形数 {} 超出 depth buffer 上限 {} —— 多余几何会被截断，且 raycast 会非常慢",
            total_tris, depth_cap
        );
    } else {
        println!("✓ 在 depth buffer 上限 {} 之内", depth_cap);
    }

    // 粗估 raycast 性能：连续扫描 2016 射线/秒 × 三角形数
    let intersects_per_sec = 2016 * total_tris;
    println!(
        "粗估每秒射线相交测试：{:>15}",
        format_count(intersects_per_sec)
    );
    if intersects_per_sec > 50_000_000 {
        println!("⚠️  超出单线程暴力 raycast 可承受范围（~5e7/s），需要空间加速结构或减少几何");
    }
}

fn walk(
    node: &gltf::Node,
    buffers: &[gltf::buffer::Data],
    total_tris: &mut usize,
    by_prefix: &mut BTreeMap<&'static str, (usize, usize)>,
    nameless: &mut usize,
) {
    let name = node.name().unwrap_or("");
    let prefix: &'static str = if name.is_empty() {
        *nameless += 1;
        "(unnamed)"
    } else if name.starts_with("R_") {
        "R_"
    } else if name.starts_with("C_") {
        "C_"
    } else if name.starts_with("P_") {
        "P_"
    } else if name.starts_with("M_") {
        "M_"
    } else if name.starts_with("V_") {
        "V_"
    } else {
        "其它"
    };

    if let Some(mesh) = node.mesh() {
        let mut obj_tris = 0;
        for prim in mesh.primitives() {
            let reader = prim.reader(|b| buffers.get(b.index()).map(|d| d.0.as_slice()));
            let vert_count = reader
                .read_positions()
                .map(|i| i.count())
                .unwrap_or(0);
            let idx_count = reader
                .read_indices()
                .map(|i| i.into_u32().count())
                .unwrap_or(vert_count);
            obj_tris += idx_count / 3;
        }
        if obj_tris > 0 {
            *total_tris += obj_tris;
            let entry = by_prefix.entry(prefix).or_insert((0, 0));
            entry.0 += 1;
            entry.1 += obj_tris;
        }
    }

    for child in node.children() {
        walk(&child, buffers, total_tris, by_prefix, nameless);
    }
}

fn format_count(n: usize) -> String {
    if n >= 1_000_000_000 {
        format!("{:.2} G", n as f64 / 1e9)
    } else if n >= 1_000_000 {
        format!("{:.2} M", n as f64 / 1e6)
    } else if n >= 1_000 {
        format!("{:.2} k", n as f64 / 1e3)
    } else {
        format!("{}", n)
    }
}
