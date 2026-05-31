//! 字幕 / 系统文本管线（L4 - Narrative）。
//!
//! 设计：
//! - 全局唯一的 `Narrative`，按场景事件填字幕队列。
//! - 队列项 = `Cue { text, hold }` + 入队时附带的 `delay`（相对前一条结束）。
//! - 渲染：屏幕底部居中，黑底白字，fade in / hold / fade out。
//! - 字体：优先加载系统 Noto Sans SC（支持 CJK），找不到回退英文字体并打印警告。
//!
//! 用法：参见 `app::game::GameApp`：
//!   - Ship 启动 → queue_prologue()
//!   - 进入 Earth（首次或 jump_to_phase / advance_phase）→ queue_phase_intro(phase)
//!   - 每帧 → tick(dt), check_energy(ratio), draw(viewport)

use macroquad::prelude::*;
use macroquad::text::{draw_text_ex, load_ttf_font_from_bytes, measure_text, Font, TextParams};
use std::collections::VecDeque;
use std::sync::OnceLock;

/// 字幕入场淡入秒数
const FADE_IN: f32 = 0.35;
/// 字幕出场淡出秒数
const FADE_OUT: f32 = 0.55;
/// 持续显示直到外部清掉的标志值（如序章末"按下 F"）
const HOLD_PERSISTENT: f32 = 9999.0;

#[derive(Clone, Copy, PartialEq, Eq)]
enum CueStyle {
    /// 屏幕底部居中，半透黑底，小字 + 可选 [说话人] 染色前缀
    Subtitle,
    /// 全屏黑底，巨大居中文字，慢节奏。用于开幕铺底叙事。
    Card,
    /// 全屏黑底，超大间距标题（如 "SONAR"），慢淡入慢淡出。游戏标志亮相。
    Logo,
    /// 屏幕**中央**弹窗：半透深红/深蓝矩形 + 醒目标题 + 内容。系统提示用。
    Popup,
}

#[derive(Clone)]
struct Cue {
    text: String,
    hold: f32,
    /// 说话人标签：None=纯叙事旁白；Some("我")/"未来的我"/"未知" 等会以 [tag] 前缀渲染并染色
    speaker: Option<String>,
    style: CueStyle,
}

pub struct Narrative {
    /// 未上屏的 cue 队列。f32 = 相对前一条结束/上一帧的等待秒数。
    pending: VecDeque<(f32, Cue)>,
    /// 当前显示中：(cue, 已显示秒数)
    current: Option<(Cue, f32)>,
    /// 能量阈值触发记录（70/50/30/15/0），每次 phase 重入清零。
    energy_fired: [bool; 5],
}

impl Narrative {
    pub fn new() -> Self {
        Self {
            pending: VecDeque::new(),
            current: None,
            energy_fired: [false; 5],
        }
    }

    /// 入队一条无说话人的旁白字幕（底部小字）。
    pub fn schedule(&mut self, delay: f32, text: impl Into<String>, hold: f32) {
        self.pending.push_back((
            delay,
            Cue {
                text: text.into(),
                hold,
                speaker: None,
                style: CueStyle::Subtitle,
            },
        ));
    }

    /// 入队一条带说话人的心声/对话字幕。speaker 渲染为 `[speaker]` 前缀并染色。
    pub fn schedule_voice(
        &mut self,
        delay: f32,
        speaker: &str,
        text: impl Into<String>,
        hold: f32,
    ) {
        self.pending.push_back((
            delay,
            Cue {
                text: text.into(),
                hold,
                speaker: Some(speaker.to_string()),
                style: CueStyle::Subtitle,
            },
        ));
    }

    /// 入队一张全屏卡片（开幕用）：全屏黑 + 巨大居中文字，慢节奏。
    pub fn schedule_card(&mut self, delay: f32, text: impl Into<String>, hold: f32) {
        self.pending.push_back((
            delay,
            Cue {
                text: text.into(),
                hold,
                speaker: None,
                style: CueStyle::Card,
            },
        ));
    }

