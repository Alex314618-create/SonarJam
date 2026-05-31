//! 一次性：把根目录两个 wav 叠加成 assets/sfx/gun.wav，并删源文件。
//! 用法：cargo run --release --bin mix_gun_sound

use rodio::{Decoder, Source};
use std::fs::{self, File};
use std::io::{BufReader, BufWriter, Write};
use std::path::Path;

fn main() {
    let file_a = "sonar 按下扳机的声音以及沙沙电流声.wav";
    let file_b = "sonar.wav";
    let out_path = "assets/sfx/gun.wav";

    println!("解码 A: {}", file_a);
    let (a_samples, a_sr, a_ch) = decode(file_a);
    println!(
        "  → {} samples  /  {} Hz  /  {} ch",
        a_samples.len(),
        a_sr,
        a_ch
    );

    println!("解码 B: {}", file_b);
    let (b_samples, b_sr, b_ch) = decode(file_b);
    println!(
        "  → {} samples  /  {} Hz  /  {} ch",
        b_samples.len(),
        b_sr,
        b_ch
    );

    // 采样率 + 声道必须一致才能"直接叠加"。两边不一致就警告 + 用 A 的格式。
    if a_sr != b_sr || a_ch != b_ch {
        eprintln!(
            "⚠  采样率/声道不一致（A {}Hz/{}ch  vs  B {}Hz/{}ch）。\
             rodio 简化处理：直接相加，输出用 A 的格式——可能出现速度/音高错乱。\
             如果听起来奇怪，告诉架构师做正经重采样。",
            a_sr, a_ch, b_sr, b_ch
        );
    }

    // 叠加：两源各 ×0.6 防止 clip。短的零填到长的长度。
    let len = a_samples.len().max(b_samples.len());
    let mut mix: Vec<f32> = Vec::with_capacity(len);
    for i in 0..len {
        let av = a_samples.get(i).copied().unwrap_or(0.0);
        let bv = b_samples.get(i).copied().unwrap_or(0.0);
        mix.push(av * 0.6 + bv * 0.6);
    }
    // 找峰值，若 > 1.0 整体归一
    let peak = mix.iter().fold(0.0_f32, |m, v| m.max(v.abs()));
    if peak > 1.0 {
        let g = 0.98 / peak;
        for v in mix.iter_mut() {
            *v *= g;
        }
        println!("  峰值 {:.3} > 1.0 → 归一到 0.98", peak);
    } else {
        println!("  峰值 {:.3}（无需归一）", peak);
    }

    // f32 → i16
    let samples_i16: Vec<i16> = mix
        .iter()
        .map(|v| (v.clamp(-1.0, 1.0) * 32767.0) as i16)
        .collect();

    write_wav(Path::new(out_path), a_ch, a_sr, &samples_i16).unwrap();
    println!(
        "✓ 写入 {}  ({} samples，{:.2}s)",
        out_path,
        samples_i16.len(),
        samples_i16.len() as f32 / (a_sr as f32 * a_ch as f32)
    );

    // 删源文件
    if let Err(e) = fs::remove_file(file_a) {
        eprintln!("[warn] 删 A 失败：{}", e);
    } else {
        println!("✓ 删 {}", file_a);
    }
    if let Err(e) = fs::remove_file(file_b) {
        eprintln!("[warn] 删 B 失败：{}", e);
    } else {
        println!("✓ 删 {}", file_b);
    }
}

fn decode(path: &str) -> (Vec<f32>, u32, u16) {
    let file = BufReader::new(File::open(path).unwrap_or_else(|e| {
        eprintln!("打不开 {}: {}", path, e);
        std::process::exit(1);
    }));
    let decoder = Decoder::new(file).unwrap_or_else(|e| {
        eprintln!("解码失败 {}: {}", path, e);
        std::process::exit(1);
    });
    let sr = decoder.sample_rate();
    let ch = decoder.channels();
    let samples: Vec<f32> = decoder.convert_samples().collect();
    (samples, sr, ch)
}

fn write_wav(path: &Path, channels: u16, sample_rate: u32, samples: &[i16]) -> std::io::Result<()> {
    let mut f = BufWriter::new(File::create(path)?);
    let data_len = (samples.len() * 2) as u32;
    let byte_rate = sample_rate * channels as u32 * 2;
    let block_align = channels * 2;

    f.write_all(b"RIFF")?;
    f.write_all(&(36 + data_len).to_le_bytes())?;
    f.write_all(b"WAVE")?;
    f.write_all(b"fmt ")?;
    f.write_all(&16u32.to_le_bytes())?;
    f.write_all(&1u16.to_le_bytes())?; // PCM
    f.write_all(&channels.to_le_bytes())?;
    f.write_all(&sample_rate.to_le_bytes())?;
    f.write_all(&byte_rate.to_le_bytes())?;
    f.write_all(&block_align.to_le_bytes())?;
    f.write_all(&16u16.to_le_bytes())?;
    f.write_all(b"data")?;
    f.write_all(&data_len.to_le_bytes())?;
    for &s in samples {
        f.write_all(&s.to_le_bytes())?;
    }
    Ok(())
}
