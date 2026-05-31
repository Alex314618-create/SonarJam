"""
build_12345.py — 生成 12345（现实世界）GLB。

12345 = 现实世界 / 自然 → 有 树 / 石 / 草 / 水 / 雪 / 蓝天
共有 = lander (shuttle) / ruins / boats
没有 = 末日建筑 / 信号塔 / 卡车残骸 / 破车 / 骨头

源:
  - mountain_final.blend  (54321 末日版，作基础。保留坐标/lander/ruins/boats/terrain/water/snow/M_spawn)
  - mountain_mine.blend   (原始版，提供 R_trees/rocks/grass)

操作:
  1. 打开 mountain_final → 删末日 R_/C_ (building/antenna/truck/wagon/bones)
  2. 从 mountain_mine 提取 R_trees/rocks/grass → 暂存
  3. 把暂存 append 回 mountain_final 的剩余里
  4. 保存 mountain_12345.blend + 导出 scene_12345.glb
"""

import bpy, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC_FINAL = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
SRC_MINE  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_mine.blend")
DST_BLEND = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_12345.blend")
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_12345.glb")
TEMP_TRG  = os.path.join(ROOT, "_temp_Blender", "_trg_pluck.blend")

KEEP_FROM_MINE = ("R_trees_", "R_rocks_", "R_grass_")

DELETE_FROM_FINAL = (
    "R_building_alpha_", "R_building_beta_",
    "R_antenna_",
    "R_truck_rocket_", "R_truck_debris_",
    "R_wagon_",
    "R_bones_skeleton_",
    "C_building_alpha_", "C_building_beta_",
    "C_antenna_structure_",
    "C_wreck_rocket_", "C_wreck_debris_", "C_wreck_wagon_",
    "C_corpse_bones_",
)

# Step 1: 从 mountain_mine 拔出 R_trees/rocks/grass 暂存到 TEMP_TRG
print(f"\n[STEP 1] 从 mountain_mine 提取 trees/rocks/grass")
bpy.ops.wm.open_mainfile(filepath=SRC_MINE)
to_keep_names = [o.name for o in bpy.data.objects
                  if o.type == 'MESH'
                  and any(o.name.startswith(p) for p in KEEP_FROM_MINE)]
print(f"  找到 {len(to_keep_names)} 个: {[n for n in to_keep_names]}")
# 删除其他所有对象，只留我们要的
for o in list(bpy.data.objects):
    if o.name not in to_keep_names:
        bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=TEMP_TRG)
print(f"  暂存到 {TEMP_TRG}")

# Step 2: 打开 mountain_final，删末日物
print(f"\n[STEP 2] 打开 mountain_final，删除末日物件")
bpy.ops.wm.open_mainfile(filepath=SRC_FINAL)
deleted_log = []
for o in list(bpy.data.objects):
    if o.type == 'MESH' and any(o.name.startswith(p) for p in DELETE_FROM_FINAL):
        deleted_log.append(o.name)
        bpy.data.objects.remove(o, do_unlink=True)
from collections import Counter
cnt = Counter()
for n in deleted_log:
    cnt[n.split('_', 2)[1] if '_' in n else n] += 1
print(f"  删 {len(deleted_log)} 个末日物件:")
for k, v in sorted(cnt.items()):
    print(f"    {k}: {v}")

# Step 3: append 暂存的 trees/rocks/grass
print(f"\n[STEP 3] append 暂存的 trees/rocks/grass")
with bpy.data.libraries.load(TEMP_TRG, link=False) as (data_from, data_to):
    data_to.objects = list(data_from.objects)
appended = 0
for o in data_to.objects:
    if o is not None:
        bpy.context.collection.objects.link(o)
        appended += 1
print(f"  appended {appended} 个 R_trees/rocks/grass")

# 清理 TEMP_TRG
try:
    os.remove(TEMP_TRG)
    bk = TEMP_TRG + "1"
    if os.path.exists(bk): os.remove(bk)
except: pass

# Step 4: 保存 + 导出
print(f"\n[STEP 4] 保存 + 导出")
bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
print(f"  [.blend] {DST_BLEND}")

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
print(f"  [.glb]  {DST_GLB}  ({sz/1024/1024:.2f} MB)")

# 总结
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
total_polys = sum(len(o.data.polygons) for o in meshes)
r_count = sum(1 for o in meshes if o.name.startswith("R_"))
c_count = sum(1 for o in meshes if o.name.startswith("C_"))
m_count = sum(1 for o in bpy.data.objects if o.name.startswith("M_"))

# 按 R_ 类型列出
r_kinds = Counter()
for o in meshes:
    if o.name.startswith("R_"):
        cat = o.name.split("_")[1] if "_" in o.name else "?"
        r_kinds[cat] += 1

print(f"\n[FINAL 12345]")
print(f"  meshes: {len(meshes)} (R_={r_count}, C_={c_count}, M_={m_count})")
print(f"  polys: {total_polys}")
print(f"  R_ 类别:")
for k, v in sorted(r_kinds.items()):
    print(f"    R_{k}: {v}")
