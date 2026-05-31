"""列 1/2/3.blend 里所有名字含 CJK 或 '树' 的对象"""
import bpy, sys, os, mathutils

argv = sys.argv
sep = argv.index("--") if "--" in argv else -1
BLEND = argv[sep+1] if sep >= 0 else "1.blend"

SRC = os.path.join(r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\更新与交付", BLEND)
bpy.ops.wm.open_mainfile(filepath=SRC)

print(f"\n=== {BLEND} 含 CJK / 树相关 ===")
for o in bpy.data.objects:
    has_cjk = any(0x4e00 <= ord(c) <= 0x9fff for c in o.name)
    has_tree = "tree" in o.name.lower() or "树" in o.name or "leak_tree" in o.name.lower() or "cover_tree" in o.name.lower()
    if has_cjk or has_tree:
        if o.type == 'MESH':
            pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
            mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
            mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
            c = (mn+mx)/2; s = mx-mn
            polys = len(o.data.polygons)
            print(f"  MESH  {o.name[:60]:<62s}  polys={polys:>6} center=({c.x:6.1f},{c.y:6.1f},{c.z:5.1f}) size=({s.x:.1f}x{s.y:.1f}x{s.z:.1f})")
        else:
            loc = tuple(round(v, 2) for v in o.matrix_world.translation)
            print(f"  {o.type:<6s}{o.name[:60]:<62s}  loc={loc}")
