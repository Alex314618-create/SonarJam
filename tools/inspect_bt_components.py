import bpy
from mathutils import Vector


obj = bpy.data.objects.get("BT_proto")
if obj is None or obj.type != "MESH":
    raise RuntimeError("BT_proto mesh not found")

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
    comp = []
    while stack:
        v = stack.pop()
        comp.append(v)
        for n in neighbors[v]:
            if n not in seen:
                seen.add(n)
                stack.append(n)
    coords = [obj.matrix_world @ mesh.vertices[i].co for i in comp]
    min_v = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
    max_v = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    components.append((len(comp), min_v, max_v))

for i, (count, mn, mx) in enumerate(sorted(components, key=lambda item: item[0], reverse=True)):
    print(
        f"component {i}: verts={count} "
        f"min=({mn.x:.3f},{mn.y:.3f},{mn.z:.3f}) "
        f"max=({mx.x:.3f},{mx.y:.3f},{mx.z:.3f})"
    )
