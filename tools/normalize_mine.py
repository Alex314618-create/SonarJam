"""
normalize_mine.py — 把 mountain_mine.blend 规范化为 SonarJam R_/C_/M_ 约定

输入  : _temp_Blender/我的工作区/mountain_mine.blend  (用户手工搭好的地图，不动)
输出  :
  - _temp_Blender/我的工作区/mountain_normalized.blend  (最终干净 .blend)
  - _temp_Blender/我的工作区/NORMALIZE_REPORT.md         (人类可读改名/优化报告)

三个阶段：
  1) RENAME : 按 (对象名 + 首材质名 + 位置) 把 117 个杂名物件分到 8 个 R_<category>
              CJK 命名的标记物 → M_leak_* / M_poi_*
              保留 obj["original_name"] = "..." 作 traceability
  2) C_ COLLIDERS : 围绕每个 R_ 簇生成 AABB 简化盒（架构师说 C_ 必须是简化代理，
                    宽度 ≥0.8m；我们这里只做"够用"的盒子，作者还能在 Blender 里再调整）
  3) DECIMATE : 针对 Building 内壳 / Building 外壳冗余分片 / TV antenna 的密集小件
                做定向稀疏化。ratio 保守在 0.2~0.5 之间，配合
                use_collapse_triangulate=True，避免把模型撕散。
                不动 R_terrain/R_rocks/R_trees/R_grass/R_snow（那些已经在 prep
                里处理过，且任何动作都会影响湖光山色的可识别轮廓）。

运行：
  blender -b mountain_mine.blend --python tools/normalize_mine.py
（无需 GUI；脚本读 mountain_mine.blend，写 mountain_normalized.blend）
"""

import bpy, os, math, mathutils, re
from collections import defaultdict, OrderedDict

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC_BLEND = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_mine.blend")
DST_BLEND = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_normalized.blend")
REPORT_MD = os.path.join(ROOT, "_temp_Blender", "我的工作区", "NORMALIZE_REPORT.md")

# ---------------------------------------------------------------------------
# 1) RENAME 规则（顺序匹配，先匹中先生效）
#
# 每条 rule = (matcher_func, category_string)
# matcher_func(name_lower, mat_lower, loc_xyz) → bool
# ---------------------------------------------------------------------------

def build_rename_rules():
    R = []  # rules
    add = lambda fn, cat: R.append((fn, cat))

    # 已有的 R_/C_/P_/M_ 前缀 → 跳过（保留用户/前序脚本的命名）
    add(lambda n,m,p: n.startswith("r_") or n.startswith("c_") or n.startswith("p_") or n.startswith("m_"), None)

    # === 叙事标记（CJK 长名）→ M_ ============================================
    # 这些是用户手工创建的 6-poly cube，明显是 leak/POI 触发点
    add(lambda n,m,p: "诡异的人形" in n or "诡异的" in n,        "M_leak_phantom")
    add(lambda n,m,p: "兴趣点" in n or "途径点" in n or "导航" in n, "M_poi_waypoint")

    # === Buildings ==========================================================
    add(lambda n,m,p: "building #1" in n,                       "R_building_alpha")
    add(lambda n,m,p: "building #6" in n,                       "R_building_beta")

    # === Old truck + rocket（cluster at (-45, -60, 12)） =====================
    # rocket / thruster 材质 + Cube.00X 命名
    add(lambda n,m,p: "rocket" in m or "thruster" in m,          "R_truck_rocket")
    # Object001_Material #66/76/77 也是 truck 散件（cluster at (-44, -85, 2)）
    add(lambda n,m,p: "material_66" in m or "material_76" in m or "material_77" in m, "R_truck_debris")

    # === Wagon（在 (14, -83, 5) 附近） =======================================
    add(lambda n,m,p: "ascht" in m or "material.002" in m,       "R_wagon")

    # === Bones（cluster at (50~70, -82~-86)） =================================
    add(lambda n,m,p: "bone2" in m or "skull" in n or "sacrum" in n, "R_bones_skeleton")

    # === Space shuttle（Object_NN, 法语材质，cluster at (75, -73, 7)） ========
    # 用位置判断更稳：x > 60 且 y in [-80,-65]
    add(lambda n,m,p: re.match(r"^object_\d+$", n) and 60 < p[0] < 90 and -85 < p[1] < -65, "R_shuttle")

    # === TV antenna（cluster at (-43, -76, 5)，所有金属密集小件） ============
    # 用材质捕获 + 位置兜底
    add(lambda n,m,p: ("metalwhite" in m or "metalred" in m or "metalgrey" in m or
                       "redlight" in m or "concrete" in m or
                       m == "black" or m == "grey" or "cube.025__0" in m),
        "R_antenna")
    # Plane.008_Material.002 是 wagon 已捕获；其它 Plane.008_ascht 在 wagon
    # 位置兜底：未分类对象若靠近 antenna 中心也归 antenna
    add(lambda n,m,p: abs(p[0]-(-43)) < 4 and abs(p[1]-(-76)) < 6 and p[2] < 10,
        "R_antenna")

    # === 最后兜底：未归类但有名字的，扔进 R_misc =============================
    add(lambda n,m,p: True, "R_misc")
    return R


