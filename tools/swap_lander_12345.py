"""
swap_lander_12345.py — 仅在 12345 文件里把 Bloc-A.3ds 那 22 个无贴图垃圾替换成带贴图的真 N1 rocket。
位置 + 尺寸保持 = Bloc-A 当前的 bbox。
54321 (mountain_final.blend) 不动。

步骤：
  A. 打开 mountain_12345，量 Bloc-A 簇当前 bbox (center, size) — 这是目标
  B. 删掉 R_shuttle_* + 父 Bloc-A.3ds.001 + C_crashed_shuttle_*
  C. 暂存 12345 当前状态
  D. 从 mountain_mine 拔出 rocket/thruster mesh（带贴图）+ 它们的父
  E. append 进 12345
  F. 解 parent → 用 Empty pivot 等比 scale + 移动 → apply transform → 删 Empty
  G. 重命名 R_lander_NN
  H. 派生 C_crashed_lander_NN (dup + inflate 1cm)
  I. 保存 + 导出
"""

import bpy, bmesh, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC_12345 = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_12345.blend")
SRC_MINE  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_mine.blend")
DST_BLEND = SRC_12345
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_12345.glb")
TEMP      = os.path.join(ROOT, "_temp_Blender", "_n1rocket_pluck.blend")

INFLATE = 0.01

# === A. 量 Bloc-A 当前 bbox ===
bpy.ops.wm.open_mainfile(filepath=SRC_12345)
shuttle_objs = [o for o in bpy.data.objects if o.name.startswith("R_shuttle_") and o.type == 'MESH']
pts = []
for o in shuttle_objs:
    for v in o.bound_box:
        pts.append(o.matrix_world @ mathutils.Vector(v))
target_mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
target_mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
target_center = (target_mn + target_mx) / 2
target_size   = target_mx - target_mn
print(f"\n[A] Bloc-A.3ds bbox in 12345:")
print(f"   center=({target_center.x:.2f}, {target_center.y:.2f}, {target_center.z:.2f})")
print(f"   size=({target_size.x:.2f}, {target_size.y:.2f}, {target_size.z:.2f})")

# === B. 删 Bloc-A.3ds 一切 ===
removed = []
for o in shuttle_objs:
    removed.append(o.name)
    bpy.data.objects.remove(o, do_unlink=True)
for o in list(bpy.data.objects):
    if o.name.startswith("C_crashed_shuttle_"):
        removed.append(o.name)
        bpy.data.objects.remove(o, do_unlink=True)
p = bpy.data.objects.get("Bloc-A.3ds.001")
if p:
    removed.append(p.name)
    bpy.data.objects.remove(p, do_unlink=True)
print(f"[B] 删 {len(removed)} 个对象 (R_shuttle / C_crashed_shuttle / Bloc-A.3ds.001)")

# === C. 暂存 12345 当前状态 ===
bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)

# === D. 从 mountain_mine 拔出真 N1 rocket 到 TEMP ===
bpy.ops.wm.open_mainfile(filepath=SRC_MINE)
keep = set()
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    for slot in o.material_slots:
        if slot.material and slot.material.name in ('rocket', 'thruster'):
            keep.add(o.name)
            # 保留父链
            p = o.parent
            while p is not None:
                keep.add(p.name)
                p = p.parent
            break
print(f"[D] N1 rocket 集合（含父）：{sorted(keep)}")
for o in list(bpy.data.objects):
    if o.name not in keep:
        bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=TEMP)

# === E. append 进 12345 ===
bpy.ops.wm.open_mainfile(filepath=DST_BLEND)
with bpy.data.libraries.load(TEMP, link=False) as (data_from, data_to):
    data_to.objects = list(data_from.objects)
appended = [o for o in data_to.objects if o is not None]
for o in appended:
    bpy.context.collection.objects.link(o)
mesh_appended = [o for o in appended if o.type == 'MESH']
print(f"[E] append {len(appended)} 个 ({len(mesh_appended)} 是 mesh)")

# === F. 用 Empty pivot 等比缩放 + 移动 ===
# 量当前簇 bbox
pts = []
for o in mesh_appended:
    for v in o.bound_box:
        pts.append(o.matrix_world @ mathutils.Vector(v))
cur_mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
cur_mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
cur_center = (cur_mn + cur_mx) / 2
cur_size   = cur_mx - cur_mn
print(f"[F1] N1 rocket 当前 bbox:")
print(f"   center=({cur_center.x:.2f}, {cur_center.y:.2f}, {cur_center.z:.2f})")
print(f"   size=({cur_size.x:.2f}, {cur_size.y:.2f}, {cur_size.z:.2f})")

