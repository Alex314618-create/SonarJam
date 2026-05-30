"""列出 R_antenna_* 和 R_building_* 的详细信息，给 further 优化做计划。"""
import bpy, mathutils

print("=" * 100)
print("R_antenna_* 详表（含 original_name，用于识别卫星锅）")
print("=" * 100)
print(f"{'name':<22} {'poly':>6} {'X':>5} {'Y':>5} {'Z':>5}  dish?  original")
print("-" * 100)
antennas = []
for o in bpy.data.objects:
    if not o.name.startswith("R_antenna_"): continue
    if o.type != 'MESH': continue
    poly = len(o.data.polygons)
    bb = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
    dx = max(p.x for p in bb) - min(p.x for p in bb)
    dy = max(p.y for p in bb) - min(p.y for p in bb)
    dz = max(p.z for p in bb) - min(p.z for p in bb)
    # dish 启发：XY 比例接近 1（差异 < 30%），且较扁（Z < min(X,Y)*0.6）
    xy_min, xy_max = min(dx, dy), max(dx, dy)
    aspect = (xy_max - xy_min) / xy_max if xy_max > 0 else 1
    flat = dz < min(dx, dy) * 0.6
    is_dish = aspect < 0.30 and flat and min(dx, dy) > 1.0
    orig = o.get("original_name", "")
    antennas.append((poly, o.name, dx, dy, dz, is_dish, orig))

antennas.sort(key=lambda r: -r[0])
for poly, name, dx, dy, dz, dish, orig in antennas:
    flag = "  DISH" if dish else "      "
    print(f"{name:<22} {poly:>6} {dx:5.1f} {dy:5.1f} {dz:5.1f}  {flag}  {orig}")

print()
print("=" * 100)
print("R_building_* 详表（识别 concrete inner / metal_bar 等破损细节）")
print("=" * 100)
print(f"{'name':<24} {'poly':>6}  original_name")
print("-" * 100)
buildings = []
for o in bpy.data.objects:
    if not o.name.startswith("R_building_"): continue
    if o.type != 'MESH': continue
    poly = len(o.data.polygons)
    orig = o.get("original_name", "")
    buildings.append((poly, o.name, orig))
buildings.sort(key=lambda r: -r[0])
for poly, name, orig in buildings:
    print(f"{name:<24} {poly:>6}  {orig}")
