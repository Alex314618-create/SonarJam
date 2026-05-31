"""
build_phase3_tree_leak.py — 在 3.blend 里准备 Phase 3 树泄漏事件的三件套：
  1. R_leak_tree_01   — 真实树（从 mountain_mine 拔 R_trees_02 → 移到 CJK marker 位置）
  2. M_leak_tree_01   — Empty 触发点（在树位置，引擎按半径 6m 检测）
  3. H_cover_tree_01  — 覆盖圆柱（默认未激活，事件触发后引擎拉入感知层）
"""
import bpy, bmesh, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC_3      = os.path.join(ROOT, "_temp_Blender", "更新与交付", "3.blend")
SRC_MINE   = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_mine.blend")
TEMP_TREE  = os.path.join(ROOT, "_temp_Blender", "_tree_clean.blend")
DST_BLEND  = SRC_3
DST_GLB    = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_loop3.glb")

# CJK 标记给出的目标位置（树脚）
TARGET_TREE_BASE = mathutils.Vector((14.29, -83.33, 1.32))

# ============ STEP A: 干净抽取 R_trees_02 ============
bpy.ops.wm.open_mainfile(filepath=SRC_MINE)
tree = bpy.data.objects.get("R_trees_02")
if not tree:
    raise SystemExit("mountain_mine 里找不到 R_trees_02")

# 烘父变换 → mesh
bpy.ops.object.select_all(action='DESELECT')
tree.select_set(True)
bpy.context.view_layer.objects.active = tree
if tree.parent is not None:
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 删其他
for o in list(bpy.data.objects):
    if o.name != "R_trees_02":
        bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=TEMP_TREE)

# 量原始 bbox（用于后续 cylinder 大小）
tree = bpy.data.objects["R_trees_02"]
pts = [tree.matrix_world @ mathutils.Vector(v) for v in tree.bound_box]
mn0 = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx0 = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
print(f"[A] 干净树 bbox: center=({(mn0.x+mx0.x)/2:.2f},{(mn0.y+mx0.y)/2:.2f},{(mn0.z+mx0.z)/2:.2f}) size=({mx0.x-mn0.x:.2f},{mx0.y-mn0.y:.2f},{mx0.z-mn0.z:.2f})")

# ============ STEP B: 打开 3.blend，append + 移位 + 重命名 ============
bpy.ops.wm.open_mainfile(filepath=SRC_3)

# 删旧的（万一）
for n in ("R_leak_tree_01", "M_leak_tree_01", "H_cover_tree_01", "R_trees_02"):
    o = bpy.data.objects.get(n)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

with bpy.data.libraries.load(TEMP_TREE, link=False) as (df, dt):
    dt.objects = list(df.objects)
appended = [o for o in dt.objects if o is not None]
for o in appended:
    bpy.context.collection.objects.link(o)

tree = bpy.data.objects.get("R_trees_02")
if not tree:
    raise SystemExit("append 后找不到 R_trees_02")

# 移到 CJK 位置：让树底 (min Z) 落到 TARGET_TREE_BASE
pts = [tree.matrix_world @ mathutils.Vector(v) for v in tree.bound_box]
cur_center_xy = mathutils.Vector((sum(p.x for p in pts)/8, sum(p.y for p in pts)/8, 0))
cur_min_z = min(p.z for p in pts)
delta = mathutils.Vector((
    TARGET_TREE_BASE.x - cur_center_xy.x,
    TARGET_TREE_BASE.y - cur_center_xy.y,
    TARGET_TREE_BASE.z - cur_min_z,
))
tree.location = (tree.location.x + delta.x, tree.location.y + delta.y, tree.location.z + delta.z)
bpy.context.view_layer.update()

