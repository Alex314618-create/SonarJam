"""
replace_each_card.py — 每张 card 替换成真树（共享 mesh data → glTF instancing）

Phase 1: 打开 mountain_mine, 对 R_trees_01 / R_trees_02 separate by loose
         → 每个 component = 一张 card 实例 → 收集 (cx, cy, base_z, height)
Phase 2: 打开 12345, 删现 R_trees_*, import tree.glb 作为 master mesh template
         → 对每个 card 位置创建 linked duplicate（共享 mesh data）
         → 缩放到 card 高度 × ~3（让真树比 card 稍大一点表现"真"感）
"""
import bpy, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC_12345 = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_12345.blend")
SRC_MINE  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_mine.blend")
TREE_GLB  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "C_s", "tree.glb")
DST_BLEND = SRC_12345
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_12345.glb")

TREE_OBJECTS_TO_PROCESS = ["R_trees_01", "R_trees_02"]


def get_card_positions(src_name):
    """对 src_name 做 separate by loose，返回每个 component 的 (cx, cy, base_z, height)"""
    obj = bpy.data.objects.get(src_name)
    if not obj:
        return []

    # 解父 + 烘 transform
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if obj.parent is not None:
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # separate by loose
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')

    parts = [o for o in bpy.data.objects
             if (o.name == src_name or o.name.startswith(src_name + "."))
             and o.type == 'MESH']

    positions = []
    for p in parts:
        pts = [p.matrix_world @ mathutils.Vector(v) for v in p.bound_box]
        mn = mathutils.Vector((min(pt.x for pt in pts), min(pt.y for pt in pts), min(pt.z for pt in pts)))
        mx = mathutils.Vector((max(pt.x for pt in pts), max(pt.y for pt in pts), max(pt.z for pt in pts)))
        cx = (mn.x + mx.x) / 2
        cy = (mn.y + mx.y) / 2
        base_z = mn.z
        height = mx.z - mn.z
        # 过滤明显异常（极小/极大）
        if 0.1 < height < 100:
            positions.append((cx, cy, base_z, height))
    return positions


# ========= PHASE 1: 从 mountain_mine 抽 card 位置 =========
print(f"\n=== PHASE 1: 抽 card 位置 from mountain_mine ===")
bpy.ops.wm.open_mainfile(filepath=SRC_MINE)

all_positions = {}  # src_name → list of positions
for src in TREE_OBJECTS_TO_PROCESS:
    positions = get_card_positions(src)
    all_positions[src] = positions
    heights = [p[3] for p in positions]
    if heights:
        h_avg = sum(heights) / len(heights)
        h_min = min(heights); h_max = max(heights)
        print(f"  {src}: {len(positions)} cards, height avg={h_avg:.2f}m min={h_min:.2f} max={h_max:.2f}")
    else:
        print(f"  {src}: 0 cards")

# ========= PHASE 2: 在 12345 实例化真树 =========
print(f"\n=== PHASE 2: 在 mountain_12345 实例化 tree.glb ===")
bpy.ops.wm.open_mainfile(filepath=SRC_12345)

# 删现有 R_trees_*（我上版本错放的单树）
removed = []
for o in list(bpy.data.objects):
    if o.name.startswith("R_trees_") and o.type == 'MESH':
        removed.append(o.name)
        bpy.data.objects.remove(o, do_unlink=True)
print(f"  删 {len(removed)} 个旧 R_trees_*")

# Import tree.glb 作 master
before_set = set(o.name for o in bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=TREE_GLB)
after_set = set(o.name for o in bpy.data.objects)
new_names = after_set - before_set
new_objs = [bpy.data.objects[n] for n in new_names]
imported_meshes = [o for o in new_objs if o.type == 'MESH']

# 烘父变换
for m in list(imported_meshes):
    bpy.ops.object.select_all(action='DESELECT')
    m.select_set(True)
    bpy.context.view_layer.objects.active = m
    if m.parent is not None:
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 删 import 的非 mesh 父
for o in list(new_objs):
    if o.type != 'MESH' and o.name in bpy.data.objects:
        bpy.data.objects.remove(o, do_unlink=True)

