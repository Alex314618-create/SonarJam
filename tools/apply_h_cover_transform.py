"""把 H_cover_tree_01 的 transform Apply 掉，符合 L3-03 §11 要求"""
import bpy, mathutils, os

SRC = r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\更新与交付\3.blend"
DST_GLB = r"C:\Users\ROG\Desktop\GameJam\content\levels\earth_return_01\scene_loop3.glb"

bpy.ops.wm.open_mainfile(filepath=SRC)

cyl = bpy.data.objects.get("H_cover_tree_01")
if cyl:
    print(f"Before: object.location={tuple(round(v,3) for v in cyl.location)}")
    bpy.ops.object.select_all(action='DESELECT')
    cyl.select_set(True)
    bpy.context.view_layer.objects.active = cyl
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print(f"After:  object.location={tuple(round(v,3) for v in cyl.location)}")
    pts = [cyl.matrix_world @ mathutils.Vector(v) for v in cyl.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (mn+mx)/2; s = mx-mn
    print(f"World bbox: center=({c.x:.2f},{c.y:.2f},{c.z:.2f}) size=({s.x:.2f},{s.y:.2f},{s.z:.2f})")

bpy.ops.wm.save_as_mainfile(filepath=SRC)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB, export_format='GLB', export_materials='EXPORT',
    export_image_format='AUTO', export_apply=True, export_lights=False,
    export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"\n[SAVED .glb] {DST_GLB}  ({sz/1024/1024:.2f} MB)")

# 最终验收
print(f"\n[L3-03 §11 内容验收]")
for n in ("R_leak_tree_01", "M_leak_tree_01", "H_cover_tree_01"):
    o = bpy.data.objects.get(n)
    if o:
        print(f"  ✓ {n} ({o.type}) loc={tuple(round(v,3) for v in o.location)}")
    else:
        print(f"  ✗ {n}")
