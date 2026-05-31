//! 头盔面罩 HUD：按 docs/ui-mockups/crosshair_energy_warnings.html 翻译。
//!
//! 设计基准 1920×1080，所有元素坐标在设计空间；运行时按当前 viewport 比例缩放
//! （类似 HTML 那个 stage transform: scale）。

use crate::app::config::{
    GUN_ANCHOR_OFFSET_X, GUN_ANCHOR_OFFSET_Y, GUN_DESIGN_W, GUN_MUZZLE_U, GUN_MUZZLE_V,
};
use crate::sonar::system::FireVisualState;
use macroquad::prelude::*;
use macroquad::text::{load_ttf_font_from_bytes, Font, TextParams};

/// DM Mono Regular，编译期嵌入到二进制（避免运行时路径问题）。
static DM_MONO_REGULAR: &[u8] = include_bytes!("../../assets/fonts/DMMono-Regular.ttf");
static DM_MONO_MEDIUM: &[u8] = include_bytes!("../../assets/fonts/DMMono-Medium.ttf");
/// 手持声呐枪贴图。
static SONAR_GUN_PNG: &[u8] = include_bytes!("../../assets/ui/sonar_gun.png");

// ============ 设计基准与缩放 ============

const DESIGN_W: f32 = 1920.0;
const DESIGN_H: f32 = 1080.0;

/// 设计空间→运行时像素映射；字号有独立倍率（统一放大可读性）。
pub struct Scale {
    s: f32,
    ox: f32,
    oy: f32,
}

/// 字号统一放大倍率：HTML 设计稿字号偏小，游戏里 ×N 更易读。
const FONT_BOOST: f32 = 1.4;

/// 共用：枪图在屏幕上的矩形（左上 x/y + 宽高，单位 = 屏幕像素）。
/// UI 元素和 renderer 的激光起点都从这里推出来，保证两边永远对齐。
pub fn gun_screen_rect(viewport: Vec2) -> (f32, f32, f32, f32) {
    let scale = Scale::from(viewport);
    let aspect = sonar_gun_aspect();
    let w = scale.len(GUN_DESIGN_W);
    let h = w * aspect;
    // 把枪图右下角对齐到屏幕右下角 + 偏移
    let off = scale.px(
        DESIGN_W + GUN_ANCHOR_OFFSET_X,
        DESIGN_H + GUN_ANCHOR_OFFSET_Y,
    );
    let x = off.x - w;
    let y = off.y - h;
    (x, y, w, h)
}

/// 共用：枪口（激光发射点）在屏幕上的像素坐标。
pub fn muzzle_screen_pos(viewport: Vec2) -> Vec2 {
    let (x, y, w, h) = gun_screen_rect(viewport);
    vec2(x + w * GUN_MUZZLE_U, y + h * GUN_MUZZLE_V)
}

fn sonar_gun_aspect() -> f32 {
    let t = sonar_gun_tex();
    t.height() / t.width().max(1.0)
}

fn sonar_gun_tex() -> &'static Texture2D {
    use std::sync::OnceLock;
    static T: OnceLock<Texture2D> = OnceLock::new();
    T.get_or_init(|| {
        let tex = Texture2D::from_file_with_format(SONAR_GUN_PNG, Some(ImageFormat::Png));
        tex.set_filter(FilterMode::Linear);
        tex
    })
}

impl Scale {
    fn from(viewport: Vec2) -> Self {
        let s = (viewport.x / DESIGN_W).min(viewport.y / DESIGN_H);
        let ox = (viewport.x - DESIGN_W * s) * 0.5;
        let oy = (viewport.y - DESIGN_H * s) * 0.5;
        Self { s, ox, oy }
    }
    fn px(&self, x: f32, y: f32) -> Vec2 {
        vec2(self.ox + x * self.s, self.oy + y * self.s)
    }
    fn len(&self, l: f32) -> f32 {
        l * self.s
    }
    /// 字号专用：在普通 len 基础上再放大 FONT_BOOST，并强制最小可读尺寸。
    fn font(&self, design_px: f32) -> f32 {
        (design_px * self.s * FONT_BOOST).max(12.0)
    }
}

/// 全局加载一次的字体；首次访问时初始化。
#[allow(dead_code)] // medium 留作强调字体用
struct Fonts {
    regular: Font,
    medium: Font,
}

fn fonts() -> &'static Fonts {
    use std::sync::OnceLock;
    static F: OnceLock<Fonts> = OnceLock::new();
    F.get_or_init(|| {
        let regular = load_ttf_font_from_bytes(DM_MONO_REGULAR).expect("DM Mono Regular 加载失败");
        let medium = load_ttf_font_from_bytes(DM_MONO_MEDIUM).expect("DM Mono Medium 加载失败");
        Fonts { regular, medium }
    })
}

/// CJK 字体（系统 Noto Sans SC 优先；找不到就回 DM Mono 不渲染中文）。
/// 用于左下 COMMS 等需要中文的 UI 元素。
fn font_cjk() -> &'static Font {
    use std::sync::OnceLock;
    static F: OnceLock<Font> = OnceLock::new();
    F.get_or_init(|| {
        for path in [
            "C:/Windows/Fonts/NotoSansSC-VF.ttf",
            "C:/Windows/Fonts/simhei.ttf",
        ] {
            if let Ok(bytes) = std::fs::read(path) {
                if let Ok(f) = load_ttf_font_from_bytes(&bytes) {
                    return f;
                }
            }
        }
        load_ttf_font_from_bytes(DM_MONO_REGULAR).unwrap()
    })
}

/// 中文字体版本 draw_t——给 COMMS 等中文 UI 用。
fn draw_t_cjk(text: &str, x: f32, y: f32, fs: f32, color: Color) {
    draw_text_ex(
        text,
        x.round(),
        y.round(),
        TextParams {
            font: Some(font_cjk()),
            font_size: fs.round() as u16,
            font_scale: 1.0,
            color,
            ..Default::default()
        },
    );
}

/// 用 DM Mono Regular 在指定位置画文本。
/// atlas raster size = display size（1:1），配合 high_dpi=true 确保
/// 一个 atlas 像素映射到一个屏幕物理像素 → pixel-perfect。
/// 坐标 round → 像素对齐。
fn draw_t(text: &str, x: f32, y: f32, fs: f32, color: Color) {
    draw_text_ex(
        text,
        x.round(),
        y.round(),
        TextParams {
            font: Some(&fonts().regular),
            font_size: fs.round() as u16,
            font_scale: 1.0,
            color,
            ..Default::default()
        },
    );
}