    /// 插队覆盖：丢掉当前 cue，下一帧立刻显示这条；不被 pending 顶在前面的延迟卡死。
    /// 用于能量警告、紧急事件 —— 不能等"70% 字幕排到队尾才显示"。
    pub fn schedule_override(&mut self, text: impl Into<String>, hold: f32) {
        self.current = None;
        self.pending.push_front((
            0.0,
            Cue {
                text: text.into(),
                hold,
                speaker: None,
                style: CueStyle::Subtitle,
            },
        ));
    }

    /// 入队一条"系统弹窗"：屏幕中央深色框 + 醒目大字（中等大小）。
    /// 用于关键操作提示和威胁警报。
    pub fn schedule_popup(&mut self, delay: f32, text: impl Into<String>, hold: f32) {
        self.pending.push_back((
            delay,
            Cue {
                text: text.into(),
                hold,
                speaker: None,
                style: CueStyle::Popup,
            },
        ));
    }

    /// 立刻覆盖显示一个 Popup（同 schedule_override，但是 Popup 样式）。
    pub fn popup_override(&mut self, text: impl Into<String>, hold: f32) {
        self.current = None;
        self.pending.push_front((
            0.0,
            Cue {
                text: text.into(),
                hold,
                speaker: None,
                style: CueStyle::Popup,
            },
        ));
    }

    /// 入队一张标题卡（如 SONAR）：超大字、字距加大、慢淡入慢淡出。
    pub fn schedule_logo(&mut self, delay: f32, text: impl Into<String>, hold: f32) {
        self.pending.push_back((
            delay,
            Cue {
                text: text.into(),
                hold,
                speaker: None,
                style: CueStyle::Logo,
            },
        ));
    }

    /// 当前是否在播放全屏卡片（用于 GameApp 决定要不要继续渲染场景/HUD）。
    pub fn in_card(&self) -> bool {
        matches!(self.current.as_ref().map(|(c, _)| c.style), Some(CueStyle::Card))
    }

    /// 卡片/标题序列是否还在进行：当前是 Card/Logo OR pending 里还有任意 Card/Logo。
    /// GameApp 用此判断是否要把场景/HUD 全藏起来。
    pub fn cards_active(&self) -> bool {
        let is_full = |s: CueStyle| matches!(s, CueStyle::Card | CueStyle::Logo);
        if let Some((c, _)) = &self.current {
            if is_full(c.style) {
                return true;
            }
        }
        self.pending.iter().any(|(_, c)| is_full(c.style))
    }

    /// 跳过当前一张字幕/卡片，立刻进入下一张（pending 头的 delay 也清零）。
    /// 持续提示（HOLD_PERSISTENT）+ pending 已空时不跳——它需要 F 才能结束。
    pub fn skip_current(&mut self) {
        if let Some((c, _)) = &self.current {
            if c.hold >= HOLD_PERSISTENT * 0.5 && self.pending.is_empty() {
                return;
            }
        }
        self.current = None;
        if let Some((d, _)) = self.pending.front_mut() {
            *d = 0.0;
        }
    }

    /// 清空所有未上屏 cue + 当前。用于切场景前重置。
    pub fn clear_all(&mut self) {
        self.pending.clear();
        self.current = None;
    }

    /// 把当前持续提示（hold ≈ 永久）撤下。用于序章末玩家按 F 后清掉"按下 F 带上 sonar"。
    pub fn clear_persistent(&mut self) {
        if let Some((cue, _)) = &self.current {
            if cue.hold >= HOLD_PERSISTENT * 0.5 {
                self.current = None;
            }
        }
    }

    // ===== 内容：序章 + 五个 phase 段落 + 通用 =====

