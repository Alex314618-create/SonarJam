# Phase 3 树泄漏事件实现说明

> Title：Phase 3 树泄漏事件实现说明
>
> Document Level：L3
>
> Status：Draft
>
> Scope：定义 `54321` 中第 3 轮“靠近树后真实树突然显形、系统标记为 bug、随后圆柱体覆盖树”的内容命名、运行时实现、触发流程与验收标准
>
> Upstream Refs：`L0-无技术创意文档.md`, `L0-感知反转-镜山备忘.md`, `L1-技术设计总纲.md`, `L2-02-内容管线设计.md`, `L3-02-Blender作者规范.md`
>
> Target Asset：`_temp_Blender/更新与交付/3.blend`

## 1. 设计目标

Phase 3 中，玩家靠近一棵真实世界里的树时，声呐系统短暂“漏出”真实世界：

1. 玩家接近树附近触发点。
2. 树的轮廓突然以红色像素点显形。
3. HUD / 系统提示标记该现象为 bug 或意识异常。
4. 极短延迟后，系统生成一个圆柱体覆盖这棵树。
5. 覆盖完成后，玩家后续再扫描，只能扫到圆柱体/遮蔽物，而不再直接看到树。

这个事件的意义不是普通 jump scare，而是第一次明确告诉玩家：声呐系统会主动抹除真实世界。

## 2. 核心原则

必须继续遵守项目架构铁律：

**真实世界层不可被篡改，系统只篡改感知结果层。**

因此：

- 树本身属于真实世界 `R_`。
- 树默认不参与声呐 raycast。
- 红色显形不是树变成 phantom，而是一次“真实层泄漏采样”。
- 圆柱体不是美术上凭空替换树，而是系统在感知层里激活一个遮蔽物。

不要把树直接命名为 `P_`，否则它从加载开始就会被声呐扫到，无法表达“突然泄漏”。

不要把圆柱体直接命名为 `C_`，否则它从 phase 3 开始就已经存在于声呐世界里，无法表达“系统随后覆盖”。

## 3. Blender 命名契约

在 `3.blend` 中，建议使用以下对象命名。

### 3.1 真实树

```text
R_leak_tree_01
```

用途：

- 真实树模型。
- 属于真实世界层。
- 可参与真实渲染 / 深度 / 后期真相阶段。
- 默认不参与声呐 raycast。

要求：

- 保留在真实位置。
- Apply Transform。
- 不要使用 `P_` 或 `C_` 前缀。

### 3.2 触发点

```text
M_leak_tree_01
```

用途：

- 玩家靠近此 marker 后触发泄漏事件。
- 运行时读取它的世界坐标。

建议：

- 放在玩家第一次应该注意到树的位置附近。
- 触发半径由代码配置，初始建议 `5m - 8m`。
- Marker 的朝向暂不重要。

### 3.3 系统遮蔽圆柱体

```text
H_cover_tree_01
```

用途：

- 事件触发后才激活的系统遮蔽物。
- 激活后参与声呐 raycast。
- 激活后参与深度遮挡。
- 可选：参与玩家碰撞，按玩法需要决定。

命名前缀说明：

- `H_` 表示 Hidden / Held / Hot-activated mesh。
- 当前运行时尚不支持 `H_`，需要架构师在导入器里新增该分类。
- 不建议命名成 `C_cover_tree_01`，因为 `C_` 会开局立即进入系统所见层。

### 3.4 可选触发体

如果 marker 距离触发不够精确，可以额外建：

```text
V_leak_tree_01
```

用途：

- 体积触发区。
- 玩家进入体积后触发泄漏。

当前建议 MVP 先用 `M_leak_tree_01 + 半径检测`，实现更快。

## 4. 运行时数据需求

当前 `src/content/mod.rs` 会把网格扁平化，并且只保留部分分类结果。要实现该事件，需要保留对象身份。

建议新增以下运行时结构：

```rust
pub struct NamedMesh {
    pub name: String,
    pub tris: Vec<[Vec3; 3]>,
}

pub struct Marker {
    pub name: String,
    pub position: Vec3,
}
```

`LoadedLevel` 建议增加：

```rust
pub leak_meshes: Vec<NamedMesh>,   // R_leak_*
pub hidden_meshes: Vec<NamedMesh>, // H_*
pub markers: Vec<Marker>,         // M_*
```

最低限度只需要支持：

- 查找 `R_leak_tree_01`
- 查找 `H_cover_tree_01`
- 查找 `M_leak_tree_01`

## 5. World 层职责

`World` 需要支持“动态激活隐藏遮蔽物”。

建议新增能力：

```rust
impl World {
    pub fn marker_position(&self, name: &str) -> Option<Vec3>;
    pub fn sample_leak_mesh(&self, name: &str, count: usize, color: Color) -> Vec<Point>;
    pub fn activate_hidden_mesh(&mut self, name: &str);
}
```

激活 `H_cover_tree_01` 后：

- 它应进入声呐 raycast 源。
- 它应进入深度预通道。
- 如需要阻挡玩家，也可进入碰撞源。

注意：激活圆柱体后需要调用：

```rust
self.renderer.reload_world();
```

否则渲染器缓存的 depth buffer 不会重传。

## 6. Sonar 层职责

`Sonar` 需要支持一次性注入特殊颜色点云。

建议新增方法：

```rust
pub fn seed_event_points(&mut self, points: &[Point]);
```

这批点：

- 不触发枪口细线。
- 不消耗能量。
- origin 可使用 `PointOrigin::World`。
- 颜色固定红色，建议与 Danger 红区分不大，但更偏系统告警：