/// 用 DM Mono Medium（更粗）画文本——用于强调（如 BEARING 值）。
#[allow(dead_code)]
fn draw_t_bold(text: &str, x: f32, y: f32, fs: f32, color: Color) {
    draw_text_ex(
        text,
        x.round(),
        y.round(),
        TextParams {
            font: Some(&fonts().medium),
            font_size: fs.round() as u16,
            font_scale: 1.0,
            color,
            ..Default::default()
        },
    );
}

/// 用 Regular 字体测量文本宽度（与 draw_t 配套，对应 SSAA 渲染参数）。
struct TextDims {
    width: f32,
}

fn meas(text: &str, fs: f32) -> f32 {
    let dims = measure_text(text, Some(&fonts().regular), fs.round() as u16, 1.0);
    dims.width
}

// ============ 配色（抄 HTML CSS variables）============

fn ink_dim() -> Color {
    Color::new(0.66, 0.80, 0.84, 0.78)
}
fn ink_mid() -> Color {
    Color::new(0.80, 0.92, 0.96, 0.92)
}
fn ink_strong() -> Color {
    Color::new(0.95, 1.0, 1.0, 1.0)
}
fn ink_warm() -> Color {
    Color::new(0.96, 0.85, 0.69, 0.84)
}
fn line_soft() -> Color {
    Color::new(0.59, 0.74, 0.78, 0.10)
}
fn warn_line() -> Color {
    Color::new(0.91, 0.50, 0.41, 0.46)
}
fn warn_ink() -> Color {
    Color::new(0.97, 0.83, 0.78, 0.90)
}
fn bio_pulse() -> Color {
    Color::new(0.82, 0.45, 0.52, 0.74)
}
fn energy_fill() -> Color {
    Color::new(0.42, 0.61, 0.69, 0.78)
}
fn ink_warm_sub() -> Color {
    Color::new(0.91, 0.77, 0.70, 0.58)
}

// ============ 数据结构 ============

#[allow(dead_code)]
pub struct Vitals {
    pub t_ext_c: i32,   // 外部温度
    pub t_int_c: f32,   // 内部温度
    pub o2_pct: u32,    // 氧气
    pub press_psi: f32, // 舱压
    pub co2_pct: f32,   // 二氧化碳
}
impl Default for Vitals {
    fn default() -> Self {
        Self {
            t_ext_c: -89,
            t_int_c: 21.2,
            o2_pct: 78,
            press_psi: 14.2,
            co2_pct: 0.42,
        }
    }
}

#[allow(dead_code)]
pub struct Bio {
    pub hr_bpm: u32,
    pub resp: u32,
    pub spo2_pct: u32,
    pub core_c: f32,
}
impl Default for Bio {
    fn default() -> Self {
        Self {
            hr_bpm: 112,
            resp: 22,
            spo2_pct: 96,
            core_c: 37.2,
        }
    }
}

#[allow(dead_code)]
pub struct CommsLine {
    pub who: String,
    pub msg: String,
    /// 入栈后存活时间（秒），驱动淡入与排位淡出。
    pub age: f32,
}

#[allow(dead_code)]
pub struct WarningCard {
    pub tag: String,
    pub msg: String,
    pub sub: String,
}

// 旧 Warning / LogLine 保留（GameApp::push_warning / push_log 仍可用，未来叙事用）
#[allow(dead_code)]
pub struct Warning {
    pub text: String,
    pub age: f32,
    pub life: f32,
}
#[allow(dead_code)]
pub struct LogLine {
    pub text: String,
    pub age: f32,
}

#[allow(dead_code)]
#[derive(Copy, Clone)]
pub struct UiContext<'a> {
    pub viewport: Vec2,
    pub time: f32,
    pub energy_segments: u32,
    pub energy_ratio: f32,
    pub phase: u32,
    pub fire_state: FireVisualState,
    // 罗盘
    pub bearing_deg: f32,
    pub drift_mps: f32,
    // 各模块
    pub vitals: &'a Vitals,
    pub bio: &'a Bio,
    pub integrity_cell_pct: u32,
    pub comms: &'a [CommsLine],
    pub warning_card: Option<&'a WarningCard>,
    // 旧通道（保留）
    pub warnings: &'a [Warning],
    pub system_log: &'a [LogLine],
    pub sprinting: bool,
    /// 在动但不是 sprint（走路）。drift > 阈值且未按 Shift。
    pub walking: bool,
    /// 当前是否在 Ship 模式（开场飞船舱）。true 时藏掉准星/枪/能量条等声呐 HUD。
    pub in_ship: bool,
    /// HUD 启动进度（0=尚未启动，1=完全显示）。在 0..1 之间时 Ui::draw 会按元素 wake_time
    /// 拉 CRT 扫线启动效果。Idle 状态由 GameApp 传 1.0，转场期间逐帧推进。
    pub hud_boot_t: f32,
}

// ============ 框架 ============

pub trait UiElement {
    fn draw(&self, ctx: &UiContext<'_>, scale: &Scale);
    /// 该元素在 HUD boot 序列中的醒来时间（0..1，相对 BOOT_DUR）。
    /// 默认 1.0 = 立刻显示，无 CRT 启动。覆盖此方法可让元素分段亮起。
    fn wake_time(&self) -> f32 {
        1.0
    }
    /// 元素屏幕 bbox（用于 boot 期间盖 CRT 启动遮罩）。None = 无遮罩。
    fn bbox(&self, _ctx: &UiContext<'_>, _scale: &Scale) -> Option<Rect> {
        None
    }
}

pub struct Ui {
    elements: Vec<Box<dyn UiElement>>,
    fog: BreathFog,
    last_sprinting: bool,
}

impl Ui {
    pub fn new() -> Self {
        // HelmetOverlay 暂时不注册：暗角会让全部 HUD 在压暗区里看着昏暗
        let elements: Vec<Box<dyn UiElement>> = vec![
            // SonarGunEl 排第一 = 最先画 = 在所有 HUD 之下
            Box::new(SonarGunEl),
            Box::new(CrosshairEnergy),
            Box::new(CompassTape),
            Box::new(WarningCardEl),
            Box::new(SuitVitalsEl),
            Box::new(BioSignsEl),
            Box::new(CommsLogEl),
            Box::new(IntegrityCellEl),
        ];
        Self {
            elements,
            fog: BreathFog::new(),
            last_sprinting: false,
        }
    }

    pub fn update(&mut self, ctx: &UiContext<'_>, dt: f32) {
        self.fog.update(dt, ctx.sprinting, ctx.walking);
        self.last_sprinting = ctx.sprinting;
    }

    /// 玩家主动触发一次"哈气"（叙事节拍 / 重击 / 高 CO2 等场景）。
    #[allow(dead_code)] // 公共 API，叙事系统稍后会调用
    pub fn trigger_exhale(&mut self, intensity: f32) {
        self.fog.exhale(intensity, false);
    }

