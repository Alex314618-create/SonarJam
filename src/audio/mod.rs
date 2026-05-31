//! 音频：rodio 后端 + 背景音乐 ducking + 随机 ambient stinger 调度。
//!
//! 公共 API：
//!   - `audio::init()`                       启动时一次
//!   - `audio::play(name)`                   一次性事件
//!   - `audio::loop_start(name) / loop_stop` 连续循环
//!   - `audio::music_start(name) / music_stop` 背景音乐（带 ducking）
//!   - `audio::set_stingers_active(bool)`    Earth 模式打开/关闭随机恐怖 stinger
//!   - `audio::update(dt)`                   每帧推进 ducking + stinger 调度
//!
//! ducking 行为（仿死亡搁浅）：
//!   - 任何 play()/loop_start() 被调用 → music 音量 1.5s 内降到 30%
//!   - 1.5s 内无新触发 → 音量在 0.25s 内 lerp 回 100%
//!   - 状态由 `duck_until` 时间戳驱动，update(dt) 维护

use rodio::source::Source;
use rodio::{Decoder, OutputStream, OutputStreamHandle, Sink};
use std::cell::RefCell;
use std::collections::HashMap;
use std::io::Cursor;

// ===== 资产嵌入 =====
const WARP_CHARGE: &[u8] = include_bytes!("../../assets/sfx/warp_charge.wav");
const GUN: &[u8] = include_bytes!("../../assets/sfx/gun.wav");
const PROMPT_TONE: &[u8] = include_bytes!("../../assets/sfx/prompt_tone.wav");
const RUN_BREATH: &[u8] = include_bytes!("../../assets/sfx/run_breath.wav");
const STEPS: &[u8] = include_bytes!("../../assets/sfx/steps.wav");
const STEPS_REAL: &[u8] = include_bytes!("../../assets/sfx/steps_real.wav");
const SYSTEM_NOTIFICATION: &[u8] = include_bytes!("../../assets/sfx/system_notification.wav");
const COMM_BLIP: &[u8] = include_bytes!("../../assets/sfx/comm_blip.wav");
const BREATH_LIGHT: &[u8] = include_bytes!("../../assets/sfx/breath_light.wav");
const BREATH_TERROR: &[u8] = include_bytes!("../../assets/sfx/breath_terror.wav");
const HORROR_STING_01: &[u8] = include_bytes!("../../assets/sfx/horror_sting_01.wav");
const HORROR_STING_02: &[u8] = include_bytes!("../../assets/sfx/horror_sting_02.wav");
const HORROR_PASS: &[u8] = include_bytes!("../../assets/sfx/horror_pass.wav");
const AMBIENT_STING_RADIATION: &[u8] =
    include_bytes!("../../assets/sfx/ambient_sting_radiation.wav");
const AMBIENT_STING_HORROR: &[u8] = include_bytes!("../../assets/sfx/ambient_sting_horror.wav");
const HEARTBEAT: &[u8] = include_bytes!("../../assets/sfx/heartbeat.wav");
const REBIRTH: &[u8] = include_bytes!("../../assets/sfx/rebirth.wav");
const BACKGROUND_MUSIC: &[u8] = include_bytes!("../../assets/sfx/background_music.wav");
const MUSIC_RELIEF: &[u8] = include_bytes!("../../assets/sfx/music_relief.wav");
const MUSIC_THREAT: &[u8] = include_bytes!("../../assets/sfx/music_threat.wav");

// ===== Ducking 参数 =====
/// 一次 play() 后 music 维持低音量多久（秒）
const DUCK_HOLD: f32 = 1.5;
/// music 音量趋向目标的 lerp 速率（越大反应越快）
const MUSIC_LERP_RATE: f32 = 4.0;
/// ducking 期间 music 的音量
const MUSIC_DUCK_VOL: f32 = 0.30;

// ===== 随机 stinger 调度参数 =====
const STINGER_MIN_GAP: f32 = 30.0;
const STINGER_MAX_GAP: f32 = 90.0;
const STINGER_INITIAL_DELAY_MIN: f32 = 15.0;
const STINGER_INITIAL_DELAY_MAX: f32 = 30.0;

