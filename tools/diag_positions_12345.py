"""比对 mountain_mine vs mountain_12345 同名对象的位置/尺寸，揭露 scale offset"""
import bpy, mathutils

ROOT = r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\我的工作区"
files = {
    "mine":   ROOT + r"\mountain_mine.blend",
    "12345":  ROOT + r"\mountain_12345.blend",
}

def bbox_world(o):
    pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (mn+mx)/2, mx-mn

# Reference objects to compare across both
TARGETS = ["R_terrain_01", "R_terrain_02", "R_water_02", "R_snow_01"]

# Trees/rocks/grass to show their positions
NATURE = ["R_trees", "R_rocks", "R_grass"]

results = {}
for tag, path in files.items():
    bpy.ops.wm.open_mainfile(filepath=path)
    results[tag] = {}
    # In mountain_mine, R_ prefixes might be different (it had Object_NN etc.)
    # But terrain was likely renamed during normalize before save
    for name in TARGETS:
        o = bpy.data.objects.get(name)
        if o and o.type == 'MESH':
            c, s = bbox_world(o)
            results[tag][name] = (tuple(round(v,2) for v in c), tuple(round(v,2) for v in s))
    # Also collect ALL R_trees / R_rocks / R_grass found
    for pre in NATURE:
        objs = [o for o in bpy.data.objects if o.name.startswith(pre + "_") and o.type == 'MESH']
        results[tag][f"{pre}_count"] = len(objs)
        for o in objs:
            c, s = bbox_world(o)
            results[tag][o.name] = (tuple(round(v,2) for v in c), tuple(round(v,2) for v in s))

# 显示对比
print("\n=== 共有对象（同名）对比：mine vs 12345 ===")
for name in TARGETS:
    m = results["mine"].get(name)
    n = results["12345"].get(name)
    print(f"\n{name}:")
    print(f"  mine:  center={m[0] if m else 'MISSING'}  size={m[1] if m else ''}")
    print(f"  12345: center={n[0] if n else 'MISSING'}  size={n[1] if n else ''}")
    if m and n:
        cmd = tuple(round(n[0][i] - m[0][i], 2) for i in range(3))
        smd = tuple(round(n[1][i] / m[1][i], 3) if m[1][i] != 0 else 0 for i in range(3))
        print(f"  delta center: {cmd}")
        print(f"  size ratio:   {smd}")

print("\n=== R_trees/rocks/grass 在 12345 里的位置 ===")
for pre in NATURE:
    names = [k for k in results["12345"] if k.startswith(pre + "_") and not k.endswith("_count")]
    print(f"\n{pre} ({results['12345'].get(pre+'_count', 0)} obj):")
    for n in sorted(names):
        c, s = results["12345"][n]
        print(f"  {n}: center={c}  size={s}")