# 关键：直接把 location 烘到 mesh 顶点，并把 location 归零。
# 上版本只动 object.location → 导出后 GLB node.translation 还在 mountain 原始位置，
# 引擎读到的 R_leak_tree_01 跑到 (-39, -2.5) 而不是 marker 处。
bpy.ops.object.select_all(action='DESELECT')
tree.select_set(True)
bpy.context.view_layer.objects.active = tree
if tree.parent is not None:
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.context.view_layer.update()

# 验证新位置
pts = [tree.matrix_world @ mathutils.Vector(v) for v in tree.bound_box]
mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
center = (mn + mx) / 2
size = mx - mn
print(f"\n[B] R_leak_tree_01 烘焙后 bbox: center=({center.x:.2f},{center.y:.2f},{center.z:.2f}) size=({size.x:.2f},{size.y:.2f},{size.z:.2f})")
print(f"    object.location 已归零 → {tuple(round(v,3) for v in tree.location)}")

tree.name = "R_leak_tree_01"
tree["original_name"] = "R_trees_02 from mountain_mine"

# ============ STEP C: M_leak_tree_01 Empty ============
empty = bpy.data.objects.new("M_leak_tree_01", None)
# 放在树脚位置（Z 略上来一点便于可视化）
empty.location = (TARGET_TREE_BASE.x, TARGET_TREE_BASE.y, TARGET_TREE_BASE.z + 1.0)
empty.empty_display_type = 'PLAIN_AXES'
empty.empty_display_size = 2.0
bpy.context.collection.objects.link(empty)
print(f"\n[C] M_leak_tree_01 @ ({empty.location.x:.2f}, {empty.location.y:.2f}, {empty.location.z:.2f}) (引擎按 6m 半径检测)")

# ============ STEP D: H_cover_tree_01 圆柱 ============
# 半径 = max(bbox.x, bbox.y) / 2 + 0.8m margin
# 高 = bbox.z + 1m margin
cyl_radius = max(size.x, size.y) / 2 + 0.8
cyl_depth  = size.z + 1.0
cyl_center_z = center.z + 0.5  # 底部略低于树脚，顶部略高于树顶

bpy.ops.mesh.primitive_cylinder_add(
    radius=cyl_radius,
    depth=cyl_depth,
    location=(center.x, center.y, cyl_center_z),
    vertices=16,
)
cyl = bpy.context.object
cyl.name = "H_cover_tree_01"

# 材质：水泥灰，类似其他人造结构
mat = bpy.data.materials.new(name="hcover_grey")
mat.use_nodes = True
bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.42, 0.42, 0.43, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    bsdf.inputs['Metallic'].default_value = 0.0
cyl.data.materials.append(mat)

print(f"\n[D] H_cover_tree_01 圆柱: 半径={cyl_radius:.2f}m, 高={cyl_depth:.2f}m, center=({center.x:.2f},{center.y:.2f},{cyl_center_z:.2f})")
print(f"   多边形数={len(cyl.data.polygons)}（16 vertices × 1 cylinder = 16-sided）")

# 清 TEMP
try:
    os.remove(TEMP_TREE)
    bk = TEMP_TREE + "1"
    if os.path.exists(bk): os.remove(bk)
except: pass

# ============ STEP E: 保存 + 导出 ============
bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB,
    export_format='GLB',
    export_materials='EXPORT',
    export_image_format='AUTO',
    export_apply=True,
    export_lights=False,
    export_yup=True,
    export_extras=True,
    use_visible=False,
    use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"\n[SAVED .blend] {DST_BLEND}")
print(f"[SAVED .glb]   {DST_GLB}  ({sz/1024/1024:.2f} MB)")

# 最终验证
print(f"\n[VERIFY] Phase 3 树泄漏三件套:")
for n in ("R_leak_tree_01", "M_leak_tree_01", "H_cover_tree_01"):
    o = bpy.data.objects.get(n)
    if o:
        loc = tuple(round(v,2) for v in o.matrix_world.translation)
        print(f"  ✓ {n} (type={o.type})  loc={loc}")
    else:
        print(f"  ✗ {n} 不存在")