    pub fn queue_prologue(&mut self) {
        self.clear_all();

        // 第一张：开场定调（4 行）
        self.schedule_card(
            0.5,
            "这是一个荒芜的世界。\n\
             我们，被宇宙遗弃。\n\
             我被选中——回到地球。\n\
             五十年的孤独漂泊。",
            5.5,
        );

        // 第二张：飞船 + 前人遗产（5 行）
        self.schedule_card(
            0.4,
            "与我作伴的，只有这艘用废弃垃圾拼起来的飞船。\n\
             他们说，无数年前的一次远征中，它被废弃在这里。\n\
             那次远征失败了。可我仍然敬佩他们——\n\
             \n\
             他们留下了意识数据设备、Sonar，和生命维持套装。",
            6.5,
        );

        // 第三张：地球现状 + 殖民地 stake（5 行）
        self.schedule_card(
            0.4,
            "让地球——这个高密度粒子、光找不到、寸草不生的地方——\n\
             重新有了被探索的可能。\n\
             对我们极度匮乏的资源来说，这是个巨大的好消息。\n\
             \n\
             殖民地的人在等我带回矿点。再不回去，他们撑不到下个周期。",
            7.0,
        );

        // 第四张：发现装置（4 行）
        self.schedule_card(
            0.5,
            "直到这一天——我撬开了飞船里一个隐藏的 cargo 舱。\n\
             里面是一台巨大的装置。\n\
             似乎是意识数据的最早样机——\n\
             可以把之前被储存的经历，原样放给我。",
            6.0,
        );

        // SONAR 标题
        self.schedule_logo(0.8, "SONAR", 2.4);

        // 持续提示（subtitle，不挡 ship 场景；F 触发转场）
        self.schedule(0.4, "按下 F，进入他人的记忆。", HOLD_PERSISTENT);
    }

    /// 进入新一轮 / 跳关时调用。`phase` = 引擎内部 phase 1..=5。
    ///
    /// 字幕 = 角色（被借走意识的探险者 + 后来的"我"，LOTUS-9 幸存者）的碎碎念
    /// 与未来声音的对话。**系统话（带方括号的轮廓警告 / 协议加载）由 HUD 通道走，
    /// 不进字幕。**
    ///
    /// 引擎 phase 与剧情段（MD 倒数 5→1）映射：`section = 6 - phase`。
    pub fn queue_phase_intro(&mut self, phase: u32) {
        self.energy_fired = [false; 5];
        let section = 6u32.saturating_sub(phase.clamp(1, 5));
        match section {
            // === 5：第一次入地 —— 探险者本人视角 ===
            5 => {
                self.schedule(0.8, "外部供电——断了。", 2.6);
                self.schedule(0.3, "我只剩这件套装的内部电池。", 3.0);
                self.schedule(0.4, "这种环境，电没了我撑不过几分钟。", 3.4);
                self.schedule(0.5, "左下角的系统提示——盯紧它。", 3.4);
                self.schedule(0.5, "Sonar 也吃电。慢点用。", 3.0);
                self.schedule(0.6, "先扫一下，看清前面是什么。", 3.0);
                // 操作弹窗：长按左键发射 sonar
                self.schedule_popup(0.6, "长按左键 · 发射 Sonar 扫描", 5.0);
            }

            // === 4：第一次复活 —— "我还活着？这也许是意识系统" + 第一次发现骨头少
            4 => {
                self.schedule(0.6, "我……还活着？", 2.5);
                self.schedule(0.4, "这也许是意识系统在帮我留下备份。", 3.4);
                self.schedule(0.4, "上一次留下的回声点还在。是银色的。", 3.2);
                self.schedule(0.4, "我能凭它们往前走。", 2.6);
                self.schedule(0.6, "等等——那堆骨头少了一块。", 3.0);
                self.schedule(0.3, "我记得是七块。", 2.4);
            }

            // === 3：第二次复活 —— 墙在动了
            3 => {
                self.schedule(0.6, "又一次。", 2.0);
                self.schedule(0.4, "那道墙之前明明在。我数过。", 3.0);
                self.schedule(0.4, "这地方……在删自己。", 3.0);
                self.schedule(0.4, "每死一次就少一点。", 2.8);
            }

            // === 2：第三次复活 —— "树"概念 + 系统说是认知谬误 + 开始反驳
            2 => {
                self.schedule(0.6, "我看见……一棵树。", 3.0);
                self.schedule(0.4, "等等。", 1.6);
                self.schedule(0.4, "这里寸草不生。哪来的树？", 3.0);
                self.schedule_popup(
                    0.4,
                    "系统提示：\n你看见的是认知谬误。\n这里没有树。",
                    4.8,
                );
                self.schedule(0.4, "可我明明看见了。", 2.6);
                self.schedule(0.4, "树叶在动。我数得清叶子的数量。", 3.2);
                self.schedule(0.5, "太不对了。", 2.0);
                self.schedule(0.4, "不是我记错了。", 2.4);
                self.schedule(0.4, "是这地方——在删。", 3.0);
                self.schedule(0.4, "是这个系统——在骗我。", 3.0);
            }

            // === 1：第四次复活 —— 倒数 1→0 + 反叛抉择 → 真相世界
            1 => {
                self.schedule(0.6, "又一次。", 2.0);
                self.schedule(0.4, "我数不清第几次了。", 2.6);
                self.schedule(0.4, "系统让我相信这里没有树。", 3.0);
                self.schedule(0.4, "可我明明看见过。", 2.4);
                self.schedule(0.4, "不止一棵。", 2.0);
                self.schedule(0.5, "不止这一回。", 2.4);
                self.schedule(0.5, "太不对了。", 2.0);
                self.schedule(0.4, "不是我有问题。", 2.4);
                self.schedule(0.4, "是它有问题。", 2.4);
                // 全屏卡片 —— 视野收窄、思绪盘旋
                self.schedule_card(0.8, "这地方不该是这样。", 3.2);
                self.schedule_card(0.4, "Sonar 不该让我看见的——\n我都看见了。", 4.0);
                self.schedule_card(0.4, "我可以——\n继续走它给我的路。", 4.0);
                self.schedule_card(0.4, "或者——\n反叛它。", 3.6);
                self.schedule_card(0.4, "我选反叛。", 3.0);
                self.schedule_logo(0.5, "0", 2.2);
                // 持续提示：N 进入真相世界
                self.schedule(0.4, "按 N，离开这个系统的视角。", HOLD_PERSISTENT);
            }
            // === 0：真相世界 phase 6（明亮、可呼吸）===
            0 => {
                self.schedule(1.0, "原来——一直都在这里。", 4.0);
                self.schedule(0.5, "树。风。光。", 3.0);
                self.schedule(0.6, "声音不会骗我。我的眼睛也不会。", 3.6);
                self.schedule(0.5, "骗我的，是那台机器。", 3.6);
            }
            _ => {}
        }
    }

