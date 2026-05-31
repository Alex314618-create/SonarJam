//! 飞船舱（开场场景）的加载与渲染。
//!
//! 与声呐世界（src/render/renderer.rs 走 miniquad GL_POINTS 黑暗管线）完全分离：
//! 这里走 macroquad 标准 3D + draw_mesh，CPU Lambert 烘到顶点色，base/emissive 双通道。
//! 加载侧绕过 `KHR_lights_punctual` 校验。

use macroquad::models::{Mesh, Vertex};
use macroquad::prelude::*;

/// CPU Lambert 主灯方向（指向光源）
const LIGHT_DIR: Vec3 = Vec3::new(0.45, 0.95, 0.30);
const LIGHT_COLOR: Vec3 = Vec3::new(1.00, 0.96, 0.88);
const AMBIENT: Vec3 = Vec3::new(0.32, 0.36, 0.44);
const DIFFUSE_GAIN: f32 = 0.75;
const MAX_IDX_PER_BATCH: usize = 4992;

pub struct Batch {
    pub mesh: Mesh,
    /// 预算的 unlit 顶点色（base_factor × vertex_color）；主游戏当前总是用 unlit。
    #[allow(dead_code)]
    pub color_unlit: Vec<[u8; 4]>,
    /// 预算的 Lambert 烘光顶点色；ship_preview 用 L 键切换。
    #[allow(dead_code)]
    pub color_lit: Vec<[u8; 4]>,
    pub is_emissive: bool,
}

pub struct Scene {
    pub batches: Vec<Batch>,
    pub aabb_min: Vec3,
    pub aabb_max: Vec3,
}

impl Scene {
    /// 加载 GLB 并构建 batches。返回 None 表示文件缺失或解析失败。
    pub fn load(path: &str) -> Option<Self> {
        let raw = std::fs::read(path).ok()?;
        let patched = strip_extensions_required(&raw);
        let (doc, buffers, images) = gltf::import_slice(&patched).ok()?;

        let textures: Vec<Texture2D> = images
            .iter()
            .map(|img| {
                let rgba = to_rgba8(img);
                let t = Texture2D::from_rgba8(img.width as u16, img.height as u16, &rgba);
                t.set_filter(FilterMode::Linear);
                t
            })
            .collect();

        let mut batches: Vec<Batch> = Vec::new();
        for scene in doc.scenes() {
            for node in scene.nodes() {
                walk(&node, Mat4::IDENTITY, &buffers, &textures, &mut batches);
            }
        }

        let (aabb_min, aabb_max) = compute_aabb(&batches);
        Some(Self {
            batches,
            aabb_min,
            aabb_max,
        })
    }

    /// 当前场景的水平中心（XZ），y 取地板（AABB.min.y）。供 spawn 用。
    pub fn floor_center(&self) -> Vec3 {
        let mid = (self.aabb_min + self.aabb_max) * 0.5;
        vec3(mid.x, self.aabb_min.y, mid.z)
    }
}

/// 渲染：base 在前、emissive overlay 在后。调用者负责 set_camera。
pub fn render(scene: &Scene) {
    for b in scene.batches.iter().filter(|b| !b.is_emissive) {
        draw_mesh(&b.mesh);
    }
    for b in scene.batches.iter().filter(|b| b.is_emissive) {
        draw_mesh(&b.mesh);
    }
}

fn walk(
    node: &gltf::Node,
    parent: Mat4,
    buffers: &[gltf::buffer::Data],
    textures: &[Texture2D],
    batches: &mut Vec<Batch>,
) {
    let local = Mat4::from_cols_array_2d(&node.transform().matrix());
    let world = parent * local;
    let name = node.name().unwrap_or("");
    let is_render = name.starts_with("R_");
    if let Some(mesh) = node.mesh() {
        if is_render {
            for prim in mesh.primitives() {
                process_primitive(&prim, world, buffers, textures, batches);
            }
        }
    }
    for c in node.children() {
        walk(&c, world, buffers, textures, batches);
    }
}

