"""详细 transform 诊断 R_shuttle_01 + 其 parent 链 + 所有 R_shuttle 实际位置"""
import bpy, mathutils

# 找所有 R_shuttle 的真实世界位置（通过 mesh 数据 + parent 链）
print("=" * 90)
print("所有 R_shuttle_NN 真实世界中心位置")
print("=" * 90)
for o in bpy.data.objects:
    if not o.name.startswith("R_shuttle_") or o.type != 'MESH': continue
    # 累计 parent 链的 matrix_world
    M = o.matrix_world
    # 用 bound_box 中心
    bb_local_cx = sum(v[0] for v in o.bound_box) / 8
    bb_local_cy = sum(v[1] for v in o.bound_box) / 8
    bb_local_cz = sum(v[2] for v in o.bound_box) / 8
    cw = M @ mathutils.Vector((bb_local_cx, bb_local_cy, bb_local_cz))
    par_name = o.parent.name if o.parent else "<none>"
    print(f"  {o.name:<18s}  parent={par_name:<28s}  world_center=({cw.x:7.2f},{cw.y:7.2f},{cw.z:7.2f})")

print()
print("=" * 90)
print("parent 对象 Bloc-A.3ds.001 链")
print("=" * 90)
p = bpy.data.objects.get("Bloc-A.3ds.001")
while p:
    print(f"  {p.name:<32s} loc={tuple(round(x,2) for x in p.location)} rot={tuple(round(x,2) for x in p.rotation_euler)} scale={tuple(round(x,2) for x in p.scale)}")
    print(f"    matrix_world center: {tuple(round(x,2) for x in p.matrix_world.translation)}")
    p = p.parent
