"""
finalize_ship_room.py v33 — 保守碰撞模式：贴近真实几何，少偷空间

v33 变化（相对 v32）：
- PA 反馈：apply transforms 后发现 v32 设置过激进——椅子完全无碰撞、装置偷
  太多空间显得穿墙。玩家 collision radius 已经够小，不需要 script 额外偷
- COLLISION_SKIP_ORIG_NAMES 清空（椅子加回 C_，AABB 老实给）
- C_DEVICE_INSET 0.10 → 0.04（玩家 radius ~0.08，4cm tolerance 足够）
- COLLISION_INSET_OVERRIDES 全删（device 一视同仁用默认 0.04）
- C_WALL_OUT_EXPAND 0.05 → 0.10（墙增厚到 0.25m C_，防穿）
- collision_free marker 仍然有效，靠 marker 定义走道（marker 比偷 inset 精准）

v32 变化（相对 v31）：
- try_read_markers_from_output_glb 后列出输出 GLB 所有 mesh 名（找不到 marker 时排查）
- 放宽匹配：collision_free / collisionfree / no_collision / "free" 开头都接受

v31 变化（相对 v30）：
- 新增 OUTPUT_SCENE_GLB 常量 + try_read_markers_from_output_glb()：
  当前 .blend 没找到 marker 时，自动 import 输出 GLB 抢救 marker bbox
  解决 PA 在工作 .blend 之外的 scene.glb 加 marker、跑脚本扫不到的问题

v30 变化（相对 v29）：
- 新增 COLLISION_FREE_AUTO_EXTEND_Y（默认 True）：marker Y 自动扫全室
  marker 现在语义是"通道横截面"：X+Z 定义通道宽高，Y 自动从前到后

v29 变化（相对 v28）：
- subtract_aabb 加 CARVE_MIN_SLAB_XY=0.25 阈值，丢弃裁切产生的薄 sliver
  防止 marker 没盖满 device 时留下卡人的薄条

v28 变化（相对 v27）：
- 每个 marker 实际挖到了哪几个 device 的报告

v27 变化（相对 v26）：
- COLLISION_FREE_AUTO_EXTEND_Z（默认 True）：marker Z 自动延全高
  防止地面薄 marker 让 3m 高装置上半截 C_ 继续挡人

v26 变化（相对 v25）：

v26 变化（相对 v25）：
- PA 在输出 scene.glb 里手放 collision_free1/2 等方块标记"我要能通过这片"
  → 脚本现在：
    1. CLEAN_IMPORT wipe 之前先扫描所有 collision_free* mesh 存其 world bbox
    2. 装置 C_ 生成时，对每个 C_ box 做 AABB 差集：C_ minus collision_free
       结果是 0-6 个 slab 替代原 C_（自动避开标记区，标记之外的体积保留）
    3. 完整重建标记到场景（同名 hidden mesh，无 R_/C_/P_/M_ 前缀 →
       L3-02 §4.2 运行时 Cat::Skip 忽略），下次跑脚本仍能被扫到，幂等保留
- 新增 _gather_collision_free / _subtract_aabb / _recreate_markers
- 工作流：PA 开 scene.glb → 手放 collision_free 方块 → 跑脚本 → 导出 →
  下次还能开同一 scene.glb 跑（方块持久化）

v20-v25 见旧 docstring 段。

v20 变化（相对 v19）：

v20 变化（相对 v19）：
- v19 门装饰全装在了 -Y 外侧，玩家在室内根本看不到 → 一片纯橙棕门板
  → v20 全部翻面：
    - 门板移到墙的室内侧（紧贴 y=y_min，不再居中在墙厚度中央）
    - 加强带、铆钉、阀轮、控制面板、门框都凸出到室内方向（+Y）
- v19 阀轮是 "+" 字形 box，不像阀门
  → v20 用真 torus（圆环）+ 中心 hub 圆柱 + 双向辐条 box，潜艇舱门感
  → 新增 _bm_add_torus_y 助手（沿 Y 轴的环面，参数化 major/minor radius）
  → 新增 _bm_add_cylinder_y 助手（沿 Y 轴的实心圆柱，给 hub 用）
- 新增 import math, mathutils.Matrix

v19 变化（相对 v18）：
- v18 门的补丁色块跟墙融为一体 → 完全看不出门
  → v19 取消补丁，门 panel 改单一纯色"舱门警示橙棕"（door_solid），
    跟墙的橄榄屎反差明显，玩家一眼能识别"这是门"
- 去掉传统门把手 R_door_handle（不再设计成普通门）
  → 改成 R_door_wheel：中央阀轮（保险柜/潜艇舱门感）
    - 中央 hub box（18cm × 7cm × 18cm，凸出门外侧）
    - 水平臂 60cm × 5cm × 8cm
    - 垂直臂 8cm × 5cm × 60cm
    - 合并成单一 mesh
- 保留 R_door_band（中间加强带）和 R_door_rivets（6 颗铆钉）
- 去掉 _DOOR_PALETTE（不再需要）
- _MAT_DEFS 加 "door_solid"，去掉 door_iron_0..3 4 个

v18 变化（相对 v17）：
- 门改造为厚重钢板舱门：
  - R_door_panel subdivide cuts=3 + 区域生长 BFS（door_iron 调色板 4 色，
    冷暗钢灰为主、少量暖锈灰，区别于墙的橄榄屎）→ 钢板补丁质感
  - 新增 R_door_rivets：6 颗黄铜铆钉（4 角 + 上下中点），凸出门外侧 1.2cm
  - 新增 R_door_band：水平加强带，门高一半处，全宽，凸出 1.5cm，暗钢色
- 装置碰撞：build_device_collision 原有逻辑已生成 C_ship_*；
  增强日志：列出每个 device 名 + size，让 PA 可见每个物件都拿到了碰撞代理
- _MAT_DEFS 新增 door_iron_0..3 / rivet / door_band 共 6 个材质

v17 变化（相对 v16）：
- v15/16 的 per-face 分配看着是均匀马赛克（每个 quad 独立抽色）
  → v17 改区域生长 BFS：选种子 face → 抽色 → 按概率 grow 到相邻 face，
    达到 patch_size 上限或邻居被堵就停 → 边界 face 进入下一个补丁
  → 结果是大小不一、形状不规则的色块，像焊接铁补丁
- subdivide 细化（cuts 4→6，每个 box 面 7×7=49 quads × 6 面 = 294 quads / box）
  让补丁有足够分辨率呈现"小补丁/大补丁"差异
- patch_min=2 / patch_max=14 / grow_prob=0.62
  → 多数补丁 4-10 个 quad（中等），少数 2-3（小钉片）和 12-14（大铁板）
- 调色板扩到 7 种橄榄屎暗色（增加色彩变化丰富度）
- 4 面墙独立 seed → 补丁分布完全不重复

v16 变化（相对 v15）：
- PA 反馈：之前的 _temp_Blender/scene.glb 是已修改的版本，不想依赖它
  → 脚本自己 import 源资产 tools/GLB/surveillance_room_scaled_3m.glb，
    自包含起步，PA 在 Blender 里只需 Open 脚本 + Run
- 新增 CLEAN_IMPORT 开关 + SOURCE_GLB 路径常量
- main() 开头：
    1. 删除所有 MESH / EMPTY 对象（如果 CLEAN_IMPORT=True）
    2. bpy.ops.import_scene.gltf(filepath=SOURCE_GLB)
    3. 进入既有 finalize 流程（rename / 房间 / 材质 / spawn）
- 关闭 CLEAN_IMPORT 仍可对当前场景做 finalize（兼容旧用法）

v15 变化（相对 v14）：
- 关键认知：运行时 GLB 渲染**纯颜色无光影**——procedural Noise/ColorRamp 不出
  GLB（base color socket 被节点占用 → 导出近乎默认），v11-v14 viewport 看到的
  "不均匀斑驳"在游戏里都是假的。墙在游戏里就是一坨纯色 → "难绷"
- 改方案：subdivide_wall_for_patches() 把每面墙 box 细分成网格（cuts=4 → ~5×5
  网格/面），然后给 mesh 加 4-5 个橄榄屎调色板材质（每个都是纯 base color），
  按 face 中心位置 stable-hash 分配 material_index → GLB 导出每个 face 一个
  平色材质，游戏里直接看到色块拼接的"墙皮"质感
- 移除 goggle：PA 已删 VR 眼镜，交互不再依赖它
  - rename_existing_meshes 去掉 goggle 分支
  - main 去掉 goggle 上色 + M_interact_vr_headset
  - 删除 GOGGLES_ROOT / GOGGLES_PART_MAP / find_goggles_center
- 清理死代码：make_directional_lit_material / make_gradient_iron_material /
  assign_directional_lit / assign_gradient_iron / make_rusty_iron_material /
  assign_rusty_iron 全部移除（运行时不出 GLB，已被 subdivide+palette 取代）
- _MAT_DEFS 去掉 goggles_* 4 个条目

v14 变化（相对 v13）：
- 诊断证实 4 个 goggle mesh 几乎完全重合（同心多层 Tripo 输出，center 全一致，
  size 都 ~0.24m）→ 不存在壳/带/镜片语义分区，统一上色是物理正确做法
  保留 uniform shell，删除"等 PA 填 map"的注释引导
- 4 面墙合并到单一 wall_spec（深橄榄屎）：
  dark=(0.006, 0.008, 0.002), rust=(0.038, 0.046, 0.012)
  比 v13 -Y/+Y/±X 三套 spec 再压暗一档，并去掉方向性差异
  PA 反馈：墙之间亮度不一致比墙太亮更违和 → 统一阴影感优先

v13 变化（相对 v12）：
- PA 反馈：墙比延伸出去的外围裸地板（已被 viewport 阴影染深褐）还要亮 → 违和
  → 4 面墙 rust 色全部 × 0.4，dark 色保持极暗，ramp_lo 全部提到 0.55+
  让"暗区"占大头，亮斑只是隐约可见的偏色提示，整体在阴影里
  - -Y 墙（原柠檬亮）：rust (0.85,0.65,0.10) → (0.30,0.22,0.04)
  - +Y 墙（已暗）：rust (0.12,0.09,0.025) → (0.05,0.04,0.012)
  - ±X 墙（橄榄屎）：rust (0.13,0.14,0.045) → (0.055,0.060,0.018)
  - 同时压低 metallic（0.45/0.20/0.20 → 0.15）避免反射拉亮
- 顶线/踢脚线 base 也压暗一档配合阴影感

v12 变化（相对 v11）：
- ±X 墙颜色改"暗橄榄屎色"：dark=(0.025, 0.028, 0.010), rust=(0.13, 0.14, 0.045)
  比 v11 的土黄暗约 2.5×，绿通道略高于红 → 带橄榄绿色调（真"屎"色）
  ramp_lo 提到 0.45 → 暗区占比更大
- goggles 分区方式改造：vertex 数量启发式不准（v11 把主壳错赋成了 lens 黑）
  → 改为显式名字映射 GOGGLES_PART_MAP（dict: mesh_name → mat_key）
  + 默认 fallback 到 goggles_shell（不再有怪异黑斑）
  + 每次运行打印每个 goggle mesh 的诊断（verts / bbox / center），
    PA 看完一次后把 4 个名字填进 GOGGLES_PART_MAP，下一轮就精准分区

v11 变化（相对 v10）：
- 门改回单板 R_door_panel（v3 双开中央那 2cm 缝被 PA 判定为"关不上"），
  panel 留 0.5cm 跟门洞边缝；把手改为一个、贴右侧
- ±X 墙改纯色"屎黄"暗黄棕褐（0.32, 0.26, 0.08）+ noise 不均匀
  （v10 gradient 在金属上看不出方向感，放弃 gradient_iron）
- goggles 放弃 Fresnel/程序化方案，改手动分区上色：
  按 vertex 数量排序 4 个 mesh，从大到小分别赋 shell / strap / lens / misc
  4 种纯色（暗棕 / 黄褐 / 几乎黑 / 暗黄铜），融入屎黄环境

v10 变化（相对 v9）：
- 几何：-Y 墙位置向 +Y 内移 0.9m（WALL_YNEG_INSET），房间在 Y 方向缩短，
  门、踢脚线、控制面板自动跟随；玩家进门后看到墙外有原地板平台
- 锈墙 ramp 改 LINEAR（v9 的 B_SPLINE 让边界水墨晕染）
- 加 make_gradient_iron_material 函数：沿 Generated 轴渐变 + Noise 不均匀
  ±X 墙用此 shader，沿 Y 方向 -Y 端亮（被屏幕辐射打到）→ +Y 端暗（屏幕背后）
  → 墙在 Y 维度有明显光照分布，不再均匀
- goggle shader 重写：去 noise MULTIPLY mix（避免均匀化），让 Fresnel 直接驱动
  base color；3 段 ramp（中心纯黑 → 中部暗暖褐 → 边缘亮柠檬白），IOR 2.0、
  metallic 0.55 让金属表面 Fresnel 高光极显；Noise 单独驱动 roughness 微变化

v9 变化（相对 v8）：
- goggles 用 Fresnel-based directional_lit shader：
    Fresnel(IOR 1.4) → ColorRamp(中心 0.04 极暗 → 边缘 0.48 柠檬土黄高光)
                     × Noise(scale 22) → BaseColor
  Eevee/Cycles 都支持。让 goggle 边缘出现"被强光打到突起"的高光，
  中心保持极暗，加 noise 污渍 → 不再均匀柠檬色块，有方向性体积感
- 墙 rust 颜色饱和度大幅提高：
    -Y 墙 highlight (0.85,0.65,0.10) 强烈柠檬黄（被屏幕直射）
    ±X 墙 highlight (0.45,0.35,0.08) 中等土黄
    +Y 墙 highlight (0.12,0.09,0.025) 几乎无（屏幕背后）
- 调小 noise scale（3.0-4.5）让斑块更大，模拟光照分布

v8 变化（相对 v7）：
- goggles 大幅压暗 + 完全哑光：base (0.085,0.055,0.030), metallic 0.05, roughness 0.97
  （暗灰红 × 黄光环境 = 极暗棕红黑，几乎吸光不反射）
- 4 面墙各自独立材质，模拟"屏幕装置朝 -Y 辐射"的方向性光照：
  - R_wall_yneg（门那面，正对屏幕辐射）：最亮，大块土黄高光
  - R_wall_ypos（屏幕背后）：几乎全暗，少许高光
  - R_wall_x±（侧向掠射）：中等
- Noise 加 Distortion 1.5-2.0 + Detail 12 + ColorRamp B_SPLINE 插值，
  纹理不再机械斑驳，更接近自然光斑/锈渍

v7 变化（相对 v6）：
- goggles 从金属反光改为哑光黄褐塑料感（metallic 0.20, roughness 0.80）
- 墙程序化纹理改为"被柠檬土黄光照亮的旧铁皮"：深黄黑底 + 土黄绿光斑
  scale 4 大斑块（像光照投影而非细锈）
- 门改深锈黄黑融入环境（不再蓝），门框增强暖锈黄铜让门保持辨识度
- 控制面板绿光增到 emission 4.0（暗环境对比）
- 踢脚线/顶线/把手统一调到偏黄褐色调

v6 变化（相对 v5）：
- 修 bug：assign_material 后把所有 poly.material_index 重置到 0
  （Tripo goggle / Sketchfab 多 slot mesh 之前显示中灰是因为 face index 指向已删 slot）
- 墙改为程序化锈铁材质：Noise → ColorRamp 输出深锈黑斑驳，scale=6 大斑块
- goggles 颜色加深到旧黄铜，融入装置色调

v5 变化（相对 v4）：
- 墙改深锈铁（0.14,0.12,0.10）、roughness 0.72，工业暗色调
- 天花板压到近黑（0.06）、高 roughness（0.85）
- 踢脚线/顶线改锈红铁/旧锈铁
- 门改深蓝黑金属，门框锈黄铜，把手磨损金属
- 控制面板绿光更亮（暗环境对比）
- goggles 从 chrome 改为脏污旧黄铜（融入装置色调，不再突兀）

v4 变化（相对 v3）：
- 不再 hide/排除原大薄板地板 Object_4：rename 为 R_floor_orig 保留其纹理/烧入光影
  （v2/v3 已 exclude 的会从 _OriginalFloor_excluded collection 救回）
- 不再创建新 R_floor（避免和 R_floor_orig z-fight），但保留 C_floor 薄碰撞板
- 墙改暖米色（0.58,0.52,0.42），跟装置黄色融合；天花板深暗棕灰
- 踢脚线/顶线改旧黄铜色
- R_goggles_* 覆盖为 chrome 银亮金属（替换 Tripo 默认哑光黑塑料）
- 房间内尺寸不变（5.5×5.5），原地板延伸出墙外形成"飞船平台"视觉

v3 变化（相对 v2）：
- 给所有新建 R_* mesh 赋 Principled BSDF 材质（金属灰墙、暗地板、蓝灰门、
  暖黄铜门框、银亮把手、绿色发光控制面板），让 viewport / 运行时 PBR 渲染
  与已有 goggles 纹理协调
- 门优化为双开气闸门：左右两扇 R_door_panel_left/right + 中央 2cm 缝；
  R_door_handle 双面把手；R_door_panel_ctrl 门顶发光绿色控制面板（暗示锁住）
- 原始装置 mesh 自带材质保留（不覆盖）

v2 变化（相对 v1）：
- 房间按"监控装置"bbox 收紧（自动排除大薄板地板 Object_4）
- 内尺寸 ≈ 装置 bbox + 1.2m 玩家走动余地
- 4 面墙咬合无缝（+/-X 墙包外侧，+/-Y 墙夹内侧）
- -Y 墙整体用 bmesh 合成（左/右/过梁 3 段合并为单一 R_wall_yneg mesh）
- 门：单门板 R_door_panel + 4 边门框合并为单 R_door_frame
- 踢脚线 R_baseboard、顶线 R_crown（各为单一 mesh，4 段合并）
- 所有 C_* 碰撞代理 hide_set 隐藏 viewport（不影响导出）
- 原始大地板 Object_4 去 R_ 前缀 + hide + 移到 _OriginalFloor_excluded

PA 用法（v16 自包含）：
  1. Blender 启动（任意空场景或 default cube 都行）
  2. Scripting → Open → tools/finalize_ship_room.py → Run Script
     → 脚本自动清空场景 + import 源 GLB + 组装房间 + 上色 + 放 spawn
  3. 导出前选所有 R_/C_/P_ → Object → Apply → All Transforms
  4. File → Export → glTF 2.0:
     - Format: glTF Binary
     - Include → Limit to: 全部不勾
     - Transform → +Y Up: 勾
     - 路径：content/levels/ship_room/scene.glb

如果你想在已有场景上跑（不清空），把顶部 CLEAN_IMPORT 改成 False。

幂等：本脚本生成的对象带 generator=SCRIPT_TAG，重跑会清理重建。
"""

