"""在 mountain_mine.blend 里找带 rocket/thruster 材质的对象——这才是真正的 space_shuttle"""
import bpy, mathutils

bpy.ops.wm.open_mainfile(filepath=r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\我的工作区\mountain_mine.blend")

# 找用 rocket 或 thruster 材质 的 mesh
print("=== 用 rocket / thruster 材质的对象 ===")
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    for slot in o.material_slots:
        if slot.material:
            mn = slot.material.name.lower()
            if "rocket" == mn or "thruster" == mn or mn.startswith("rocket") or mn.startswith("thruster"):
                bb = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
                cx = sum(p.x for p in bb)/8; cy = sum(p.y for p in bb)/8; cz = sum(p.z for p in bb)/8
                dx = max(p.x for p in bb)-min(p.x for p in bb)
                dy = max(p.y for p in bb)-min(p.y for p in bb)
                dz = max(p.z for p in bb)-min(p.z for p in bb)
                par = o.parent.name if o.parent else "—"
                polys = len(o.data.polygons)
                print(f"  {o.name:<40s} mat={slot.material.name:<12s} world=({cx:6.2f},{cy:6.2f},{cz:5.2f}) size=({dx:.1f}x{dy:.1f}x{dz:.1f}) parent={par}")
                break

# 也找带 baseColorTexture 的（有贴图）shuttle 类对象
print("\n=== 所有材质带 IMG 节点的 mesh (按 parent 分组) ===")
from collections import defaultdict
by_parent = defaultdict(list)
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    for slot in o.material_slots:
        if slot.material and slot.material.use_nodes:
            for n in slot.material.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image:
                    par = o.parent.name if o.parent else "<no parent>"
                    by_parent[par].append((o.name, slot.material.name))
                    break
            else:
                continue
            break
for par, items in sorted(by_parent.items()):
    print(f"\n  parent: {par}  ({len(items)} mesh)")
    for n, m in items[:4]:
        print(f"    {n} (mat={m})")
    if len(items) > 4:
        print(f"    ... +{len(items)-4} more")
