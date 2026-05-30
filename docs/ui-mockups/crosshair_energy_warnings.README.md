# SonarJam HUD — Helmet Visor Mockup

宇航员头盔面罩 HUD 设计稿。单文件，纯 HTML/CSS/JS，浏览器直接打开。

文件：`crosshair_energy_warnings.html`

---

## 1. 用途

- UI 设计稿：定位、配色、节奏、动效的视觉基准
- 接口原型：游戏端按相同的 `HUD.*` 调用形状对接，落地引擎实现时保留语义即可
- 单文件可直接给美术 / 程序看效果，无需构建

---

## 2. 组成元素

| 区域 | 元素 | 数据来源 |
|---|---|---|
| 中央 | 准星 + 5 能量点 | `HUD.setEnergy(n)` |
| 顶部中央 | 罗盘 tape + 当前朝向 + 漂移 | `HUD.setBearing(deg)` / `HUD.setDrift(mps)` |
| 左上角 | 主警告卡片（橙色斜杠纹） | `HUD.setWarning({tag,msg,sub})` |
| 左侧中部 | 套装生命数值（外/内温、O₂、压力、CO₂） | `HUD.setVitals({...})` |
| 右上角 | 生物体征（HR 带心跳脉动、RESP、SpO₂、CORE） | `HUD.setBio({...})` |
| 左下角 | 通讯回音（最多 3 条，第一条最亮） | `HUD.setComms([...])` |
| 右下角 | 单根 CELL 电池条（其余区域留给手持扫描仪） | `HUD.setIntegrity({cell})` |
| 面罩下沿 | 呼吸雾气（事件驱动） | `HUD.exhale()` / `HUD.setSprint(bool)` |
| 全屏覆盖 | 头盔曲率暗角、镜片反光、镀膜扫描线 | 静态 CSS |

---

## 3. JS 接口

引擎对接时按以下形状调用即可，落地可换成 native 实现：

```js
// 朝向（带弹簧物理：欠阻尼过冲 + 持续微抖）
HUD.setBearing(132);           // 目标朝向，自动摆动到位
HUD.nudgeBearing(-18);         // 一次性角冲量（碰撞/爆炸）
HUD.setDrift(+1.7);            // m/s

// 警告（msg 允许 <br>；传 null 隐藏）
HUD.setWarning({
  tag: "CRITICAL · POWER",
  msg: "EXTERNAL POWER LINK LOST.<br>SUIT NOW RUNNING ON INTERNAL CELL.",
  sub: "EST. 11:48 REMAINING · LIFE SUPPORT WILL FAIL ON DEPLETION"
});

// 套装生命
HUD.setVitals({ text: -89, tint: 21.2, o2: 78, press: 14.2, co2: 0.42 });
//                ↑ext    ↑int

// 生物（hr 会自动联动心跳动画速率）
HUD.setBio({ hr: 112, resp: 22, spo2: 96, core: 37.2 });

// 套装完整性（cell<50 自动转 warm 配色，可显式传 cellWarm 覆盖）
HUD.setIntegrity({ cell: 38 });

// 通讯（最多 3 条，第一条 fresh 高亮）
HUD.setComms([
  { who: "ANCHOR", msg: '"echo, your bio is spiking — slow down."' },
  { who: "ECHO-3", msg: '"…copy. lattice is humming in here."' },
]);

// 能量（0..5 整数）
HUD.setEnergy(3);

// 呼吸雾气
HUD.exhale();                                                   // 普通一口
HUD.exhale({ intensity: 1.4, duration: 1.8, size: 'big' });     // 自定义
HUD.setSprint(true);                                            // 进入疾跑节奏
HUD.setSprint(false);                                           // 停止
HUD.fogDemo();                                                  // 一次显眼的演示
```

---

## 4. 键盘 / 缩放

| 键 | 行为 |
|---|---|
| `Ctrl + 滚轮` | 缩放（自动适配窗口为初始；范围 0.2 ~ 3.0） |
| `Ctrl + 0` | 还原为自动适配 |
| `Space` | 触发一次显眼的哈气（演示用） |
| `S` | 切换疾跑节奏（演示用） |

页面打开 800ms 后自动播 6 秒疾跑节奏，便于直观看到雾气效果。**接入游戏后请删掉文件末尾的 `setTimeout(() => { setSprint(true); ... }, 800)` 演示段。**