    pub fn draw(&self, ctx: &UiContext<'_>) {
        let scale = Scale::from(ctx.viewport);
        // Ship 模式：所有 HUD 都不画；只保留头盔呼吸雾。
        if !ctx.in_ship {
            for el in &self.elements {
                el.draw(ctx, &scale);
                // CRT 启动遮罩：仅在 boot 期间生效
                if ctx.hud_boot_t < 1.0 {
                    if let Some(bbox) = el.bbox(ctx, &scale) {
                        draw_boot_curtain(bbox, el.wake_time(), ctx.hud_boot_t);
                    }
                }
            }
        }
        // HUD 启动末尾的青光闪烁（boot 完成瞬间一闪）
        if ctx.hud_boot_t > 0.92 && ctx.hud_boot_t < 1.0 {
            let k = ((ctx.hud_boot_t - 0.92) / 0.08).clamp(0.0, 1.0);
            // 0 → 1 → 0 单峰，峰值 0.4
            let bell = 1.0 - (2.0 * k - 1.0).abs();
            let a = bell * 0.42;
            draw_rectangle(
                0.0,
                0.0,
                ctx.viewport.x,
                ctx.viewport.y,
                Color::new(0.62, 0.95, 1.0, a),
            );
        }
        // 雾气最后画：盖在所有 HUD 之上（最贴近镜头/玻璃罩）
        self.fog.draw(ctx.viewport);
    }
}

/// 每元素的 CRT 启动遮罩：
///   hud_t < wake：全黑覆盖（元素隐藏）
///   wake..wake+REVEAL：中央横向"扫线"扩张，上下黑边收缩；带青色辉光条
///   wake+REVEAL..1：无遮罩
fn draw_boot_curtain(bbox: Rect, wake: f32, hud_t: f32) {
    const REVEAL: f32 = 0.09; // 单元素揭示时长（hud_t 比例，更快）
    if hud_t >= wake + REVEAL {
        return;
    }
    if hud_t < wake {
        // 全黑覆盖
        draw_rectangle(bbox.x, bbox.y, bbox.w, bbox.h, BLACK);
        return;
    }
    // 0..1 揭示进度
    let r = ((hud_t - wake) / REVEAL).clamp(0.0, 1.0);
    let r_s = r * r * (3.0 - 2.0 * r); // smoothstep
    let slit_h = bbox.h * r_s;
    let slit_y = bbox.y + (bbox.h - slit_h) * 0.5;
    // 上下黑盖
    if slit_y > bbox.y {
        draw_rectangle(bbox.x, bbox.y, bbox.w, slit_y - bbox.y, BLACK);
    }
    let below_y = slit_y + slit_h;
    if below_y < bbox.y + bbox.h {
        draw_rectangle(bbox.x, below_y, bbox.w, bbox.y + bbox.h - below_y, BLACK);
    }
    // 青色扫线辉光条（上下沿）
    if r_s > 0.02 && r_s < 0.98 {
        let glow = Color::new(0.55, 0.95, 1.0, 0.85);
        draw_rectangle(bbox.x, slit_y - 1.0, bbox.w, 1.5, glow);
        draw_rectangle(bbox.x, below_y - 0.5, bbox.w, 1.5, glow);
    }
}

// ============ 元素：SonarGun（右下手持枪 sprite）============

struct SonarGunEl;
impl UiElement for SonarGunEl {
    fn draw(&self, ctx: &UiContext<'_>, _scale: &Scale) {
        if ctx.in_ship {
            return;
        }
        let (x, y, w, h) = gun_screen_rect(ctx.viewport);
        let tex = sonar_gun_tex();
        draw_texture_ex(
            tex,
            x,
            y,
            WHITE,
            DrawTextureParams {
                dest_size: Some(vec2(w, h)),
                ..Default::default()
            },
        );
    }
    fn wake_time(&self) -> f32 {
        0.55
    }
    fn bbox(&self, ctx: &UiContext<'_>, _scale: &Scale) -> Option<Rect> {
        let (x, y, w, h) = gun_screen_rect(ctx.viewport);
        Some(Rect { x, y, w, h })
    }
}

// ============ 元素：BreathFog（呼吸雾气）============
// 抄 docs/ui-mockups/crosshair_energy_warnings.html 的 exhale / setSprint：
//   sprint 时按 ~1.0~1.3s 节奏自动生成 puff；偶尔补一小口（每 3 个加一个小 puff）。
//   单次 puff：1.7±0.4s 周期，从下方 70px 起、向上飘 -44px、scale 0.94→1.58、
//   alpha 0 → peak(0.30~0.32) → fade out。
// 绝不挡屏幕中心：所有 puff 都局限在屏幕底部 40% 区域。

struct Puff {
    age: f32,
    duration: f32,
    peak: f32,
    /// 设计像素宽度（用 Scale.len 缩放后画到屏幕）
    width_design: f32,
    x_off_design: f32, // 中心横向偏移（屏幕中线为基准）
    dx_design: f32,    // 向上飘时再额外横移
    s0: f32,
    s1: f32,
    s2: f32,
    /// 选用哪张烘焙好的雾贴图（0..N_FOG_TEX-1）
    tex_idx: usize,
    /// 是否水平翻转（再增一倍变化）
    flip_x: bool,
}

const N_FOG_TEX: usize = 4;

struct BreathFog {
    puffs: Vec<Puff>,
    /// sprint 节奏：到下一次主呼气还剩多久（秒）
    next_sprint_beat: f32,
    sprint_tick: u32,
    /// 走路节奏：长间隔哈一口（默认 4-7s）
    next_walk_beat: f32,
    /// 计划中的"补一小口"延迟（秒），>0 时倒数到 0 触发
    pending_small_puff: f32,
    rng: u32,
    last_sprinting: bool,
    last_walking: bool,
    /// 启动时烘焙的雾贴图（带 value-noise 扭曲的软椭圆 alpha 蒙版）
    textures: Vec<Texture2D>,
}

impl BreathFog {
    fn new() -> Self {
        let mut rng = 0xFEEDFACEu32;
        let textures = (0..N_FOG_TEX)
            .map(|i| {
                bake_fog_texture(
                    0xA5C1D000 ^ (i as u32 * 0x9E3779B1) ^ {
                        rng ^= rng << 13;
                        rng ^= rng >> 17;
                        rng ^= rng << 5;
                        rng
                    },
                )
            })
            .collect();
        Self {
            puffs: Vec::with_capacity(8),
            next_sprint_beat: 0.0,
            sprint_tick: 0,
            next_walk_beat: 4.0, // 启动后 4s 第一口
            pending_small_puff: -1.0,
            rng: 0xC0FFEE15,
            last_sprinting: false,
            last_walking: false,
            textures,
        }
    }

    fn rand_f32(&mut self) -> f32 {
        // xorshift32 → [0,1)
        let mut x = self.rng;
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        self.rng = x;
        (x as f32) / (u32::MAX as f32)
    }

