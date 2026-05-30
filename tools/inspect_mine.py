"""读 mountain_mine.blend，给所有 mesh 出清单：名字 / 材质 / poly / bbox / 可见性"""
import bpy, mathutils

print("=" * 100)
total = 0
rows = []
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    me = obj.data
    poly = len(me.polygons)
    total += poly
    mats = [s.material.name if s.material else '<none>' for s in obj.material_slots] or ['<none>']
    bb = [obj.matrix_world @ mathutils.Vector(v) for v in obj.bound_box]
    dx = max(p.x for p in bb) - min(p.x for p in bb)
    dy = max(p.y for p in bb) - min(p.y for p in bb)
    dz = max(p.z for p in bb) - min(p.z for p in bb)
    diag = (dx*dx + dy*dy + dz*dz) ** 0.5
    cx = sum(p.x for p in bb) / 8
    cy = sum(p.y for p in bb) / 8
    cz = sum(p.z for p in bb) / 8
    hide_r = obj.hide_render
    hide_v = obj.hide_get()
    # density: polys per unit volume → high density + small size = candidate for decimate
    vol = max(dx*dy*dz, 0.01)
    density = poly / vol
    rows.append((poly, obj.name, mats, dx, dy, dz, cx, cy, cz, hide_r, hide_v, density))

# sort by poly desc
rows.sort(key=lambda r: -r[0])
print(f"{'poly':>7} {'name':<48} {'size XYZ':<22} {'center':<22} {'hide':<6} {'dens':>8} mat")
print("-" * 130)
for poly, name, mats, dx, dy, dz, cx, cy, cz, hr, hv, dens in rows:
    hide = ('R' if hr else '-') + ('V' if hv else '-')
    print(f"{poly:>7} {name[:46]:<48} {dx:5.1f}x{dy:5.1f}x{dz:5.1f}     ({cx:6.1f},{cy:6.1f},{cz:6.1f}) {hide:<6} {dens:8.1f} {mats[0][:30]}")

print(f"\nTOTAL meshes: {len(rows)}, total polys: {total}")
print(f"\nPrefix tally:")
from collections import Counter
pref = Counter()
for r in rows:
    n = r[1]
    if n.startswith("R_"): pref["R_"]+=1
    elif n.startswith("C_"): pref["C_"]+=1
    elif n.startswith("P_"): pref["P_"]+=1
    elif n.startswith("M_"): pref["M_"]+=1
    else: pref["other"]+=1
for k, v in pref.items(): print(f"  {k}: {v}")
