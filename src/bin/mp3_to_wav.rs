//! 一次性：把 assets/sfx/ 下的 .mp3 / .ogg 解码 + 写成 16-bit PCM .wav，删源文件。
//! 用法：cargo run --release --bin mp3_to_wav

use rodio::{Decoder, Source};
use std::fs::{self, File};
use std::io::{BufReader, BufWriter, Write};
use std::path::Path;

fn main() {
    let dir = Path::new("assets/sfx");
    let mut converted = Vec::new();
    for entry in fs::read_dir(dir).expect("read assets/sfx") {
        let entry = entry.unwrap();
        let path = entry.path();
        let ext_ok = path
            .extension()
            .and_then(|e| e.to_str())
            .map(|e| e.eq_ignore_ascii_case("mp3") || e.eq_ignore_ascii_case("ogg"))
            .unwrap_or(false);
        if !ext_ok {
            continue;
        }
        let dst = path.with_extension("wav");
        if dst.exists() {
            println!("[skip] {} 已存在", dst.display());
            continue;
        }
        let file = BufReader::new(File::open(&path).expect("open"));
        let decoder = Decoder::new(file).expect("decode");
        let channels = decoder.channels();
        let sample_rate = decoder.sample_rate();
        let samples: Vec<i16> = decoder.convert_samples().collect();
        write_wav(&dst, channels, sample_rate, &samples).expect("write");
        println!(
            "[ok]   {} → {}  ({} ch, {} Hz, {} samples)",
            path.file_name().unwrap().to_string_lossy(),
            dst.file_name().unwrap().to_string_lossy(),
            channels,
            sample_rate,
            samples.len()
        );
        converted.push(path);
    }
    // 转换成功后删原 mp3
    for p in &converted {
        if let Err(e) = fs::remove_file(p) {
            eprintln!("[warn] 删 {} 失败：{}", p.display(), e);
        }
    }
    println!("完成。已删 {} 个 .mp3", converted.len());
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
    f.write_all(&16u16.to_le_bytes())?; // bits per sample
    f.write_all(b"data")?;
    f.write_all(&data_len.to_le_bytes())?;
    for &s in samples {
        f.write_all(&s.to_le_bytes())?;
    }
    Ok(())
}
