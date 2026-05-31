"""检查 5.blend 里的水 / 河道 / 地形相关"""
import bpy, mathutils, os

bpy.ops.wm.open_mainfile(filepath=r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\更新与交付\5.blend")

print("=== 所有 R_water_* / 含'river/shore/河/水' 的对象 ===")
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    n = o.name.lower()
    if (o.name.startswith("R_water_") or
        "river" in n or "shore" in n or "河" in o.name or "水" in o.name):
        pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
        mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        c = (mn+mx)/2; s = mx-mn
        polys = len(o.data.polygons)
        verts = len(o.data.vertices)
        print(f"  {o.name:<30s} polys={polys:>5} verts={verts:>5} center=({c.x:.2f},{c.y:.2f},{c.z:.2f}) size=({s.x:.2f},{s.y:.2f},{s.z:.2f})")
        # 列出所有 vertex world 位置（如果不多）
        if verts <= 20:
            for i, v in enumerate(o.data.vertices):
                wv = o.matrix_world @ v.co
                print(f"    v[{i}]: ({wv.x:.2f}, {wv.y:.2f}, {wv.z:.2f})")

print("\n=== R_terrain_* (用于估算地形高度) ===")
for o in bpy.data.objects:
    if o.name.startswith("R_terrain_") and o.type == 'MESH':
        pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
        mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        c = (mn+mx)/2; s = mx-mn
        print(f"  {o.name}: center=({c.x:.2f},{c.y:.2f},{c.z:.2f}) size=({s.x:.2f},{s.y:.2f},{s.z:.2f})")

print("\n=== 含 CJK '河' / '岸' / '墙' 的标记 ===")
for o in bpy.data.objects:
    if "河" in o.name or "岸" in o.name or "墙" in o.name or "wall" in o.name.lower():
        print(f"  {o.type} {o.name}")
