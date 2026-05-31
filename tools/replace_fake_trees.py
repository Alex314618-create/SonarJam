"""
replace_fake_trees.py — 12345 里 R_trees_01 / R_trees_02 的纸片假树全部替换成
C_s/tree.glb 里的真 3D 树（保持原 XY 位置，base 贴原 min Z）。
"""
import bpy, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC_12345 = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_12345.blend")
TREE_GLB  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "C_s", "tree.glb")
DST_BLEND = SRC_12345
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_12345.glb")

bpy.ops.wm.open_mainfile(filepath=SRC_12345)

# 1. 记录现有 R_trees 的位置（XY 中心 + base Z）
r_trees = [o for o in bpy.data.objects if o.name.startswith("R_trees_") and o.type == 'MESH']
records = []
for tree in r_trees:
    pts = [tree.matrix_world @ mathutils.Vector(v) for v in tree.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    cx = (mn.x + mx.x) / 2
    cy = (mn.y + mx.y) / 2
    base_z = mn.z
    records.append((tree.name, cx, cy, base_z, mx - mn))
    print(f"[OLD] {tree.name}: XY=({cx:.2f}, {cy:.2f}) base Z={base_z:.2f} size=({(mx-mn).x:.1f}x{(mx-mn).y:.1f}x{(mx-mn).z:.1f})")

# 2. 删旧
for tree in r_trees:
    bpy.data.objects.remove(tree, do_unlink=True)
print(f"\n删 {len(r_trees)} 个旧纸片树")

# 3. 对每个原位置，import tree.glb → join → move → rename
for name, target_cx, target_cy, target_base_z, orig_size in records:
    print(f"\n=== 处理 {name} → 真树 @ ({target_cx:.2f}, {target_cy:.2f}, base Z={target_base_z:.2f}) ===")

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

    # 删非 mesh 父
    for o in list(new_objs):
        if o.type != 'MESH' and o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)

    # join 两个 mesh
    bpy.ops.object.select_all(action='DESELECT')
    for m in imported_meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = imported_meshes[0]
    bpy.ops.object.join()
    tree = bpy.context.active_object

    # 量当前世界 bbox
    pts = [tree.matrix_world @ mathutils.Vector(v) for v in tree.bound_box]
    cur_mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    cur_mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    cur_cx = (cur_mn.x + cur_mx.x) / 2
    cur_cy = (cur_mn.y + cur_mx.y) / 2
    cur_base_z = cur_mn.z

    # 移到目标位置
    dx = target_cx - cur_cx
    dy = target_cy - cur_cy
    dz = target_base_z - cur_base_z
    tree.location = (tree.location.x + dx, tree.location.y + dy, tree.location.z + dz)
    bpy.context.view_layer.update()

    # 烘 location 进 mesh
    bpy.ops.object.select_all(action='DESELECT')
    tree.select_set(True)
    bpy.context.view_layer.objects.active = tree
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # 命名
    tree.name = name
    tree["original_name"] = f"REPLACED_FROM_tree.glb"

    # 验证
    pts = [tree.matrix_world @ mathutils.Vector(v) for v in tree.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    print(f"  [NEW] {tree.name}: base Z={mn.z:.2f} size=({(mx-mn).x:.2f}x{(mx-mn).y:.2f}x{(mx-mn).z:.2f}), polys={len(tree.data.polygons)}")

# 4. 保存 + 导出
bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB,
    export_format='GLB', export_materials='EXPORT',
    export_image_format='AUTO', export_apply=True, export_lights=False,
    export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"\n[SAVED .blend] {DST_BLEND}")
print(f"[SAVED .glb]   {DST_GLB}  ({sz/1024/1024:.2f} MB)")