def classify_object(obj, rules):
    name = obj.name.lower()
    first_mat = ""
    if obj.type == 'MESH' and obj.material_slots and obj.material_slots[0].material:
        first_mat = obj.material_slots[0].material.name.lower()
    # 世界空间中心
    bb = [obj.matrix_world @ mathutils.Vector(v) for v in obj.bound_box]
    cx = sum(p.x for p in bb) / 8
    cy = sum(p.y for p in bb) / 8
    cz = sum(p.z for p in bb) / 8
    for fn, cat in rules:
        if fn(name, first_mat, (cx, cy, cz)):
            return cat
    return None  # 不该到这里


# ---------------------------------------------------------------------------
# 2) C_ COLLIDER 生成：按簇生成 AABB 简化盒
# ---------------------------------------------------------------------------

# 每个 R_cluster → 一个或多个 C_collider 的策略
COLLIDER_PLAN = OrderedDict([
    # cluster name           : (collider_name_template, strategy)
    # strategy = "bbox": 单个 AABB 包络整簇
    #           "per_object_cylinder": 每个对象一个直立胶囊（适合石头/树）
    #           "per_object_bbox": 每对象一个 AABB（适合分散物件）
    #           "floor_plane": 大薄板做地面
    ("R_terrain",         ("C_floor_terrain",       "floor_plane")),
    ("R_building_alpha",  ("C_building_alpha_block","bbox")),
    ("R_building_beta",   ("C_building_beta_block", "bbox")),
    ("R_antenna",         ("C_antenna_pole",        "bbox")),
    ("R_truck_rocket",    ("C_truck_block",         "bbox")),
    ("R_truck_debris",    ("C_truck_debris_block",  "bbox")),
    ("R_wagon",           ("C_wagon_block",         "bbox")),
    ("R_shuttle",         ("C_shuttle_block",       "bbox")),
    ("R_rocks",           ("C_rocks_block",         "per_object_bbox")),
    ("R_trees",           ("C_trees_pole",          "per_object_cylinder")),
    ("R_bones_skeleton",  ("C_bones_block",         "per_object_bbox")),
    # R_grass / R_snow / R_water / R_boat / R_ruin / R_misc 暂不生成 C_
    # 因为草雪水高度变化不影响导航，船/废墟可走可不走，留给用户后续决定
])


def aabb_of_objects(objs):
    """返回 (min_v, max_v) 世界空间 AABB"""
    mn = mathutils.Vector(( 1e9,  1e9,  1e9))
    mx = mathutils.Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for v in o.bound_box:
            wv = o.matrix_world @ mathutils.Vector(v)
            for i in range(3):
                if wv[i] < mn[i]: mn[i] = wv[i]
                if wv[i] > mx[i]: mx[i] = wv[i]
    return mn, mx


