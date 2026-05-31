import bpy
from mathutils import Vector


for obj in bpy.context.scene.objects:
    if obj.type != "MESH":
        print(f"{obj.type}: {obj.name}")
        continue
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    tris = sum(max(1, len(poly.vertices) - 2) for poly in mesh.polygons)
    world_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_v = [min(c[i] for c in world_corners) for i in range(3)]
    max_v = [max(c[i] for c in world_corners) for i in range(3)]
    print(
        "MESH:",
        obj.name,
        f"verts={len(mesh.vertices)}",
        f"polys={len(mesh.polygons)}",
        f"tris={tris}",
        f"min={tuple(round(v, 3) for v in min_v)}",
        f"max={tuple(round(v, 3) for v in max_v)}",
        f"materials={[slot.material.name if slot.material else None for slot in obj.material_slots]}",
    )
    eval_obj.to_mesh_clear()
