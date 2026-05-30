"""
fix_lander_v4.py — 最终修：尊重 origin 文件 CJK hint。

发现（对比 origin vs final）：
  origin 中:
    - shuttle 簇真实位置 (76.38, -73.57, 7.05)
    - CJK Empty「登陆仓——就是那个crashed」at (86.82, -66.66, 9.85) — 紧挨 shuttle
    - CJK Empty「坠毁的飞机」at (-47.70, -57.11, 11.02) — N1 火箭，是另一处坠机道具
  final 中:
    - shuttle 跑到了 (0, 39, 0) —— 我的 pipeline 某步把 rotation 烘进 mesh + reset object origin
    - M_spawn 错放在 N1 火箭旁

修复操作：
  A. 把 R_shuttle 簇平移回 origin 位置 (76.38, -73.57, 7.05)
     delta = origin_center - current_center
     对每个 R_shuttle_NN: location += delta
     这样保留当前 mesh 形状（已烘进的 rotation 形态），只恢复位置
  B. 删错的 C_crashed_rocket_*（N1 火箭不是登陆仓）
     删 C_shuttle_wreck_*（位置错了，下面重生成）
     删现 M_spawn
  C. 从平移回正确位置的 R_shuttle 重新生成:
     - C_crashed_shuttle_NN ← 全部 22 个 R_shuttle parts，decimate 0.3 = 稠密点云源
  D. 重命名 R_truck_rocket 的相关 C_:
     N1 火箭是 "坠毁的飞机" 道具，C_ 命名应含 "wreck" → Structure tag (粒子 ×3)
     原 C_crashed_rocket_* 已删，重生成为 C_wreck_rocket_NN（前面 B 步删了）
  E. M_spawn 放在 CJK hint 位置 (86.82, -66.66, 9.85)
  F. 验证：没有 C_rocks / C_trees / C_grass（应该早就清空，但确认一次）
"""

import bpy, os, mathutils

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC       = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST_BLEND = SRC
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")

# Origin shuttle 簇中心（从 diag_origin.py 测出）
SHUTTLE_ORIGIN_CENTER = mathutils.Vector((76.38, -73.57, 7.05))

# CJK hint 位置（玩家出舱点）
SPAWN_HINT_POS = mathutils.Vector((86.82, -66.66, 9.85))

bpy.ops.wm.open_mainfile(filepath=SRC)

# ============================================================
# A. 把 R_shuttle 簇平移回 origin 位置
# ============================================================
shuttle_objs = [o for o in bpy.data.objects if o.name.startswith("R_shuttle_") and o.type == 'MESH']
print(f"\n[STEP A] R_shuttle 簇平移回 origin 位置")
print(f"  数量: {len(shuttle_objs)}")

# 计算当前簇中心
all_pts = []
for o in shuttle_objs:
    for v in o.bound_box:
        all_pts.append(o.matrix_world @ mathutils.Vector(v))
cur_center = mathutils.Vector((
    sum(p.x for p in all_pts) / len(all_pts),
    sum(p.y for p in all_pts) / len(all_pts),
    sum(p.z for p in all_pts) / len(all_pts),
))
delta = SHUTTLE_ORIGIN_CENTER - cur_center
print(f"  当前中心: ({cur_center.x:.2f}, {cur_center.y:.2f}, {cur_center.z:.2f})")
print(f"  目标中心: ({SHUTTLE_ORIGIN_CENTER.x:.2f}, {SHUTTLE_ORIGIN_CENTER.y:.2f}, {SHUTTLE_ORIGIN_CENTER.z:.2f})")
print(f"  平移 delta: ({delta.x:.2f}, {delta.y:.2f}, {delta.z:.2f})")

# 直接给每个 shuttle 加 delta（修改 location，配合现 parent 不变）
for o in shuttle_objs:
    o.location = (o.location.x + delta.x, o.location.y + delta.y, o.location.z + delta.z)

# ============================================================
# B. 清理错误的 C_crashed_rocket_*, C_shuttle_wreck_*, M_spawn
# ============================================================
print(f"\n[STEP B] 清理错的代理")
to_remove = []
for o in list(bpy.data.objects):
    n = o.name
    if (n.startswith("C_crashed_rocket_") or
        n.startswith("C_shuttle_wreck_") or
        n.startswith("M_spawn") or
        # 也清掉以前的 C_crashed_shuttle_*（如果残留）
        n.startswith("C_crashed_shuttle_")):
        to_remove.append(n)
for n in to_remove:
    obj = bpy.data.objects.get(n)
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)
print(f"  删除 {len(to_remove)} 个错位代理")

