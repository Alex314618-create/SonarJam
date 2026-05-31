"""找 R_ 没对应 C_ 的对象（特别是用户新建的）"""
import bpy, sys, os, mathutils

argv = sys.argv
sep = argv.index("--") if "--" in argv else -1
BLEND_NAME = argv[sep+1] if sep >= 0 else "1.blend"

SRC = os.path.join(r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\更新与交付", BLEND_NAME)
bpy.ops.wm.open_mainfile(filepath=SRC)

print(f"\n=== {BLEND_NAME} ===\n")

# 所有 R_ 和 C_ mesh
r_objs = [o for o in bpy.data.objects if o.name.startswith("R_") and o.type == 'MESH']
c_objs = [o for o in bpy.data.objects if o.name.startswith("C_") and o.type == 'MESH']

print(f"R_ count: {len(r_objs)}, C_ count: {len(c_objs)}")

# 检查每个 R_ 是否有对应 C_
# 命名规律：R_<x> 对应 C_<x>（同名）
def bbox(o):
    pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (mn+mx)/2, mx-mn

print("\n所有 R_ 对象（按 poly 倒序）:")
r_sorted = sorted(r_objs, key=lambda o: -len(o.data.polygons))
for o in r_sorted:
    polys = len(o.data.polygons)
    c, s = bbox(o)
    # 找配对的 C_
    paired = None
    candidates = [c_obj for c_obj in c_objs if c_obj.name == "C_" + o.name[2:]]
    if candidates: paired = candidates[0].name
    # 重叠 bbox C_（无配对名但位置重合的）
    overlapping_c = []
    for c_obj in c_objs:
        cc, cs = bbox(c_obj)
        if (abs(cc.x - c.x) < max(s.x, 1) * 0.6 and
            abs(cc.y - c.y) < max(s.y, 1) * 0.6 and
            abs(cc.z - c.z) < max(s.z, 1) * 0.6):
            overlapping_c.append(c_obj.name)
    pair_str = f"✓ {paired}" if paired else (f"~{overlapping_c[:2]}" if overlapping_c else "✗ NO C_!")
    print(f"  {o.name:<40s} polys={polys:>5} c=({c.x:5.1f},{c.y:5.1f},{c.z:5.1f}) s=({s.x:.1f}x{s.y:.1f}x{s.z:.1f})  pair: {pair_str}")