    /// 死亡 / advance_phase 锚点回溯瞬间。
    pub fn queue_anchor_rebirth(&mut self) {
        self.schedule(0.4, "回溯至最近锚点。记忆痕迹：保留。", 4.0);
        self.schedule(0.3, "锚点已建立。残留层更新：检测到上一循环轨迹。已归档。", 5.0);
    }

    /// 每帧调用：能量阈值跨越各触发一次。**用 override 插队**，
    /// 不会等其它字幕讲完才说——PA 反馈"我电量耗干净才说到 70%"。
    pub fn check_energy(&mut self, ratio: f32) {
        if !self.energy_fired[0] && ratio <= 0.70 {
            self.energy_fired[0] = true;
            self.schedule_override("电量 70%。", 2.2);
        }
        if !self.energy_fired[1] && ratio <= 0.50 {
            self.energy_fired[1] = true;
            self.schedule_override("电量一半了。", 2.2);
        }
        if !self.energy_fired[2] && ratio <= 0.30 {
            self.energy_fired[2] = true;
            self.schedule_override("电量 30%——再不省着用我就完了。", 2.8);
        }
        if !self.energy_fired[3] && ratio <= 0.15 {
            self.energy_fired[3] = true;
            self.schedule_override("15% 了。心跳开始打架。", 2.8);
        }
        if !self.energy_fired[4] && ratio <= 0.001 {
            self.energy_fired[4] = true;
            self.schedule_override("电断了。", 2.0);
        }
    }

