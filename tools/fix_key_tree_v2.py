"""
fix_key_tree_v2.py — L3-03 严格版：3.blend 重做关键树三件套

要求（L3-03 第 11 条）：
  - R_leak_tree_01 / M_leak_tree_01 / H_cover_tree_01 三者位于同一世界坐标系
  - 对象 transform 已 Apply
  - 树自 CJK marker「一棵突兀的、关键的树」(14.29, -83.33, 1.32) 旁的真树

5&4.blend 已在上一步清掉 R_wagon_01/02。3.blend 这里：
  1. 删可能残留的旧 R_leak_tree_01 / H_cover_tree_01
  2. join R_wagon_01 + R_wagon_02 → R_leak_tree_01，Apply Transform
  3. 删 C_wreck_wagon_01/02
  4. 重建 H_cover_tree_01 围 R_leak_tree_01 真 bbox，Apply Transform
  5. M_leak_tree_01 重设到 CJK marker XYZ (14.29, -83.33, 1.32 + 1.0)
"""
import bpy, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC  = os.path.join(ROOT, "_temp_Blender", "更新与交付", "3.blend")
DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_loop3.glb")

CJK_MARKER = mathutils.Vector((14.29, -83.33, 1.32))

bpy.ops.wm.open_mainfile(filepath=SRC)
print(f"\n=== 3.blend L3-03 严格版 ===")

# 1. 清理旧
for n in ("R_leak_tree_01", "H_cover_tree_01", "M_leak_tree_01"):
    o = bpy.data.objects.get(n)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)
        print(f"  删旧 {n}")
for n in ("C_wreck_wagon_01", "C_wreck_wagon_02"):
    o = bpy.data.objects.get(n)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)
        print(f"  删 {n}")

# 2. join R_wagon_01 + R_wagon_02 → R_leak_tree_01
r1 = bpy.data.objects.get("R_wagon_01")
r2 = bpy.data.objects.get("R_wagon_02")
if not r1 or not r2:
    raise SystemExit(f"3.blend 里缺 R_wagon_01/02：r1={r1}, r2={r2}")

bpy.ops.object.select_all(action='DESELECT')
r1.select_set(True)
r2.select_set(True)
bpy.context.view_layer.objects.active = r1
bpy.ops.object.join()
leak = bpy.context.active_object
leak.name = "R_leak_tree_01"
leak["original_name"] = "joined R_wagon_01 (foliage) + R_wagon_02 (trunk) = tree.glb mesh"

# Apply Transform 严格
bpy.ops.object.select_all(action='DESELECT')
leak.select_set(True)
bpy.context.view_layer.objects.active = leak
if leak.parent is not None:
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 量 bbox
pts = [leak.matrix_world @ mathutils.Vector(v) for v in leak.bound_box]
mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
tree_center = (mn+mx)/2
tree_size = mx-mn
print(f"\n[R_leak_tree_01] polys={len(leak.data.polygons)}")
print(f"  bbox center=({tree_center.x:.2f},{tree_center.y:.2f},{tree_center.z:.2f}) size=({tree_size.x:.2f},{tree_size.y:.2f},{tree_size.z:.2f})")
print(f"  object.location={tuple(round(v,3) for v in leak.location)} (应≈0)")
print(f"  CJK marker {tuple(round(v,2) for v in CJK_MARKER)} 与树脚 ({tree_center.x:.2f},{tree_center.y:.2f},{mn.z:.2f}) 距离 {(tree_center.xy.to_3d() - CJK_MARKER.xy.to_3d()).length:.2f}m")

# 3. 重建 H_cover_tree_01：cylinder 围真树 bbox
cyl_radius = max(tree_size.x, tree_size.y) / 2 + 0.4
cyl_depth = tree_size.z + 0.8
cyl_center_z = tree_center.z + 0.2  # 略上移让顶部超出树顶

bpy.ops.mesh.primitive_cylinder_add(
    radius=cyl_radius, depth=cyl_depth,
    location=(tree_center.x, tree_center.y, cyl_center_z),
    vertices=16,
)
cyl = bpy.context.object
cyl.name = "H_cover_tree_01"

# 材质：水泥灰
mat = bpy.data.materials.new(name="hcover_grey")
mat.use_nodes = True
bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.42, 0.42, 0.43, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    bsdf.inputs['Metallic'].default_value = 0.0
cyl.data.materials.append(mat)

# Apply Transform 严格
bpy.ops.object.select_all(action='DESELECT')
cyl.select_set(True)
bpy.context.view_layer.objects.active = cyl
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

print(f"\n[H_cover_tree_01] cylinder 半径={cyl_radius:.2f}m 高={cyl_depth:.2f}m polys={len(cyl.data.polygons)}")
print(f"  object.location={tuple(round(v,3) for v in cyl.location)} (应≈0)")

# 4. M_leak_tree_01 在 CJK marker 上方 1m
empty = bpy.data.objects.new("M_leak_tree_01", None)
empty.location = (CJK_MARKER.x, CJK_MARKER.y, CJK_MARKER.z + 1.0)
empty.empty_display_type = 'PLAIN_AXES'
empty.empty_display_size = 2.0
bpy.context.collection.objects.link(empty)
print(f"\n[M_leak_tree_01] Empty @ {tuple(round(v,2) for v in empty.location)}")

# 5. 保存 + 导出
bpy.ops.wm.save_as_mainfile(filepath=SRC)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB,
    export_format='GLB', export_materials='EXPORT',
    export_image_format='AUTO', export_apply=True, export_lights=False,
    export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"\n[SAVED .blend] {SRC}")
print(f"[SAVED .glb]   {DST_GLB}  ({sz/1024/1024:.2f} MB)")

# 6. 验收
print(f"\n[VERIFY L3-03 §11 内容验收]")
for n in ("R_leak_tree_01", "M_leak_tree_01", "H_cover_tree_01"):
    o = bpy.data.objects.get(n)
    if o:
        print(f"  ✓ {n} ({o.type}) loc={tuple(round(v,3) for v in o.location)}")
    else:
        print(f"  ✗ {n} 缺失")