    fn exhale(&mut self, intensity: f32, small: bool) {
        let size_mul = if small { 0.78 } else { 1.0 };
        // 主 puff：设计 1100~1400 宽 ≈ 屏 60~75%
        let main_w = (1100.0 + self.rand_f32() * 300.0) * size_mul;
        self.spawn_puff(main_w, 0.0, intensity, 1.0);
        if small {
            crate::audio::play("breath_light");
        } else {
            crate::audio::play("run_breath");
        }

        // 两侧贴底卫星雾：仅主呼气出，弱一档 + 持续略长（先到先散），
        // 让屏幕下方左右与中央雾连成一片均匀贴底
        if !small && intensity > 0.5 {
            let sat_w = main_w * 0.62;
            let off = main_w * 0.34;
            self.spawn_puff(sat_w, -off, intensity * 0.55, 1.15);
            self.spawn_puff(sat_w, off, intensity * 0.55, 1.15);
        }
    }

    fn spawn_puff(&mut self, w: f32, x_off_extra: f32, intensity: f32, duration_mul: f32) {
        if self.puffs.len() >= 12 {
            return;
        }
        let x_off = (self.rand_f32() - 0.5) * 60.0 + x_off_extra;
        let dx = (self.rand_f32() - 0.5) * 18.0;
        let s0 = 0.90 + self.rand_f32() * 0.08;
        let s1 = 1.24 + self.rand_f32() * 0.16;
        let s2 = 1.50 + self.rand_f32() * 0.18;
        let duration = (1.9 + self.rand_f32() * 0.5) * duration_mul;
        let peak = 0.30 * intensity.clamp(0.2, 1.5);
        let tex_idx = (self.rand_f32() * N_FOG_TEX as f32) as usize % N_FOG_TEX;
        let flip_x = self.rand_f32() > 0.5;
        self.puffs.push(Puff {
            age: 0.0,
            duration,
            peak,
            width_design: w,
            x_off_design: x_off,
            dx_design: dx,
            s0,
            s1,
            s2,
            tex_idx,
            flip_x,
        });
    }

    fn update(&mut self, dt: f32, sprinting: bool, walking: bool) {
        // 老化 + 清理
        for p in self.puffs.iter_mut() {
            p.age += dt;
        }
        self.puffs.retain(|p| p.age < p.duration);

        // sprint 节奏：进入 sprint 时给 1.8~3.0s 的"先喘几口"延迟，再开始 1s 一拍。
        if sprinting {
            if !self.last_sprinting {
                self.next_sprint_beat = 1.8 + self.rand_f32() * 1.2;
                self.sprint_tick = 0;
            }
            self.next_sprint_beat -= dt;
            if self.next_sprint_beat <= 0.0 {
                self.sprint_tick += 1;
                self.exhale(1.25, false);
                if self.sprint_tick % 3 == 1 {
                    self.pending_small_puff = 0.22;
                }
                self.next_sprint_beat = 0.95 + self.rand_f32() * 0.25;
            }
        } else if walking {
            // 走路慢节奏：~4-7s 一口，更弱（intensity ~0.8）
            if self.last_sprinting {
                // 刚停跑：让走路节奏从 3s 后开始，别接 sprint 屁股喷
                self.next_walk_beat = 3.5 + self.rand_f32() * 1.5;
            }
            self.next_walk_beat -= dt;
            if self.next_walk_beat <= 0.0 {
                self.exhale(0.80, false);
                self.next_walk_beat = 4.0 + self.rand_f32() * 3.0;
            }
        } else {
            // 静止：保留正在飘的，节奏计数器静止（保留余量到下次走/跑）
        }

        if self.pending_small_puff > 0.0 {
            self.pending_small_puff -= dt;
            if self.pending_small_puff <= 0.0 {
                self.exhale(0.55, true);
                self.pending_small_puff = -1.0;
            }
        }

        self.last_sprinting = sprinting;
        self.last_walking = walking;
    }

