import bpy, mathutils, os
bpy.ops.wm.open_mainfile(filepath=r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\更新与交付\3.blend")
print("\n=== 3.blend 当前内容 ===")
for n in ("R_wagon_01", "R_wagon_02", "R_leak_tree_01", "M_leak_tree_01", "H_cover_tree_01",
          "C_wreck_wagon_01", "C_wreck_wagon_02"):
    o = bpy.data.objects.get(n)
    if o:
        if o.type == 'MESH':
            pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
            c = sum(pts, mathutils.Vector()) / 8
            polys = len(o.data.polygons)
            print(f"  ✓ {n} (MESH polys={polys}) world center=({c.x:.2f},{c.y:.2f},{c.z:.2f}) obj.location={tuple(round(v,3) for v in o.location)}")
        else:
            print(f"  ✓ {n} ({o.type}) loc={tuple(round(v,2) for v in o.location)}")
    else:
        print(f"  ✗ {n} 不存在")
