# Blender 作者规范

> Title：Blender 作者规范（建模指南）
>  
> Document Level：L3
>  
> Status：Approved
>  
> Version：0.1.0
>  
> Owner：主设计师/架构师
>  
> Approver：Product Authority
>  
> Last Updated：2026-05-29
>  
> Scope：定义所有在 Blender 中建模、导出为 GLB 的对象的命名规范、尺寸约定、collection 组织与导出 checklist。运行时导入器按本规范读取语义。
>  
> Upstream Refs：[L2-02-内容管线设计.md](L2-02-内容管线设计.md), [L2-03-循环与世界切换设计.md](L2-03-循环与世界切换设计.md)

## 1. 文档目的

PA 在 Blender 中建模时的**唯一权威**参考。所有运行时行为（碰撞、显影、颜色、出生点）都由对象**名字前缀**和所在 **collection** 决定，**不需要侧车 JSON**。

只要遵守命名规则，导出 GLB 覆盖到 `content/levels/earth_return_01/<file>.glb` 即可生效。

## 2. 单位与坐标

- **单位**：米（Metric）。在 Blender 中 `Scene Properties → Unit System = Metric`。
- **坐标系**：Y-up（导出 glTF 时 Blender 自动从 Z-up 转 Y-up，使用默认 `+Y Up` 选项即可）。
- **原点**：世界原点 (0,0,0) 对应运行时世界原点。**所有循环地图共享原点**——同一坐标在 phase1/3/4/5 是同一个物理位置。
- **地面高度**：地板顶面 y=0。
- **玩家眼睛高度**：y = 2.0（建模时可参考这个高度判断视角）。
- **典型房间高度**：3 m 以上（保留可达性）。

## 3. Collection 组织

Blender 中至少有这四个顶层 collection：

| Collection | 用途 |
|------------|------|
| `Render` | 玩家声呐扫描时会显形的"墙/地板/天花板/家具" |
| `Collision` | 玩家不能穿过的几何代理（粗略包围盒） |
| `Markers` | 出生点、触发器等空对象（Empty） |
| `Phantoms` | 人形/按钮/提示/标识等"特殊建构" |

**Collection 仅供作者组织，运行时只看对象名前缀**——名字写对了，放哪个 collection 都能识别。但**强烈建议保持组织清晰**。

## 4. 对象命名规范

### 4.1 通用结构

```
<前缀>_<可选语义>_<id>
```

- **前缀**：单字母大写 + 下划线，决定运行时分类（见 §4.2）
- **id**：自由 ASCII，**全局唯一**。可以包含房间名、用途、序号等

### 4.2 前缀总表

| 前缀 | 含义 | 运行时行为 |
|------|------|------------|
| `R_` | Render Mesh | 声呐 raycast 命中，按法线分色（墙青、地面青、天花板浅蓝）。也是深度遮挡几何 |
| `C_` | Collision Mesh | 玩家移动碰撞代理。**不参与渲染、不被扫到** |
| `P_` | Phantom | 声呐能扫到、命中显示**指定颜色**。**不参与玩家碰撞** |
| `M_` | Marker（Empty） | 标记点（出生点 / 触发位置等），见 §4.5 |
| `V_` | Volume（Empty Cube） | 体积/触发区域（当前未启用，预留） |

### 4.3 Render（`R_*`）规则

- 静态网格。**Apply transform**（Ctrl+A → All Transforms）后再导出
- 不要用 modifier 动态生成（导出时未应用会丢失）
- 不要负缩放
- 法线决定颜色：朝上 = 地面色，朝下 = 天花板色，其余 = 墙色

### 4.4 Collision（`C_*`）规则

- 应为**简化的凸包**（盒子最佳）——不要把高面数的装饰 mesh 复用为碰撞
- 与 Render 不要完全重叠（轻微外扩 1-2cm 避免玩家"卡墙"）
- 没有 Collision 几何时，运行时会用 Render 兜底（会很卡）

### 4.5 Markers（`M_*`，Empty 对象）

| 命名 | 用途 |
|------|------|
| `M_spawn_main` | **必须**：玩家出生点。导入器取第一个 `M_spawn*` 作为该地图 spawn |
| `M_spawn_<id>` | 备用出生点（当前未启用） |
| `M_trigger_<id>` | 触发器位置（当前未启用） |
| `M_end_<id>` | 结局触发点（当前未启用） |

只有位置（`Empty Arrows` 即可）会被读取，不读旋转。

### 4.6 Phantom（`P_*`）—— 最重要的扩展，详见 §5

## 5. Phantom 规范（重点）

Phantom 是**任何特殊建构**：人形、按钮、提示牌、标识、神秘装置、不该存在的几何……运行时声呐能扫到、显示成指定颜色，但玩家走过去**穿得过去**（不阻挡）。

### 5.1 命名格式

```
P_<kind>_<color?>_<id>
```

- **`<kind>`**：自由分类名，**运行时不区分**，给你自己组织内容用
  - 推荐：`humanoid`（人形）、`button`（按钮）、`hint`（提示）、`sign`（标识/标志）、`pillar`（柱状物）、`glyph`（符文/字符）、`device`（设备）、`anomaly`（异常体）
- **`<color>`**：可选，决定扫到时显形的颜色。**不写默认红色**
- **`<id>`**：自由 ASCII，建议加位置/语义（如 `corridor_a_01`、`door_workshop`）

### 5.2 颜色 token

可在名字任意位置作为独立 `_` 段出现：

