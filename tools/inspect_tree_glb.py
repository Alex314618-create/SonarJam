"""检查 tree.glb 的对象 + 材质 + 大小"""
import bpy, mathutils

GLB = r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\我的工作区\C_s\tree.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)

print(f"=== {GLB} ===")
print(f"Total objects: {len(bpy.data.objects)}")

mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH']
all_pts = []
for o in mesh_objs:
    for v in o.bound_box:
        all_pts.append(o.matrix_world @ mathutils.Vector(v))
if all_pts:
    mn = mathutils.Vector((min(p.x for p in all_pts), min(p.y for p in all_pts), min(p.z for p in all_pts)))
    mx = mathutils.Vector((max(p.x for p in all_pts), max(p.y for p in all_pts), max(p.z for p in all_pts)))
    c = (mn+mx)/2; s = mx-mn
    print(f"Combined bbox: center=({c.x:.2f},{c.y:.2f},{c.z:.2f}) size=({s.x:.2f},{s.y:.2f},{s.z:.2f})")

print(f"\nMesh:")
for o in mesh_objs:
    pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (mn+mx)/2; s = mx-mn
    polys = len(o.data.polygons)
    par = o.parent.name if o.parent else "—"
    mats = [m.material.name for m in o.material_slots if m.material]
    print(f"  {o.name:<28s} polys={polys:>5} center=({c.x:5.1f},{c.y:5.1f},{c.z:5.1f}) size=({s.x:.1f}x{s.y:.1f}x{s.z:.1f}) parent={par} mats={mats}")