# 等比缩放 = 三轴 ratio 平均（保持比例）
sx = target_size.x / cur_size.x if cur_size.x > 0 else 1.0
sy = target_size.y / cur_size.y if cur_size.y > 0 else 1.0
sz = target_size.z / cur_size.z if cur_size.z > 0 else 1.0
uniform_scale = (sx + sy + sz) / 3.0
print(f"[F2] scale ratios: x={sx:.3f}, y={sy:.3f}, z={sz:.3f}  → uniform={uniform_scale:.3f}")

# 先解 parent (keep transform)
for o in appended:
    if o.parent is not None and o.parent not in appended:
        # parent 已不在场景，自然解
        continue
# 处理每个对象的 parent
for o in list(appended):
    if o.parent is not None:
        wm = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = wm

# 把 mesh objects 都 parent 到一个 Empty pivot 上，操作 Empty 来缩放/移动
bpy.ops.object.empty_add(type='PLAIN_AXES', location=tuple(cur_center))
root = bpy.context.object
root.name = "__pivot__"

bpy.ops.object.select_all(action='DESELECT')
for o in mesh_appended:
    o.select_set(True)
bpy.context.view_layer.objects.active = root
bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

# 设 root 的 scale 和 location
root.scale = (uniform_scale, uniform_scale, uniform_scale)
root.location = tuple(target_center)
bpy.context.view_layer.update()

# 解 parent 保留世界变换
bpy.ops.object.select_all(action='DESELECT')
for o in mesh_appended:
    o.select_set(True)
bpy.context.view_layer.objects.active = mesh_appended[0]
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

# 应用 scale 到 mesh data
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# 删 root pivot
bpy.data.objects.remove(root, do_unlink=True)

# 删多余的非 mesh appended（empties 如 Cube.009-016）
for o in list(appended):
    if o.type != 'MESH' and o.name in bpy.data.objects:
        bpy.data.objects.remove(o, do_unlink=True)

# 验证
pts = []
for o in mesh_appended:
    for v in o.bound_box:
        pts.append(o.matrix_world @ mathutils.Vector(v))
new_mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
new_mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
new_center = (new_mn + new_mx) / 2
new_size   = new_mx - new_mn
print(f"[F3] N1 rocket 变换后 bbox:")
print(f"   center=({new_center.x:.2f}, {new_center.y:.2f}, {new_center.z:.2f})  (目标 {target_center.x:.2f},{target_center.y:.2f},{target_center.z:.2f})")
print(f"   size=({new_size.x:.2f}, {new_size.y:.2f}, {new_size.z:.2f})  (目标 {target_size.x:.2f},{target_size.y:.2f},{target_size.z:.2f})")

# === G. 重命名为 R_lander_NN ===
mesh_appended.sort(key=lambda o: -len(o.data.polygons))
for i, o in enumerate(mesh_appended, 1):
    old = o.name
    o.name = f"R_lander_{i:02d}"
    o["original_name"] = old

# === H. 派生 C_crashed_lander_NN ===
crashed_count = 0
for i, src in enumerate(mesh_appended, 1):
    dup = src.copy()
    dup.data = src.data.copy()
    bpy.context.collection.objects.link(dup)
    dup.name = f"C_crashed_lander_{i:02d}"
    dup["original_name"] = f"DERIVED_FROM:{src.name}"
    dup.hide_render = True
    dup.display_type = 'WIRE'
    # inflate 1cm
    bm = bmesh.new()
    bm.from_mesh(dup.data)
    if len(bm.faces) > 0:
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.normal_update()
    for v in bm.verts:
        v.co = v.co + v.normal * INFLATE
    bm.to_mesh(dup.data)
    bm.free()
    dup.data.update()
    crashed_count += 1
print(f"[H] 派生 {crashed_count} 个 C_crashed_lander_NN")

# === 清 TEMP ===
try:
    os.remove(TEMP)
    bk = TEMP + "1"
    if os.path.exists(bk): os.remove(bk)
except: pass

# === I. 保存 + 导出 ===
bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
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
print(f"\n[I] [.blend] {DST_BLEND}")
print(f"   [.glb]  {DST_GLB}  ({sz/1024/1024:.2f} MB)")

# 终态
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
print(f"\n[FINAL] total meshes: {len(meshes)}")
from collections import Counter
kinds = Counter()
for o in meshes:
    if o.name.startswith("R_"):
        cat = o.name.split("_")[1] if "_" in o.name else "?"
        kinds[f"R_{cat}"] += 1
    elif o.name.startswith("C_"):
        cat = o.name.split("_")[1] if "_" in o.name else "?"
        kinds[f"C_{cat}"] += 1
for k, v in sorted(kinds.items()):
    print(f"  {k}: {v}")