# join 两个 mesh
bpy.ops.object.select_all(action='DESELECT')
for m in imported_meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = imported_meshes[0]
bpy.ops.object.join()
master = bpy.context.active_object

# 把 master 移到原点 (XY=0, base Z=0)
pts = [master.matrix_world @ mathutils.Vector(v) for v in master.bound_box]
mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
master_height = mx.z - mn.z
master.location = (master.location.x - (mn.x + mx.x)/2,
                   master.location.y - (mn.y + mx.y)/2,
                   master.location.z - mn.z)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 关键：decimate 到 ~50 polys，否则 6000×32000=192M 多边形卡死
TARGET_POLYS = 50
cur_polys = len(master.data.polygons)
if cur_polys > TARGET_POLYS:
    bpy.context.view_layer.objects.active = master
    mod = master.modifiers.new(name='dec', type='DECIMATE')
    mod.ratio = max(0.001, TARGET_POLYS / cur_polys)
    mod.decimate_type = 'COLLAPSE'
    mod.use_collapse_triangulate = True
    try:
        bpy.ops.object.modifier_apply(modifier='dec')
    except Exception as e:
        print(f"  [WARN] decimate failed: {e}")
print(f"  master tree: 原点对齐, 高 {master_height:.2f}m, polys={len(master.data.polygons)} (decimated from {cur_polys})")
master.hide_render = True   # 模板不渲染
master.hide_set(True)
master.name = "__tree_master_template"

# 给每个 card 位置生成 linked duplicate（共享 master.data）
total_count = 0
for src_name, positions in all_positions.items():
    if not positions:
        continue
    # 用平均 card 高度算缩放
    h_avg = sum(p[3] for p in positions) / len(positions)
    # 真树缩到 card 高度 × 1.0（保持原 card 高度尺度）
    scale = h_avg / master_height
    print(f"  {src_name}: {len(positions)} 棵, 缩放={scale:.3f} (avg card height {h_avg:.2f}m / master {master_height:.2f}m)")

    for i, (cx, cy, bz, height) in enumerate(positions, 1):
        dup = master.copy()
        # 不 copy data → 共享 mesh
        bpy.context.collection.objects.link(dup)
        dup.location = (cx, cy, bz)
        dup.scale = (scale, scale, scale)
        dup.hide_render = False
        dup.hide_set(False)
        dup.name = f"{src_name}_inst_{i:04d}"
        total_count += 1

print(f"\n  共生成 {total_count} 棵真树实例（linked, 共享同一份 mesh）")

# 把所有实例 join 成单 mesh 减少 draw call
print(f"\n  join 全部实例 → 单 mesh ...")
inst_objs = [o for o in bpy.data.objects
             if o.type == 'MESH'
             and any(o.name.startswith(s + "_inst_") for s in TREE_OBJECTS_TO_PROCESS)]
if inst_objs:
    bpy.ops.object.select_all(action='DESELECT')
    for o in inst_objs:
        o.hide_set(False)  # join 必须可见
        o.select_set(True)
    bpy.context.view_layer.objects.active = inst_objs[0]
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = "R_trees_01"   # 用回原名作为单 mesh
    joined["original_name"] = f"REPLACED_FROM_tree.glb x {total_count} cards"
    print(f"  join 后: {joined.name}, polys={len(joined.data.polygons)}")

# 删 master 模板
m = bpy.data.objects.get("__tree_master_template")
if m: bpy.data.objects.remove(m, do_unlink=True)

# 保存 + 导出
bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB,
    export_format='GLB', export_materials='EXPORT',
    export_image_format='AUTO', export_apply=True,
    export_lights=False,
    export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"\n[SAVED .blend] {DST_BLEND}")
print(f"[SAVED .glb]   {DST_GLB}  ({sz/1024/1024:.2f} MB)")
