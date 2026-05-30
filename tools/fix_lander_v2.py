"""
fix_lander_v2.py — 修复 C_shuttle 实际位置错位 + 树石头不该有碰撞。

发现的真相：
  - R_shuttle_NN 都 parent 到 Bloc-A.3ds.001（位于原点）
  - 但 R_shuttle 自身 matrix_world 是单位矩阵（parent transform 没起作用）
  - mesh data 的 LOCAL bbox 已经在 Y=24~52 区间
  - 所以 R_shuttle 真实世界中心是 (0, ~38, 0)，不是 (76, -73)
  - 我之前从过时位置生成的 C_shuttle_block_01 是孤儿盒子，要重做

同时解决 user 抱怨：
  - "声呐模式还看到/撞树石头" → 是我自动生成的 C_rocks_block / C_trees_pole 害的
  - 删掉它们；树石头变成纯 R_（仅深度遮挡，声呐看不到，没碰撞）

操作：
  A. 删 C_rocks_block_01..05 (5 个)
  B. 删 C_trees_pole_01..02 (2 个)
  C. 删错位的 C_crashed_shuttle_block_01
  D. 删错位的 M_spawn_lander
  E. 复制全部 R_shuttle_NN → 解 parent → C_crashed_shuttle_NN → decimate 0.3
  F. 新 M_spawn_lander 放在 shuttle 真实位置旁边
  G. 保存 + 重导出
"""

import bpy, os, mathutils

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC       = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST_BLEND = SRC  # 原地覆盖
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")

CRASHED_RATIO = 0.30

bpy.ops.wm.open_mainfile(filepath=SRC)

# ============================================================
# A/B/C/D: 清理错的
# ============================================================
to_remove = []
for o in list(bpy.data.objects):
    n = o.name
    if (n.startswith("C_rocks_block_") or
        n.startswith("C_trees_pole_") or
        n == "C_crashed_shuttle_block_01" or
        n.startswith("M_spawn")):
        to_remove.append(n)

for n in to_remove:
    obj = bpy.data.objects.get(n)
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)
print(f"[CLEANUP] 删除 {len(to_remove)} 个对象:")
for n in to_remove:
    print(f"  - {n}")

# ============================================================
# E: 复制全部 R_shuttle_NN → C_crashed_shuttle_NN
# ============================================================
shuttle_srcs = [o for o in bpy.data.objects if o.name.startswith("R_shuttle_") and o.type == 'MESH']
print(f"\n[CRASHED] 找到 {len(shuttle_srcs)} 个 R_shuttle 部件")

# 先算 shuttle 簇真实世界 bbox（含 mesh-local 偏移）
all_pts = []
for o in shuttle_srcs:
    for v in o.bound_box:
        all_pts.append(o.matrix_world @ mathutils.Vector(v))
mn = mathutils.Vector((min(p.x for p in all_pts), min(p.y for p in all_pts), min(p.z for p in all_pts)))
mx = mathutils.Vector((max(p.x for p in all_pts), max(p.y for p in all_pts), max(p.z for p in all_pts)))
cx = (mn.x + mx.x) / 2
cy = (mn.y + mx.y) / 2
cz = (mn.z + mx.z) / 2
print(f"  shuttle 真实世界 bbox: X[{mn.x:.1f},{mx.x:.1f}] Y[{mn.y:.1f},{mx.y:.1f}] Z[{mn.z:.1f},{mx.z:.1f}]")
print(f"  簇中心 world = ({cx:.2f}, {cy:.2f}, {cz:.2f})")

# 复制 + 解 parent + 改名 + decimate
crashed_log = []
total_before = total_after = 0
for i, src in enumerate(shuttle_srcs, 1):
    dup = src.copy()
    dup.data = src.data.copy()
    bpy.context.collection.objects.link(dup)
    new_name = f"C_crashed_shuttle_{i:02d}"
    dup.name = new_name
    dup["original_name"] = f"DERIVED_FROM:{src.name}"
    dup["sonarjam_kind"] = "lander_pod"
    dup.hide_render = True
    dup.display_type = 'WIRE'

    # 解 parent 同时保留世界变换：将 parent 的 matrix_world 烘进 dup 的 matrix_basis
    if dup.parent is not None:
        world_m = dup.parent.matrix_world @ dup.matrix_basis
        dup.parent = None
        dup.matrix_basis = world_m

    # decimate
    bpy.context.view_layer.objects.active = dup
    before = len(dup.data.polygons)
    mod = dup.modifiers.new(name='dec', type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = CRASHED_RATIO
    mod.use_collapse_triangulate = True
    try:
        bpy.ops.object.modifier_apply(modifier='dec')
    except Exception as e:
        print(f"  [WARN] decimate failed on {new_name}: {e}")
        dup.modifiers.remove(mod)
    after = len(dup.data.polygons)
    crashed_log.append((new_name, src.name, before, after))
    total_before += before
    total_after += after

print(f"  ratio={CRASHED_RATIO}  TOTAL: {total_before} → {total_after} polys")

# ============================================================
# F: M_spawn_lander 在 shuttle 真实位置旁边
# ============================================================
# 偏移到 shuttle 簇南侧（朝-Y 方向，远离簇中心）
spawn_x = cx
spawn_y = mn.y - 2.0   # shuttle 南面外侧
spawn_z = mn.z         # 引擎忽略 Z

empty = bpy.data.objects.new("M_spawn_lander", None)
empty.location = (spawn_x, spawn_y, spawn_z)
empty.empty_display_type = 'PLAIN_AXES'
empty.empty_display_size = 2.0
bpy.context.collection.objects.link(empty)
print(f"\n[M_spawn_lander] Blender XYZ = ({spawn_x:.2f}, {spawn_y:.2f}, {spawn_z:.2f})")

# ============================================================
# G: 保存 + 重导出
# ============================================================
bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
print(f"\n[SAVED .blend] {DST_BLEND}")

bpy.ops.export_scene.gltf(
    filepath=DST_GLB,
    export_format='GLB',
    export_materials='EXPORT',
    export_image_format='AUTO',
    export_apply=True,
    export_lights=False,
    export_yup=True,
    export_extras=True,
    use_visible=False,
    use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"[SAVED .glb]   {DST_GLB}  ({sz/1024/1024:.2f} MB)")

# 终态
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
crashed = [o for o in meshes if o.name.startswith("C_") and "crashed" in o.name.lower()]
crashed_tris = sum(len(o.data.polygons) for o in crashed)
total = sum(len(o.data.polygons) for o in meshes)
print(f"\n[FINAL]")
print(f"  total meshes: {len(meshes)}, total polys: {total}")
print(f"  C_*crashed*: {len(crashed)} obj, {crashed_tris} tris  →  采样点云源")
