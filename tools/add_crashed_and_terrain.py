"""
add_crashed_and_terrain.py — 在 mountain_further.blend 基础上：
  1. 把 R_truck_rocket_* 视为登陆仓 → 复制+轻度 decimate → C_crashed_pod_NN
     这样引擎启动时会从 C_crashed_* 采样 ~150k 点云覆盖登陆仓
  2. 复制 R_terrain_02..05 → 重度 decimate 到总 ~8k tri → C_terrain_NN
     给声呐扫地一个低成本反射代理
  3. 在登陆仓附近放 M_spawn_lander Empty
     （引擎只读其水平 XZ，垂直高度由 PLAYER_HEIGHT 兜底）

源    : mountain_further.blend  （不动）
输出  : mountain_final.blend
也直接重新导出 GLB 到 content/levels/earth_return_01/scene.glb
"""

import bpy, os, mathutils

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC       = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_further.blend")
DST_BLEND = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")

LANDER_PREFIX = "R_truck_rocket_"   # 改这一行就能换登陆仓（比如 "R_shuttle_"）
CRASHED_RATIO = 0.7                  # 登陆仓 C_ 副本的 decimate ratio（保持稠密）
TERRAIN_TARGET_TOTAL = 8000          # C_terrain 总三角目标

bpy.ops.wm.open_mainfile(filepath=SRC)

# ============================================================
# 1) 登陆仓识别
# ============================================================
lander_objs = [o for o in bpy.data.objects if o.name.startswith(LANDER_PREFIX) and o.type == 'MESH']
if not lander_objs:
    raise SystemExit(f"没找到 {LANDER_PREFIX}* 对象")

# 簇 bbox
all_pts = []
for o in lander_objs:
    for v in o.bound_box:
        all_pts.append(o.matrix_world @ mathutils.Vector(v))
mn = mathutils.Vector((min(p.x for p in all_pts), min(p.y for p in all_pts), min(p.z for p in all_pts)))
mx = mathutils.Vector((max(p.x for p in all_pts), max(p.y for p in all_pts), max(p.z for p in all_pts)))
cx = (mn.x + mx.x) / 2
cy = (mn.y + mx.y) / 2
top_z = mx.z

print(f"\n[LANDER] {LANDER_PREFIX}* × {len(lander_objs)}")
print(f"  bbox = X[{mn.x:.1f},{mx.x:.1f}] Y[{mn.y:.1f},{mx.y:.1f}] Z[{mn.z:.1f},{mx.z:.1f}]")
print(f"  cluster center XY = ({cx:.2f}, {cy:.2f})")

# ============================================================
# 2) M_spawn_lander Empty
# ============================================================
# 偏移到登陆仓东北角外侧 ~3m，避免出生在登陆仓几何内部
spawn_x = cx + (mx.x - mn.x) * 0.4
spawn_y = cy + (mx.y - mn.y) * 0.4
spawn_z = top_z + 1.0  # Z 在 Blender 是高度，但引擎会忽略，重写为 PLAYER_HEIGHT

# 删掉旧 M_spawn_*（如果有）
for o in [obj for obj in bpy.data.objects if obj.name.startswith("M_spawn")]:
    bpy.data.objects.remove(o, do_unlink=True)

empty = bpy.data.objects.new("M_spawn_lander", None)
empty.location = (spawn_x, spawn_y, spawn_z)
empty.empty_display_type = 'PLAIN_AXES'
empty.empty_display_size = 2.0
bpy.context.collection.objects.link(empty)
print(f"\n[M_spawn_lander] at Blender XYZ ({spawn_x:.2f}, {spawn_y:.2f}, {spawn_z:.2f})")
print(f"  注：引擎只用 XZ（glTF 轴），Y 强制为 PLAYER_HEIGHT")

