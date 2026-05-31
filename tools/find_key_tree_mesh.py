"""在 5&4.blend 里找 CJK marker (14.29, -83.33) 附近的 mesh"""
import bpy, mathutils, os

bpy.ops.wm.open_mainfile(filepath=r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\更新与交付\5&4.blend")

TARGET = mathutils.Vector((14.29, -83.33, 1.32))

print(f"\n=== 离 {tuple(round(v,2) for v in TARGET)} 半径 10m 内的所有 MESH ===")
hits = []
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (mn+mx)/2
    d = ((c - TARGET).length)
    if d < 10:
        s = mx - mn
        polys = len(o.data.polygons)
        hits.append((d, o.name, c, s, polys))

hits.sort()
for d, name, c, s, polys in hits:
    print(f"  d={d:5.2f}m  {name[:45]:<47s}  center=({c.x:6.2f},{c.y:6.2f},{c.z:5.2f}) size=({s.x:.2f}x{s.y:.2f}x{s.z:.2f}) polys={polys}")

print(f"\n=== CJK marker 在 5&4.blend 中 ===")
for o in bpy.data.objects:
    if "一棵突兀" in o.name or "关键的树" in o.name:
        print(f"  {o.type} {o.name!r}  loc={tuple(round(v,2) for v in o.matrix_world.translation)}")
