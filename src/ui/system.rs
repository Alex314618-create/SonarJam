//! Theme-driven anchored UI framework with pluggable elements and zero-intrusion extension path.

use macroquad::prelude::*;

#[derive(Clone, Copy)]
#[allow(dead_code)] // 完整九宫格锚点，供后续 UI 元素按需使用
pub enum Anchor {
    TopLeft,
    TopCenter,
    TopRight,
    CenterLeft,
    Center,
    CenterRight,
    BottomLeft,
    BottomCenter,
    BottomRight,
}

pub struct Theme {
    pub energy_bg: Color,
    pub energy_fill: Color,
    pub gun_body: Color,
    pub gun_glow: Color,
    pub crosshair: Color,
    pub line_thickness: f32,
    pub energy_size: Vec2,
    pub gun_size: Vec2,
    pub crosshair_size: f32,
}

impl Default for Theme {
    fn default() -> Self {
        Self {
            energy_bg: Color::new(0.08, 0.12, 0.18, 0.75),
            energy_fill: Color::new(0.0, 0.92, 0.84, 0.95),
            gun_body: Color::new(0.16, 0.2, 0.24, 0.9),
            gun_glow: Color::new(0.0, 1.0, 0.86, 1.0),
            crosshair: Color::new(0.72, 0.95, 1.0, 0.92),
            line_thickness: 2.0,
            energy_size: vec2(260.0, 18.0),
            gun_size: vec2(118.0, 138.0),
            crosshair_size: 10.0,
        }
    }
}

/// 顶部红警告横幅条目。GameApp 用 push_warning() 推入，自然 TTL 衰减后淡出。
#[allow(dead_code)]
pub struct Warning {
    pub text: String,
    /// 已存在秒数。UI 元素自行做"前 0.3s 淡入、后 0.5s 淡出、4s 总时长"等表现。
    pub age: f32,
    /// 总寿命；超过即可被 Ui 清掉。
    pub life: f32,
}

/// 左下系统日志一行。新条目顶部 push，旧的随 age 增长被 UI 渲染成 dim/faded。
#[allow(dead_code)]
pub struct LogLine {
    pub text: String,
    pub age: f32,
}

/// 每帧由 GameApp 现场拼装的 UI 输入快照。
/// 用引用持有可变长字段，避免不必要的克隆。
/// 部分字段当前未被任何 UiElement 消费——它们是为 HUD 翻译预留的数据通道，
/// 等 PA 的 HTML 设计稿敲定后会被新元素读取。
#[allow(dead_code)]
#[derive(Copy, Clone)]
pub struct UiContext<'a> {
    pub viewport: Vec2,
    pub energy_ratio: f32,
    /// 离散能量段数 0..=5（满圆数）；UI 用它决定哪几个圆点 .full / .empty。
    pub energy_segments: u32,
    pub phase: u32,
    pub fire_state: crate::sonar::system::FireVisualState,
    pub warnings: &'a [Warning],
    pub system_log: &'a [LogLine],
}

impl<'a> UiContext<'a> {
    pub fn new(
        viewport: Vec2,
        energy_ratio: f32,
        fire_state: crate::sonar::system::FireVisualState,
        phase: u32,
        warnings: &'a [Warning],
        system_log: &'a [LogLine],
    ) -> Self {
        // 满圆数 = ceil(ratio * 5)，0..=5；ratio 极小时仍允许显示 0（全空提示能量耗尽）。
        let energy_segments = (energy_ratio * 5.0).ceil().clamp(0.0, 5.0) as u32;
        Self {
            viewport,
            energy_ratio,
            energy_segments,
            phase,
            fire_state,
            warnings,
            system_log,
        }
    }
}