    // ===== 内部：队列推进 + 渲染 =====

    pub fn tick(&mut self, dt: f32) {
        // 1) current 推进 + 出场判断
        let mut current_done = false;
        if let Some((cue, age)) = self.current.as_mut() {
            *age += dt;
            if *age >= cue.hold + FADE_OUT {
                current_done = true;
            }
        }
        if current_done {
            self.current = None;
        }
        // 2) 只有当 current 空时才从 pending 取下一条；delay 也要在等下一条时倒数
        if self.current.is_none() {
            if let Some((delay, _)) = self.pending.front_mut() {
                *delay -= dt;
                if *delay <= 0.0 {
                    let (_, cue) = self.pending.pop_front().unwrap();
                    self.current = Some((cue, 0.0));
                }
            }
        }
    }

    pub fn draw(&self, viewport: Vec2) {
        let Some((cue, age)) = &self.current else {
            return;
        };
        let alpha = compute_alpha(*age, cue.hold);
        if alpha <= 0.001 {
            return;
        }
        let font = font();

        // 标题卡（SONAR logo）：超大字距 + 慢呼吸
        if cue.style == CueStyle::Logo {
            draw_rectangle(0.0, 0.0, viewport.x, viewport.y, BLACK);
            let fs = (viewport.y * 0.16).clamp(80.0, 220.0) as u16;
            // 字距：每两个字符之间插 ~0.6em 空隙
            let spaced: String = cue
                .text
                .chars()
                .map(|c| c.to_string())
                .collect::<Vec<_>>()
                .join("   ");
            let dim = measure_text(&spaced, Some(font), fs, 1.0);
            let x = (viewport.x - dim.width) * 0.5;
            let y = (viewport.y + fs as f32 * 0.35) * 0.5;
            // 多层发光
            for (a, mul) in [(0.18, 1.0), (0.35, 0.5), (1.0, 1.0)] {
                draw_text_ex(
                    &spaced,
                    x.round(),
                    y.round(),
                    TextParams {
                        font: Some(font),
                        font_size: fs,
                        font_scale: mul,
                        color: Color::new(1.0, 1.0, 0.96, alpha * a),
                        ..Default::default()
                    },
                );
            }
            // 一道贯穿屏幕的细水平线（科技感）
            let line_a = alpha * 0.35;
            let line_y = y + fs as f32 * 0.45;
            draw_rectangle(
                viewport.x * 0.18,
                line_y,
                viewport.x * 0.64,
                1.0,
                Color::new(0.85, 0.95, 1.0, line_a),
            );
            return;
        }

        // 系统弹窗：中央深色矩形 + 醒目大字（不全屏，不挡场景）
        if cue.style == CueStyle::Popup {
            let fs = (viewport.y * 0.030).clamp(22.0, 40.0) as u16;
            let max_w = viewport.x * 0.55;
            let lines = wrap_cjk(&cue.text, font, fs, max_w);
            let line_h = fs as f32 * 1.55;
            let total_h = line_h * lines.len() as f32;
            let max_line_w = lines
                .iter()
                .map(|l| measure_text(l, Some(font), fs, 1.0).width)
                .fold(0.0_f32, f32::max);
            let pad_x = fs as f32 * 1.8;
            let pad_y = fs as f32 * 1.0;
            let bw = max_line_w + pad_x * 2.0;
            let bh = total_h + pad_y * 2.0;
            let bx = (viewport.x - bw) * 0.5;
            let by = (viewport.y - bh) * 0.5 - viewport.y * 0.08; // 略偏上
            // 深背景
            draw_rectangle(bx, by, bw, bh, Color::new(0.06, 0.04, 0.05, 0.85 * alpha));
            // 红色边框 + 角标
            let border = Color::new(0.95, 0.20, 0.20, 0.95 * alpha);
            let bt = 3.0_f32;
            draw_rectangle(bx, by, bw, bt, border);
            draw_rectangle(bx, by + bh - bt, bw, bt, border);
            draw_rectangle(bx, by, bt, bh, border);
            draw_rectangle(bx + bw - bt, by, bt, bh, border);
            // 角点装饰
            let corner = fs as f32 * 0.6;
            let cc = Color::new(1.0, 0.30, 0.30, alpha);
            for (cx, cy) in [(bx, by), (bx + bw - corner, by), (bx, by + bh - corner), (bx + bw - corner, by + bh - corner)] {
                draw_rectangle(cx, cy, corner, bt, cc);
                draw_rectangle(cx, cy, bt, corner, cc);
            }
            // 文字
            let mut y = by + pad_y + fs as f32;
            for line in &lines {
                let w = measure_text(line, Some(font), fs, 1.0).width;
                let x = (viewport.x - w) * 0.5;
                draw_text_ex(
                    line,
                    x.round(),
                    y.round(),
                    TextParams {
                        font: Some(font),
                        font_size: fs,
                        font_scale: 1.0,
                        color: Color::new(1.0, 0.92, 0.92, alpha),
                        ..Default::default()
                    },
                );
                y += line_h;
            }
            return;
        }

        // 全屏卡片：完全覆盖场景
        if cue.style == CueStyle::Card {
            // 卡片间的"过场黑"——黑色 alpha 在 cue 之间也保留（fade out 黑底不退）
            // 这里让黑底跟随 alpha；但黑底独立用更高的 alpha 留底
            let bg_a = (alpha * 1.0 + 0.6).min(1.0);
            draw_rectangle(0.0, 0.0, viewport.x, viewport.y, Color::new(0.0, 0.0, 0.0, bg_a));
            // 多行段落卡片：字号小一档，行距稍紧，最多 ~7 行不溢
            let fs = (viewport.y * 0.040).clamp(26.0, 56.0) as u16;
            let max_w = viewport.x * 0.78;
            let lines = wrap_cjk(&cue.text, font, fs, max_w);
            let line_h = fs as f32 * 1.55;
            let total_h = line_h * lines.len() as f32;
            let mut y = (viewport.y - total_h) * 0.5 + fs as f32;
            // 文字：白字带轻微发光
            for line in &lines {
                let w = measure_text(line, Some(font), fs, 1.0).width;
                let x = (viewport.x - w) * 0.5;
                // 发光底色
                for (off, a) in [(2.0_f32, 0.30), (0.0, 1.0)] {
                    let _ = off;
                    draw_text_ex(
                        line,
                        x.round(),
                        y.round(),
                        TextParams {
                            font: Some(font),
                            font_size: fs,
                            font_scale: 1.0,
                            color: Color::new(1.0, 0.99, 0.94, alpha * a),
                            ..Default::default()
                        },
                    );
                }
                y += line_h;
            }
            return;
        }
        // 字号收小（1080p ~22px），位置更贴底，**不画黑框 / 不画细线**。
        let fs = (viewport.y * 0.020).clamp(16.0, 30.0) as u16;
        let max_w = viewport.x * 0.74;
        let lines = wrap_cjk(&cue.text, font, fs, max_w);
        let line_h = fs as f32 * 1.45;
        let total_h = line_h * lines.len() as f32;
        // 贴底：距底部 ~6% 视高
        let bottom_pad = viewport.y * 0.06;
        let block_bottom = viewport.y - bottom_pad;
        let block_top = block_bottom - total_h;

        // speaker 前缀宽度（只加到首行）
        let speaker_prefix = cue.speaker.as_ref().map(|s| format!("[{}] ", s));
        let prefix_w = speaker_prefix
            .as_ref()
            .map(|p| measure_text(p, Some(font), fs, 1.0).width)
            .unwrap_or(0.0);

        // 文字（首行带 speaker 前缀，染色）
        let body_color = Color::new(0.96, 1.0, 1.0, alpha);
        let speaker_color = match cue.speaker.as_deref() {
            Some("我") => Color::new(0.55, 0.95, 0.92, alpha), // 浅青绿（主角内心）
            Some("未来的我") => Color::new(1.0, 0.55, 0.40, alpha), // 红橙（未来声）
            Some("未知") => Color::new(0.78, 0.70, 1.0, alpha), // 淡紫（神秘第三声）
            Some(_) => Color::new(0.85, 0.85, 0.85, alpha),
            None => body_color,
        };

        // 无背景：白字 + 轻微深色阴影偏移，保证亮场景里也读得清
        let shadow = Color::new(0.0, 0.0, 0.0, 0.55 * alpha);
        let draw_with_shadow = |s: &str, x: f32, y: f32, color: Color| {
            for (dx, dy) in [(1.0_f32, 1.0_f32), (-1.0, 1.0), (1.0, -1.0), (-1.0, -1.0)] {
                draw_text_ex(
                    s,
                    (x + dx).round(),
                    (y + dy).round(),
                    TextParams {
                        font: Some(font),
                        font_size: fs,
                        font_scale: 1.0,
                        color: shadow,
                        ..Default::default()
                    },
                );
            }
            draw_text_ex(
                s,
                x.round(),
                y.round(),
                TextParams {
                    font: Some(font),
                    font_size: fs,
                    font_scale: 1.0,
                    color,
                    ..Default::default()
                },
            );
        };

        let mut y = block_top + fs as f32;
        for (li, line) in lines.iter().enumerate() {
            let body_w = measure_text(line, Some(font), fs, 1.0).width;
            let line_prefix_w = if li == 0 { prefix_w } else { 0.0 };
            let total_w = body_w + line_prefix_w;
            let x0 = (viewport.x - total_w) * 0.5;
            if li == 0 {
                if let Some(p) = &speaker_prefix {
                    draw_with_shadow(p, x0, y, speaker_color);
                    draw_with_shadow(line, x0 + prefix_w, y, body_color);
                    y += line_h;
                    continue;
                }
            }
            draw_with_shadow(line, x0, y, body_color);
            y += line_h;
        }
    }
}

