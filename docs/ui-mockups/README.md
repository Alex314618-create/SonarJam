# UI 设计稿（HTML 交付）

PA 用 HTML/CSS 写 UI 设计稿放这里，架构师读了翻译成 Rust UI 元素。

## 工作流

1. PA 写/改 `*.html` 放在本目录
2. PA 在浏览器里调到自己满意
3. PA 告诉架构师"看 `xxx.html`"
4. 架构师读 HTML/CSS、把它注册成 `UiElement` 进 `src/ui/`
5. 数据接 `UiContext`（能量、状态、phase 等）

## HTML 写法约定

- **位置**：用 CSS `position: absolute` + `top/left/right/bottom`。在注释里说屏幕哪个锚点（如 `<!-- anchor: center -->` 或 `<!-- anchor: bottom-right offset (-20, -20) -->`）
- **状态**：用 class 表达不同状态，例如能量圆的 `<div class="cell full">` / `<div class="cell empty">`。运行时按需切 class
- **颜色/尺寸**：CSS 直接读，我抄过去
- **动画**：用 CSS keyframes 或注释说明，我用 Rust 实现 lerp
- **可读性**：每个独立 UI 元素一段，注释说它绑什么数据（如 `<!-- data: energy_ratio 0..1 -->`）

## 数据接口（当前 UiContext 暴露的）

| 字段 | 类型 | 含义 |
|------|------|------|
| `viewport` | `Vec2` | 窗口宽高（自动） |
| `energy_ratio` | `f32` 0..1 | 能量比例 |
| `fire_state.muzzle_flash` | `f32` 0..1 | 发射时的脉冲，自然衰减 |

需要新的数据接口（如 `phase`、`warnings`、`time_in_phase`）告诉架构师，会加进 UiContext。

## 示例

- `crosshair_energy_warnings.html` —— PA 提议的十字准星 + 5 能量圆 + 警告文字