def make_collider_bbox(name, mn, mx):
    cx = (mn.x + mx.x) / 2; cy = (mn.y + mx.y) / 2; cz = (mn.z + mx.z) / 2
    sx = max((mx.x - mn.x) / 2, 0.4)  # 半径 ≥0.4 → 直径 ≥0.8m（架构师宽度下限）
    sy = max((mx.y - mn.y) / 2, 0.4)
    sz = max((mx.z - mn.z) / 2, 0.4)
    bpy.ops.mesh.primitive_cube_add(size=2, location=(cx, cy, cz))
    obj = bpy.context.object
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.name = name
    # 标记为"系统所见"——可走可挡声呐，运行时识别 C_ 前缀
    obj["sonarjam_kind"] = "collider"
    obj["sonarjam_visual"] = False  # 渲染时不画
    obj.hide_render = True
    obj.display_type = 'BOUNDS'  # 在 Blender 里也以 wireframe 显示
    return obj


def make_collider_floor(name, mn, mx, thickness=0.5):
    cx = (mn.x + mx.x) / 2; cy = (mn.y + mx.y) / 2
    sx = max((mx.x - mn.x) / 2, 0.5)
    sy = max((mx.y - mn.y) / 2, 0.5)
    bpy.ops.mesh.primitive_cube_add(size=2, location=(cx, cy, mn.z + thickness/2))
    obj = bpy.context.object
    obj.scale = (sx, sy, thickness/2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.name = name
    obj["sonarjam_kind"] = "collider_floor"
    obj["sonarjam_visual"] = False
    obj.hide_render = True
    obj.display_type = 'BOUNDS'
    return obj


def make_collider_cylinder(name, mn, mx):
    """直立胶囊：用于树（树干主轴垂直 Z）"""
    cx = (mn.x + mx.x) / 2; cy = (mn.y + mx.y) / 2
    # 半径取 XY bbox 较小边的 ~30%，避免把树叶都圈进碰撞
    r = max(min((mx.x - mn.x), (mx.y - mn.y)) * 0.30, 0.4)
    h = max(mx.z - mn.z, 1.0)
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=(cx, cy, (mn.z + mx.z)/2), vertices=8)
    obj = bpy.context.object
    obj.name = name
    obj["sonarjam_kind"] = "collider_cylinder"
    obj["sonarjam_visual"] = False
    obj.hide_render = True
    obj.display_type = 'BOUNDS'
    return obj


# ---------------------------------------------------------------------------
# 3) DECIMATE 策略
#   挑选规则：
#     a) 名字含 "inner" 的 building 内壳   → ratio 0.2（玩家几乎看不到）
#     b) building outer 的同位置冗余分片  → ratio 0.5
#     c) TV antenna 主体 Cube.025__0 (85k) → ratio 0.3
#     d) antenna 细密小件 (density > 1000 且 poly > 5000) → ratio 0.3
#   非目标：地形/石头/树/草/船——保持原状（之前 prep 已处理过 / 视觉关键）
# ---------------------------------------------------------------------------

def decimate_targets():
    """返回 [(对象原名 substring, ratio, 说明)]"""
    return [
        ("inner_Metal inner",        0.20, "建筑内壳金属（被外壳遮蔽）"),
        ("concrete inner",           0.30, "建筑内壳混凝土"),
        ("Building #6 outer_Metal",  0.50, "Building#6 外壳金属（多片冗余）"),
        ("Building #6 outer_paint",  0.50, "Building#6 外壳油漆"),
        ("Building #6 outer_Glass",  0.50, "Building#6 玻璃窗（保留少量保 alpha 边）"),
        ("Building #1 outer_Metal",  0.50, "Building#1 外壳金属"),
        ("Building #1 outer_paint",  0.50, "Building#1 外壳油漆"),
        ("Building #1 outer_Glass",  0.50, "Building#1 玻璃窗"),
        ("Cube.025__0",              0.30, "TV antenna 主体（85k → 25k）"),
        ("Scale.001",                0.20, "antenna scale 部件（密度奇高）"),
        ("Scale__0",                 0.20, "antenna scale 部件"),
        ("PlateWithScrew",           0.30, "antenna 螺栓板"),
        ("Plane.008_Material.002",   0.20, "wagon 高密度小件"),
    ]


