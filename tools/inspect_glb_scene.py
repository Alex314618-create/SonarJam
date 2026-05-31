import sys
from pathlib import Path

import bpy
from mathutils import Vector


path = Path(sys.argv[-1])
bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=str(path))

for obj in bpy.context.scene.objects:
    if obj.type != "MESH":
        print(f"{obj.type}: {obj.name}")
        continue
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    tris = sum(max(1, len(poly.vertices) - 2) for poly in mesh.polygons)
    coords = [obj.matrix_world @ v.co for v in mesh.vertices]
    mn = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
    mx = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    print(
        f"MESH: {obj.name} verts={len(mesh.vertices)} polys={len(mesh.polygons)} tris={tris} "
        f"min=({mn.x:.3f},{mn.y:.3f},{mn.z:.3f}) max=({mx.x:.3f},{mx.y:.3f},{mx.z:.3f}) "
        f"materials={[slot.material.name if slot.material else None for slot in obj.material_slots]}"
    )
    eval_obj.to_mesh_clear()