# ============================================================
# 3) 复制 R_truck_rocket_* → C_crashed_pod_NN
# ============================================================
print(f"\n[C_crashed] 从 {LANDER_PREFIX}* 复制 + decimate ratio={CRASHED_RATIO}")
crashed_log = []
crashed_total_before = 0
crashed_total_after = 0
for i, src in enumerate(lander_objs, 1):
    dup = src.copy()
    dup.data = src.data.copy()
    bpy.context.collection.objects.link(dup)
    new_name = f"C_crashed_pod_{i:02d}"
    dup.name = new_name
    dup["original_name"] = f"DERIVED_FROM:{src.name}"
    dup["sonarjam_kind"] = "crashed_pod"
    dup.hide_render = True  # C_ 不渲染
    dup.display_type = 'WIRE'

    bpy.context.view_layer.objects.active = dup
    before = len(dup.data.polygons)
    mod = dup.modifiers.new(name='dec', type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = CRASHED_RATIO
    mod.use_collapse_triangulate = True
    try:
        bpy.ops.object.modifier_apply(modifier='dec')
    except Exception as e:
        dup.modifiers.remove(mod)
        print(f"  [WARN] decimate failed on {new_name}: {e}")
    after = len(dup.data.polygons)
    crashed_log.append((new_name, src.name, before, after))
    crashed_total_before += before
    crashed_total_after += after
    print(f"  {new_name:<24s}  {before:>6} -> {after:>5}")

print(f"  TOTAL: {crashed_total_before} -> {crashed_total_after}")

# ============================================================
# 4) 复制 R_terrain_02..05 → C_terrain_NN（重度 decimate）
# ============================================================
terrain_objs = [o for o in bpy.data.objects
                if o.name.startswith("R_terrain_") and o.name != "R_terrain_01" and o.type == 'MESH']
total_in = sum(len(o.data.polygons) for o in terrain_objs)
target_ratio = max(0.03, min(0.5, TERRAIN_TARGET_TOTAL / total_in)) if total_in > 0 else 0.1
print(f"\n[C_terrain] 从 {len(terrain_objs)} 个 R_terrain 复制；目标总 ~{TERRAIN_TARGET_TOTAL} tri")
print(f"  源总 tri: {total_in}, 计算 ratio: {target_ratio:.3f}")
terrain_log = []
terrain_total_before = 0
terrain_total_after = 0
for i, src in enumerate(terrain_objs, 1):
    dup = src.copy()
    dup.data = src.data.copy()
    bpy.context.collection.objects.link(dup)
    new_name = f"C_terrain_{i:02d}"
    dup.name = new_name
    dup["original_name"] = f"DERIVED_FROM:{src.name}"
    dup["sonarjam_kind"] = "terrain_proxy"
    dup.hide_render = True
    dup.display_type = 'WIRE'

    bpy.context.view_layer.objects.active = dup
    before = len(dup.data.polygons)
    mod = dup.modifiers.new(name='dec', type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = target_ratio
    mod.use_collapse_triangulate = True
    try:
        bpy.ops.object.modifier_apply(modifier='dec')
    except Exception as e:
        dup.modifiers.remove(mod)
        print(f"  [WARN] decimate failed on {new_name}: {e}")
    after = len(dup.data.polygons)
    terrain_log.append((new_name, src.name, before, after))
    terrain_total_before += before
    terrain_total_after += after
    print(f"  {new_name:<24s}  {before:>6} -> {after:>5}")

print(f"  TOTAL: {terrain_total_before} -> {terrain_total_after}")

# ============================================================
# 5) 保存 .blend + 导出 GLB
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

# 终态统计
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
r_n = sum(1 for o in meshes if o.name.startswith("R_"))
c_n = sum(1 for o in meshes if o.name.startswith("C_"))
m_n = sum(1 for o in bpy.data.objects if o.name.startswith("M_"))
crashed_n = sum(1 for o in meshes if o.name.startswith("C_") and "crashed" in o.name.lower())
total = sum(len(o.data.polygons) for o in meshes)
print(f"\n[FINAL] meshes={len(meshes)} (R_={r_n}, C_={c_n}, M_={m_n}, C_crashed={crashed_n})")
print(f"  total polys: {total}")