```rust
Color::new(1.0, 0.12, 0.10, 1.0)
```

采样方式：

- 对 `R_leak_tree_01` 的三角形按面积采样。
- 初始数量建议 `2000 - 8000`，根据树大小调。
- 点位可加入轻微 jitter，让它看起来像系统异常显形，而不是完整模型渲染。

## 7. GameApp 事件状态机

在 `GameApp` 中新增一个事件状态。

```rust
enum LeakTreeState {
    Idle,
    RedReveal { t: f32 },
    Covered,
}
```

`GameApp` 增加字段：

```rust
leak_tree_state: LeakTreeState,
```

只在 `phase == 3` 且 `mode == Earth` 时启用。

推荐流程：

```rust
const LEAK_TREE_TRIGGER_RADIUS: f32 = 6.0;
const LEAK_TREE_REVEAL_DURATION: f32 = 0.45;
const LEAK_TREE_POINTS: usize = 5000;

fn tick_phase3_tree_leak(&mut self, dt: f32) {
    if self.phase != 3 || self.mode != Mode::Earth {
        return;
    }

    match self.leak_tree_state {
        LeakTreeState::Idle => {
            let Some(marker) = self.worlds[self.current_idx].marker_position("M_leak_tree_01") else {
                return;
            };
            let d = (self.player.position() - marker).length();
            if d <= LEAK_TREE_TRIGGER_RADIUS {
                let points = self.worlds[self.current_idx].sample_leak_mesh(
                    "R_leak_tree_01",
                    LEAK_TREE_POINTS,
                    Color::new(1.0, 0.12, 0.10, 1.0),
                );
                self.sonar.seed_event_points(&points);
                self.push_warning("CONSCIOUSNESS PATTERN ERROR");
                self.push_comm("SYSTEM", "\"visual artifact detected. correcting.\"");
                self.leak_tree_state = LeakTreeState::RedReveal { t: 0.0 };
            }
        }
        LeakTreeState::RedReveal { ref mut t } => {
            *t += dt;
            if *t >= LEAK_TREE_REVEAL_DURATION {
                self.worlds[self.current_idx].activate_hidden_mesh("H_cover_tree_01");
                self.renderer.reload_world();
                self.push_warning("UNAUTHORIZED OPTICAL TRACE SUPPRESSED");
                self.leak_tree_state = LeakTreeState::Covered;
            }
        }
        LeakTreeState::Covered => {}
    }
}
```

该函数应在 Earth 模式每帧更新中调用，位置建议在玩家移动与贴地之后、声呐更新之前。

## 8. HUD / 文案建议

红色显形瞬间：

```text
CONSCIOUSNESS PATTERN ERROR
```

系统纠正瞬间：

```text
UNAUTHORIZED OPTICAL TRACE SUPPRESSED
```

通讯占位：

```text
SYSTEM: "visual artifact detected. correcting."
ANCHOR: "...echo? your feed just spiked."
```

注意：系统文案应假装这是 bug，而不是承认“这是真树”。

## 9. 音画节奏

推荐节奏：

1. `t = 0.00s`：玩家进入触发半径。
2. `t = 0.00s`：树轮廓红色点云爆出。
3. `t = 0.05s`：系统警告出现，音频播放 `system_notification`。
4. `t = 0.30 - 0.50s`：圆柱体激活，盖住树。
5. `t = 0.50s+`：玩家再次声呐扫描，只能看到圆柱体。

圆柱体出现可以不做复杂动画。MVP 中直接激活即可；如果时间允许，可以在 `0.15s` 内从地面快速升起。

## 10. 验收标准

功能验收：

1. Phase 1 / 2 不触发该事件。
2. Phase 3 玩家靠近 `M_leak_tree_01` 后，树红色点云出现。
3. 红色树轮廓不是开局就可见。
4. 系统警告出现。
5. 约 `0.45s` 后圆柱体覆盖树。
6. 圆柱体激活后，后续声呐扫描能扫到圆柱体。
7. 事件只触发一次，不反复刷点。
8. 切换到下一轮后不应把该事件状态错误带到其他 phase。

架构验收：

1. `R_leak_tree_01` 仍属于真实世界层。
2. `H_cover_tree_01` 只在事件后加入系统感知层。
3. 不通过修改真实几何来表达遮蔽。
4. 不把树直接改成永久 `P_` phantom。

内容验收：

1. `3.blend` 中对象命名稳定。
2. `R_leak_tree_01` / `M_leak_tree_01` / `H_cover_tree_01` 均存在。
3. 三者位于同一世界坐标系下。
4. 对象 transform 已 Apply。

## 11. 最小实现优先级

如时间紧，按以下顺序实现：

1. 导入 `M_leak_tree_01` marker。
2. 导入并保留 `R_leak_tree_01` 的三角形。
3. 靠近 marker 后注入红色树点云。
4. HUD 推系统 bug 警告。
5. 导入并保留 `H_cover_tree_01`。
6. 延迟激活圆柱体到 raycast + depth。
7. 再考虑圆柱体升起动画、音频强化、屏幕红闪。

## 12. 给画图 / 关卡作者的简版说明

请在 `3.blend` 中准备三样东西：

- 一棵真实树，命名 `R_leak_tree_01`。
- 一个靠近树的触发点 Empty，命名 `M_leak_tree_01`。
- 一个盖住树的圆柱体，命名 `H_cover_tree_01`。

不要把树命名成 `P_`。

不要把圆柱体命名成 `C_`。

树是“真实世界里一直存在但系统不允许玩家看见的东西”。圆柱体是“系统发现 bug 后临时盖上去的东西”。玩家看到的不是树真的变出来，而是系统短暂露馅。

