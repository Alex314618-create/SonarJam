import bpy
import bmesh
from mathutils import Vector


obj = bpy.data.objects.get("BT_proto")
if obj is None or obj.type != "MESH":
    raise RuntimeError("BT_proto mesh not found")

bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

mesh = obj.data
neighbors = {i: set() for i in range(len(mesh.vertices))}
for poly in mesh.polygons:
    vs = list(poly.vertices)
    for a, b in zip(vs, vs[1:] + vs[:1]):
        neighbors[a].add(b)
        neighbors[b].add(a)

seen = set()
components = []
for start in range(len(mesh.vertices)):
    if start in seen:
        continue
    stack = [start]
    seen.add(start)
    comp = set()
    while stack:
        v = stack.pop()
        comp.add(v)
        for n in neighbors[v]:
            if n not in seen:
                seen.add(n)
                stack.append(n)
    components.append(comp)

keep = max(components, key=len)

bm = bmesh.new()
bm.from_mesh(mesh)
bm.verts.ensure_lookup_table()
remove = [v for v in bm.verts if v.index not in keep]
bmesh.ops.delete(bm, geom=remove, context="VERTS")
bm.to_mesh(mesh)
bm.free()
mesh.update()

min_z = min((obj.matrix_world @ Vector(corner)).z for corner in obj.bound_box)
obj.location.z -= min_z
bpy.context.view_layer.update()

tri_count = sum(max(1, len(poly.vertices) - 2) for poly in mesh.polygons)
world_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
mn = Vector((min(c.x for c in world_corners), min(c.y for c in world_corners), min(c.z for c in world_corners)))
mx = Vector((max(c.x for c in world_corners), max(c.y for c in world_corners), max(c.z for c in world_corners)))
print(
    f"Cleaned BT_proto: kept={len(keep)} removed={sum(len(c) for c in components) - len(keep)} "
    f"verts={len(mesh.vertices)} polys={len(mesh.polygons)} tris={tri_count} "
    f"min=({mn.x:.3f},{mn.y:.3f},{mn.z:.3f}) max=({mx.x:.3f},{mx.y:.3f},{mx.z:.3f})"
)
bpy.ops.wm.save_as_mainfile(filepath=r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\BT.blend")
