"""列出 shuttle 簇里所有对象：含 'block' 的、R_shuttle_NN 各件、附近其他 mesh"""
import bpy, mathutils

# 找所有名字含 "block" 的（不分大小写）
print("=" * 90)
print("所有名字含 'block' 的对象")
print("=" * 90)
for o in bpy.data.objects:
    if "block" in o.name.lower():
        bb = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
        c = sum(bb, mathutils.Vector()) / 8
        dx = max(p.x for p in bb) - min(p.x for p in bb)
        dy = max(p.y for p in bb) - min(p.y for p in bb)
        dz = max(p.z for p in bb) - min(p.z for p in bb)
        polys = len(o.data.polygons) if o.type == 'MESH' else 0
        orig = o.get("original_name", "")
        print(f"  {o.name:<36s} type={o.type:<6s} polys={polys:>5d} size={dx:.1f}x{dy:.1f}x{dz:.1f} center=({c.x:.1f},{c.y:.1f},{c.z:.1f})  orig={orig}")

print()
print("=" * 90)
print("shuttle 簇所有 R_shuttle_NN 详情（按 poly 排序）")
print("=" * 90)
shuttle = []
for o in bpy.data.objects:
    if o.name.startswith("R_shuttle_") and o.type == 'MESH':
        bb = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
        c = sum(bb, mathutils.Vector()) / 8
        dx = max(p.x for p in bb) - min(p.x for p in bb)
        dy = max(p.y for p in bb) - min(p.y for p in bb)
        dz = max(p.z for p in bb) - min(p.z for p in bb)
        polys = len(o.data.polygons)
        orig = o.get("original_name", "")
        mat = o.material_slots[0].material.name if o.material_slots and o.material_slots[0].material else ""
        shuttle.append((polys, o.name, dx, dy, dz, c.x, c.y, c.z, orig, mat))

shuttle.sort(key=lambda x: -x[0])
for polys, name, dx, dy, dz, cx, cy, cz, orig, mat in shuttle:
    print(f"  {name:<18s} polys={polys:>5d} size={dx:5.1f}x{dy:5.1f}x{dz:5.1f} center=({cx:5.1f},{cy:5.1f},{cz:5.1f})  mat={mat:<28s} orig={orig}")

print()
print("=" * 90)
print("shuttle 中心 (76, -73) ±15m 内的所有 mesh（包括非 R_shuttle）")
print("=" * 90)
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    bb = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
    cx = sum(p.x for p in bb) / 8
    cy = sum(p.y for p in bb) / 8
    if 60 < cx < 92 and -88 < cy < -58:
        polys = len(o.data.polygons)
        orig = o.get("original_name", "")
        if not o.name.startswith("R_shuttle_"):
            print(f"  {o.name:<36s} polys={polys:>5d} center=({cx:5.1f},{cy:5.1f}) orig={orig}")