    fn draw(&self, viewport: Vec2) {
        let scale = Scale::from(viewport);
        for p in &self.puffs {
            let t = (p.age / p.duration).clamp(0.0, 1.0);
            let (ty, sc, alpha_factor) = puff_keyframe(t, p.s0, p.s1, p.s2);
            let base_x = DESIGN_W * 0.5 + p.x_off_design + p.dx_design * (t * 1.6).min(1.0);
            // 起飞点整体上移（HTML 70px，这里 130px）
            let base_y = DESIGN_H - 130.0 + ty;
            let center = scale.px(base_x, base_y);
            let w_px = scale.len(p.width_design * sc);
            // 对应贴图本身 ellipse 宽:高（rx/ry = 0.55/0.50 → ≈ 0.48）；改这个会扯椭圆变形
            let h_px = w_px * 0.48;
            let alpha = p.peak * alpha_factor;
            if alpha <= 0.002 {
                continue;
            }
            let tex = &self.textures[p.tex_idx];
            // 贴图本身已携带 CSS 颜色与 stop 形状；tint 只控制全局透明度（puff peak × keyframe）。
            let tint = Color::new(1.0, 1.0, 1.0, alpha);
            draw_texture_ex(
                tex,
                center.x - w_px * 0.5,
                center.y - h_px * 0.5,
                tint,
                DrawTextureParams {
                    dest_size: Some(vec2(w_px, h_px)),
                    flip_x: p.flip_x,
                    ..Default::default()
                },
            );
        }
    }
}

/// 烘焙一张软椭圆 alpha 贴图（带 value-noise 扭曲），对应 HTML 的 radial-gradient + feTurbulence。
/// 单椭圆贴图，靠 puff 自身放大铺底，不在贴图层做 multi-lobe（避免边缘截断）。
fn bake_fog_texture(seed: u32) -> Texture2D {
    const W: u16 = 384;
    const H: u16 = 192;
    const GW: usize = 6;
    const GH: usize = 3;
    let mut s = seed.wrapping_add(1);
    let mut next = || {
        s ^= s << 13;
        s ^= s >> 17;
        s ^= s << 5;
        (s as f32) / (u32::MAX as f32)
    };
    let mut nx = [0.0f32; GW * GH];
    let mut ny = [0.0f32; GW * GH];
    for v in nx.iter_mut() {
        *v = next() * 2.0 - 1.0;
    }
    for v in ny.iter_mut() {
        *v = next() * 2.0 - 1.0;
    }
    let sample = |grid: &[f32], u: f32, v: f32| -> f32 {
        let gx = u * (GW as f32 - 1.0);
        let gy = v * (GH as f32 - 1.0);
        let x0 = gx.floor() as usize;
        let y0 = gy.floor() as usize;
        let x1 = (x0 + 1).min(GW - 1);
        let y1 = (y0 + 1).min(GH - 1);
        let fx = gx - x0 as f32;
        let fy = gy - y0 as f32;
        let sx = fx * fx * (3.0 - 2.0 * fx);
        let sy = fy * fy * (3.0 - 2.0 * fy);
        let a = grid[y0 * GW + x0];
        let b = grid[y0 * GW + x1];
        let c = grid[y1 * GW + x0];
        let d = grid[y1 * GW + x1];
        let ab = a + (b - a) * sx;
        let cd = c + (d - c) * sx;
        ab + (cd - ab) * sy
    };

    let mut bytes = vec![0u8; (W as usize) * (H as usize) * 4];
    let w_f = W as f32;
    let h_f = H as f32;
    let cx = 0.50 * w_f;
    let cy = 0.65 * h_f;
    let rx = 0.55 * w_f;
    let ry = 0.50 * h_f;
    let warp_amp = 0.16;

    let stops: [(f32, f32); 4] = [(0.00, 0.36), (0.26, 0.20), (0.52, 0.07), (0.78, 0.00)];
    let lerp_stops = |d: f32| -> f32 {
        if d >= 0.78 {
            return 0.0;
        }
        for w in stops.windows(2) {
            let (d0, a0) = w[0];
            let (d1, a1) = w[1];
            if d <= d1 {
                let k = ((d - d0) / (d1 - d0)).clamp(0.0, 1.0);
                return a0 + (a1 - a0) * k;
            }
        }
        0.0
    };

    for py in 0..H as usize {
        for px in 0..W as usize {
            let u = px as f32 / (W as usize - 1) as f32;
            let v = py as f32 / (H as usize - 1) as f32;
            let dx = sample(&nx, u, v) * warp_amp;
            let dy = sample(&ny, u, v) * warp_amp;
            let ex = (px as f32 - cx) / rx + dx;
            let ey = (py as f32 - cy) / ry + dy;
            let d = (ex * ex + ey * ey).sqrt();
            let a = lerp_stops(d);
            let i = (py * W as usize + px) * 4;
            bytes[i] = 224;
            bytes[i + 1] = 238;
            bytes[i + 2] = 244;
            bytes[i + 3] = (a.clamp(0.0, 1.0) * 255.0) as u8;
        }
    }
    let tex = Texture2D::from_rgba8(W, H, &bytes);
    tex.set_filter(FilterMode::Linear);
    tex
}

/// puff 时序（4 段）：
///   0..0.12  fade-in：alpha 0→1，位置/scale 静止
///   0.12..0.50 滞留：alpha 几乎不掉（1.0→0.92），慢慢上抬（+26 → +6）+ 微放大
///   0.50..0.78 升腾：alpha 0.92→0.55，位置 +6→-16，scale → s1
///   0.78..1.0  消散：alpha 0.55→0，位置 -16→-44，scale → s2
fn puff_keyframe(t: f32, s0: f32, s1: f32, s2: f32) -> (f32, f32, f32) {
    let s_mid = s0 * 1.06; // 滞留期末端的轻微放大

    let ty = if t < 0.12 {
        26.0
    } else if t < 0.50 {
        let k = (t - 0.12) / (0.50 - 0.12);
        26.0 + (6.0 - 26.0) * k
    } else if t < 0.78 {
        let k = (t - 0.50) / (0.78 - 0.50);
        6.0 + (-16.0 - 6.0) * k
    } else {
        let k = (t - 0.78) / (1.0 - 0.78);
        -16.0 + (-44.0 - (-16.0)) * k
    };

    let sc = if t < 0.12 {
        s0
    } else if t < 0.50 {
        let k = (t - 0.12) / (0.50 - 0.12);
        s0 + (s_mid - s0) * k
    } else if t < 0.78 {
        let k = (t - 0.50) / (0.78 - 0.50);
        s_mid + (s1 - s_mid) * k
    } else {
        let k = (t - 0.78) / (1.0 - 0.78);
        s1 + (s2 - s1) * k
    };

    let a = if t < 0.12 {
        t / 0.12
    } else if t < 0.50 {
        let k = (t - 0.12) / (0.50 - 0.12);
        1.0 + (0.92 - 1.0) * k
    } else if t < 0.78 {
        let k = (t - 0.50) / (0.78 - 0.50);
        0.92 + (0.55 - 0.92) * k
    } else {
        let k = (t - 0.78) / (1.0 - 0.78);
        0.55 + (0.0 - 0.55) * k
    };
    (ty, sc, a)
}

// ============ 元素：HelmetOverlay（头盔曲率/暗角，全屏）============

#[allow(dead_code)] // 暂时未注册；保留备用
struct HelmetOverlay;
impl UiElement for HelmetOverlay {
    fn draw(&self, ctx: &UiContext<'_>, _scale: &Scale) {
        let w = ctx.viewport.x;
        let h = ctx.viewport.y;
        // 仅四角轻微暗角（不压视野），帮助玩家感受"头盔边缘"
        let bands = 10;
        for i in 0..bands {
            let t = i as f32 / bands as f32;
            let alpha_side = 0.28 * (1.0 - t).powf(1.8);
            let band_w = w * 0.18 / bands as f32;
            draw_rectangle(
                i as f32 * band_w,
                0.0,
                band_w,
                h,
                Color::new(0.0, 0.0, 0.0, alpha_side),
            );
            draw_rectangle(
                w - (i as f32 + 1.0) * band_w,
                0.0,
                band_w,
                h,
                Color::new(0.0, 0.0, 0.0, alpha_side),
            );
            // 顶部/底部更轻
            let band_h = h * 0.15 / bands as f32;
            draw_rectangle(
                0.0,
                i as f32 * band_h,
                w,
                band_h,
                Color::new(0.0, 0.0, 0.0, 0.22 * (1.0 - t).powf(1.6)),
            );
            draw_rectangle(
                0.0,
                h - (i as f32 + 1.0) * band_h,
                w,
                band_h,
                Color::new(0.0, 0.0, 0.0, 0.30 * (1.0 - t).powf(1.6)),
            );
        }
    }
}

// ============ 元素：Crosshair + 5 Energy Ring ============

struct CrosshairEnergy;
impl CrosshairEnergy {
    fn design_bbox() -> (f32, f32, f32, f32) {
        (DESIGN_W * 0.5 - 38.0, DESIGN_H * 0.5 - 38.0, 76.0, 76.0)
    }
}
impl UiElement for CrosshairEnergy {
    fn draw(&self, ctx: &UiContext<'_>, scale: &Scale) {
        if ctx.in_ship {
            return;
        }
        // 中心在 design (960, 540)
        let c = scale.px(DESIGN_W * 0.5, DESIGN_H * 0.5);

        // 准星：极小的十字（设计 9.6px 臂长）
        let arm = scale.len(9.6);
        let th = scale.len(1.2).max(1.0);
        let col = Color::new(0.59, 0.73, 0.78, 0.78);
        // 中心点
        draw_rectangle(c.x - th * 0.5, c.y - th * 0.5, th, th, col);
        // 横臂
        draw_rectangle(c.x - arm * 0.5, c.y - th * 0.5, arm, th, col);
        // 竖臂
        draw_rectangle(c.x - th * 0.5, c.y - arm * 0.5, th, arm, col);

        // 5 个能量圆点（正五边形）。
        // 逆时针排序：top → 左上 → 左下 → 右下 → 右上。
        // 每消耗 20% 空一个，从 top 开始按 CCW 推进：
        //   segments=5 全亮；segments=4 top 空；segments=3 top+左上 空；...
        let r = scale.len(26.0);
        let dot_r = scale.len(3.5);
        let positions = [
            (0.0, -r),              // top
            (-r * 0.95, -r * 0.31), // 左上
            (-r * 0.59, r * 0.81),  // 左下
            (r * 0.59, r * 0.81),   // 右下
            (r * 0.95, -r * 0.31),  // 右上
        ];
        let empty_count = 5u32.saturating_sub(ctx.energy_segments);
        for (i, (dx, dy)) in positions.iter().enumerate() {
            let p = vec2(c.x + dx, c.y + dy);
            if (i as u32) < empty_count {
                draw_circle_lines(
                    p.x,
                    p.y,
                    dot_r,
                    scale.len(1.0).max(1.0),
                    Color::new(0.41, 0.44, 0.48, 0.58),
                );
            } else {
                draw_circle(p.x, p.y, dot_r, energy_fill());
            }
        }
    }
    fn wake_time(&self) -> f32 {
        0.05
    }
    fn bbox(&self, _ctx: &UiContext<'_>, scale: &Scale) -> Option<Rect> {
        let (x, y, w, h) = Self::design_bbox();
        let tl = scale.px(x, y);
        Some(Rect {
            x: tl.x,
            y: tl.y,
            w: scale.len(w),
            h: scale.len(h),
        })
    }
}

// ============ 元素：CompassTape（顶部罗盘）============

struct CompassTape;
impl UiElement for CompassTape {
    fn draw(&self, ctx: &UiContext<'_>, scale: &Scale) {
        const TAPE_W: f32 = 560.0; // design px
        const PX_PER_DEG: f32 = 6.0;
        let cx = DESIGN_W * 0.5;
        let top_y = 52.0;
        let rail_h = 22.0;

        // tape 中心位置（屏幕坐标）
        let center = scale.px(cx, top_y + rail_h * 0.5);

        // 画刻度：从 bearing-50 到 bearing+50 度范围（约 100° × 6px = 600px tape，覆盖 560px rail）
        let bearing = ctx.bearing_deg;
        for d_int in -50..=50 {
            let d = bearing + d_int as f32;
            let mod_360 = ((d as i32 % 360) + 360) % 360;
            let is_major = mod_360 % 15 == 0;
            let is_label = mod_360 % 30 == 0;
            let tick_x = center.x + scale.len(d_int as f32 * PX_PER_DEG);
            // 视野裁剪（不画跑出 rail 的）
            let half_w = scale.len(TAPE_W * 0.5);
            if (tick_x - center.x).abs() > half_w {
                continue;
            }
            let tick_h = if is_major {
                scale.len(10.0)
            } else {
                scale.len(5.0)
            };
            let tick_col = if is_major { ink_mid() } else { ink_dim() };
            let bottom_y = center.y + scale.len(rail_h * 0.5);
            draw_rectangle(
                tick_x - scale.len(0.5),
                bottom_y - tick_h,
                scale.len(1.0).max(1.0),
                tick_h,
                tick_col,
            );
            // 标签
            if is_label {
                let label = match mod_360 {
                    0 => "N".to_string(),
                    90 => "E".to_string(),
                    180 => "S".to_string(),
                    270 => "W".to_string(),
                    n => format!("{:03}", n),
                };
                let cardinal = matches!(mod_360, 0 | 90 | 180 | 270);
                let font_size = scale.font(if cardinal { 11.0 } else { 9.0 });
                let col = if cardinal { ink_strong() } else { ink_mid() };
                let dims = TextDims {
                    width: meas(&label, font_size),
                };
                draw_t(
                    &label,
                    tick_x - dims.width * 0.5,
                    bottom_y - tick_h - scale.len(2.0),
                    font_size,
                    col,
                );
            }
        }

        // 中心指针（垂直亮线）
        let pointer_h = scale.len(14.0);
        let pointer_y = center.y + scale.len(rail_h * 0.5 + 4.0) - pointer_h;
        draw_rectangle(
            center.x - scale.len(0.5),
            pointer_y,
            scale.len(1.0).max(1.0),
            pointer_h,
            ink_strong(),
        );

        // BEARING 与 DRIFT 文本
        let mod_b = ((bearing as i32 % 360) + 360) % 360;
        let bearing_text = format!("BEARING  {:03}°    DRIFT  {:+.1}m/s", mod_b, ctx.drift_mps);
        let fs = scale.font(11.0);
        let dims = TextDims {
            width: meas(&bearing_text, fs),
        };
        draw_t(
            &bearing_text,
            center.x - dims.width * 0.5,
            center.y + scale.len(rail_h * 0.5 + 22.0),
            fs,
            ink_strong(),
        );
    }
    fn wake_time(&self) -> f32 {
        0.20
    }
    fn bbox(&self, _ctx: &UiContext<'_>, scale: &Scale) -> Option<Rect> {
        let tl = scale.px(DESIGN_W * 0.5 - 300.0, 44.0);
        Some(Rect {
            x: tl.x,
            y: tl.y,
            w: scale.len(600.0),
            h: scale.len(60.0),
        })
    }
}

// ============ 元素：WarningCard（左上）============

struct WarningCardEl;
impl UiElement for WarningCardEl {
    fn draw(&self, ctx: &UiContext<'_>, scale: &Scale) {
        let Some(w) = ctx.warning_card else { return };
        // design (108, 86), size 320 × ~80
        let tl = scale.px(108.0, 86.0);
        let card_w = scale.len(320.0);
        let card_h = scale.len(96.0);

        // 脉动 opacity (1.4s 周期)
        let pulse = 0.7 + 0.30 * ((ctx.time * (std::f32::consts::TAU / 1.4)).sin() * 0.5 + 0.5);

        // 斜杠纹背景：用对角线模拟
        let mut bg = warn_line();
        bg.a *= 0.10 * pulse;
        let n_stripes = 30;
        for i in 0..n_stripes {
            let p = i as f32 / n_stripes as f32;
            let x = tl.x + p * (card_w + card_h);
            let y0 = tl.y;
            let y1 = tl.y + card_h;
            draw_line(x, y0, x - card_h, y1, scale.len(1.0).max(1.0), bg);
        }
        // 顶部 + 左侧边框
        let border = Color::new(
            warn_line().r,
            warn_line().g,
            warn_line().b,
            warn_line().a * pulse,
        );
        draw_line(
            tl.x,
            tl.y,
            tl.x + card_w,
            tl.y,
            scale.len(1.0).max(1.0),
            border,
        );
        draw_line(
            tl.x,
            tl.y,
            tl.x,
            tl.y + card_h,
            scale.len(1.0).max(1.0),
            border,
        );

        // TAG
        let mut y = tl.y + scale.len(14.0);
        let tag_fs = scale.font(9.0);
        draw_t(&w.tag, tl.x + scale.len(14.0), y, tag_fs, warn_ink());
        // MSG（主信息，允许 <br>，简化为按 \n 换行）
        y += scale.len(18.0);
        let msg_fs = scale.font(12.0);
        for line in w.msg.split("<br>").flat_map(|s| s.split('\n')) {
            draw_t(line.trim(), tl.x + scale.len(14.0), y, msg_fs, ink_strong());
            y += scale.len(20.0);
        }
        // SUB
        let sub_fs = scale.font(9.0);
        draw_t(
            &w.sub,
            tl.x + scale.len(14.0),
            y + scale.len(2.0),
            sub_fs,
            ink_warm_sub(),
        );
    }
    fn wake_time(&self) -> f32 {
        0.70
    }
    fn bbox(&self, _ctx: &UiContext<'_>, scale: &Scale) -> Option<Rect> {
        let tl = scale.px(100.0, 82.0);
        Some(Rect {
            x: tl.x,
            y: tl.y,
            w: scale.len(340.0),
            h: scale.len(108.0),
        })
    }
}

// ============ 元素：SuitVitals（左中）============

struct SuitVitalsEl;
impl UiElement for SuitVitalsEl {
    fn draw(&self, ctx: &UiContext<'_>, scale: &Scale) {
        // design (108, 280)，width 220
        let mut y = 280.0;
        let x = 108.0;
        let head_fs = scale.font(9.0);
        let label_fs = scale.font(10.0);
        let val_fs = scale.font(10.0);
        let _small_fs = scale.font(9.0);

        // 标题
        let head_p = scale.px(x, y);
        // 头部短横线
        draw_rectangle(
            head_p.x,
            head_p.y + scale.len(4.0),
            scale.len(18.0),
            scale.len(1.0).max(1.0),
            ink_dim(),
        );
        draw_t(
            "SUIT . LIFE",
            head_p.x + scale.len(28.0),
            head_p.y + scale.len(8.0),
            head_fs,
            ink_dim(),
        );
        y += 24.0;

        // 各行
        let rows: [(&str, String, Color); 5] = [
            ("T.EXT", format!("{}°C", ctx.vitals.t_ext_c), ink_warm()),
            (
                "T.INT",
                format!("{:.1}°C", ctx.vitals.t_int_c),
                ink_strong(),
            ),
            ("O2", format!("{}%", ctx.vitals.o2_pct), ink_strong()),
            (
                "PRESS",
                format!("{:.1}psi", ctx.vitals.press_psi),
                ink_strong(),
            ),
            ("CO2", format!("{:.2}%", ctx.vitals.co2_pct), ink_warm()),
        ];
        for (label, val, val_col) in rows.iter() {
            let p = scale.px(x, y);
            // 底线
            let line_y = p.y + scale.len(16.0);
            draw_line(
                p.x,
                line_y,
                p.x + scale.len(320.0),
                line_y,
                scale.len(1.0).max(1.0),
                line_soft(),
            );
            draw_t(label, p.x, p.y + scale.len(12.0), label_fs, ink_dim());
            // 值靠右
            let val_dims = TextDims {
                width: meas(val, val_fs),
            };
            draw_t(
                val,
                p.x + scale.len(320.0) - val_dims.width,
                p.y + scale.len(12.0),
                val_fs,
                *val_col,
            );
            y += 20.0;
        }
    }
    fn wake_time(&self) -> f32 {
        0.30
    }
    fn bbox(&self, _ctx: &UiContext<'_>, scale: &Scale) -> Option<Rect> {
        let tl = scale.px(100.0, 272.0);
        Some(Rect {
            x: tl.x,
            y: tl.y,
            w: scale.len(340.0),
            h: scale.len(140.0),
        })
    }
}

// ============ 元素：BioSigns（右上）============

struct BioSignsEl;
impl UiElement for BioSignsEl {
    fn draw(&self, ctx: &UiContext<'_>, scale: &Scale) {
        // design 右上：right=108, top=96, width=200
        let panel_w = 290.0;
        let x_right = DESIGN_W - 108.0;
        let mut y = 96.0;
        let head_fs = scale.font(9.0);
        let label_fs = scale.font(10.0);
        let val_fs = scale.font(10.0);

        // 标题（右对齐）
        let head_text = "BIO . CREW-01";
        let head_dims = TextDims {
            width: meas(head_text, head_fs),
        };
        let head_p = scale.px(x_right, y);
        draw_t(
            head_text,
            head_p.x - head_dims.width - scale.len(28.0),
            head_p.y + scale.len(8.0),
            head_fs,
            ink_dim(),
        );
        // 短横线（在标题右边）
        draw_rectangle(
            head_p.x - scale.len(18.0),
            head_p.y + scale.len(4.0),
            scale.len(18.0),
            scale.len(1.0).max(1.0),
            ink_dim(),
        );
        y += 24.0;

        // 心跳脉动小点（HR 行用）
        let heart_pulse = {
            let bpm = ctx.bio.hr_bpm.max(30) as f32;
            let period = 60.0 / bpm;
            let t_norm = (ctx.time % period) / period;
            // 60ms 尖峰 + 80ms 第二峰
            if t_norm < 0.08 {
                1.0
            } else if t_norm < 0.20 {
                0.55
            } else if t_norm < 0.28 {
                0.85
            } else {
                0.55
            }
        };

        let rows: [(&str, String, bool); 4] = [
            ("HR", format!("{}bpm", ctx.bio.hr_bpm), true),
            ("RESP", format!("{}/min", ctx.bio.resp), false),
            ("SpO2", format!("{}%", ctx.bio.spo2_pct), false),
            ("CORE", format!("{:.1}°C", ctx.bio.core_c), false),
        ];
        for (label, val, has_heart) in rows.iter() {
            let p = scale.px(x_right - panel_w, y);
            let line_y = p.y + scale.len(16.0);
            draw_line(
                p.x,
                line_y,
                p.x + scale.len(panel_w),
                line_y,
                scale.len(1.0).max(1.0),
                line_soft(),
            );
            draw_t(label, p.x, p.y + scale.len(12.0), label_fs, ink_dim());

            // 值（值靠右）
            let val_dims = TextDims {
                width: meas(val, val_fs),
            };
            let val_x = p.x + scale.len(panel_w) - val_dims.width;
            draw_t(val, val_x, p.y + scale.len(12.0), val_fs, ink_strong());
            // 心跳小圆（在值左边）
            if *has_heart {
                let mut hc = bio_pulse();
                hc.a *= heart_pulse;
                draw_circle(
                    val_x - scale.len(14.0),
                    p.y + scale.len(7.5),
                    scale.len(3.0 + heart_pulse * 2.0),
                    hc,
                );
            }
            y += 18.0;
        }
    }
    fn wake_time(&self) -> f32 {
        0.40
    }
    fn bbox(&self, _ctx: &UiContext<'_>, scale: &Scale) -> Option<Rect> {
        let tl = scale.px(DESIGN_W - 108.0 - 290.0, 88.0);
        Some(Rect {
            x: tl.x,
            y: tl.y,
            w: scale.len(298.0),
            h: scale.len(110.0),
        })
    }
}

// ============ 元素：CommsLog（左下）============

struct CommsLogEl;
impl UiElement for CommsLogEl {
    fn draw(&self, ctx: &UiContext<'_>, scale: &Scale) {
        // design 左下：left=108, bottom=120
        let x = 108.0;
        let bottom = DESIGN_H - 120.0;
        let line_h = 22.0;
        let head_fs = scale.font(9.0);
        let who_fs = scale.font(9.0);
        let msg_fs = scale.font(11.0);

        // 标题
        let head_p = scale.px(x, bottom - (ctx.comms.len() as f32 * line_h) - 22.0);
        // 小圆呼吸
        let pulse = 0.55 + 0.45 * ((ctx.time * (std::f32::consts::TAU / 1.8)).sin() * 0.5 + 0.5);
        let mut dot = Color::new(0.67, 0.86, 0.91, 0.55);
        dot.a *= pulse;
        draw_circle(
            head_p.x + scale.len(3.0),
            head_p.y + scale.len(6.0),
            scale.len(2.5),
            dot,
        );
        draw_t(
            "COMMS . CH-04",
            head_p.x + scale.len(16.0),
            head_p.y + scale.len(9.0),
            head_fs,
            ink_dim(),
        );

        // 最多 4 条（第 4 条用于挤出旧条目时做淡出过渡，由 GameApp 在适当时清理）。
        let visible: usize = ctx.comms.len().min(4);
        let mut y = bottom - (visible as f32 * line_h);
        const SLOT_ALPHAS: [f32; 4] = [1.0, 0.55, 0.28, 0.0];
        const FADE_IN_T: f32 = 0.35;
        for (i, line) in ctx.comms.iter().enumerate().take(4) {
            // 新条目淡入（0→1 over FADE_IN_T 秒），槽 0 才有 fresh 特权。
            let fade_in = (line.age / FADE_IN_T).clamp(0.0, 1.0);
            let slot_alpha = SLOT_ALPHAS[i.min(3)];
            // 第 4 槽（i=3）= 正在被挤出，alpha 从 0.28→0 跟随它的 age 后段；这里直接 0 即可，
            // 因为视觉上它再多停一帧就会被 GameApp 清掉，且本帧 alpha 微弱。
            let final_alpha = slot_alpha * fade_in;
            if final_alpha < 0.02 {
                y += line_h;
                continue;
            }
            let p = scale.px(x, y);
            let who_col = {
                let mut c = ink_dim();
                c.a *= final_alpha;
                c
            };
            let msg_col = {
                let mut c = if i == 0 { ink_strong() } else { ink_mid() };
                c.a *= final_alpha;
                c
            };
            draw_t_cjk(&line.who, p.x, p.y + scale.len(10.0), who_fs, who_col);
            draw_t_cjk(
                &line.msg,
                p.x + scale.len(100.0),
                p.y + scale.len(10.0),
                msg_fs,
                msg_col,
            );
            y += line_h;
        }
    }
    fn wake_time(&self) -> f32 {
        0.85
    }
    fn bbox(&self, _ctx: &UiContext<'_>, scale: &Scale) -> Option<Rect> {
        // 左下：design left=100, bottom=120, width=460, height=120
        let tl = scale.px(100.0, DESIGN_H - 240.0);
        Some(Rect {
            x: tl.x,
            y: tl.y,
            w: scale.len(460.0),
            h: scale.len(124.0),
        })
    }
}

// ============ 元素：IntegrityCell（右下电池条）============

struct IntegrityCellEl;
impl UiElement for IntegrityCellEl {
    fn draw(&self, ctx: &UiContext<'_>, scale: &Scale) {
        if ctx.in_ship {
            return;
        }
        // design 右下：right=96, bottom=96, width=140
        let panel_w = 140.0;
        let x_right = DESIGN_W - 96.0;
        let bottom = DESIGN_H - 96.0;
        let label_fs = scale.font(9.0);
        let val_fs = scale.font(10.0);
        let p = scale.px(x_right - panel_w, bottom - 24.0);
        // 标签
        draw_t("CELL", p.x, p.y, label_fs, ink_dim());
        let pct_text = format!("{}%", ctx.integrity_cell_pct);
        let pct_dims = TextDims {
            width: meas(&pct_text, val_fs),
        };
        draw_t(
            &pct_text,
            p.x + scale.len(panel_w) - pct_dims.width,
            p.y,
            val_fs,
            ink_strong(),
        );
        // 进度条
        let bar_y = p.y + scale.len(7.0);
        let bar_h = scale.len(2.0).max(1.0);
        let bar_w = scale.len(panel_w);
        draw_rectangle(p.x, bar_y, bar_w, bar_h, Color::new(0.67, 0.81, 0.85, 0.10));
        let fill_w = bar_w * (ctx.integrity_cell_pct as f32 / 100.0).clamp(0.0, 1.0);
        // 低电警告色
        let fill = if ctx.integrity_cell_pct < 50 {
            Color::new(0.91, 0.74, 0.52, 0.85)
        } else {
            Color::new(0.78, 0.90, 0.94, 0.78)
        };
        draw_rectangle(p.x, bar_y, fill_w, bar_h, fill);
    }
    fn wake_time(&self) -> f32 {
        0.50
    }
    fn bbox(&self, _ctx: &UiContext<'_>, scale: &Scale) -> Option<Rect> {
        let tl = scale.px(DESIGN_W - 240.0, DESIGN_H - 130.0);
        Some(Rect {
            x: tl.x,
            y: tl.y,
            w: scale.len(150.0),
            h: scale.len(32.0),
        })
    }
}