import bpy
import bmesh
import math
from mathutils import Vector, Matrix

SCRIPT_TAG = "ship_room_finalize_v33"
# v31: collision_free markers 自动从输出 GLB 读取（即使工作 .blend 里没有）
OUTPUT_SCENE_GLB = r"C:\Users\ROG\Desktop\GameJam\content\levels\ship_room\scene.glb"
# v16: 自包含——脚本自己 import 源 GLB，不依赖 PA 手动 append/修改的场景
CLEAN_IMPORT = True   # True: 开局清空所有 mesh/empty 然后 import 源 GLB
import os as _os
# 源 GLB 候选路径列表（依次尝试，第一个存在的就用）
# 注：Blender 的 __file__ 在 Run Script 时可能解析成意外路径，所以硬编码绝对路径
_SOURCE_GLB_CANDIDATES = [
    r"C:\Users\ROG\Desktop\GameJam\tools\GLB\surveillance_room_scaled_3m.glb",
    r"C:/Users/ROG/Desktop/GameJam/tools/GLB/surveillance_room_scaled_3m.glb",
]
SOURCE_GLB = next((p for p in _SOURCE_GLB_CANDIDATES if _os.path.isfile(p)),
                  _SOURCE_GLB_CANDIDATES[0])
_OLD_TAGS = ("ship_room_finalize_v1", "ship_room_finalize_v2",
             "ship_room_finalize_v3", "ship_room_finalize_v4",
             "ship_room_finalize_v5", "ship_room_finalize_v6",
             "ship_room_finalize_v7", "ship_room_finalize_v8",
             "ship_room_finalize_v9", "ship_room_finalize_v10",
             "ship_room_finalize_v11", "ship_room_finalize_v12",
             "ship_room_finalize_v13", "ship_room_finalize_v14",
             "ship_room_finalize_v15", "ship_room_finalize_v16",
             "ship_room_finalize_v17", "ship_room_finalize_v18",
             "ship_room_finalize_v19", "ship_room_finalize_v20",
             "ship_room_finalize_v21", "ship_room_finalize_v22",
             "ship_room_finalize_v23", "ship_room_finalize_v24",
             "ship_room_finalize_v25", "ship_room_finalize_v26",
             "ship_room_finalize_v27", "ship_room_finalize_v28",
             "ship_room_finalize_v29", "ship_room_finalize_v30",
             "ship_room_finalize_v31", "ship_room_finalize_v32")