# ============================================================
# C. 从已归位 R_shuttle 重新生成 C_crashed_shuttle_NN
# ============================================================
print(f"\n[STEP C] 从归位的 R_shuttle 生成 C_crashed_shuttle_NN")
CRASHED_RATIO = 0.30
shuttle_srcs = [o for o in bpy.data.objects if o.name.startswith("R_shuttle_") and o.type == 'MESH']
crashed_log = []
total_b = total_a = 0
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
    # 解 parent，烘世界变换（src 在 STEP A 已经被平移到正确位置）
    if dup.parent is not None:
        world_m = dup.parent.matrix_world @ dup.matrix_basis
        dup.parent = None
        dup.matrix_basis = world_m
    # decimate
    cur = len(dup.data.polygons)
    if cur > 0:
        bpy.context.view_layer.objects.active = dup
        mod = dup.modifiers.new(name='dec', type='DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = CRASHED_RATIO
        mod.use_collapse_triangulate = True
        try:
            bpy.ops.object.modifier_apply(modifier='dec')
        except Exception as e:
            dup.modifiers.remove(mod)
    new_polys = len(dup.data.polygons)
    crashed_log.append((new_name, cur, new_polys))
    total_b += cur; total_a += new_polys
print(f"  生成 {len(crashed_log)} 个 C_crashed_shuttle_NN")
print(f"  decimate 总计: {total_b} → {total_a} polys")

# ============================================================
# D. 把 N1 火箭的 C_ 重命名为 C_wreck_rocket_*
#    （之前 fix_proxies_v3 生成过 C_crashed_rocket_*，已在 B 步删掉，
#     现在从 R_truck_rocket 重新生成 C_wreck_rocket_*）
# ============================================================
print(f"\n[STEP D] N1 火箭重生成 C_wreck_rocket_NN（Structure tag, 不是 crashed）")
ROCKET_TARGET_TRI = 60
rocket_srcs = [o for o in bpy.data.objects if o.name.startswith("R_truck_rocket_") and o.type == 'MESH']
wreck_log = []
for i, src in enumerate(rocket_srcs, 1):
    dup = src.copy()
    dup.data = src.data.copy()
    bpy.context.collection.objects.link(dup)
    new_name = f"C_wreck_rocket_{i:02d}"
    dup.name = new_name
    dup["original_name"] = f"DERIVED_FROM:{src.name}"
    dup["sonarjam_kind"] = "wreck"
    dup.hide_render = True
    dup.display_type = 'WIRE'
    if dup.parent is not None:
        world_m = dup.parent.matrix_world @ dup.matrix_basis
        dup.parent = None
        dup.matrix_basis = world_m
    cur = len(dup.data.polygons)
    if cur > ROCKET_TARGET_TRI:
        bpy.context.view_layer.objects.active = dup
        ratio = max(0.005, ROCKET_TARGET_TRI / cur)
        mod = dup.modifiers.new(name='dec', type='DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        try:
            bpy.ops.object.modifier_apply(modifier='dec')
        except Exception as e:
            dup.modifiers.remove(mod)
    wreck_log.append((new_name, cur, len(dup.data.polygons)))
print(f"  生成 {len(wreck_log)} 个 C_wreck_rocket_NN")

# ============================================================
# E. M_spawn 放在 CJK hint 位置
# ============================================================
print(f"\n[STEP E] M_spawn at CJK hint")
spawn = bpy.data.objects.new("M_spawn", None)
spawn.location = (SPAWN_HINT_POS.x, SPAWN_HINT_POS.y, SPAWN_HINT_POS.z)
spawn.empty_display_type = 'PLAIN_AXES'
spawn.empty_display_size = 2.0
bpy.context.collection.objects.link(spawn)
print(f"  M_spawn @ Blender XYZ ({SPAWN_HINT_POS.x}, {SPAWN_HINT_POS.y}, {SPAWN_HINT_POS.z})")
print(f"  这是你的 CJK Empty「登陆仓——就是那个crashed」的原始位置")

# ============================================================
# F. 验证无 C_rocks / C_trees / C_grass
# ============================================================
print(f"\n[STEP F] 验证没有 trees/rocks/grass 的 C_ 代理")
bad_C = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("C_") and
         any(k in o.name.lower() for k in ["tree", "rock", "grass"])]
if bad_C:
    print(f"  ⚠ 找到 {len(bad_C)} 个不该有的 C_:")
    for o in bad_C:
        print(f"    - {o.name}")
else:
    print(f"  ✓ 没有 C_trees / C_rocks / C_grass")

# 列所有 C_ 给用户验证
print(f"\n[最终 C_ 清单]")
c_objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("C_")]
c_objs.sort(key=lambda o: o.name)
for o in c_objs:
    polys = len(o.data.polygons)
    print(f"  {o.name:<32s}  {polys:>5d} tris")

# ============================================================
# 保存 + 重导出
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
print(f"\n[FINAL]")
print(f"  C_*crashed*: {len(crashed)} obj, {crashed_tris} tris  →  shuttle 出生云源")
print(f"  M_spawn at: ({SPAWN_HINT_POS.x}, {SPAWN_HINT_POS.y}, {SPAWN_HINT_POS.z})  (CJK hint 原位)")