def apply_decimate_to(obj, ratio, reason, report):
    before = len(obj.data.polygons)
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new(name='auto_dec', type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    try:
        bpy.ops.object.modifier_apply(modifier='auto_dec')
    except Exception as e:
        obj.modifiers.remove(mod)
        report.append((obj.name, before, before, ratio, f"FAILED: {e}"))
        return 0
    after = len(obj.data.polygons)
    report.append((obj.name, before, after, ratio, reason))
    return before - after


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

# 因为我们用 blender -b src.blend --python script.py 启动，
# Blender 启动时已经加载了 src 文件。这里不需要 bpy.ops.wm.open_mainfile。
# 但为了脚本健壮，主动确认：
if not bpy.data.is_saved or not os.path.samefile(bpy.data.filepath, SRC_BLEND) if bpy.data.filepath else True:
    bpy.ops.wm.open_mainfile(filepath=SRC_BLEND)

print("=" * 90)
print("SonarJam · mountain_mine.blend 规范化")
print("=" * 90)

# ========== PHASE 1: RENAME ==========
rules = build_rename_rules()
plan = []        # (obj, new_category_string)
skip_count = 0
for obj in list(bpy.data.objects):
    if obj.type != 'MESH': continue
    cat = classify_object(obj, rules)
    if cat is None:
        skip_count += 1
        continue
    plan.append((obj, cat))

# 按 category 计数生成 NN 编号
counters = defaultdict(int)
rename_log = []  # (old, new, cat)

# *** 关键：先把真实原名抓到 custom prop，再做 tmp 改名，避免丢失 ***
for obj, cat in plan:
    if "original_name" not in obj:
        obj["original_name"] = obj.name

# 两遍法避命名冲突
for i, (obj, cat) in enumerate(plan):
    obj.name = f"__tmp_norm_{i:04d}"
for obj, cat in plan:
    counters[cat] += 1
    new_name = f"{cat}_{counters[cat]:02d}"
    rename_log.append((obj["original_name"], new_name, cat))
    obj.name = new_name

# CJK 标记物：附加原标签 + 设为不渲染
for old, new, cat in rename_log:
    if cat.startswith("M_"):
        obj = bpy.data.objects.get(new)
        if obj:
            # 找回 original_name 已被前面写入 custom prop
            obj.hide_render = True
            obj["sonarjam_kind"] = "marker"

print(f"\n[RENAME] {len(plan)} objects renamed, {skip_count} skipped (already R_/C_/P_/M_)")
for cat, n in sorted(counters.items()):
    print(f"  {cat:<26s} × {n}")

# ========== PHASE 2: C_ COLLIDERS ==========
print("\n[COLLIDERS] 生成 AABB 碰撞代理盒")
collider_log = []  # (collider_name, source_cluster, strategy, n_sources)
for cluster_prefix, (collider_template, strategy) in COLLIDER_PLAN.items():
    sources = [o for o in bpy.data.objects if o.name.startswith(cluster_prefix + "_") and o.type == 'MESH']
    if not sources:
        continue

    if strategy == "bbox":
        mn, mx = aabb_of_objects(sources)
        c = make_collider_bbox(collider_template + "_01", mn, mx)
        collider_log.append((c.name, cluster_prefix, "bbox", len(sources)))
    elif strategy == "floor_plane":
        mn, mx = aabb_of_objects(sources)
        c = make_collider_floor(collider_template + "_01", mn, mx)
        collider_log.append((c.name, cluster_prefix, "floor_plane", len(sources)))
    elif strategy == "per_object_bbox":
        for i, src in enumerate(sources, 1):
            bb = [src.matrix_world @ mathutils.Vector(v) for v in src.bound_box]
            mn = mathutils.Vector((min(p.x for p in bb), min(p.y for p in bb), min(p.z for p in bb)))
            mx = mathutils.Vector((max(p.x for p in bb), max(p.y for p in bb), max(p.z for p in bb)))
            c = make_collider_bbox(f"{collider_template}_{i:02d}", mn, mx)
            collider_log.append((c.name, src.name, "per_object_bbox", 1))
    elif strategy == "per_object_cylinder":
        for i, src in enumerate(sources, 1):
            bb = [src.matrix_world @ mathutils.Vector(v) for v in src.bound_box]
            mn = mathutils.Vector((min(p.x for p in bb), min(p.y for p in bb), min(p.z for p in bb)))
            mx = mathutils.Vector((max(p.x for p in bb), max(p.y for p in bb), max(p.z for p in bb)))
            c = make_collider_cylinder(f"{collider_template}_{i:02d}", mn, mx)
            collider_log.append((c.name, src.name, "cylinder", 1))

print(f"  生成 {len(collider_log)} 个 C_ collider")

# ========== PHASE 3: DECIMATE ==========
print("\n[DECIMATE] 定向稀疏化（保守 ratio，use_collapse_triangulate=True）")
dec_report = []
saved_total = 0
targets = decimate_targets()
# 我们要按 "对象 original_name 是否含 substring" 来定位
for obj in list(bpy.data.objects):
    if obj.type != 'MESH': continue
    orig = obj.get("original_name", obj.name)
    for substr, ratio, reason in targets:
        if substr in orig:
            saved_total += apply_decimate_to(obj, ratio, reason, dec_report)
            break

print(f"  减面合计: {saved_total} polys")

# ========== SAVE ==========
bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
print(f"\n[SAVED] {DST_BLEND}")

# ========== REPORT ==========
total_polys = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
r_count = sum(1 for o in bpy.data.objects if o.name.startswith("R_"))
c_count = sum(1 for o in bpy.data.objects if o.name.startswith("C_"))
m_count = sum(1 for o in bpy.data.objects if o.name.startswith("M_"))
print(f"\n[FINAL] R_={r_count}  C_={c_count}  M_={m_count}  total polys={total_polys}")

# ----- 写 markdown 报告 -----
lines = []
lines.append("# 山地地图规范化报告")
lines.append("")
lines.append(f"- **源**：`{os.path.basename(SRC_BLEND)}`")
lines.append(f"- **输出**：`{os.path.basename(DST_BLEND)}`")
lines.append(f"- **生成于**：脚本 `tools/normalize_mine.py`")
lines.append("")
lines.append("## 总览")
lines.append("")
lines.append(f"| 指标 | 数值 |")
lines.append(f"|---|---|")
lines.append(f"| 重命名对象数 | {len(plan)} |")
lines.append(f"| 新建 C_ collider 数 | {len(collider_log)} |")
lines.append(f"| Decimate 减面合计 | {saved_total} polys |")
lines.append(f"| 最终 R_ 数 | {r_count} |")
lines.append(f"| 最终 C_ 数 | {c_count} |")
lines.append(f"| 最终 M_ 数 | {m_count} |")
lines.append(f"| 最终总多边形数 | {total_polys} |")
lines.append("")
lines.append("## 1. RENAME 分类统计")
lines.append("")
lines.append("| 类别 | 数量 |")
lines.append("|---|---|")
for cat, n in sorted(counters.items()):
    lines.append(f"| `{cat}` | {n} |")
lines.append("")
lines.append("> 每个对象都保留了 `original_name` 自定义属性指向旧名（在 Blender 的 Object Properties → Custom Properties 可见，方便溯源）。")
lines.append("")
lines.append("## 2. RENAME 详表")
lines.append("")
lines.append("| 旧名 | 新名 | 类别 |")
lines.append("|---|---|---|")
for old, new, cat in rename_log:
    lines.append(f"| `{old}` | `{new}` | {cat} |")
lines.append("")
lines.append("## 3. C_ COLLIDER 生成详表")
lines.append("")
lines.append("**说明**：C_ 是「系统所见」几何，运行时同时是碰撞体 + 声呐 raycast 源。架构师约定走道净宽 ≥0.8m，所有 collider 半径下限 0.4m。这里只是「够用」的 AABB 起点，**你可以在 Blender 里继续微调，定义「工具撒谎」的几何**——例如：把山顶的 C_rocks 改成一堵断壁，让玩家在声呐世界里看到的轮廓和真山形状不一致。")
lines.append("")
lines.append("| Collider 新名 | 来源 R_ 簇 | 策略 | 来源对象数 |")
lines.append("|---|---|---|---|")
for cn, src, strat, ns in collider_log:
    lines.append(f"| `{cn}` | `{src}` | {strat} | {ns} |")
lines.append("")
lines.append("> 所有 C_ collider 已设 `hide_render = True` + `display_type = 'BOUNDS'`，不参与渲染但参与碰撞与声呐扫描。")
lines.append("")
lines.append("## 4. DECIMATE 减面详表")
lines.append("")
lines.append("**策略**：")
lines.append("- 只动「全渲染下完全看不见」的内壳（`*_inner_*`）和密度异常的小件")
lines.append("- 同位置冗余分片（Building 外壳 5 片重叠）适度降到 0.5")
lines.append("- 全部使用 `Decimate Collapse` + `use_collapse_triangulate=True`，最低 ratio=0.20，**不会把模型拆散**")
lines.append("- **不动** R_terrain / R_rocks / R_trees / R_grass / R_snow / R_water / R_boat / R_ruin（之前 prep 已处理过，且视觉关键）")
lines.append("")
lines.append("| 对象 | before | after | ratio | 说明 |")
lines.append("|---|---:|---:|---:|---|")
for name, before, after, ratio, reason in dec_report:
    lines.append(f"| `{name}` | {before} | {after} | {ratio:.2f} | {reason} |")
lines.append("")
lines.append("## 5. M_ 叙事标记（CJK 原名保留）")
lines.append("")
lines.append("| 新名 | 原 CJK 标签 |")
lines.append("|---|---|")
for old, new, cat in rename_log:
    if cat.startswith("M_"):
        lines.append(f"| `{new}` | {old} |")
lines.append("")
lines.append("> M_ 标记物已设 `hide_render = True`，在运行时由脚本读取位置驱动漏事件 / POI 引导，不参与渲染或碰撞。")
lines.append("")
lines.append("## 6. 下一步建议")
lines.append("")
lines.append("1. **审一遍 C_ collider**：在 Blender 里打开 mountain_normalized.blend，把 wireframe 显示的 C_ 盒子拉拽成你「想让玩家以为」的形状（叙事红利在这里）。")
lines.append("2. **导 GLB**：File → Export → glTF 2.0 → `content/levels/earth_return_01/scene.glb`")
lines.append("   - Format: glTF Binary")
lines.append("   - Materials: Export / Images: Automatic / Apply Modifiers: ✓ / Punctual Lights: ✗")
lines.append("3. **校验**：`cargo run --release --bin glb_inspect content/levels/earth_return_01/scene.glb`")
lines.append("4. **R_misc 兜底类**：报告里 `R_misc_*` 的对象是分类没匹中的，请手工挑出来归到正确的 R_ 群（或新建 R_ 群）。")
lines.append("")

with open(REPORT_MD, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"[REPORT] {REPORT_MD}")