struct AudioState {
    handle: OutputStreamHandle,
    bytes: HashMap<&'static str, &'static [u8]>,
    loops: HashMap<&'static str, Sink>,
    // 背景音乐
    music_sink: Option<Sink>,
    music_current_vol: f32,
    duck_until: f32, // 累计游戏时间
    elapsed: f32,
    // 随机 stinger
    stingers_active: bool,
    next_stinger_in: f32,
    stinger_pool: Vec<&'static str>,
    rng: u32,
}

thread_local! {
    static AUDIO: RefCell<Option<AudioState>> = const { RefCell::new(None) };
}

pub fn init() {
    AUDIO.with_borrow_mut(|slot| {
        if slot.is_some() {
            return;
        }
        let (stream, handle) = match OutputStream::try_default() {
            Ok(v) => v,
            Err(e) => {
                eprintln!("[audio] 无音频设备，静默运行：{}", e);
                return;
            }
        };
        std::mem::forget(stream); // 防 Windows 退出 panic（rodio 已知坑）

        let mut bytes: HashMap<&'static str, &'static [u8]> = HashMap::new();
        bytes.insert("warp_charge", WARP_CHARGE);
        bytes.insert("gun", GUN);
        bytes.insert("prompt_tone", PROMPT_TONE);
        bytes.insert("run_breath", RUN_BREATH);
        bytes.insert("steps", STEPS);
        bytes.insert("steps_real", STEPS_REAL);
        bytes.insert("system_notification", SYSTEM_NOTIFICATION);
        bytes.insert("comm_blip", COMM_BLIP);
        bytes.insert("breath_light", BREATH_LIGHT);
        bytes.insert("breath_terror", BREATH_TERROR);
        bytes.insert("horror_sting_01", HORROR_STING_01);
        bytes.insert("horror_sting_02", HORROR_STING_02);
        bytes.insert("horror_pass", HORROR_PASS);
        bytes.insert("ambient_sting_radiation", AMBIENT_STING_RADIATION);
        bytes.insert("ambient_sting_horror", AMBIENT_STING_HORROR);
        bytes.insert("heartbeat", HEARTBEAT);
        bytes.insert("rebirth", REBIRTH);
        bytes.insert("background_music", BACKGROUND_MUSIC);
        bytes.insert("music_relief", MUSIC_RELIEF);
        bytes.insert("music_threat", MUSIC_THREAT);

        *slot = Some(AudioState {
            handle,
            bytes,
            loops: HashMap::new(),
            music_sink: None,
            music_current_vol: 1.0,
            duck_until: 0.0,
            elapsed: 0.0,
            stingers_active: false,
            next_stinger_in: 999.0, // 等 set_stingers_active 激活时设置
            stinger_pool: vec![
                "horror_sting_01",
                "horror_sting_02",
                "horror_pass",
                "ambient_sting_radiation",
                "ambient_sting_horror",
            ],
            rng: 0xCAFEBABE,
        });
    });
}

/// 一次性事件。任何 play() 都会触发 music ducking。
pub fn play(name: &'static str) {
    AUDIO.with_borrow_mut(|slot| {
        let Some(audio) = slot.as_mut() else { return };
        play_inline(audio, name);
        audio.duck_until = audio.elapsed + DUCK_HOLD;
    });
}

fn play_inline(audio: &mut AudioState, name: &'static str) {
    let Some(&data) = audio.bytes.get(name) else {
        eprintln!("[audio] 未知 sfx：{}", name);
        return;
    };
    let Ok(source) = Decoder::new(Cursor::new(data)) else {
        eprintln!("[audio] 解码失败：{}", name);
        return;
    };
    let _ = audio.handle.play_raw(source.convert_samples());
}

