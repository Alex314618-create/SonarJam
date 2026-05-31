"""量 R_riverwall 北缘 vs R_building_beta_block 南缘的间隙"""
import bpy, mathutils, sys, os
argv = sys.argv
sep = argv.index("--") if "--" in argv else -1
BLEND = argv[sep+1] if sep >= 0 else "1.blend"
bpy.ops.wm.open_mainfile(filepath=os.path.join(r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\更新与交付", BLEND))

def world_bbox(o):
    pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx

print(f"\n=== {BLEND} ===")
wall = bpy.data.objects.get("R_riverwall_structure_01")
block = bpy.data.objects.get("R_building_beta_block_01")
if wall:
    wmn, wmx = world_bbox(wall)
    print(f"R_riverwall:  Y=[{wmn.y:.2f}, {wmx.y:.2f}]  (北缘 Y={wmx.y:.2f})")
if block:
    bmn, bmx = world_bbox(block)
    print(f"R_block:      Y=[{bmn.y:.2f}, {bmx.y:.2f}]  (南缘 Y={bmn.y:.2f})")
if wall and block:
    gap = bmn.y - wmx.y
    print(f"通道宽度 = {gap:.2f}m  ({'✓ 通畅' if gap > 1.5 else '⚠ 太窄'})")
