"""
fix_lander.py — 把登陆仓定位修正到 shuttle 簇。

用户澄清：
  - 登陆仓 = C_shuttle_block_01（虚=R_shuttle 渲染，实=C_shuttle_block_01 碰撞）
  - 我之前误把火箭 (R_truck_rocket) 当登陆仓做了 C_crashed_pod_*，要删掉
  - 登陆仓需要"做旧"——给 R_shuttle 材质加暗色 tint + Roughness 拉到 0.95

操作：
  1. 删除我之前错误创建的 C_crashed_pod_01..08
  2. 删除我之前错误位置的 M_spawn_lander
  3. 删除用户的中文 Empty「登陆仓——就是那个crashed——需要做旧一点。真实的。」
     （CJK 在 glTF JSON 里 mojibake，且其作用已被 M_spawn_lander 替代）
  4. 重命名 C_shuttle_block_01 → C_crashed_shuttle_block_01
     （引擎 content/mod.rs 看到 C_ + name 含 "crashed" → 进 crashed_tris）
  5. 在 C_shuttle_block_01 中心放新 M_spawn_lander
  6. 给 R_shuttle_* 材质做旧：Base Color default 加暗色 tint, Roughness 0.95

源    : mountain_final.blend
输出  : mountain_final.blend（原地覆盖，已是最终态）
重导出: content/levels/earth_return_01/scene.glb
"""

import bpy, os, mathutils

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC       = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST_BLEND = SRC  # 覆盖
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")

LANDER_C_NAME = "C_shuttle_block_01"
SHUTTLE_R_PREFIX = "R_shuttle_"

# 做旧参数
AGED_TINT = (0.55, 0.50, 0.45, 1.0)   # 暖灰色暗化，模拟岁月+灰尘
AGED_ROUGHNESS = 0.95                  # 几乎全漫反射

bpy.ops.wm.open_mainfile(filepath=SRC)

# ============================================================
# 1) 清理：删除错误的 C_crashed_pod / 旧 M_spawn / CJK Empty
# ============================================================
removed = []
for o in list(bpy.data.objects):
    n = o.name
    # 我之前错的 crashed
    if n.startswith("C_crashed_pod_"):
        removed.append(n)
        bpy.data.objects.remove(o, do_unlink=True)
        continue
    # 旧 M_spawn
    if n.startswith("M_spawn"):
        removed.append(n)
        bpy.data.objects.remove(o, do_unlink=True)
        continue
    # 用户的中文 Empty（含"crashed"作 hint）
    if o.type == 'EMPTY' and "crashed" in n.lower() and not n.startswith(("C_", "R_", "P_", "M_")):
        removed.append(f"CJK_EMPTY:{n[:40]}...")
        bpy.data.objects.remove(o, do_unlink=True)
        continue

print(f"[CLEANUP] 删除 {len(removed)} 个废弃对象")
for r in removed:
    print(f"  - {r}")

# ============================================================
# 2) 找登陆仓 C_ 盒，重命名加 crashed 标记
# ============================================================
lander = bpy.data.objects.get(LANDER_C_NAME)
if not lander:
    raise SystemExit(f"没找到 {LANDER_C_NAME}！")

# 算其世界空间中心
bb = [lander.matrix_world @ mathutils.Vector(v) for v in lander.bound_box]
mn = mathutils.Vector((min(p.x for p in bb), min(p.y for p in bb), min(p.z for p in bb)))
mx = mathutils.Vector((max(p.x for p in bb), max(p.y for p in bb), max(p.z for p in bb)))
cx = (mn.x + mx.x) / 2
cy = (mn.y + mx.y) / 2
top_z = mx.z
print(f"\n[LANDER] {LANDER_C_NAME}  bbox center=({cx:.2f}, {cy:.2f})  top_z={top_z:.2f}")

new_lander_name = "C_crashed_shuttle_block_01"
lander.name = new_lander_name
lander["sonarjam_kind"] = "lander_pod"
print(f"  rename: {LANDER_C_NAME} → {new_lander_name}")

# ============================================================
# 3) M_spawn_lander Empty（在登陆仓东南角外侧，避免出生在几何内部）
# ============================================================
spawn_x = mx.x + 1.5   # 登陆仓东侧 1.5m
spawn_y = (mn.y + mx.y) / 2
spawn_z = top_z + 0.5  # 引擎会忽略 Z，重写为 PLAYER_HEIGHT
empty = bpy.data.objects.new("M_spawn_lander", None)
empty.location = (spawn_x, spawn_y, spawn_z)
empty.empty_display_type = 'PLAIN_AXES'
empty.empty_display_size = 2.0
bpy.context.collection.objects.link(empty)
print(f"\n[M_spawn_lander] at Blender XYZ ({spawn_x:.2f}, {spawn_y:.2f}, {spawn_z:.2f})")

# ============================================================
# 4) 做旧：R_shuttle 材质 Base Color tint + Roughness 0.95
# ============================================================
# 收集 R_shuttle 用到的所有材质（去重）
shuttle_mats = set()
for o in bpy.data.objects:
    if not o.name.startswith(SHUTTLE_R_PREFIX): continue
    if o.type != 'MESH': continue
    for slot in o.material_slots:
        if slot.material:
            shuttle_mats.add(slot.material)

print(f"\n[AGED] 对 {len(shuttle_mats)} 个 shuttle 材质做旧")
print(f"  tint={AGED_TINT}  roughness={AGED_ROUGHNESS}")
aged_log = []
for mat in shuttle_mats:
    if not mat.use_nodes:
        aged_log.append((mat.name, "skipped (no nodes)"))
        continue
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        aged_log.append((mat.name, "skipped (no BSDF)"))
        continue
    # Base Color default_value 作为 glTF baseColorFactor（多乘以贴图）
    bsdf.inputs['Base Color'].default_value = AGED_TINT
    # Roughness
    bsdf.inputs['Roughness'].default_value = AGED_ROUGHNESS
    # Metallic 拉低（飞船本来可能金属感强，做旧后氧化粗糙）
    bsdf.inputs['Metallic'].default_value = 0.0
    aged_log.append((mat.name, "tinted + roughened"))

for m, s in aged_log[:5]:
    print(f"  {m}: {s}")
if len(aged_log) > 5:
    print(f"  ... +{len(aged_log)-5} more")

# ============================================================
# 5) 保存 + 重导出
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
crashed_n = sum(1 for o in meshes if o.name.startswith("C_") and "crashed" in o.name.lower())
crashed_tris = sum(len(o.data.polygons) for o in meshes if o.name.startswith("C_") and "crashed" in o.name.lower())
spawn_n = sum(1 for o in bpy.data.objects if o.name.startswith("M_spawn"))
total = sum(len(o.data.polygons) for o in meshes)
print(f"\n[FINAL]")
print(f"  total meshes: {len(meshes)}, total polys: {total}")
print(f"  C_*crashed*: {crashed_n} 对象, {crashed_tris} triangles  →  采样点云源")
print(f"  M_spawn_*:   {spawn_n} 对象")
