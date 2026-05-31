"""
fix_key_tree.py — 用「一棵突兀的、关键的树」CJK marker 旁的真树（被错命名为 R_wagon_01/02）

Phase 1: 5&4.blend — 删 R_wagon_01/02 + C_wreck_wagon_01/02（人造 wagon 实际是误标的树）
Phase 2: 3.blend  —
  a. 删现有 R_leak_tree_01（我之前导入的随机树）
  b. 把 R_wagon_01 + R_wagon_02 合并 → 重命名 R_leak_tree_01
  c. 删 C_wreck_wagon_01/02
  d. 重做 H_cover_tree_01 套真树 bbox
"""
import bpy, bmesh, mathutils, os, sys

ROOT = r"C:\Users\ROG\Desktop\GameJam"
DELIV = os.path.join(ROOT, "_temp_Blender", "更新与交付")

WAGON_NAMES = ["R_wagon_01", "R_wagon_02", "C_wreck_wagon_01", "C_wreck_wagon_02"]

argv = sys.argv
sep = argv.index("--") if "--" in argv else -1
script_args = argv[sep+1:] if sep >= 0 else []
TARGET = script_args[0] if script_args else "5&4.blend"

src = os.path.join(DELIV, TARGET)
basename = os.path.splitext(TARGET)[0].replace("&", "_")
if TARGET == "5&4.blend":
    dst_glbs = ["scene.glb"]
elif TARGET == "3.blend":
    dst_glbs = ["scene_loop3.glb"]
else:
    dst_glbs = [f"scene_loop{basename}.glb"]

bpy.ops.wm.open_mainfile(filepath=src)

print(f"\n=== 处理 {TARGET} ===")

if TARGET == "5&4.blend":
    # 删 R_wagon + C_wreck_wagon
    removed = []
    for n in WAGON_NAMES:
        o = bpy.data.objects.get(n)
        if o:
            removed.append(n)
            bpy.data.objects.remove(o, do_unlink=True)
    print(f"  删 {len(removed)}: {removed}")

elif TARGET == "3.blend":
    # 1. 删现有的随机 R_leak_tree_01 + H_cover_tree_01
    for n in ("R_leak_tree_01", "H_cover_tree_01"):
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
            print(f"  删旧 {n}")

    # 2. 把 R_wagon_01 + R_wagon_02 join → R_leak_tree_01
    r1 = bpy.data.objects.get("R_wagon_01")
    r2 = bpy.data.objects.get("R_wagon_02")
    if not r1 or not r2:
        raise SystemExit(f"3.blend 里缺 R_wagon_01/02：{r1=}, {r2=}")

    bpy.ops.object.select_all(action='DESELECT')
    r1.select_set(True)
    r2.select_set(True)
    bpy.context.view_layer.objects.active = r1
    bpy.ops.object.join()
    leak = bpy.context.active_object
    leak.name = "R_leak_tree_01"
    leak["original_name"] = "joined_from_R_wagon_01+02"
    print(f"  join: R_wagon_01 + R_wagon_02 → R_leak_tree_01 (polys={len(leak.data.polygons)})")

    # 3. 删 C_wreck_wagon_01 + 02
    for n in ("C_wreck_wagon_01", "C_wreck_wagon_02"):
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
            print(f"  删 {n}")

    # 4. 量真树 bbox
    pts = [leak.matrix_world @ mathutils.Vector(v) for v in leak.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center = (mn+mx)/2
    size = mx-mn
    print(f"  R_leak_tree_01 真树 bbox: center=({center.x:.2f},{center.y:.2f},{center.z:.2f}) size=({size.x:.2f},{size.y:.2f},{size.z:.2f})")

    # 5. 重做 H_cover_tree_01 套真树
    cyl_radius = max(size.x, size.y) / 2 + 0.4
    cyl_depth = size.z + 0.8
    bpy.ops.mesh.primitive_cylinder_add(
        radius=cyl_radius, depth=cyl_depth,
        location=(center.x, center.y, center.z + 0.2),
        vertices=16,
    )
    cyl = bpy.context.object
    cyl.name = "H_cover_tree_01"
    # 灰色 PBR
    mat = bpy.data.materials.new(name="hcover_grey")
    mat.use_nodes = True
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.42, 0.42, 0.43, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.85
    cyl.data.materials.append(mat)
    print(f"  新 H_cover_tree_01: 半径={cyl_radius:.2f}m 高={cyl_depth:.2f}m")

    # 6. 确认 M_leak_tree_01 还在
    m = bpy.data.objects.get("M_leak_tree_01")
    if m:
        print(f"  M_leak_tree_01 已存在 @ {tuple(round(v,2) for v in m.matrix_world.translation)}")
    else:
        empty = bpy.data.objects.new("M_leak_tree_01", None)
        empty.location = (center.x, center.y, mn.z + 1.0)
        empty.empty_display_type = 'PLAIN_AXES'
        empty.empty_display_size = 2.0
        bpy.context.collection.objects.link(empty)
        print(f"  补 M_leak_tree_01 @ ({center.x:.2f},{center.y:.2f},{mn.z+1.0:.2f})")

# 保存
bpy.ops.wm.save_as_mainfile(filepath=src)

# 导出每个 GLB
out_dir = os.path.join(ROOT, "content", "levels", "earth_return_01")
for g in dst_glbs:
    dst = os.path.join(out_dir, g)
    bpy.ops.export_scene.gltf(
        filepath=dst, export_format='GLB', export_materials='EXPORT',
        export_image_format='AUTO', export_apply=True, export_lights=False,
        export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
    )
    sz = os.path.getsize(dst)
    print(f"  [.glb] {dst}  ({sz/1024/1024:.2f} MB)")

print(f"  [.blend] {src}")
