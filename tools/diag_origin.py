"""
查 origin 文件（mountain_mine.blend）里：
  1. 所有 CJK 命名的物件位置（特别是含"登陆仓"/"crashed"的）
  2. 当时 shuttle (Object_*) 的真实世界位置
  3. 与现在 mountain_final.blend 对比，看 shuttle 是不是被我的脚本搞跑位了
"""
import bpy, sys, mathutils

phase = sys.argv[sys.argv.index("--") + 1]  # "origin" or "final"

print(f"\n>>>>>> Phase: {phase} <<<<<<\n")

# 1. CJK / 含登陆仓 / crashed 标记的物件
print("=== CJK / 登陆仓 / crashed 标记 ===")
for o in bpy.data.objects:
    n = o.name
    has_cjk = any(0x4e00 <= ord(c) <= 0x9fff for c in n)
    has_keyword = "登陆" in n or "crashed" in n.lower() or "lander" in n.lower()
    if has_cjk or has_keyword:
        bb = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box] if o.type == 'MESH' else None
        if bb:
            cx = sum(p.x for p in bb)/8; cy = sum(p.y for p in bb)/8; cz = sum(p.z for p in bb)/8
            world = (cx, cy, cz)
        else:
            world = tuple(o.matrix_world.translation)
        print(f"  {o.type:<6s} {n[:50]:<52s}  world=({world[0]:6.2f},{world[1]:6.2f},{world[2]:5.2f})")

# 2. 所有 "Object_NN" 命名（原 shuttle）或 R_shuttle 真实位置
print("\n=== Shuttle 簇真实位置（Object_NN 或 R_shuttle_NN） ===")
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    n = o.name
    is_shuttle = n.startswith("R_shuttle_") or (n.startswith("Object_") and "_0" not in n and any(c.isdigit() for c in n))
    # 更宽：检测 mat 中含 Tube/Cylindre/Capsule（法语 shuttle 材质特征）
    has_french_mat = False
    for slot in o.material_slots:
        if slot.material and any(k in slot.material.name for k in ["Tube56", "Cylindre", "Capsule", "Bo_te", "Sph_re", "mesh16"]):
            has_french_mat = True; break
    if not (is_shuttle or has_french_mat): continue

    bb = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
    cx = sum(p.x for p in bb)/8; cy = sum(p.y for p in bb)/8; cz = sum(p.z for p in bb)/8
    par = o.parent.name if o.parent else "—"
    print(f"  {n:<22s} world=({cx:6.2f},{cy:6.2f},{cz:5.2f}) parent={par}")

# 3. shuttle 簇整体 bbox
print("\n=== Shuttle 簇整体 bbox ===")
all_pts = []
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    n = o.name
    fmat = False
    for slot in o.material_slots:
        if slot.material and any(k in slot.material.name for k in ["Tube56", "Cylindre", "Capsule", "Bo_te", "Sph_re", "mesh16"]):
            fmat = True; break
    if not fmat and not n.startswith("R_shuttle_"): continue
    for v in o.bound_box:
        all_pts.append(o.matrix_world @ mathutils.Vector(v))
if all_pts:
    mn = (min(p.x for p in all_pts), min(p.y for p in all_pts), min(p.z for p in all_pts))
    mx = (max(p.x for p in all_pts), max(p.y for p in all_pts), max(p.z for p in all_pts))
    print(f"  shuttle bbox: X[{mn[0]:.2f},{mx[0]:.2f}]  Y[{mn[1]:.2f},{mx[1]:.2f}]  Z[{mn[2]:.2f},{mx[2]:.2f}]")
    print(f"  shuttle center: ({(mn[0]+mx[0])/2:.2f}, {(mn[1]+mx[1])/2:.2f}, {(mn[2]+mx[2])/2:.2f})")