# v10: -Y 墙向 +Y 方向收紧 0.9m
WALL_YNEG_INSET = 0.9
EXCLUDED_COLL_NAME = "_OriginalFloor_excluded"

# ---- 配置 ----
PLAYER_PADDING = 1.2     # 装置 bbox 到墙内表面的距离
ROOM_HEIGHT = 3.2        # 内净高（监控柱 3m，留 0.2m 头顶）
WALL_T = 0.15
FLOOR_T = 0.10
CEIL_T = 0.10
DOOR_W = 1.1
DOOR_H = 2.2
DOOR_PANEL_T = 0.06
FRAME_T = 0.06
FRAME_DEPTH = 0.18
BASEBOARD_H = 0.10
BASEBOARD_PROUD = 0.02
CROWN_H = 0.08

# v22: 跳过 C_ship_* 碰撞代理的原始 GLB 物件名（去掉 R_ship_ 前缀后的名字）
# 椅子等"有空隙"的形状用 AABB 会把空隙填实 → 玩家挤不过去；
# 跳过后运行时按 L3-02 §4.4 回退到 R_render 几何作碰撞，玩家能穿过缝隙
# 默认跳过 surveillance_room 的 3 张椅子（Object_6/7/8）；
# 如果在游戏里发现别的物件也挤不过去，把名字（去掉 R_ship_ 前缀）加到这里
COLLISION_SKIP_ORIG_NAMES = set()
# v33: 椅子加回（玩家应该撞椅子，不该穿）；如果要 skip 某个 object，把名字加进来

# v23/33: 墙 C_ 向房间外侧多扩（防"挤出墙"穿模）；R_ 不变
# v33: 0.05 → 0.10，墙 C_ 总厚度 0.25m，更不易穿
C_WALL_OUT_EXPAND = 0.10

# v23/33: 装置 C_ 在 AABB 每侧内缩（玩家 radius tolerance）
# v33: 0.10 → 0.04（玩家 radius ~0.08，4cm 容差够；不再大量偷空间，碰撞老实）
# 想偷走道走 collision_free marker 路径（精准），别靠全局 inset
C_DEVICE_INSET = 0.04

# v24: 按原始物件名（去掉 R_ship_ 前缀后）覆盖默认 inset 或直接跳过
# - 大型屏幕架/监控柱建议 0.15-0.20（多偷点过道）
# - 桌子等贴近的小物件用 0.04（少偷点防穿）
# - 完全跳过：用 COLLISION_SKIP_ORIG_NAMES（上面那个 set）
# 跑一次脚本 → 看 [collision] 日志 → 找到对应 Object 名 → 在这里加条目 → 重跑
# v27: collision_free marker 默认自动延伸到全高（PA 的 marker 常是地面薄方块，
# 不会顾 Z；C_装置 3m 高的话上半截 C_ 仍挡人 → 把 hole Z 拉到房顶以上）
COLLISION_FREE_AUTO_EXTEND_Z = True

# v30: marker Y 方向也自动延伸到全房间——把 marker 当"通道横截面"，
# X+Z 定义通道宽高，Y 自动扫到底（最常见的"我要从前走到后"语义）
# 如果你想要"只在 marker bbox 内部清碰撞"的严格盒子语义，改成 False
COLLISION_FREE_AUTO_EXTEND_Y = True

# v29: 裁切产生的薄 slab 阈值——任何 XY 边长 < 此值的 slab 视为伪影丢弃
# 原因：marker 没盖满 device 时会留下 marker 边界到 device 边界的薄条，
# 玩家挤不过去那薄条 → 体感像"空间被压缩"。25cm 比玩家直径大，安全。
CARVE_MIN_SLAB_XY = 0.25

COLLISION_INSET_OVERRIDES = {
    # v33: 清空，全部 device 用默认 C_DEVICE_INSET=0.04
    # 如果某个物件需要单独调，按 "Object_X": 0.XX 加进来
}

# v15: 墙面调色板（深橄榄屎色，7 个变体，每个都是纯 base color → GLB 兼容）
# G 略 > R，B 极低 → 橄榄绿调
_WALL_PALETTE = ["wall_olive_0", "wall_olive_1", "wall_olive_2",
                 "wall_olive_3", "wall_olive_4",
                 "wall_olive_5", "wall_olive_6"]
WALL_SUBDIV_CUTS = 6   # v17: 6 刀 → 每个 box 面 7×7 quads（足够补丁分辨率）


# -------------------- 通用工具 --------------------

def ensure_collection(name):
    if name in bpy.data.collections:
        coll = bpy.data.collections[name]
        if name not in [c.name for c in bpy.context.scene.collection.children]:
            bpy.context.scene.collection.children.link(coll)
    else:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def move_to_collection(obj, target):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    target.objects.link(obj)


def tag(obj):
    obj["generator"] = SCRIPT_TAG


def clear_previous_run():
    valid = (SCRIPT_TAG,) + _OLD_TAGS
    rm = [o for o in bpy.data.objects if o.get("generator") in valid]
    for o in rm:
        bpy.data.objects.remove(o, do_unlink=True)
    return len(rm)


def world_bbox(objs):
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            wc = o.matrix_world @ Vector(c)
            mn = Vector((min(mn.x, wc.x), min(mn.y, wc.y), min(mn.z, wc.z)))
            mx = Vector((max(mx.x, wc.x), max(mx.y, wc.y), max(mx.z, wc.z)))
    return mn, mx


def is_under(obj, ancestor_name):
    a = obj
    while a:
        if a.name == ancestor_name or a.name.startswith(ancestor_name):
            return True
        a = a.parent
    return False


# -------------------- bmesh 几何 --------------------

def _bm_add_box(bm, center, size):
    cx, cy, cz = center
    sx, sy, sz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
    v = [
        bm.verts.new((cx - sx, cy - sy, cz - sz)),  # 0
        bm.verts.new((cx + sx, cy - sy, cz - sz)),  # 1
        bm.verts.new((cx + sx, cy + sy, cz - sz)),  # 2
        bm.verts.new((cx - sx, cy + sy, cz - sz)),  # 3
        bm.verts.new((cx - sx, cy - sy, cz + sz)),  # 4
        bm.verts.new((cx + sx, cy - sy, cz + sz)),  # 5
        bm.verts.new((cx + sx, cy + sy, cz + sz)),  # 6
        bm.verts.new((cx - sx, cy + sy, cz + sz)),  # 7
    ]
    # 顶点顺序经过验证：每个面法线指向 box 外侧
    bm.faces.new([v[0], v[3], v[2], v[1]])  # -Z bottom
    bm.faces.new([v[4], v[5], v[6], v[7]])  # +Z top
    bm.faces.new([v[0], v[1], v[5], v[4]])  # -Y
    bm.faces.new([v[1], v[2], v[6], v[5]])  # +X
    bm.faces.new([v[2], v[3], v[7], v[6]])  # +Y
    bm.faces.new([v[3], v[0], v[4], v[7]])  # -X


def _bm_add_cylinder_y(bm, center, radius, depth, segments=16):
    """沿 Y 轴的实心圆柱（顶/底面朝 ±Y）"""
    cx, cy, cz = center
    mat = (Matrix.Translation((cx, cy, cz))
           @ Matrix.Rotation(math.radians(90), 4, 'X'))
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=segments,
        radius1=radius, radius2=radius, depth=depth, matrix=mat)


def _bm_add_torus_y(bm, center, major_r, minor_r,
                    major_segs=24, minor_segs=8):
    """沿 Y 轴的环面（donut 面朝 ±Y）。环在 XZ 平面，管沿 Y 凸起"""
    cx, cy, cz = center
    rings = []
    for i in range(major_segs):
        ang_maj = (2.0 * math.pi / major_segs) * i
        cos_m, sin_m = math.cos(ang_maj), math.sin(ang_maj)
        ring = []
        for j in range(minor_segs):
            ang_min = (2.0 * math.pi / minor_segs) * j
            cos_n, sin_n = math.cos(ang_min), math.sin(ang_min)
            vx = cx + cos_m * (major_r + cos_n * minor_r)
            vy = cy + sin_n * minor_r
            vz = cz + sin_m * (major_r + cos_n * minor_r)
            ring.append(bm.verts.new((vx, vy, vz)))
        rings.append(ring)
    for i in range(major_segs):
        a = rings[i]
        b = rings[(i + 1) % major_segs]
        for j in range(minor_segs):
            j2 = (j + 1) % minor_segs
            bm.faces.new([a[j], a[j2], b[j2], b[j]])


def create_mesh_obj(name, boxes, coll):
    """boxes: [(center3, size3), ...]; 合并为单一 mesh 对象"""
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm = bmesh.new()
    for center, size in boxes:
        _bm_add_box(bm, center, size)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    move_to_collection(obj, coll)
    tag(obj)
    return obj


# -------------------- 材质（PBR for viewport + 运行时 PBR 渲染）--------------------