---

## 5. 关键设计决策

### 5.1 不挡视野
所有信息退到屏幕四角，中央 ~600×400 px 区域只留准星 + 5 能量点。右下角进一步精简（仅一根 CELL 条），给手持扫描仪让出空间。

### 5.2 罗盘物理
真磁罗盘式的二阶弹簧：
- `SPRING_K=10, DAMPING=3.9` → 阻尼比 ≈ 0.62，过冲温和、回摆柔和
- `TORQUE_CAP=24°` 对 delta 做软限幅，避免大跳一开始的暴力加速度（180° 跳变不会瞬间产生 3240 deg/s²）
- `VEL_CAP=220 deg/s` 速度上限
- 两路低频 sin (0.55Hz / 1.30Hz)、幅度 0.10° 的持续微抖，到位也在晃

### 5.3 雾气
事件驱动，不是 CSS infinite 循环（避免"抽烟"感）：
- 每次 `exhale()` 创建独立 puff，播完销毁
- 随机化 x/dx/旋转/大小/scale 曲线，每口都不一样
- 疾跑节拍 950~1200ms 抖动，每 3 拍补一小口（呼吸不均匀）
- SVG `feTurbulence + feDisplacementMap` 滤镜把圆形扭成不规则团块，turbulence 自身缓慢变形

### 5.4 警告卡片
- 位置：左上角（与生命数值同列，警告在上）
- 视觉：橙色斜杠纹 + warn-pulse 缓脉动（1.4s 周期）
- 文案三段式：`tag`（短标签）/ `msg`（主信息，允许换行）/ `sub`（详细说明）

---

## 6. 调参速查

雾气：
| 参数 | 文件位置 | 说明 |
|---|---|---|
| 单口动画时长 | `exhale()` 内 `duration` | 默认 1.7~2.1s |
| 最大不透明度 | `exhale()` 内 `peak` | 默认 0.30 × intensity |
| 疾跑节拍 | `setSprint()` 内 `gap` | 950 + random*250 ms |
| turbulence 频率 | SVG `<feTurbulence baseFrequency>` | 越小团块越大整 |
| 边缘扭曲幅度 | SVG `<feDisplacementMap scale>` | 越大边缘越乱 |
| 上飘距离 | `@keyframes breath-once` 末段 translateY | 当前 -44px |

罗盘：
| 参数 | 文件位置 | 说明 |
|---|---|---|
| 弹簧刚度 | JS 顶部 `SPRING_K` | 越大转得越急 |
| 阻尼 | `DAMPING` | 越小过冲越多 |
| 大跳软限 | `TORQUE_CAP` | 越大首发加速度越猛 |
| 速度上限 | `VEL_CAP` | 越大转得越快 |
| 微抖幅度 | `NOISE_AMP` | 0 = 完全稳定 |
| tape 像素密度 | `PX_PER_DEG` | 越大同样角度移动得越多 |

警告：
- 颜色：CSS 顶部 `--warn-line` / `--warn-ink`
- 脉动周期：`@keyframes warn-pulse`

---

## 7. 浏览器要求

- Chrome / Edge / Firefox 现代版本均可
- 关键依赖：SVG filter (`feTurbulence` + `feDisplacementMap`)、CSS Custom Properties、`mix-blend-mode: screen`、`requestAnimationFrame`
- 不依赖任何外部资源（字体回退到 Bahnschrift / Segoe UI / Consolas 等系统字体）

---

## 8. 上线前清理

1. 删除文件末尾雾气演示段 `setTimeout(() => { setSprint(true); ... }, 800)`
2. 视需要删除 `keydown` 中的 `Space` / `KeyS` 演示键
3. 删除右下角缩放提示 `.zoom-hint`（若不想暴露给玩家）
4. 把 demo 默认值（HR=112、cell=42、warning 文案等）替换为占位或读自游戏状态

---

## 9. 已知约束

- `transform: scale()` 缩放可能在缩小到极小（<0.4）时让细线变虚，正常窗口大小无影响
- SVG turbulence 在低端 GPU 上每帧 ~0.3ms，移动端慎用（本项目桌面端无需考虑）
- 警告卡片 `msg` 字段允许 HTML（用了 `innerHTML`），如果文案来自玩家可输入源需先转义