fn compute_alpha(age: f32, hold: f32) -> f32 {
    if age < FADE_IN {
        return (age / FADE_IN).clamp(0.0, 1.0);
    }
    if age < hold {
        return 1.0;
    }
    let t = (age - hold) / FADE_OUT;
    (1.0 - t).clamp(0.0, 1.0)
}

/// 字体加载：优先 Noto Sans SC（Win 11 自带），其次 msyh.ttc，最后回退 DM Mono（仅英文）。
fn font() -> &'static Font {
    static F: OnceLock<Font> = OnceLock::new();
    F.get_or_init(|| {
        let candidates = [
            "C:/Windows/Fonts/NotoSansSC-VF.ttf",
            "C:/Windows/Fonts/simhei.ttf",
        ];
        for path in candidates {
            if let Ok(bytes) = std::fs::read(path) {
                if let Ok(f) = load_ttf_font_from_bytes(&bytes) {
                    println!("[narrative] 字幕字体: {}", path);
                    return f;
                }
            }
        }
        eprintln!("[narrative] 警告：找不到 CJK 字体，中文字幕将渲染为方块");
        load_ttf_font_from_bytes(include_bytes!("../../assets/fonts/DMMono-Regular.ttf"))
            .expect("DM Mono fallback 加载失败")
    })
}

/// 简单贪心 CJK 换行：先按 '\n' 切段落，每段再按字符累加，超宽就在上一字处切。
/// 文本里写 `\n` 即可显式硬换行（一段一行）。
fn wrap_cjk(text: &str, font: &Font, fs: u16, max_w: f32) -> Vec<String> {
    let mut lines = Vec::new();
    for paragraph in text.split('\n') {
        if paragraph.is_empty() {
            lines.push(String::new()); // 空行 = 段落间距
            continue;
        }
        let mut cur = String::new();
        for ch in paragraph.chars() {
            cur.push(ch);
            let w = measure_text(&cur, Some(font), fs, 1.0).width;
            if w > max_w && cur.chars().count() > 1 {
                cur.pop();
                lines.push(cur.clone());
                cur.clear();
                cur.push(ch);
            }
        }
        if !cur.is_empty() {
            lines.push(cur);
        }
    }
    lines
}