# 颜色（linear RGBA 0-1）+ Principled BSDF 参数
_MAT_DEFS = {
    # 房间通用
    "ceiling":    ((0.025, 0.022, 0.018, 1.0), 0.30, 0.90, 0.0),  # 几乎全黑
    "baseboard":  ((0.07, 0.055, 0.020, 1.0),  0.40, 0.85, 0.0),
    "crown":      ((0.07, 0.055, 0.020, 1.0),  0.40, 0.85, 0.0),
    "door":       ((0.10, 0.08, 0.04, 1.0),    0.55, 0.80, 0.0),
    "panel":      ((0.10, 0.55, 0.30, 1.0),    0.30, 0.30, 4.0),
    # v17 墙调色板：7 个橄榄屎暗色变体（G略>R，B极低），每个都是纯 base color
    "wall_olive_0": ((0.012, 0.016, 0.004, 1.0), 0.05, 0.95, 0.0),  # 极暗（最多面积）
    "wall_olive_1": ((0.020, 0.024, 0.007, 1.0), 0.05, 0.95, 0.0),  # 暗
    "wall_olive_2": ((0.030, 0.036, 0.010, 1.0), 0.05, 0.95, 0.0),  # 中暗
    "wall_olive_3": ((0.040, 0.048, 0.014, 1.0), 0.05, 0.95, 0.0),  # 中
    "wall_olive_4": ((0.018, 0.020, 0.012, 1.0), 0.05, 0.95, 0.0),  # 偏冷暗（多点 B）
    "wall_olive_5": ((0.050, 0.045, 0.012, 1.0), 0.05, 0.95, 0.0),  # 偏暖（R≥G，锈感补丁）
    "wall_olive_6": ((0.058, 0.070, 0.022, 1.0), 0.05, 0.95, 0.0),  # 偏亮（少量高光补丁）
    # v19 门：纯色舱门（警示橙棕，跟墙的橄榄屎反差明显）
    "door_solid": ((0.10, 0.045, 0.012, 1.0), 0.10, 0.85, 0.0),     # 深暗橙棕（v21 压暗一倍）
    "wheel":      ((0.45, 0.32, 0.10, 1.0),  0.65, 0.55, 0.0),      # 阀轮黄铜
    "rivet":      ((0.30, 0.22, 0.08, 1.0),  0.55, 0.55, 0.0),      # 铆钉黄铜
    "door_band":  ((0.10, 0.05, 0.015, 1.0), 0.30, 0.75, 0.0),      # 加强带暗棕
}


def _set_bsdf_input(bsdf, candidates, value):
    """跨 Blender 版本兼容地设置 BSDF 输入（按名字尝试多个候选）"""
    for n in candidates:
        if n in bsdf.inputs:
            try:
                bsdf.inputs[n].default_value = value
                return True
            except Exception:
                continue
    return False


def get_or_create_material(key):
    """每次都重置参数到 _MAT_DEFS（避免旧版残留覆盖）"""
    name = f"ship_{key}"
    base, metallic, roughness, emission = _MAT_DEFS[key]
    if name in bpy.data.materials:
        mat = bpy.data.materials[name]
    else:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        return mat
    _set_bsdf_input(bsdf, ("Base Color",), base)
    _set_bsdf_input(bsdf, ("Metallic",), metallic)
    _set_bsdf_input(bsdf, ("Roughness",), roughness)
    # emission 总是显式设置（即使为 0，覆盖旧版的非零值）
    _set_bsdf_input(bsdf, ("Emission Color", "Emission"), base)
    _set_bsdf_input(bsdf, ("Emission Strength",), emission)
    try:
        mat.diffuse_color = base
    except Exception:
        pass
    return mat


