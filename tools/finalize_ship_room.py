"""
finalize_ship_room.py v14 — 4 面墙统一深橄榄屎色 + goggle 重合诊断确认

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

PA 用法：
  Scripting → Open → tools/finalize_ship_room.py → Run Script
  导出前选所有 R_/C_/P_ → Object → Apply → All Transforms
  File → Export → glTF 2.0:
    - Format: glTF Binary
    - Include → Limit to: 全部不勾
    - Transform → +Y Up: 勾
    - 路径：content/levels/ship_room/scene.glb

幂等：本脚本生成的对象带 generator=SCRIPT_TAG，重跑会清理重建。
"""

import bpy
import bmesh
from mathutils import Vector

SCRIPT_TAG = "ship_room_finalize_v14"
_OLD_TAGS = ("ship_room_finalize_v1", "ship_room_finalize_v2",
             "ship_room_finalize_v3", "ship_room_finalize_v4",
             "ship_room_finalize_v5", "ship_room_finalize_v6",
             "ship_room_finalize_v7", "ship_room_finalize_v8",
             "ship_room_finalize_v9", "ship_room_finalize_v10",
             "ship_room_finalize_v11", "ship_room_finalize_v12",
             "ship_room_finalize_v13")

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
GOGGLES_ROOT = "CodexScaleRoot_Goggles"

# v12: goggle 分区显式映射（key = rename 后的 mesh 名，value = 材质 key）
# 第一次跑脚本时这个 dict 是空的 → 全部 fallback 到 goggles_shell
# 控制台会打印每个 mesh 的 verts / bbox / center
# PA 看完后把 4 个名字 + 想要的材质 key 填进来，下次跑就生效
# 可用 material key: goggles_shell, goggles_strap, goggles_lens, goggles_misc
GOGGLES_PART_MAP = {
    # 例: "R_goggles_part_Object_5": "goggles_shell",
}


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
    # v7: 被装置柠檬+土黄光照亮的脏旧集装箱舱内
    "ceiling":    ((0.025, 0.022, 0.018, 1.0), 0.30, 0.90, 0.0),  # 几乎全黑
    "wall":       ((0.14, 0.12, 0.10, 1.0),    0.40, 0.85, 0.0),  # 兜底（实际墙走 rusty_iron）
    "baseboard":  ((0.07, 0.055, 0.020, 1.0),  0.40, 0.85, 0.0),  # v13 压暗
    "crown":      ((0.07, 0.055, 0.020, 1.0),  0.40, 0.85, 0.0),
    "door":       ((0.10, 0.08, 0.04, 1.0),    0.55, 0.80, 0.0),  # 深锈黄黑（融入环境）
    "door_frame": ((0.38, 0.28, 0.08, 1.0),    0.85, 0.50, 0.0),  # 锈黄铜（让门可见）
    "handle":     ((0.42, 0.38, 0.25, 1.0),    0.75, 0.50, 0.0),  # 磨损脏金属
    "panel":      ((0.10, 0.55, 0.30, 1.0),    0.30, 0.30, 4.0),  # 发光绿（更亮，暗里更显眼）
    # goggles: v11 手动分区上色（4 个 mesh 各一色，融入环境屎黄色调）
    "goggles_shell":  ((0.16, 0.11, 0.04, 1.0), 0.15, 0.85, 0.0),  # 外壳：暗棕
    "goggles_strap":  ((0.22, 0.16, 0.06, 1.0), 0.05, 0.92, 0.0),  # 带子：黄褐布感
    "goggles_lens":   ((0.020, 0.018, 0.012, 1.0), 0.20, 0.65, 0.0),  # 镜片：几乎黑亮
    "goggles_misc":   ((0.18, 0.13, 0.05, 1.0), 0.55, 0.55, 0.0),  # 按钮/小件：暗黄铜
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
        if is_under(o, GOGGLES_ROOT):
            o.name = f"R_goggles_part_{clean}"
        else:
            o.name = f"R_ship_{clean}"
        n += 1
    return n