| Token | 显示色（基色 ±10% 抖动） | 推荐语义 |
|-------|--------------------------|----------|
| `red` | 红色 (0.95, 0.18, 0.22) | 威胁、警告、敌意（默认） |
| `yellow` | 黄色 (0.98, 0.85, 0.18) | 可交互的按钮、信号、注意 |
| `silver` | 银色 (0.78, 0.80, 0.84) | "过去的自己"、记忆残留、信使 |
| `cyan` | 青色 (0.18, 0.92, 0.95) | 友善提示、系统信息 |
| `purple` | 紫色 (0.62, 0.20, 0.85) | 异常、真相边界、不可名状 |
| `orange` | 橙色 (0.98, 0.55, 0.15) | 警示、能源、过热 |
| `green` | 绿色 (0.20, 0.92, 0.40) | 出口、安全、生机（在这游戏里极少用，更震撼） |
| `white` | 白色 (0.95, 0.95, 0.95) | 中性、参考、未分类 |

**±10% 抖动**：每个三角形命中产生的点云颗粒在基色上 R/G/B 各通道 ±10% 随机扰动，让 phantom 不显得"塑料质感"，与环境其他点云有相似的颗粒生命感。

### 5.3 示例

| 对象名 | 含义 | 显形色 |
|--------|------|--------|
| `P_humanoid_silver_old_self_01` | 过去的自己（信使）| 银色 |
| `P_humanoid_red_threat_lobby` | 系统标记为威胁的人形 | 红色 |
| `P_button_yellow_door_a` | 黄色按钮（可交互暗示） | 黄色 |
| `P_hint_cyan_corridor_west` | 走廊里的青色提示 | 青色 |
| `P_sign_white_lab_03` | 实验室白色标识 | 白色 |
| `P_anomaly_purple_tank_hall` | 储罐厅的紫色异常体 | 紫色 |
| `P_humanoid_01` | 默认人形 | 红色（默认） |

### 5.4 Phantom 几何规则

- **Apply transform** 后导出
- 静态 mesh，no rigging
- **不参与玩家碰撞**——玩家会直接穿过 phantom 几何
- 几何复杂度建议低（人形 < 200 三角形足够；按钮等小物件 < 50 三角形）
- 多个 phantom 可以放在同一个 collection 里，建议 collection 名 `Phantoms`

### 5.5 大小指南

| Phantom 类型 | 建议尺寸 |
|--------------|----------|
| 人形（humanoid） | 高 1.7–1.9 m（接近玩家高度 2 m 但略矮，制造"它在那"的存在感） |
| 按钮（button） | 直径 0.2–0.4 m，距地面 1.0–1.5 m（与玩家手臂高度对齐） |
| 提示/标识（hint/sign） | 0.5–1.5 m 宽、贴墙或独立 |
| 异常体（anomaly） | 自由——越奇怪越好。建议大于 2 m 才有压迫感 |
| 柱状物（pillar） | 0.3–0.8 m 直径，2–3 m 高 |

## 6. 导出 GLB Checklist

每次导出前：

1. ☐ 所有 `R_` / `C_` / `P_` 对象都已 **Apply transform**（Ctrl+A → All Transforms）
2. ☐ 所有对象命名遵守 §4 / §5 规范，前缀正确
3. ☐ `M_spawn_main` 存在且位置合理（不在墙里）
4. ☐ 没有遗漏 collection（Render / Collision / Phantoms / Markers）

导出步骤：

1. `File → Export → glTF 2.0 (.glb/.gltf)`
2. **Format**：`glTF Binary (.glb)`
3. **Include → Selected Objects**：**不勾**（导出全部）
4. **Transform → +Y Up**：勾上（默认）
5. **Data → Mesh → Apply Modifiers**：勾上
6. **Data → Mesh → UVs / Normals / Tangents**：勾上 normals（其他可选）
7. **Custom Properties**：勾上（保留任何扩展字段，无害）
8. 文件名按 L2-03 §3：
   - `scene.glb`（轮 1+2）
   - `scene_loop3.glb`（轮 3 开始 glitchy）
   - `scene_loop4.glb`（轮 4 怪）
   - `scene_loop5.glb`（轮 5 诡异）
9. 保存到：`C:\Users\ROG\Desktop\GameJam\content\levels\earth_return_01\`

## 7. 验证

启动游戏后控制台会打印：

```
[world] GLB 加载 content/levels/earth_return_01/scene.glb: render N / collision M / phantom K 三角形
```

- 如果 `render` 是 0 → 没有 `R_` 对象或导出有问题
- 如果 `phantom` 是 0 → 没有 `P_` 对象或前缀写错
- 如果加载失败 → 控制台显示 "未找到 GLB"，自动回退代码盒子房间

## 8. 不要做的事

- ❌ 不要用骨骼动画（运行时不读）
- ❌ 不要用粒子系统（不读）
- ❌ 不要用复杂材质（不读，颜色由代码决定）
- ❌ 不要用负缩放（导出后法线翻转，显影会乱）
- ❌ 不要在 `R_` 对象里放装饰小物件混在大墙里——分开命名，便于运行时识别
- ❌ 不要让对象重名（导入器按名字解析，重名行为未定义）
- ❌ 不要在名字里用空格或中文（用下划线分割 ASCII）

## 9. 想要新的语义？

如果你需要超出当前前缀的新行为（比如可拾取道具、动态门、声源点等），告诉架构师，会扩展运行时 + 在本文档新增前缀。

## 10. 修订记录

| 版本 | 日期 | 摘要 |
|------|------|------|
| 0.1.0 | 2026-05-29 | 初版：Render/Collision/Phantom/Marker 命名规范、Phantom 颜色编码、Blender 导出 checklist |