def make_rusty_iron_material(name, dark=(0.04, 0.035, 0.030, 1.0),
                              rust=(0.22, 0.10, 0.04, 1.0),
                              scale=8.0, roughness=0.85, metallic=0.55,
                              distortion=1.5, detail=12.0,
                              ramp_lo=0.35, ramp_hi=0.70):
    """程序化锈铁：Noise(distortion) → ColorRamp → BaseColor"""
    if name in bpy.data.materials:
        mat = bpy.data.materials[name]
    else:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    output = nt.nodes.new("ShaderNodeOutputMaterial"); output.location = (500, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled");   bsdf.location = (200, 0)
    coord = nt.nodes.new("ShaderNodeTexCoord");        coord.location = (-700, 100)
    noise = nt.nodes.new("ShaderNodeTexNoise");        noise.location = (-450, 100)
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = detail
    if "Roughness" in noise.inputs:
        noise.inputs["Roughness"].default_value = 0.65
    if "Distortion" in noise.inputs:
        noise.inputs["Distortion"].default_value = distortion

    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-150, 100)
    ramp.color_ramp.interpolation = "LINEAR"  # v10: 改 LINEAR 避免水墨晕染感
    ramp.color_ramp.elements[0].position = ramp_lo
    ramp.color_ramp.elements[0].color = dark
    ramp.color_ramp.elements[1].position = ramp_hi
    ramp.color_ramp.elements[1].color = rust

    nt.links.new(coord.outputs["Generated"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    _set_bsdf_input(bsdf, ("Metallic",), metallic)
    _set_bsdf_input(bsdf, ("Roughness",), roughness)
    try:
        mat.diffuse_color = dark
    except Exception:
        pass
    return mat


def assign_rusty_iron(obj, name, **kwargs):
    if obj is None or obj.type != "MESH":
        return
    mat = make_rusty_iron_material(name, **kwargs)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.material_index = 0


def make_directional_lit_material(name,
        center_dark=(0.005, 0.003, 0.001, 1.0),
        mid_warm=(0.20, 0.14, 0.04, 1.0),
        edge_lit=(0.90, 0.65, 0.12, 1.0),
        noise_scale=30.0,
        roughness=0.55, metallic=0.50,
        fresnel_ior=2.0):
    """
    v10: Fresnel 主导（无 noise mix 稀释），让效果在 viewport 一眼可见
      Fresnel(高 IOR 2.0 让边缘高光范围更大)
        → ColorRamp(3 段：中心纯黑 → 中部暖褐 → 边缘亮柠檬白)
        → 直接到 BaseColor
      Noise 单独驱动 roughness 微变化（让表面不均匀反光）
    高 metallic + 中 roughness 让 fresnel 边缘高光在金属物上极显著
    """
    if name in bpy.data.materials:
        mat = bpy.data.materials[name]
    else:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    output = nt.nodes.new("ShaderNodeOutputMaterial"); output.location = (700, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled");   bsdf.location = (400, 0)

    fresnel = nt.nodes.new("ShaderNodeFresnel");        fresnel.location = (-400, 200)
    fresnel.inputs["IOR"].default_value = fresnel_ior

    ramp_f = nt.nodes.new("ShaderNodeValToRGB");        ramp_f.location = (-100, 200)
    ramp_f.color_ramp.interpolation = "LINEAR"
    ramp_f.color_ramp.elements[0].position = 0.0
    ramp_f.color_ramp.elements[0].color = center_dark
    e_mid = ramp_f.color_ramp.elements.new(0.45)
    e_mid.color = mid_warm
    ramp_f.color_ramp.elements[1].position = 1.0
    ramp_f.color_ramp.elements[1].color = edge_lit

    nt.links.new(fresnel.outputs["Fac"], ramp_f.inputs["Fac"])
    nt.links.new(ramp_f.outputs["Color"], bsdf.inputs["Base Color"])

    # Noise → roughness 微变化（让金属反光不均匀，但不影响颜色）
    coord = nt.nodes.new("ShaderNodeTexCoord");         coord.location = (-700, -200)
    noise = nt.nodes.new("ShaderNodeTexNoise");         noise.location = (-450, -200)
    noise.inputs["Scale"].default_value = noise_scale
    noise.inputs["Detail"].default_value = 8.0
    if "Distortion" in noise.inputs:
        noise.inputs["Distortion"].default_value = 1.2
    ramp_r = nt.nodes.new("ShaderNodeValToRGB");        ramp_r.location = (-150, -200)
    ramp_r.color_ramp.interpolation = "LINEAR"
    ramp_r.color_ramp.elements[0].color = (roughness - 0.15,) * 3 + (1.0,)
    ramp_r.color_ramp.elements[1].color = (min(roughness + 0.20, 0.99),) * 3 + (1.0,)
    nt.links.new(coord.outputs["Generated"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp_r.inputs["Fac"])
    nt.links.new(ramp_r.outputs["Color"], bsdf.inputs["Roughness"])

    nt.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    _set_bsdf_input(bsdf, ("Metallic",), metallic)
    # Roughness 由 noise 驱动，不再硬设
    try:
        mat.diffuse_color = mid_warm  # solid mode 看暖褐而非纯黑
    except Exception:
        pass
    return mat


def assign_directional_lit(obj, name, **kwargs):
    if obj is None or obj.type != "MESH":
        return
    mat = make_directional_lit_material(name, **kwargs)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.material_index = 0


def make_gradient_iron_material(name,
        far_color=(0.55, 0.42, 0.10, 1.0),
        near_color=(0.04, 0.035, 0.015, 1.0),
        noise_scale=4.0, distortion=1.8,
        roughness=0.85, metallic=0.35,
        axis="Y", invert=False):
    """
    沿指定轴渐变 + Noise 不均匀。用于 ±X 墙：
      far_color 在 mesh 的轴 0 端，near_color 在 1 端（或 invert 反过来）
      模拟"光从一端来"在墙上的分布
    """
    if name in bpy.data.materials:
        mat = bpy.data.materials[name]
    else:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    output = nt.nodes.new("ShaderNodeOutputMaterial"); output.location = (700, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled");   bsdf.location = (400, 0)

    coord = nt.nodes.new("ShaderNodeTexCoord");         coord.location = (-900, 100)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ");        sep.location = (-700, 100)
    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    grad_socket = sep.outputs[axis]

    if invert:
        m = nt.nodes.new("ShaderNodeMath");             m.location = (-500, 100)
        m.operation = "SUBTRACT"
        m.inputs[0].default_value = 1.0
        nt.links.new(grad_socket, m.inputs[1])
        grad_socket = m.outputs[0]

    ramp_g = nt.nodes.new("ShaderNodeValToRGB");        ramp_g.location = (-300, 100)
    ramp_g.color_ramp.interpolation = "LINEAR"
    ramp_g.color_ramp.elements[0].position = 0.0
    ramp_g.color_ramp.elements[0].color = far_color
    ramp_g.color_ramp.elements[1].position = 1.0
    ramp_g.color_ramp.elements[1].color = near_color
    nt.links.new(grad_socket, ramp_g.inputs["Fac"])

    # Noise 不均匀 multiplier
    noise = nt.nodes.new("ShaderNodeTexNoise");         noise.location = (-500, -200)
    noise.inputs["Scale"].default_value = noise_scale
    noise.inputs["Detail"].default_value = 10.0
    if "Distortion" in noise.inputs:
        noise.inputs["Distortion"].default_value = distortion
    nt.links.new(coord.outputs["Generated"], noise.inputs["Vector"])
    ramp_n = nt.nodes.new("ShaderNodeValToRGB");        ramp_n.location = (-250, -200)
    ramp_n.color_ramp.interpolation = "LINEAR"
    ramp_n.color_ramp.elements[0].color = (0.55, 0.55, 0.55, 1.0)
    ramp_n.color_ramp.elements[1].color = (1.10, 1.10, 1.10, 1.0)
    nt.links.new(noise.outputs["Fac"], ramp_n.inputs["Fac"])

    mix = nt.nodes.new("ShaderNodeMixRGB");             mix.location = (100, 0)
    mix.blend_type = "MULTIPLY"
    mix.inputs["Fac"].default_value = 0.65
    nt.links.new(ramp_g.outputs["Color"], mix.inputs["Color1"])
    nt.links.new(ramp_n.outputs["Color"], mix.inputs["Color2"])
    nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    _set_bsdf_input(bsdf, ("Metallic",), metallic)
    _set_bsdf_input(bsdf, ("Roughness",), roughness)
    try:
        mat.diffuse_color = far_color
    except Exception:
        pass
    return mat


def assign_gradient_iron(obj, name, **kwargs):
    if obj is None or obj.type != "MESH":
        return
    mat = make_gradient_iron_material(name, **kwargs)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.material_index = 0


def assign_material(obj, key):
    """覆盖所有 material slot，并把所有 face.material_index 归零（兼容多 slot mesh）"""
    if obj is None or obj.type != "MESH":
        return
    mat = get_or_create_material(key)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    # ⚠️ Tripo / Sketchfab mesh 常有多 slot；face.material_index 会指向已不存在的 slot
    # 导致 Blender 显示默认中灰。重置全部 face 到 slot 0。
    for poly in obj.data.polygons:
        poly.material_index = 0


# -------------------- v15: 墙面 subdivide + 调色板分配 --------------------

def subdivide_mesh(obj, cuts=4):
    """对 obj 的 mesh 做整体边细分，每条边切 cuts 刀"""
    if obj is None or obj.type != "MESH":
        return
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.subdivide_edges(
        bm, edges=list(bm.edges), cuts=cuts, use_grid_fill=True)
    bm.to_mesh(obj.data)
    bm.free()


def _stable_hash(*ints):
    """位置稳定 hash（不依赖 Python 内置 hash 的不稳定性）"""
    h = 2166136261
    for x in ints:
        h ^= (x & 0xFFFFFFFF)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def assign_palette_by_position(obj, palette_keys, weights=None, seed=0):
    """
    给 obj 加 palette_keys 里的所有材质作 slots，
    每个 face 按中心位置 stable-hash 分到一个 slot。
    weights: 同 palette_keys 长度的整数 list，控制各色出现概率（默认等权）
    """
    if obj is None or obj.type != "MESH" or not palette_keys:
        return
    obj.data.materials.clear()
    for key in palette_keys:
        obj.data.materials.append(get_or_create_material(key))

    n = len(palette_keys)
    if weights is None:
        weights = [1] * n
    # 展开权重 → 索引表（按权抽签）
    bag = []
    for i, w in enumerate(weights):
        bag.extend([i] * max(1, w))
    bag_len = len(bag)

    for poly in obj.data.polygons:
        c = poly.center
        h = _stable_hash(
            int(c.x * 1000), int(c.y * 1000), int(c.z * 1000), seed)
        poly.material_index = bag[h % bag_len]


def assign_patches_by_region_grow(obj, palette_keys, weights=None, seed=0,
                                  patch_min=2, patch_max=14, grow_prob=0.62):
    """
    v17: 把 mesh face 用区域生长 BFS 分成不规则补丁，每个补丁一色。
      - 在未上色 face 中按顺序选种子 → 抽一种颜色
      - BFS 扩散到相邻 face（共享边），按 grow_prob 概率接受
      - patch 长到 [patch_min, patch_max] 之间随机大小或邻居耗尽即停
      - 下一个未上色 face 成为新补丁的种子
    结果：大小/形状不规则的色块拼接，像焊接铁皮补丁
    """
    if obj is None or obj.type != "MESH" or not palette_keys:
        return
    obj.data.materials.clear()
    for key in palette_keys:
        obj.data.materials.append(get_or_create_material(key))

    n_colors = len(palette_keys)
    if weights is None:
        weights = [1] * n_colors
    bag = []
    for i, w in enumerate(weights):
        bag.extend([i] * max(1, w))
    bag_len = len(bag)

    mesh = obj.data
    # 邻接表：共享 edge_key 的 face 互为邻居
    edge_to_faces = {}
    for f in mesh.polygons:
        for ek in f.edge_keys:
            edge_to_faces.setdefault(ek, []).append(f.index)
    neighbors = {f.index: [] for f in mesh.polygons}
    for ek, fids in edge_to_faces.items():
        if len(fids) == 2:
            a, b = fids
            neighbors[a].append(b)
            neighbors[b].append(a)

    # 可控伪随机（LCG，避免 import random 的全局 seed 污染）
    state = [(seed * 2654435761 + 1) & 0xFFFFFFFF]

    def rand():
        state[0] = (state[0] * 1664525 + 1013904223) & 0xFFFFFFFF
        return state[0] / 0xFFFFFFFF

    assigned = {}
    n_patches = 0
    for seed_face in range(len(mesh.polygons)):
        if seed_face in assigned:
            continue
        color_idx = bag[int(rand() * bag_len) % bag_len]
        target = patch_min + int(rand() * (patch_max - patch_min + 1))
        frontier = [seed_face]
        patch_size = 0
        while frontier and patch_size < target:
            current = frontier.pop(0)
            if current in assigned:
                continue
            assigned[current] = color_idx
            patch_size += 1
            for nb in neighbors[current]:
                if nb in assigned:
                    continue
                if rand() < grow_prob:
                    frontier.append(nb)
        n_patches += 1

    for f in mesh.polygons:
        f.material_index = assigned.get(f.index, 0)
    return n_patches


# -------------------- Empty --------------------

def add_empty(name, location, coll, kind="PLAIN_AXES", size=0.3):
    bpy.ops.object.empty_add(type=kind, location=location)
    obj = bpy.context.active_object
    obj.empty_display_size = size
    obj.name = name
    move_to_collection(obj, coll)
    tag(obj)
    return obj


# -------------------- 主流程 --------------------

def rename_existing_meshes():
    n = 0
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.name.startswith(("R_", "C_", "P_", "excluded_", "_")):
            continue
        clean = o.name.replace(".", "_")
        o.name = f"R_ship_{clean}"
        n += 1
    return n


def identify_device_meshes():
    """devices = 非地板的 R_ship_* 装置 mesh"""
    devices = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if not o.name.startswith("R_"):
            continue
        if o.get("generator") == SCRIPT_TAG:
            continue
        if o.name.startswith("R_floor"):
            continue
        devices.append(o)
    return devices


def restore_and_promote_floor(render_coll):
    """v4: 找原始大薄板地板 mesh，rename 为 R_floor_orig 保留其纹理；
    包括从 v2/v3 _OriginalFloor_excluded collection 中救回来的"""
    promoted = []

    # 先从 v2/v3 排除 collection 救回
    excluded_coll = bpy.data.collections.get(EXCLUDED_COLL_NAME)
    if excluded_coll:
        for o in list(excluded_coll.objects):
            if o.type != "MESH":
                continue
            o.hide_set(False)
            o.name = "R_floor_orig"
            move_to_collection(o, render_coll)
            promoted.append(o)

    # 兜底：扫描所有非脚本生成的 mesh，识别大薄板
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.get("generator") == SCRIPT_TAG:
            continue
        if o in promoted:
            continue
        if o.name.startswith("R_floor"):
            continue
        mn, mx = world_bbox([o])
        sx, sy, sz = mx.x - mn.x, mx.y - mn.y, mx.z - mn.z
        if sz < 0.05 and sx > 5.0 and sy > 5.0:
            o.hide_set(False)
            o.name = "R_floor_orig"
            move_to_collection(o, render_coll)
            promoted.append(o)

    return promoted


def build_floor_ceiling(cx, cy, inner_dx, inner_dy, render_coll, collision_coll):
    """v4: 不再创建 R_floor（使用原始 R_floor_orig 的纹理），只造 C_floor 碰撞 + R_ceiling"""
    t = WALL_T
    fdx = inner_dx + 2 * t
    fdy = inner_dy + 2 * t
    # C_floor：薄碰撞板贴在原地板下方，避免玩家穿地
    create_mesh_obj("C_floor",
        [((cx, cy, -FLOOR_T * 0.5), (fdx, fdy, FLOOR_T))], collision_coll)
    # R_ceiling：房间上方
    create_mesh_obj("R_ceiling",
        [((cx, cy, ROOM_HEIGHT + CEIL_T * 0.5), (fdx, fdy, CEIL_T))], render_coll)


def build_walls(x_min, x_max, y_min, y_max, cx, cy,
                render_coll, collision_coll):
    """
    咬合策略：
      +/-X 墙在 Y 方向延伸 inner_dy + 2t（包住 +/-Y 墙外侧），
      +/-Y 墙在 X 方向只 inner_dx（夹在 +/-X 墙之间）。
    v23: C_wall_* 在房间外侧多扩 C_WALL_OUT_EXPAND（防穿墙）；R_ 不变
    """
    t = WALL_T
    h = ROOM_HEIGHT
    inner_dx = x_max - x_min
    inner_dy = y_max - y_min
    e = C_WALL_OUT_EXPAND
    t_c = t + e   # C_ 墙厚度
    half_e = e * 0.5

    # +X：R 在 x_max+t/2；C 在 x_max+t/2 + e/2（中心外移 e/2，厚度+e）
    create_mesh_obj("R_wall_xpos",
        [((x_max + t * 0.5, cy, h * 0.5), (t, inner_dy + 2 * t, h))],
        render_coll)
    create_mesh_obj("C_wall_xpos",
        [((x_max + t * 0.5 + half_e, cy, h * 0.5),
          (t_c, inner_dy + 2 * t, h))],
        collision_coll)
    # -X
    create_mesh_obj("R_wall_xneg",
        [((x_min - t * 0.5, cy, h * 0.5), (t, inner_dy + 2 * t, h))],
        render_coll)
    create_mesh_obj("C_wall_xneg",
        [((x_min - t * 0.5 - half_e, cy, h * 0.5),
          (t_c, inner_dy + 2 * t, h))],
        collision_coll)
    # +Y（无门）
    create_mesh_obj("R_wall_ypos",
        [((cx, y_max + t * 0.5, h * 0.5), (inner_dx, t, h))],
        render_coll)
    create_mesh_obj("C_wall_ypos",
        [((cx, y_max + t * 0.5 + half_e, h * 0.5),
          (inner_dx, t_c, h))],
        collision_coll)

    # -Y（带门洞，3 段合成单一 mesh）
    door_cx = cx
    left_w = (door_cx - DOOR_W * 0.5) - x_min
    right_w = x_max - (door_cx + DOOR_W * 0.5)
    lintel_h = h - DOOR_H
    wall_y = y_min - t * 0.5
    wall_y_c = wall_y - half_e   # C_ 中心向 -Y 外移
    boxes_r, boxes_c = [], []
    if left_w > 0.01:
        boxes_r.append(((x_min + left_w * 0.5, wall_y, h * 0.5),
                        (left_w, t, h)))
        boxes_c.append(((x_min + left_w * 0.5, wall_y_c, h * 0.5),
                        (left_w, t_c, h)))
    if right_w > 0.01:
        boxes_r.append(((x_max - right_w * 0.5, wall_y, h * 0.5),
                        (right_w, t, h)))
        boxes_c.append(((x_max - right_w * 0.5, wall_y_c, h * 0.5),
                        (right_w, t_c, h)))
    if lintel_h > 0.01:
        boxes_r.append(((door_cx, wall_y, DOOR_H + lintel_h * 0.5),
                        (DOOR_W, t, lintel_h)))
        boxes_c.append(((door_cx, wall_y_c, DOOR_H + lintel_h * 0.5),
                        (DOOR_W, t_c, lintel_h)))
    if boxes_r:
        create_mesh_obj("R_wall_yneg", boxes_r, render_coll)
        create_mesh_obj("C_wall_yneg", boxes_c, collision_coll)
    return door_cx


def build_door(door_cx, y_min, render_coll, collision_coll):
    """
    v20: 门板紧贴墙的室内侧（y=y_min），所有装饰朝室内方向 +Y 凸出
      + 阀轮改 torus 环 + hub 圆柱 + 双向辐条 box
    """
    panel_full_w = DOOR_W - 0.01
    panel_h_eff = DOOR_H - 0.01

    # 门板：紧贴墙的室内面，向外侧延伸（不再居中在墙厚度中央）
    door_panel_cy = y_min - DOOR_PANEL_T * 0.5
    create_mesh_obj("R_door_panel",
        [((door_cx, door_panel_cy, DOOR_H * 0.5),
          (panel_full_w, DOOR_PANEL_T, panel_h_eff))],
        render_coll)
    create_mesh_obj("C_door_panel",
        [((door_cx, door_panel_cy, DOOR_H * 0.5),
          (panel_full_w, DOOR_PANEL_T, panel_h_eff))],
        collision_coll)

    # 室内面（门板朝室内的一面）= y_min
    inner_face_y = y_min

    # 水平加强带（全宽，凸出室内 4cm）
    band_h = 0.10
    band_d = 0.04
    band_y = inner_face_y + band_d * 0.5
    create_mesh_obj("R_door_band",
        [((door_cx, band_y, DOOR_H * 0.5),
          (panel_full_w - 0.04, band_d, band_h))],
        render_coll)

    # 6 颗铆钉，凸出室内 2.5cm
    rivet_size = 0.045
    rivet_d = 0.025
    rivet_y = inner_face_y + rivet_d * 0.5
    rivet_margin = 0.10
    rivet_xs = [door_cx - panel_full_w * 0.5 + rivet_margin,
                door_cx + panel_full_w * 0.5 - rivet_margin]
    rivet_zs_corners = [rivet_margin + 0.02,
                        DOOR_H - rivet_margin - 0.02]
    rivet_boxes = []
    for rx in rivet_xs:
        for rz in rivet_zs_corners:
            rivet_boxes.append(
                ((rx, rivet_y, rz), (rivet_size, rivet_d, rivet_size)))
    band_top_z = DOOR_H * 0.5 + band_h * 0.5
    band_bot_z = DOOR_H * 0.5 - band_h * 0.5
    rivet_boxes.append(
        ((door_cx, rivet_y, band_top_z + 0.15),
         (rivet_size, rivet_d, rivet_size)))
    rivet_boxes.append(
        ((door_cx, rivet_y, band_bot_z - 0.15),
         (rivet_size, rivet_d, rivet_size)))
    create_mesh_obj("R_door_rivets", rivet_boxes, render_coll)

    # v20: 阀轮 — torus 环 + hub 圆柱 + 水平/垂直辐条
    wheel_cz = DOOR_H * 0.5 - 0.45
    major_r = 0.18       # 环中心半径
    minor_r = 0.025      # 环管半径
    hub_r = 0.05         # hub 半径
    hub_depth = 0.09     # hub 凸出 9cm（比环更突出）
    spoke_w = 0.030      # 辐条横截面宽（XZ 平面方向）
    spoke_d = 0.045      # 辐条凸出深度（Y 方向）

    wheel_mesh = bpy.data.meshes.new("R_door_wheel_mesh")
    bm = bmesh.new()
    # torus 环（管中心在 y = inner_face_y + minor_r → 整环凸出 2×minor_r=5cm）
    _bm_add_torus_y(
        bm, (door_cx, inner_face_y + minor_r, wheel_cz),
        major_r, minor_r, major_segs=32, minor_segs=10)
    # hub 圆柱
    _bm_add_cylinder_y(
        bm, (door_cx, inner_face_y + hub_depth * 0.5, wheel_cz),
        hub_r, hub_depth, segments=14)
    # 辐条：水平 + 垂直，跨越整环（XZ 方向 box，沿 Y 凸出 spoke_d）
    spoke_y = inner_face_y + spoke_d * 0.5
    arm_full = (major_r + minor_r) * 2  # 跨越外环外缘
    _bm_add_box(bm, (door_cx, spoke_y, wheel_cz),
                (arm_full, spoke_d, spoke_w))   # 水平辐条
    _bm_add_box(bm, (door_cx, spoke_y, wheel_cz),
                (spoke_w, spoke_d, arm_full))   # 垂直辐条
    bm.to_mesh(wheel_mesh)
    bm.free()
    wheel_obj = bpy.data.objects.new("R_door_wheel", wheel_mesh)
    move_to_collection(wheel_obj, render_coll)
    tag(wheel_obj)

    # 门顶控制面板（绿色发光盒，暗示"已锁"）— 室内侧
    cp_w, cp_h, cp_d = 0.32, 0.10, 0.04
    cp_z = DOOR_H + 0.18
    cp_y = inner_face_y + cp_d * 0.5 + 0.01
    create_mesh_obj("R_door_panel_ctrl",
        [((door_cx, cp_y, cp_z), (cp_w, cp_d, cp_h))],
        render_coll)

    # v21: 去掉室内门框（PA 反馈室内不要门框装饰）


def build_trim(cx, cy, x_min, x_max, y_min, y_max, door_cx, render_coll):
    bh = BASEBOARD_H
    p = BASEBOARD_PROUD
    inner_dx = x_max - x_min
    inner_dy = y_max - y_min

    # 踢脚线：4 边合并（-Y 边避开门洞，拆左右两段）
    bb = []
    bb.append(((x_max - p * 0.5, cy, bh * 0.5), (p, inner_dy, bh)))
    bb.append(((x_min + p * 0.5, cy, bh * 0.5), (p, inner_dy, bh)))
    bb.append(((cx, y_max - p * 0.5, bh * 0.5), (inner_dx, p, bh)))
    left_w = (door_cx - DOOR_W * 0.5) - x_min
    right_w = x_max - (door_cx + DOOR_W * 0.5)
    if left_w > 0.01:
        bb.append(((x_min + left_w * 0.5, y_min + p * 0.5, bh * 0.5),
                   (left_w, p, bh)))
    if right_w > 0.01:
        bb.append(((x_max - right_w * 0.5, y_min + p * 0.5, bh * 0.5),
                   (right_w, p, bh)))
    create_mesh_obj("R_baseboard", bb, render_coll)

    # 顶线：4 边完整
    ch = CROWN_H
    cz = ROOM_HEIGHT - ch * 0.5
    crown = [
        ((x_max - p * 0.5, cy, cz), (p, inner_dy, ch)),
        ((x_min + p * 0.5, cy, cz), (p, inner_dy, ch)),
        ((cx, y_max - p * 0.5, cz), (inner_dx, p, ch)),
        ((cx, y_min + p * 0.5, cz), (inner_dx, p, ch)),
    ]
    create_mesh_obj("R_crown", crown, render_coll)


def build_device_collision(devices, collision_coll):
    """为每个 R_ship_* 装置 mesh 生成 AABB 碰撞代理 C_ship_*。
    v18: 增强日志——列出每个 device 拿到的碰撞 size，让 PA 可见全部生成情况。
    v28: 跟踪每个 collision_free marker 实际挖到了哪几个 device，事后报告
    跳过：过小（<5cm任一轴）/ 大薄板（>6m×6m×<20cm 是原地板兜底）"""
    n = 0
    skipped = []
    # v28: marker_name -> set(device_clean_name)
    marker_touched = {name: [] for (_, _, name) in _COLLISION_FREE_BBOXES}
    for o in devices:
        if not o.name.startswith("R_ship_"):
            continue
        mn, mx = world_bbox([o])
        size = mx - mn
        if size.x < 0.05 or size.y < 0.05 or size.z < 0.05:
            skipped.append((o.name, "too-small",
                            (size.x, size.y, size.z)))
            continue
        if size.x > 6.0 and size.y > 6.0 and size.z < 0.2:
            skipped.append((o.name, "thin-plate",
                            (size.x, size.y, size.z)))
            continue
        clean = o.name.replace("R_ship_", "")
        if clean in COLLISION_SKIP_ORIG_NAMES:
            skipped.append((o.name, "configured-skip (gaps)",
                            (size.x, size.y, size.z)))
            continue
        center = (mn + mx) * 0.5
        # v24: 默认 inset + per-name override
        inset = COLLISION_INSET_OVERRIDES.get(clean, C_DEVICE_INSET)
        sx_c = max(0.10, size.x - 2 * inset)
        sy_c = max(0.10, size.y - 2 * inset)
        sz_c = size.z  # Z 不缩（不影响走道宽度，且避免桌面变矮的诡异感）
        # v26/27: 减去所有 collision_free 标记区域（v27 默认 Z 自动延全高）
        c_center = (center.x, center.y, center.z)
        c_size = (sx_c, sy_c, sz_c)
        holes = []
        # v28: 单独检查每个 marker 是否真碰到这个 device
        for (mn3, mx3, m_name) in _COLLISION_FREE_BBOXES:
            # v30: 按各轴 flag 决定是否自动延伸
            hmn_y = -1000.0 if COLLISION_FREE_AUTO_EXTEND_Y else mn3[1]
            hmx_y = +1000.0 if COLLISION_FREE_AUTO_EXTEND_Y else mx3[1]
            hmn_z = -1.0 if COLLISION_FREE_AUTO_EXTEND_Z else mn3[2]
            hmx_z = ROOM_HEIGHT + 1.0 if COLLISION_FREE_AUTO_EXTEND_Z else mx3[2]
            hmn = (mn3[0], hmn_y, hmn_z)
            hmx = (mx3[0], hmx_y, hmx_z)
            holes.append((hmn, hmx))
            # 简单 AABB 相交检测
            cmn = [c_center[i] - c_size[i] * 0.5 for i in range(3)]
            cmx = [c_center[i] + c_size[i] * 0.5 for i in range(3)]
            if (cmn[0] < hmx[0] and cmx[0] > hmn[0] and
                cmn[1] < hmx[1] and cmx[1] > hmn[1] and
                cmn[2] < hmx[2] and cmx[2] > hmn[2]):
                marker_touched[m_name].append(clean)
        final_boxes = carve_box_with_holes(c_center, c_size, holes)
        if not final_boxes:
            skipped.append((o.name, "carved out by collision_free",
                            (sx_c, sy_c, sz_c)))
            continue
        create_mesh_obj(f"C_ship_{clean}", final_boxes, collision_coll)
        tag_inset = "(override)" if clean in COLLISION_INSET_OVERRIDES else ""
        carve_note = f"  carved={len(final_boxes)}slabs" if len(final_boxes) > 1 else ""
        print(f"[collision]   C_ship_{clean}  "
              f"render=({size.x:.2f},{size.y:.2f},{size.z:.2f})  "
              f"collide=({sx_c:.2f},{sy_c:.2f},{sz_c:.2f})  "
              f"inset={inset:.2f}{tag_inset}  "
              f"center=({center.x:+.2f},{center.y:+.2f}){carve_note}")
        n += 1
    for name, reason, sz in skipped:
        print(f"[collision]   SKIP {name} ({reason}) size={sz}")
    # v28: per-marker 报告
    if _COLLISION_FREE_BBOXES:
        print(f"[collision] --- collision_free marker 挖掘报告 ---")
        for m_name, touched in marker_touched.items():
            if touched:
                print(f"[collision]   {m_name} 挖到: {touched}")
            else:
                print(f"[collision]   {m_name} ⚠ 没碰到任何 device "
                      f"（marker 太小/位置偏？这个 marker 没起作用）")
    return n


def hide_collision_viewport(collision_coll):
    for o in collision_coll.objects:
        try:
            o.hide_set(True)
        except RuntimeError:
            o.hide_viewport = True


# -------------------- v26: collision_free 标记处理 --------------------

# 全局：收集到的 collision_free* bbox 列表，元素是 (mn3, mx3, name)
_COLLISION_FREE_BBOXES = []


def gather_collision_free():
    """扫当前 Blender 场景里所有 collision_free* mesh，返回其 world bbox 列表"""
    out = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if not o.name.lower().startswith("collision_free"):
            continue
        mn, mx = world_bbox([o])
        out.append((tuple(mn), tuple(mx), o.name))
    return out


def try_read_markers_from_output_glb(path):
    """v31: 临时 import 输出 GLB，挖出 collision_free* 的 world bbox，然后删掉刚 import 的对象。
    用于 PA 工作 .blend 不含 marker、marker 只存在于已导出 scene.glb 的情况。"""
    if not _os.path.isfile(path):
        print(f"[finalize] (output GLB 不存在，跳过 marker fallback 读取: {path})")
        return []
    pre = set(bpy.data.objects.keys())
    try:
        bpy.ops.import_scene.gltf(filepath=path)
    except Exception as e:
        print(f"[finalize] WARN: 读取输出 GLB 失败: {e}")
        return []
    post = set(bpy.data.objects.keys())
    new_names = post - pre
    new_objs = [bpy.data.objects[n] for n in new_names if n in bpy.data.objects]

    out = []
    all_mesh_names = []
    for o in new_objs:
        if o.type != "MESH":
            continue
        all_mesh_names.append(o.name)
        # 宽松匹配：名字里包含 "collision_free" / "collisionfree" / "no_collision" 都接受
        nm = o.name.lower()
        if ("collision_free" in nm or "collisionfree" in nm
                or "no_collision" in nm or nm.startswith("free")):
            mn, mx = world_bbox([o])
            clean = o.name.split(".")[0]
            out.append((tuple(mn), tuple(mx), clean))
            print(f"[finalize]   matched marker in output GLB: '{o.name}'")

    # v32: 列出输出 GLB 里所有 mesh 名字，方便定位为什么 marker 没找到
    print(f"[finalize] output GLB contains {len(all_mesh_names)} mesh objects:")
    for nm in sorted(all_mesh_names):
        print(f"[finalize]   - {nm}")

    # 删除所有刚 import 进来的对象
    for o in new_objs:
        try:
            bpy.data.objects.remove(o, do_unlink=True)
        except Exception:
            pass

    return out


def subtract_aabb(c_center, c_size, hole_min, hole_max, eps=0.01):
    """
    标准 3D AABB 差集：返回 c (center, size) 减去 hole (min,max) 后的 box 列表（最多 6 个 slab）
    - 不相交 → 返回原 c
    - hole 包含 c → 返回 []
    - 部分相交 → 返回 1-6 个 slab，每个 (center, size)
    """
    c_min = [c_center[i] - c_size[i] * 0.5 for i in range(3)]
    c_max = [c_center[i] + c_size[i] * 0.5 for i in range(3)]
    # 重叠区
    ov_min = [max(c_min[i], hole_min[i]) for i in range(3)]
    ov_max = [min(c_max[i], hole_max[i]) for i in range(3)]
    if any(ov_min[i] >= ov_max[i] - 1e-6 for i in range(3)):
        return [(tuple(c_center), tuple(c_size))]

    result = []
    rem_min = list(c_min)
    rem_max = list(c_max)
    for axis in range(3):
        # before-hole slab
        if rem_min[axis] < ov_min[axis] - 1e-6:
            sl_min = list(rem_min)
            sl_max = list(rem_max)
            sl_max[axis] = ov_min[axis]
            size = [sl_max[i] - sl_min[i] for i in range(3)]
            # v29: 丢弃 XY 任一边 < CARVE_MIN_SLAB_XY 的薄 slab（裁切伪影）
            if (all(s > eps for s in size)
                    and min(size[0], size[1]) >= CARVE_MIN_SLAB_XY):
                center = [(sl_min[i] + sl_max[i]) * 0.5 for i in range(3)]
                result.append((tuple(center), tuple(size)))
        # after-hole slab
        if ov_max[axis] < rem_max[axis] - 1e-6:
            sl_min = list(rem_min)
            sl_max = list(rem_max)
            sl_min[axis] = ov_max[axis]
            size = [sl_max[i] - sl_min[i] for i in range(3)]
            if (all(s > eps for s in size)
                    and min(size[0], size[1]) >= CARVE_MIN_SLAB_XY):
                center = [(sl_min[i] + sl_max[i]) * 0.5 for i in range(3)]
                result.append((tuple(center), tuple(size)))
        # remaining 收紧到 hole 在该轴的区间
        rem_min[axis] = ov_min[axis]
        rem_max[axis] = ov_max[axis]
    return result


def carve_box_with_holes(center, size, holes):
    """对 (center, size) 依次减去每个 hole（(mn, mx) tuple），返回最终 box 列表"""
    boxes = [(tuple(center), tuple(size))]
    for hmn, hmx in holes:
        new = []
        for c, s in boxes:
            new.extend(subtract_aabb(c, s, hmn, hmx))
        boxes = new
        if not boxes:
            break
    return boxes


def recreate_collision_free_markers(saved_markers, coll):
    """把保存的 collision_free* bbox 重新建成 hidden mesh，导出后下次跑脚本仍能扫到。
    名字不带 R_/C_/P_/M_ 前缀 → 运行时 src/content/mod.rs 归 Cat::Skip 忽略"""
    for mn, mx, name in saved_markers:
        center = ((mn[0] + mx[0]) * 0.5,
                  (mn[1] + mx[1]) * 0.5,
                  (mn[2] + mx[2]) * 0.5)
        size = (mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2])
        obj = create_mesh_obj(name, [(center, size)], coll)
        try:
            obj.hide_set(True)
        except RuntimeError:
            obj.hide_viewport = True


# -------------------- v16: 自包含场景准备 --------------------

def wipe_scene():
    """彻底清空：所有 mesh/empty/light/camera 对象 + collections 里的孤儿数据"""
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    # 清空孤儿数据（避免名字冲突累积）
    for block in (bpy.data.meshes, bpy.data.materials,
                  bpy.data.images, bpy.data.textures):
        for db in list(block):
            if db.users == 0:
                block.remove(db)
    # 移除非 master 的 collection
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)


def import_source_glb(path):
    """import 源 surveillance_room GLB 到当前场景"""
    if not _os.path.isfile(path):
        print(f"[finalize] FATAL: source GLB not found: {path}")
        return False
    try:
        bpy.ops.import_scene.gltf(filepath=path)
        return True
    except Exception as e:
        print(f"[finalize] FATAL: glTF import failed: {e}")
        return False




def main():
    print("=" * 64)
    print(f"[finalize] start  tag={SCRIPT_TAG}  CLEAN_IMPORT={CLEAN_IMPORT}")

    # v26/31: wipe 前先抢救 collision_free* 标记的 bbox
    # v31: 如果当前 .blend 没有 marker，自动从输出 GLB 里读
    global _COLLISION_FREE_BBOXES
    _COLLISION_FREE_BBOXES = gather_collision_free()
    if _COLLISION_FREE_BBOXES:
        print(f"[finalize] markers from CURRENT scene: "
              f"{[m[2] for m in _COLLISION_FREE_BBOXES]}")
    else:
        print(f"[finalize] 当前 .blend 无 collision_free marker，尝试从输出 GLB 读...")
        _COLLISION_FREE_BBOXES = try_read_markers_from_output_glb(OUTPUT_SCENE_GLB)
        if _COLLISION_FREE_BBOXES:
            print(f"[finalize] markers from OUTPUT GLB: "
                  f"{[m[2] for m in _COLLISION_FREE_BBOXES]}")
        else:
            print(f"[finalize] 输出 GLB 也没有 collision_free marker（跳过 carve）")
    if _COLLISION_FREE_BBOXES:
        notes = []
        if COLLISION_FREE_AUTO_EXTEND_Y:
            notes.append("Y→full room")
        if COLLISION_FREE_AUTO_EXTEND_Z:
            notes.append("Z→full height")
        ext_note = f" (auto-extend: {', '.join(notes)})" if notes else ""
        print(f"[finalize] collision_free markers preserved: "
              f"{[m[2] for m in _COLLISION_FREE_BBOXES]}{ext_note}")
        for mn3, mx3, name in _COLLISION_FREE_BBOXES:
            print(f"[finalize]   {name}: "
                  f"x=[{mn3[0]:+.2f},{mx3[0]:+.2f}] "
                  f"y=[{mn3[1]:+.2f},{mx3[1]:+.2f}] "
                  f"z=[{mn3[2]:+.2f},{mx3[2]:+.2f}]")

    if CLEAN_IMPORT:
        wipe_scene()
        print(f"[finalize] wiped scene clean")
        ok = import_source_glb(SOURCE_GLB)
        if not ok:
            return
        n_imp = len(bpy.data.objects)
        print(f"[finalize] imported {SOURCE_GLB}")
        print(f"[finalize]   -> {n_imp} objects in scene")
    else:
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for o in bpy.data.objects:
            o.select_set(False)

    removed = clear_previous_run()
    print(f"[finalize] cleared {removed} objects from previous runs")

    render_coll = ensure_collection("Render")
    collision_coll = ensure_collection("Collision")
    markers_coll = ensure_collection("Markers")
    ensure_collection("Phantoms")

    renamed = rename_existing_meshes()
    print(f"[finalize] renamed {renamed} existing meshes")

    for o in bpy.data.objects:
        if (o.type == "MESH" and o.name.startswith("R_")
                and o.get("generator") != SCRIPT_TAG):
            move_to_collection(o, render_coll)

    promoted_floor = restore_and_promote_floor(render_coll)
    print(f"[finalize] promoted {len(promoted_floor)} original floor mesh -> R_floor_orig "
          "(纹理保留)")

    devices = identify_device_meshes()
    print(f"[finalize] device meshes={len(devices)}")

    if not devices:
        print("[finalize] ERR: 未识别到装置 mesh，中止")
        return

    dmn, dmx = world_bbox(devices)
    print(f"[finalize] device bbox  "
          f"min=({dmn.x:+.2f},{dmn.y:+.2f},{dmn.z:+.2f}) "
          f"max=({dmx.x:+.2f},{dmx.y:+.2f},{dmx.z:+.2f})")

    x_min = dmn.x - PLAYER_PADDING
    x_max = dmx.x + PLAYER_PADDING
    y_min = dmn.y - PLAYER_PADDING + WALL_YNEG_INSET   # v10: -Y 墙向 +Y 收紧
    y_max = dmx.y + PLAYER_PADDING
    cx = (x_min + x_max) * 0.5
    cy = (y_min + y_max) * 0.5
    inner_dx = x_max - x_min
    inner_dy = y_max - y_min
    print(f"[finalize] room inner {inner_dx:.2f} x {inner_dy:.2f} m, "
          f"h={ROOM_HEIGHT}, center=({cx:+.2f},{cy:+.2f}) "
          f"[-Y inset {WALL_YNEG_INSET}m]")

    build_floor_ceiling(cx, cy, inner_dx, inner_dy, render_coll, collision_coll)
    door_cx = build_walls(x_min, x_max, y_min, y_max, cx, cy,
                          render_coll, collision_coll)
    build_door(door_cx, y_min, render_coll, collision_coll)
    build_trim(cx, cy, x_min, x_max, y_min, y_max, door_cx, render_coll)

    print(f"[finalize] --- device collision generation ---")
    n_col = build_device_collision(devices, collision_coll)
    print(f"[finalize] generated {n_col} C_ship_* proxies (covers {len(devices)} R_ship_* devices)")

    # v25: 走道净宽分析（每个 C_ship_* 到 4 面墙的最短距离）
    print(f"[finalize] --- 走道净宽分析（C_ship_* 边缘 → 墙内表面）---")
    wall_x_min = x_min            # 墙的内表面
    wall_x_max = x_max
    wall_y_min = y_min
    wall_y_max = y_max
    for o in collision_coll.objects:
        if not o.name.startswith("C_ship_"):
            continue
        cmn, cmx = world_bbox([o])
        gap_xneg = cmn.x - wall_x_min
        gap_xpos = wall_x_max - cmx.x
        gap_yneg = cmn.y - wall_y_min
        gap_ypos = wall_y_max - cmx.y
        warn = "  ⚠ <0.5m" if min(gap_xneg, gap_xpos, gap_yneg, gap_ypos) < 0.5 else ""
        print(f"[finalize]   {o.name}: "
              f"-X={gap_xneg:.2f}  +X={gap_xpos:.2f}  "
              f"-Y={gap_yneg:.2f}  +Y={gap_ypos:.2f}{warn}")

    # 墙：4 面独立材质，按距屏幕/朝向区分亮暗
    # 屏幕装置朝 -Y 辐射柠檬土黄光：
    #   -Y 墙（门，正对屏幕辐射方向）→ 最亮、大块高光
    #   +Y 墙（屏幕背后）→ 几乎全暗
    #   ±X 墙（侧向掠射）→ 中等
    # ramp_lo/hi 控制亮斑占比（lo 越大暗区越多；hi 越大亮区越窄）
    # v9: rust 提饱和（高光更鲜艳柠檬土黄），让方向性差异更突出
    # ±Y 墙：均匀方向性（仍用 rusty_iron）
    # v17: 4 面墙 subdivide + 区域生长 BFS 补丁分配
    # 权重 [5,4,3,3,2,2,1] → wall_olive_0/1(极暗)占比最大，wall_olive_6(偏亮)只 1/20
    # cuts=6 → 7×7=49 quads/面 × 6 面 = 294 quads/box（足够补丁分辨率）
    # patch_min=2 / patch_max=14 / grow_prob=0.62 → 多数补丁 4-10 quads，少数 2-3 或 12-14
    palette_weights = [5, 4, 3, 3, 2, 2, 1]
    for idx, wall_name in enumerate(
            ("R_wall_xpos", "R_wall_xneg",
             "R_wall_ypos", "R_wall_yneg")):
        o = bpy.data.objects.get(wall_name)
        if o is None:
            continue
        subdivide_mesh(o, cuts=WALL_SUBDIV_CUTS)
        n_patches = assign_patches_by_region_grow(
            o, _WALL_PALETTE, weights=palette_weights, seed=idx * 991 + 17,
            patch_min=2, patch_max=14, grow_prob=0.62)
        print(f"[finalize]   {wall_name}: "
              f"{len(o.data.polygons)} quads grouped into ~{n_patches} patches "
              f"({len(_WALL_PALETTE)} olive shades)")
    print(f"[finalize] walls: region-grow patches (irregular weld-plate look)")

    # v19: 门构件全部纯色（不再补丁），用强对比警示橙棕跟橄榄墙拉开
    mat_assignments = [
        ("R_ceiling", "ceiling"),
        ("R_baseboard", "baseboard"),
        ("R_crown", "crown"),
        ("R_door_panel", "door_solid"),
        ("R_door_wheel", "wheel"),
        ("R_door_panel_ctrl", "panel"),
        ("R_door_band", "door_band"),
        ("R_door_rivets", "rivet"),
    ]
    n_mat = 0
    for obj_name, mat_key in mat_assignments:
        obj = bpy.data.objects.get(obj_name)
        if obj:
            assign_material(obj, mat_key)
            n_mat += 1
    print(f"[finalize] assigned PBR materials to {n_mat} render objects")

    # spawn：门内侧 0.8m
    spawn = (cx, y_min + 0.8, 0.0)
    add_empty("M_spawn_main", spawn, markers_coll, "ARROWS", 0.4)
    print(f"[finalize] M_spawn_main at ({spawn[0]:+.2f},{spawn[1]:+.2f},{spawn[2]:+.2f})")

    hide_collision_viewport(collision_coll)
    print(f"[finalize] hidden {len(collision_coll.objects)} collision objects in viewport")

    # v26: 重建 collision_free* 标记到场景（持久化到下次跑脚本）
    if _COLLISION_FREE_BBOXES:
        recreate_collision_free_markers(_COLLISION_FREE_BBOXES, markers_coll)
        print(f"[finalize] recreated {len(_COLLISION_FREE_BBOXES)} "
              f"collision_free markers (hidden, no prefix → runtime ignores)")

    print("[finalize] DONE.")
    print("[finalize] 导出前：选所有 R_/C_ → Ctrl+A → All Transforms")
    print("[finalize] 导出 glTF 2.0 时 Include → Limit to 全部不勾")
    print("=" * 64)


if __name__ == "__main__":
    main()