pub trait UiElement {
    fn update(&mut self, ctx: &UiContext<'_>, theme: &Theme);
    fn draw(&self, ctx: &UiContext<'_>, theme: &Theme);
}

pub struct Ui {
    theme: Theme,
    elements: Vec<Box<dyn UiElement>>,
}

impl Ui {
    pub fn new() -> Self {
        let mut ui = Self {
            theme: Theme::default(),
            elements: Vec::new(),
        };

        ui.elements.push(Box::new(EnergyBar::new()));
        ui.elements.push(Box::new(GunWidget::new()));
        ui.elements.push(Box::new(Crosshair::new()));
        ui
    }

    pub fn update(&mut self, ctx: &UiContext<'_>) {
        for element in &mut self.elements {
            element.update(ctx, &self.theme);
        }
    }

    pub fn draw(&self, ctx: &UiContext<'_>) {
        for element in &self.elements {
            element.draw(ctx, &self.theme);
        }
    }
}

struct EnergyBar {
    anchor: Anchor,
    offset: Vec2,
    fill: f32,
}

impl EnergyBar {
    fn new() -> Self {
        Self {
            anchor: Anchor::BottomLeft,
            offset: vec2(36.0, -40.0),
            fill: 1.0,
        }
    }
}

impl UiElement for EnergyBar {
    fn update(&mut self, ctx: &UiContext, _theme: &Theme) {
        self.fill = ctx.energy_ratio;
    }

    fn draw(&self, ctx: &UiContext, theme: &Theme) {
        let pos = anchored_position(ctx.viewport, self.anchor, theme.energy_size, self.offset);
        draw_rectangle(pos.x, pos.y, theme.energy_size.x, theme.energy_size.y, theme.energy_bg);
        draw_rectangle(
            pos.x + 2.0,
            pos.y + 2.0,
            (theme.energy_size.x - 4.0) * self.fill,
            theme.energy_size.y - 4.0,
            theme.energy_fill,
        );
        draw_rectangle_lines(pos.x, pos.y, theme.energy_size.x, theme.energy_size.y, 1.5, theme.crosshair);
    }
}

struct GunWidget {
    anchor: Anchor,
    offset: Vec2,
    glow: f32,
}

impl GunWidget {
    fn new() -> Self {
        Self {
            anchor: Anchor::BottomRight,
            offset: vec2(-24.0, -18.0),
            glow: 0.0,
        }
    }
}

impl UiElement for GunWidget {
    fn update(&mut self, ctx: &UiContext, _theme: &Theme) {
        self.glow = ctx.fire_state.muzzle_flash;
    }

    fn draw(&self, ctx: &UiContext, theme: &Theme) {
        let pos = anchored_position(ctx.viewport, self.anchor, theme.gun_size, self.offset);
        let barrel = Rect::new(pos.x + theme.gun_size.x * 0.35, pos.y + 10.0, theme.gun_size.x * 0.4, theme.gun_size.y * 0.58);
        let handle = Rect::new(pos.x + theme.gun_size.x * 0.18, pos.y + theme.gun_size.y * 0.46, theme.gun_size.x * 0.52, theme.gun_size.y * 0.44);
        draw_rectangle(handle.x, handle.y, handle.w, handle.h, theme.gun_body);
        draw_rectangle(barrel.x, barrel.y, barrel.w, barrel.h, theme.gun_body);
        let glow_color = Color::new(
            theme.gun_glow.r,
            theme.gun_glow.g,
            theme.gun_glow.b,
            0.3 + self.glow * 0.7,
        );
        draw_circle(pos.x + theme.gun_size.x * 0.55, pos.y + theme.gun_size.y * 0.22, 14.0 + self.glow * 3.0, glow_color);
    }
}

struct Crosshair {
    anchor: Anchor,
    offset: Vec2,
}

impl Crosshair {
    fn new() -> Self {
        Self {
            anchor: Anchor::Center,
            offset: Vec2::ZERO,
        }
    }
}

impl UiElement for Crosshair {
    fn update(&mut self, _ctx: &UiContext, _theme: &Theme) {}

    fn draw(&self, ctx: &UiContext, theme: &Theme) {
        let size = vec2(theme.crosshair_size, theme.crosshair_size);
        let pos = anchored_position(ctx.viewport, self.anchor, size, self.offset);
        let center = pos + size * 0.5;
        let gap = 4.0;
        let arm = theme.crosshair_size;
        draw_line(center.x - gap - arm, center.y, center.x - gap, center.y, theme.line_thickness, theme.crosshair);
        draw_line(center.x + gap, center.y, center.x + gap + arm, center.y, theme.line_thickness, theme.crosshair);
        draw_line(center.x, center.y - gap - arm, center.x, center.y - gap, theme.line_thickness, theme.crosshair);
        draw_line(center.x, center.y + gap, center.x, center.y + gap + arm, theme.line_thickness, theme.crosshair);
    }
}

fn anchored_position(viewport: Vec2, anchor: Anchor, size: Vec2, offset: Vec2) -> Vec2 {
    let base = match anchor {
        Anchor::TopLeft => vec2(0.0, 0.0),
        Anchor::TopCenter => vec2(viewport.x * 0.5 - size.x * 0.5, 0.0),
        Anchor::TopRight => vec2(viewport.x - size.x, 0.0),
        Anchor::CenterLeft => vec2(0.0, viewport.y * 0.5 - size.y * 0.5),
        Anchor::Center => vec2(viewport.x * 0.5 - size.x * 0.5, viewport.y * 0.5 - size.y * 0.5),
        Anchor::CenterRight => vec2(viewport.x - size.x, viewport.y * 0.5 - size.y * 0.5),
        Anchor::BottomLeft => vec2(0.0, viewport.y - size.y),
        Anchor::BottomCenter => vec2(viewport.x * 0.5 - size.x * 0.5, viewport.y - size.y),
        Anchor::BottomRight => vec2(viewport.x - size.x, viewport.y - size.y),
    };
    base + offset
}