fn process_primitive(
    prim: &gltf::Primitive,
    world: Mat4,
    buffers: &[gltf::buffer::Data],
    textures: &[Texture2D],
    batches: &mut Vec<Batch>,
) {
    let reader = prim.reader(|b| buffers.get(b.index()).map(|d| d.0.as_slice()));
    let positions: Vec<Vec3> = match reader.read_positions() {
        Some(it) => it.map(Vec3::from_array).collect(),
        None => return,
    };
    let normals: Option<Vec<Vec3>> = reader
        .read_normals()
        .map(|it| it.map(Vec3::from_array).collect());
    let uvs: Vec<Vec2> = reader
        .read_tex_coords(0)
        .map(|tc| tc.into_f32().map(Vec2::from_array).collect())
        .unwrap_or_else(|| vec![Vec2::ZERO; positions.len()]);
    let vcolors: Option<Vec<Vec3>> = reader
        .read_colors(0)
        .map(|c| c.into_rgb_f32().map(Vec3::from_array).collect());
    let indices: Vec<u32> = reader
        .read_indices()
        .map(|i| i.into_u32().collect())
        .unwrap_or_else(|| (0..positions.len() as u32).collect());

    let mat = prim.material();
    let pbr = mat.pbr_metallic_roughness();
    let base_factor = pbr.base_color_factor();
    let base_tint = vec3(base_factor[0], base_factor[1], base_factor[2]);
    let base_texture = pbr.base_color_texture().and_then(|info| {
        let src = info.texture().source().index();
        textures.get(src).cloned()
    });
    let em_factor_arr = mat.emissive_factor();
    let em_factor = vec3(em_factor_arr[0], em_factor_arr[1], em_factor_arr[2]);
    let em_texture = mat.emissive_texture().and_then(|info| {
        let src = info.texture().source().index();
        textures.get(src).cloned()
    });
    let has_emissive = em_factor.length_squared() > 1e-6 || em_texture.is_some();

    let nm = Mat3::from_cols(
        world.x_axis.truncate(),
        world.y_axis.truncate(),
        world.z_axis.truncate(),
    );

    let mut base_v: Vec<Vertex> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut base_i: Vec<u16> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut base_unlit: Vec<[u8; 4]> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut base_lit: Vec<[u8; 4]> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut em_v: Vec<Vertex> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut em_i: Vec<u16> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut em_unlit: Vec<[u8; 4]> = Vec::with_capacity(MAX_IDX_PER_BATCH);
    let mut em_lit: Vec<[u8; 4]> = Vec::with_capacity(MAX_IDX_PER_BATCH);

    fn flush(
        v: &mut Vec<Vertex>,
        i: &mut Vec<u16>,
        cu: &mut Vec<[u8; 4]>,
        cl: &mut Vec<[u8; 4]>,
        batches: &mut Vec<Batch>,
        tex: Option<Texture2D>,
        is_em: bool,
    ) {
        if i.is_empty() {
            return;
        }
        batches.push(Batch {
            mesh: Mesh {
                vertices: std::mem::take(v),
                indices: std::mem::take(i),
                texture: tex,
            },
            color_unlit: std::mem::take(cu),
            color_lit: std::mem::take(cl),
            is_emissive: is_em,
        });
    }

    let em_color: [u8; 4] = if em_texture.is_some() && em_factor.length_squared() < 1e-6 {
        [255, 255, 255, 255]
    } else {
        [
            (em_factor.x.clamp(0.0, 1.0) * 255.0) as u8,
            (em_factor.y.clamp(0.0, 1.0) * 255.0) as u8,
            (em_factor.z.clamp(0.0, 1.0) * 255.0) as u8,
            255,
        ]
    };

    for tri in indices.chunks_exact(3) {
        if base_i.len() + 3 > MAX_IDX_PER_BATCH {
            flush(
                &mut base_v,
                &mut base_i,
                &mut base_unlit,
                &mut base_lit,
                batches,
                base_texture.clone(),
                false,
            );
        }
        if has_emissive && em_i.len() + 3 > MAX_IDX_PER_BATCH {
            flush(
                &mut em_v,
                &mut em_i,
                &mut em_unlit,
                &mut em_lit,
                batches,
                em_texture.clone(),
                true,
            );
        }
        let i0 = tri[0] as usize;
        let i1 = tri[1] as usize;
        let i2 = tri[2] as usize;
        let p_world = [
            world.transform_point3(positions[i0]),
            world.transform_point3(positions[i1]),
            world.transform_point3(positions[i2]),
        ];
        let n_world = match &normals {
            Some(ns) => [
                nm.mul_vec3(ns[i0]).normalize_or_zero(),
                nm.mul_vec3(ns[i1]).normalize_or_zero(),
                nm.mul_vec3(ns[i2]).normalize_or_zero(),
            ],
            None => {
                let fn_ = (p_world[1] - p_world[0])
                    .cross(p_world[2] - p_world[0])
                    .normalize_or_zero();
                [fn_, fn_, fn_]
            }
        };
        for k in 0..3 {
            let vi = [i0, i1, i2][k];
            let n_k = n_world[k];
            let uv_k = uvs[vi];
            let vc = vcolors.as_ref().map(|v| v[vi]).unwrap_or(Vec3::ONE);
            let tint = vec3(base_tint.x * vc.x, base_tint.y * vc.y, base_tint.z * vc.z);
            let unlit_k: [u8; 4] = [
                (tint.x.clamp(0.0, 1.0) * 255.0) as u8,
                (tint.y.clamp(0.0, 1.0) * 255.0) as u8,
                (tint.z.clamp(0.0, 1.0) * 255.0) as u8,
                255,
            ];
            let lit = lambert(n_k, tint);
            let lit_color = [
                (lit.x.clamp(0.0, 1.0) * 255.0) as u8,
                (lit.y.clamp(0.0, 1.0) * 255.0) as u8,
                (lit.z.clamp(0.0, 1.0) * 255.0) as u8,
                255,
            ];
            let base_idx = base_v.len() as u16;
            base_v.push(Vertex {
                position: p_world[k],
                uv: uv_k,
                color: unlit_k,
                normal: Vec4::new(n_k.x, n_k.y, n_k.z, 0.0),
            });
            base_unlit.push(unlit_k);
            base_lit.push(lit_color);
            base_i.push(base_idx);
            if has_emissive {
                let em_idx = em_v.len() as u16;
                em_v.push(Vertex {
                    position: p_world[k],
                    uv: uv_k,
                    color: em_color,
                    normal: Vec4::new(n_k.x, n_k.y, n_k.z, 0.0),
                });
                em_unlit.push(em_color);
                em_lit.push(em_color);
                em_i.push(em_idx);
            }
        }
    }
    flush(
        &mut base_v,
        &mut base_i,
        &mut base_unlit,
        &mut base_lit,
        batches,
        base_texture,
        false,
    );
    if has_emissive {
        flush(
            &mut em_v,
            &mut em_i,
            &mut em_unlit,
            &mut em_lit,
            batches,
            em_texture,
            true,
        );
    }
}