/// 启动一个循环（已在播则 no-op）。loop_start 同样触发 ducking（一次）。
pub fn loop_start(name: &'static str) {
    AUDIO.with_borrow_mut(|slot| {
        let Some(audio) = slot.as_mut() else { return };
        if audio.loops.contains_key(name) {
            return;
        }
        let Some(&data) = audio.bytes.get(name) else {
            return;
        };
        let Ok(source) = Decoder::new(Cursor::new(data)) else {
            return;
        };
        let Ok(sink) = Sink::try_new(&audio.handle) else {
            return;
        };
        sink.append(source.buffered().repeat_infinite());
        audio.loops.insert(name, sink);
        audio.duck_until = audio.elapsed + DUCK_HOLD;
    });
}

pub fn loop_stop(name: &'static str) {
    AUDIO.with_borrow_mut(|slot| {
        let Some(audio) = slot.as_mut() else { return };
        if let Some(sink) = audio.loops.remove(name) {
            sink.stop();
        }
    });
}

/// 背景音乐：永久 loop + 受 ducking 控制。
pub fn music_start(name: &'static str) {
    AUDIO.with_borrow_mut(|slot| {
        let Some(audio) = slot.as_mut() else { return };
        if audio.music_sink.is_some() {
            return;
        }
        let Some(&data) = audio.bytes.get(name) else {
            return;
        };
        let Ok(source) = Decoder::new(Cursor::new(data)) else {
            return;
        };
        let Ok(sink) = Sink::try_new(&audio.handle) else {
            return;
        };
        sink.set_volume(1.0);
        sink.append(source.buffered().repeat_infinite());
        audio.music_sink = Some(sink);
        audio.music_current_vol = 1.0;
    });
}

#[allow(dead_code)]
pub fn music_stop() {
    AUDIO.with_borrow_mut(|slot| {
        let Some(audio) = slot.as_mut() else { return };
        if let Some(sink) = audio.music_sink.take() {
            sink.stop();
        }
    });
}

/// 切随机恐怖 stinger 的总开关。Earth 模式开，Ship 模式关。
pub fn set_stingers_active(active: bool) {
    AUDIO.with_borrow_mut(|slot| {
        let Some(audio) = slot.as_mut() else { return };
        if audio.stingers_active == active {
            return;
        }
        audio.stingers_active = active;
        if active {
            let r = rand_f32(&mut audio.rng);
            audio.next_stinger_in = STINGER_INITIAL_DELAY_MIN
                + r * (STINGER_INITIAL_DELAY_MAX - STINGER_INITIAL_DELAY_MIN);
        }
    });
}

/// 每帧调用：推 elapsed、维护 music 音量、调度随机 stinger。
pub fn update(dt: f32) {
    AUDIO.with_borrow_mut(|slot| {
        let Some(audio) = slot.as_mut() else { return };
        audio.elapsed += dt;

        // ===== Ducking =====
        let target = if audio.elapsed < audio.duck_until {
            MUSIC_DUCK_VOL
        } else {
            1.0
        };
        let k = (MUSIC_LERP_RATE * dt).min(1.0);
        audio.music_current_vol += (target - audio.music_current_vol) * k;
        if let Some(sink) = audio.music_sink.as_ref() {
            sink.set_volume(audio.music_current_vol);
        }

        // ===== 随机 stinger =====
        if audio.stingers_active && !audio.stinger_pool.is_empty() {
            audio.next_stinger_in -= dt;
            if audio.next_stinger_in <= 0.0 {
                let idx = (rand_u32(&mut audio.rng) as usize) % audio.stinger_pool.len();
                let name = audio.stinger_pool[idx];
                play_inline(audio, name);
                audio.duck_until = audio.elapsed + DUCK_HOLD;
                let r = rand_f32(&mut audio.rng);
                audio.next_stinger_in = STINGER_MIN_GAP + r * (STINGER_MAX_GAP - STINGER_MIN_GAP);
            }
        }
    });
}

// ===== xorshift32 内联 RNG =====

fn rand_u32(s: &mut u32) -> u32 {
    *s ^= *s << 13;
    *s ^= *s >> 17;
    *s ^= *s << 5;
    *s
}

fn rand_f32(s: &mut u32) -> f32 {
    (rand_u32(s) as f32) / (u32::MAX as f32)
}
