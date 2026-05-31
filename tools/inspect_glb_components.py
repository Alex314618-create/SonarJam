import sys
from pathlib import Path

import bpy
from mathutils import Vector


path = Path(sys.argv[-1])
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=str(path))

for obj in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
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
        mn = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
        mx = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
        components.append((len(comp), mn, mx))

    print(f"MESH {obj.name}: components={len(components)} verts={len(mesh.vertices)} polys={len(mesh.polygons)}")
    for i, (count, mn, mx) in enumerate(sorted(components, key=lambda item: item[0], reverse=True)):
        print(
            f"component {i}: verts={count} "
            f"min=({mn.x:.3f},{mn.y:.3f},{mn.z:.3f}) "
            f"max=({mx.x:.3f},{mx.y:.3f},{mx.z:.3f})"
        )
