"""列出所有 mesh 对象（包括用户新建的没规范命名的）"""
import bpy, sys, os, mathutils

argv = sys.argv
sep = argv.index("--") if "--" in argv else -1
BLEND_NAME = argv[sep+1] if sep >= 0 else "1.blend"
SRC = os.path.join(r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\更新与交付", BLEND_NAME)
bpy.ops.wm.open_mainfile(filepath=SRC)

print(f"\n=== {BLEND_NAME} 所有 mesh ===")

# 分两组：规范前缀 vs 其他
prefixes = ("R_", "C_", "P_", "M_")
non_standard = []
standard = []
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    if not o.name.startswith(prefixes):
        non_standard.append(o)
    else:
        standard.append(o)

print(f"\n非标准命名的 mesh ({len(non_standard)} 个):")
for o in non_standard:
    pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (mn+mx)/2; s = mx-mn
    polys = len(o.data.polygons)
    verts = len(o.data.vertices)
    # 判断形状特征
    is_sphere = verts > 20 and abs(s.x - s.y) < 0.5 and abs(s.y - s.z) < 0.5
    is_box = verts == 8 and polys == 6
    shape = "SPHERE/球" if is_sphere else ("BOX/长方体" if is_box else f"{polys}poly/{verts}vert")
    print(f"  {o.name:<32s}  {shape:<18s}  center=({c.x:6.1f},{c.y:6.1f},{c.z:5.1f}) size=({s.x:.1f}x{s.y:.1f}x{s.z:.1f})")
