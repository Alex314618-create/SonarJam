"""核 R_truck_rocket 真实位置 + 它有没有 parent 错位"""
import bpy, mathutils
print("R_truck_rocket_NN 真实世界位置：")
for o in bpy.data.objects:
    if o.name.startswith("R_truck_rocket_") and o.type == 'MESH':
        bb = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
        cx = sum(p.x for p in bb)/8; cy = sum(p.y for p in bb)/8; cz = sum(p.z for p in bb)/8
        dx = max(p.x for p in bb)-min(p.x for p in bb)
        dy = max(p.y for p in bb)-min(p.y for p in bb)
        dz = max(p.z for p in bb)-min(p.z for p in bb)
        par = o.parent.name if o.parent else "<none>"
        polys = len(o.data.polygons)
        orig = o.get("original_name","")
        print(f"  {o.name:<22s} polys={polys:>5} center=({cx:6.2f},{cy:6.2f},{cz:5.2f}) size=({dx:.1f}x{dy:.1f}x{dz:.1f}) parent={par}  orig={orig}")

print("\nR_truck_debris_NN 真实位置：")
for o in bpy.data.objects:
    if o.name.startswith("R_truck_debris_") and o.type == 'MESH':
        bb = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
        cx = sum(p.x for p in bb)/8; cy = sum(p.y for p in bb)/8; cz = sum(p.z for p in bb)/8
        par = o.parent.name if o.parent else "<none>"
        polys = len(o.data.polygons)
        orig = o.get("original_name","")
        print(f"  {o.name:<22s} polys={polys:>5} center=({cx:6.2f},{cy:6.2f},{cz:5.2f}) parent={par}  orig={orig}")