def identify_device_meshes():
    """devices = 非地板、非 goggles 的 R_ship_* 装置 mesh"""
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
        if o.name.startswith("R_goggles"):
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
    """
    t = WALL_T
    h = ROOM_HEIGHT
    inner_dx = x_max - x_min
    inner_dy = y_max - y_min

    # +X
    create_mesh_obj("R_wall_xpos",
        [((x_max + t * 0.5, cy, h * 0.5), (t, inner_dy + 2 * t, h))],
        render_coll)
    create_mesh_obj("C_wall_xpos",
        [((x_max + t * 0.5, cy, h * 0.5), (t, inner_dy + 2 * t, h))],
        collision_coll)
    # -X
    create_mesh_obj("R_wall_xneg",
        [((x_min - t * 0.5, cy, h * 0.5), (t, inner_dy + 2 * t, h))],
        render_coll)
    create_mesh_obj("C_wall_xneg",
        [((x_min - t * 0.5, cy, h * 0.5), (t, inner_dy + 2 * t, h))],
        collision_coll)
    # +Y（无门）
    create_mesh_obj("R_wall_ypos",
        [((cx, y_max + t * 0.5, h * 0.5), (inner_dx, t, h))],
        render_coll)
    create_mesh_obj("C_wall_ypos",
        [((cx, y_max + t * 0.5, h * 0.5), (inner_dx, t, h))],
        collision_coll)

    # -Y（带门洞，3 段合成单一 mesh）
    door_cx = cx
    left_w = (door_cx - DOOR_W * 0.5) - x_min
    right_w = x_max - (door_cx + DOOR_W * 0.5)
    lintel_h = h - DOOR_H
    wall_y = y_min - t * 0.5
    boxes_r, boxes_c = [], []
    if left_w > 0.01:
        b = ((x_min + left_w * 0.5, wall_y, h * 0.5), (left_w, t, h))
        boxes_r.append(b); boxes_c.append(b)
    if right_w > 0.01:
        b = ((x_max - right_w * 0.5, wall_y, h * 0.5), (right_w, t, h))
        boxes_r.append(b); boxes_c.append(b)
    if lintel_h > 0.01:
        b = ((door_cx, wall_y, DOOR_H + lintel_h * 0.5), (DOOR_W, t, lintel_h))
        boxes_r.append(b); boxes_c.append(b)
    if boxes_r:
        create_mesh_obj("R_wall_yneg", boxes_r, render_coll)
        create_mesh_obj("C_wall_yneg", boxes_c, collision_coll)
    return door_cx


def build_door(door_cx, y_min, render_coll, collision_coll):
    """
    v11: 单门板（关严），1 个把手，无中央接缝
    """
    t = WALL_T
    wall_y = y_min - t * 0.5
    panel_full_w = DOOR_W - 0.01   # 跟门洞边只留 0.5cm 缝
    panel_h_eff = DOOR_H - 0.01

    # 单门板（关严）
    create_mesh_obj("R_door_panel",
        [((door_cx, wall_y, DOOR_H * 0.5),
          (panel_full_w, DOOR_PANEL_T, panel_h_eff))],
        render_coll)
    create_mesh_obj("C_door_panel",
        [((door_cx, wall_y, DOOR_H * 0.5),
          (panel_full_w, DOOR_PANEL_T, panel_h_eff))],
        collision_coll)

    # 把手：门右侧（玩家从外面看是右），内外各一
    handle_w = 0.18
    handle_th = 0.035
    handle_t = 0.04
    handle_z = 1.05
    handle_x = door_cx + DOOR_W * 0.5 - handle_w * 0.5 - 0.10  # 距右边缘 10cm
    inner_y = y_min + handle_t * 0.5 + 0.005
    outer_y = y_min - t - handle_t * 0.5 - 0.005
    handle_boxes = [
        ((handle_x, inner_y, handle_z), (handle_w, handle_t, handle_th)),
        ((handle_x, outer_y, handle_z), (handle_w, handle_t, handle_th)),
    ]
    create_mesh_obj("R_door_handle", handle_boxes, render_coll)

    # 门顶控制面板（小绿色发光盒，暗示"已锁"）— 挂在 -Y 墙外侧
    cp_w, cp_h, cp_d = 0.32, 0.10, 0.04
    cp_z = DOOR_H + 0.18
    cp_y = y_min - t - cp_d * 0.5 - 0.01
    create_mesh_obj("R_door_panel_ctrl",
        [((door_cx, cp_y, cp_z), (cp_w, cp_d, cp_h))],
        render_coll)

    # 4 边门框（合并为单 mesh）
    fy = y_min - t - FRAME_DEPTH * 0.5
    f = FRAME_T
    frame_boxes = [
        ((door_cx - DOOR_W * 0.5 - f * 0.5, fy, (DOOR_H + 2 * f) * 0.5),
         (f, FRAME_DEPTH, DOOR_H + 2 * f)),
        ((door_cx + DOOR_W * 0.5 + f * 0.5, fy, (DOOR_H + 2 * f) * 0.5),
         (f, FRAME_DEPTH, DOOR_H + 2 * f)),
        ((door_cx, fy, DOOR_H + f * 0.5),
         (DOOR_W + 2 * f, FRAME_DEPTH, f)),
        ((door_cx, fy, f * 0.5),
         (DOOR_W + 2 * f, FRAME_DEPTH, f)),
    ]
    create_mesh_obj("R_door_frame", frame_boxes, render_coll)


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
    n = 0
    for o in devices:
        if not o.name.startswith("R_ship_"):
            continue
        mn, mx = world_bbox([o])
        size = mx - mn
        if size.x < 0.05 or size.y < 0.05 or size.z < 0.05:
            continue
        if size.x > 6.0 and size.y > 6.0 and size.z < 0.2:
            continue
        center = (mn + mx) * 0.5
        clean = o.name.replace("R_ship_", "")
        create_mesh_obj(f"C_ship_{clean}",
            [((center.x, center.y, center.z), (size.x, size.y, size.z))],
            collision_coll)
        n += 1
    return n


def hide_collision_viewport(collision_coll):
    for o in collision_coll.objects:
        try:
            o.hide_set(True)
        except RuntimeError:
            o.hide_viewport = True


def find_goggles_center():
    gg = [o for o in bpy.data.objects
          if o.type == "MESH" and is_under(o, GOGGLES_ROOT)]
    if not gg:
        return None
    mn, mx = world_bbox(gg)
    return (mn + mx) * 0.5


def main():
    print("=" * 64)
    print(f"[finalize v2] start  tag={SCRIPT_TAG}")

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

    n_col = build_device_collision(devices, collision_coll)
    print(f"[finalize] generated {n_col} C_ship_* proxies")

    # 墙：4 面独立材质，按距屏幕/朝向区分亮暗
    # 屏幕装置朝 -Y 辐射柠檬土黄光：
    #   -Y 墙（门，正对屏幕辐射方向）→ 最亮、大块高光
    #   +Y 墙（屏幕背后）→ 几乎全暗
    #   ±X 墙（侧向掠射）→ 中等
    # ramp_lo/hi 控制亮斑占比（lo 越大暗区越多；hi 越大亮区越窄）
    # v9: rust 提饱和（高光更鲜艳柠檬土黄），让方向性差异更突出
    # ±Y 墙：均匀方向性（仍用 rusty_iron）
    # v14: 4 面墙统一深橄榄屎色（放弃方向性区分——PA 要的是统一阴影感）
    # 色相严格保留橄榄绿调（G > R > B），亮度极低，4 面共用同一 spec
    wall_spec = dict(
        dark=(0.006, 0.008, 0.002, 1.0),    # 几乎纯黑橄榄
        rust=(0.038, 0.046, 0.012, 1.0),    # 深橄榄屎（G略>R，绿调）
        scale=3.5, ramp_lo=0.60, ramp_hi=0.90,
        roughness=0.95, metallic=0.08, distortion=1.8)
    for name in ("R_wall_xpos", "R_wall_xneg",
                 "R_wall_ypos", "R_wall_yneg"):
        if (o := bpy.data.objects.get(name)):
            assign_rusty_iron(o, "ship_wall_unified_olive", **wall_spec)
    print(f"[finalize] walls: unified deep-olive (4 sides same spec)")

    # 其余构件用简单 BSDF（v11: door 改单板，去除 left/right）
    mat_assignments = [
        ("R_ceiling", "ceiling"),
        ("R_baseboard", "baseboard"),
        ("R_crown", "crown"),
        ("R_door_panel", "door"),
        ("R_door_handle", "handle"),
        ("R_door_panel_ctrl", "panel"),
        ("R_door_frame", "door_frame"),
    ]
    n_mat = 0
    for obj_name, mat_key in mat_assignments:
        obj = bpy.data.objects.get(obj_name)
        if obj:
            assign_material(obj, mat_key)
            n_mat += 1
    print(f"[finalize] assigned PBR materials to {n_mat} render objects")

    # goggles v12: 显式名字映射（GOGGLES_PART_MAP）+ shell fallback
    # 首次跑时 map 为空 → 全部 shell；同时打印诊断让 PA 填 map
    gg = [o for o in bpy.data.objects
          if o.type == "MESH" and o.name.startswith("R_goggles")]
    print("[finalize] --- goggle parts diagnostic (粘给我决定分区) ---")
    for o in gg:
        mn, mx = world_bbox([o])
        sz = mx - mn
        ct = (mn + mx) * 0.5
        key = GOGGLES_PART_MAP.get(o.name, "goggles_shell")
        assign_material(o, key)
        print(f"[finalize]   {o.name}")
        print(f"[finalize]     verts={len(o.data.vertices)}  "
              f"size=({sz.x:.3f},{sz.y:.3f},{sz.z:.3f})  "
              f"center=({ct.x:+.3f},{ct.y:+.3f},{ct.z:+.3f})  "
              f"-> {key}")
    print(f"[finalize] goggles: {len(gg)} parts, "
          f"map has {len(GOGGLES_PART_MAP)} explicit entries "
          f"(rest fallback to goggles_shell)")

    # spawn：门内侧 0.8m
    spawn = (cx, y_min + 0.8, 0.0)
    add_empty("M_spawn_main", spawn, markers_coll, "ARROWS", 0.4)
    print(f"[finalize] M_spawn_main at ({spawn[0]:+.2f},{spawn[1]:+.2f},{spawn[2]:+.2f})")

    g = find_goggles_center()
    if g is None:
        print("[finalize] WARN: 找不到 goggles")
    else:
        add_empty("M_interact_vr_headset",
                  (g.x, g.y, g.z), markers_coll, "SPHERE", 0.2)
        print(f"[finalize] M_interact_vr_headset at "
              f"({g.x:+.2f},{g.y:+.2f},{g.z:+.2f})")

    hide_collision_viewport(collision_coll)
    print(f"[finalize] hidden {len(collision_coll.objects)} collision objects in viewport")

    print("[finalize] DONE.")
    print("[finalize] 导出前：选所有 R_/C_ → Ctrl+A → All Transforms")
    print("[finalize] 导出 glTF 2.0 时 Include → Limit to 全部不勾")
    print("=" * 64)


if __name__ == "__main__":
    main()
