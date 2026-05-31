"""查 3.blend 当前是否有树 + CJK"一棵突兀的、关键的树" marker 是否还在"""
import bpy, mathutils

bpy.ops.wm.open_mainfile(filepath=r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\更新与交付\3.blend")

print("=== 3.blend 现状 ===")
print("\n[trees]")
trees = [o for o in bpy.data.objects if o.name.startswith("R_trees_") or o.name.startswith("R_leak_tree_")]
for o in trees:
    print(f"  {o.name}")
if not trees:
    print("  (无)")

print("\n[CJK 含'树' empty / 标记]")
for o in bpy.data.objects:
    if "树" in o.name or "leak_tree" in o.name.lower() or "cover_tree" in o.name.lower():
        pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box] if o.type == 'MESH' else None
        loc = tuple(o.matrix_world.translation)
        print(f"  {o.type} {o.name!r}  loc={tuple(round(v,2) for v in loc)}")

print("\n[现 H_*, M_leak_tree*, R_leak_tree*]")
for o in bpy.data.objects:
    if o.name.startswith("H_") or o.name.startswith("M_leak_tree") or o.name.startswith("R_leak_tree"):
        print(f"  {o.name}")