fn lambert(n: Vec3, base_tint: Vec3) -> Vec3 {
    let l = LIGHT_DIR.normalize_or_zero();
    let ndl = n.dot(l).max(0.0);
    let lit = AMBIENT + LIGHT_COLOR * (DIFFUSE_GAIN * ndl);
    vec3(
        lit.x * base_tint.x,
        lit.y * base_tint.y,
        lit.z * base_tint.z,
    )
}

fn to_rgba8(img: &gltf::image::Data) -> Vec<u8> {
    use gltf::image::Format;
    match img.format {
        Format::R8G8B8A8 => img.pixels.clone(),
        Format::R8G8B8 => {
            let mut out = Vec::with_capacity(img.pixels.len() / 3 * 4);
            for chunk in img.pixels.chunks_exact(3) {
                out.extend_from_slice(chunk);
                out.push(255);
            }
            out
        }
        Format::R8 => {
            let mut out = Vec::with_capacity(img.pixels.len() * 4);
            for &v in &img.pixels {
                out.extend_from_slice(&[v, v, v, 255]);
            }
            out
        }
        Format::R8G8 => {
            let mut out = Vec::with_capacity(img.pixels.len() * 2);
            for chunk in img.pixels.chunks_exact(2) {
                out.extend_from_slice(&[chunk[0], chunk[1], 0, 255]);
            }
            out
        }
        _ => vec![160, 160, 160, 255],
    }
}

fn compute_aabb(batches: &[Batch]) -> (Vec3, Vec3) {
    let mut mn = Vec3::splat(f32::INFINITY);
    let mut mx = Vec3::splat(f32::NEG_INFINITY);
    for b in batches {
        for v in &b.mesh.vertices {
            mn = mn.min(v.position);
            mx = mx.max(v.position);
        }
    }
    if !mn.is_finite() {
        return (Vec3::ZERO, Vec3::ONE);
    }
    (mn, mx)
}

/// 共用：GLB JSON chunk 里把 `"extensionsRequired":[...]` 清空，避免 gltf crate 拒绝。
/// 对非 GLB（普通 .gltf）或异常字节直接返回原样。
pub fn strip_extensions_required_for_glb(bytes: &[u8]) -> Vec<u8> {
    strip_extensions_required(bytes)
}

fn strip_extensions_required(bytes: &[u8]) -> Vec<u8> {
    if bytes.len() < 28 || &bytes[0..4] != b"glTF" {
        return bytes.to_vec();
    }
    let json_len = u32::from_le_bytes(bytes[12..16].try_into().unwrap()) as usize;
    if &bytes[16..20] != b"JSON" || 20 + json_len > bytes.len() {
        return bytes.to_vec();
    }
    let json_start = 20;
    let json_end = json_start + json_len;
    let Ok(s) = std::str::from_utf8(&bytes[json_start..json_end]) else {
        return bytes.to_vec();
    };
    let modified = replace_array_value(s, "\"extensionsRequired\"", "[]");
    let mut new_json: Vec<u8> = modified.into_bytes();
    if new_json.len() > json_len {
        return bytes.to_vec();
    }
    new_json.resize(json_len, b' ');
    let mut out = bytes.to_vec();
    out[json_start..json_end].copy_from_slice(&new_json);
    out
}

fn replace_array_value(s: &str, key: &str, new_value: &str) -> String {
    let Some(key_pos) = s.find(key) else {
        return s.to_string();
    };
    let bytes = s.as_bytes();
    let after_key = key_pos + key.len();
    let mut i = after_key;
    while i < bytes.len() && matches!(bytes[i], b' ' | b':' | b'\t' | b'\n' | b'\r') {
        i += 1;
    }
    if i >= bytes.len() || bytes[i] != b'[' {
        return s.to_string();
    }
    let array_start = i;
    let mut depth: i32 = 1;
    let mut j = i + 1;
    while j < bytes.len() && depth > 0 {
        match bytes[j] {
            b'[' => depth += 1,
            b']' => depth -= 1,
            _ => {}
        }
        j += 1;
    }
    if depth != 0 {
        return s.to_string();
    }
    let array_end = j;
    let mut out = String::with_capacity(s.len());
    out.push_str(&s[..array_start]);
    out.push_str(new_value);
    out.push_str(&s[array_end..]);
    out
}
