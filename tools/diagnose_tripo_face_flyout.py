from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(r"C:\Users\ROG\Desktop\GameJam")
GLB = ROOT / "_temp_Blender" / "muddy_man_by_tripo.glb"

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=str(GLB))

obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
mesh = obj.data

coords = [obj.matrix_world @ v.co for v in mesh.vertices]
mn = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
mx = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
print(f"bounds min=({mn.x:.3f},{mn.y:.3f},{mn.z:.3f}) max=({mx.x:.3f},{mx.y:.3f},{mx.z:.3f})")

regions = {
    "front_far": lambda c: c.y < -0.12 and c.z > 0.38,
    "back_far": lambda c: c.y > 0.12 and c.z > 0.38,
    "left_far": lambda c: c.x < -0.075 and c.z > 0.38,
    "right_far": lambda c: c.x > 0.075 and c.z > 0.38,
    "head_core": lambda c: abs(c.x) <= 0.075 and abs(c.y) <= 0.12 and c.z > 0.38,
}

for name, pred in regions.items():
    face_count = 0
    verts = set()
    region_coords = []
    for poly in mesh.polygons:
        center = obj.matrix_world @ poly.center
        if pred(center):
            face_count += 1
            for i in poly.vertices:
                verts.add(i)
                region_coords.append(obj.matrix_world @ mesh.vertices[i].co)
    if region_coords:
        rmn = Vector((min(c.x for c in region_coords), min(c.y for c in region_coords), min(c.z for c in region_coords)))
        rmx = Vector((max(c.x for c in region_coords), max(c.y for c in region_coords), max(c.z for c in region_coords)))
        print(
            f"{name}: faces={face_count} verts={len(verts)} "
            f"min=({rmn.x:.3f},{rmn.y:.3f},{rmn.z:.3f}) max=({rmx.x:.3f},{rmx.y:.3f},{rmx.z:.3f})"
        )
    else:
        print(f"{name}: faces=0")
