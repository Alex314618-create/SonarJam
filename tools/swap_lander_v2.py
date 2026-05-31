"""
swap_lander_v2.py — 更稳的方法：
  1. 打开 mountain_mine，对 rocket/thruster mesh 做 transform_apply（烘世界变换到 mesh data）
  2. 解 parent + 删父链
  3. 保存成干净的 _temp_rocket.blend（每个 mesh 是独立顶点世界对齐）
  4. 打开 mountain_12345，量 Bloc-A.3ds bbox，删 Bloc-A 一切
  5. append 干净 mesh，量当前簇 bbox
  6. 用 Empty pivot 等比缩放 + 平移
  7. 重命名 R_lander，派生 C_crashed_lander
"""
import bpy, bmesh, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC_12345 = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_12345.blend")
SRC_MINE  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_mine.blend")
DST_BLEND = SRC_12345
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_12345.glb")
TEMP      = os.path.join(ROOT, "_temp_Blender", "_rocket_clean.blend")
INFLATE = 0.01


# === STEP 1: 干净抽取 rocket meshes (烘世界变换到 mesh data) ===
bpy.ops.wm.open_mainfile(filepath=SRC_MINE)

# 找带 rocket/thruster material 的 mesh
rocket_names = []
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    for slot in o.material_slots:
        if slot.material and slot.material.name in ('rocket', 'thruster'):
            rocket_names.append(o.name)
            break

print(f"[STEP1] mountain_mine 里 rocket/thruster mesh: {rocket_names}")

# 对每个 mesh: select + apply transform (location, rotation, scale)
# 这把 parent 累积的世界矩阵烘到 vertices，object transform 归零
for name in rocket_names:
    obj = bpy.data.objects[name]
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    # parent_clear 保留世界变换（先解父）
    if obj.parent is not None:
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    # 现在 matrix_world 应该正确反映父链累积
    # apply all transforms (location + rotation + scale) 到 mesh
    try:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    except Exception as e:
        print(f"  [WARN] {name} transform_apply: {e}")

# 删除一切非 mesh / 非保留的对象
for o in list(bpy.data.objects):
    if o.name not in rocket_names:
        bpy.data.objects.remove(o, do_unlink=True)

# 量当前 bbox（现在 matrix_world 应是 identity，bbox 在 world 里）
pts = []
for n in rocket_names:
    obj = bpy.data.objects[n]
    for v in obj.bound_box:
        pts.append(obj.matrix_world @ mathutils.Vector(v))
mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
print(f"  cleaned bbox: center=({(mn.x+mx.x)/2:.2f},{(mn.y+mx.y)/2:.2f},{(mn.z+mx.z)/2:.2f}) size=({mx.x-mn.x:.2f},{mx.y-mn.y:.2f},{mx.z-mn.z:.2f})")

bpy.ops.wm.save_as_mainfile(filepath=TEMP)
print(f"  保存到 {TEMP}")

# === STEP 2a: 从 mountain_final (54321 不动) 读 Bloc-A target bbox ===
SRC_FINAL = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
bpy.ops.wm.open_mainfile(filepath=SRC_FINAL)
shuttle_objs = [o for o in bpy.data.objects if o.name.startswith("R_shuttle_") and o.type == 'MESH']
pts = []
for o in shuttle_objs:
    for v in o.bound_box:
        pts.append(o.matrix_world @ mathutils.Vector(v))
if not pts:
    raise SystemExit("R_shuttle_* 在 mountain_final.blend 里也找不到了！")
target_mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
target_mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
target_center = (target_mn + target_mx) / 2
target_size   = target_mx - target_mn
print(f"\n[STEP2a] (from 54321 mountain_final) Bloc-A bbox: center=({target_center.x:.2f},{target_center.y:.2f},{target_center.z:.2f}) size=({target_size.x:.2f},{target_size.y:.2f},{target_size.z:.2f})")

# === STEP 2b: 打开 12345，清理上次失败遗留 + 删 R_shuttle 残留 ===
bpy.ops.wm.open_mainfile(filepath=SRC_12345)
to_clean = []
for o in list(bpy.data.objects):
    if (o.name.startswith("R_shuttle_") or
        o.name.startswith("R_lander_") or       # 上次失败创建的
        o.name.startswith("C_crashed_shuttle_") or
        o.name.startswith("C_crashed_lander_") or
        o.name == "Bloc-A.3ds.001" or
        o.name == "__pivot__"):
        to_clean.append(o.name)
        bpy.data.objects.remove(o, do_unlink=True)
print(f"[STEP2b] 清理 {len(to_clean)} 个对象（上次失败遗留 + R_shuttle/Bloc-A 残留）")
bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)

# === STEP 3: append rocket from TEMP ===
with bpy.data.libraries.load(TEMP, link=False) as (data_from, data_to):
    data_to.objects = list(data_from.objects)
appended = [o for o in data_to.objects if o is not None]
for o in appended:
    bpy.context.collection.objects.link(o)
mesh_appended = [o for o in appended if o.type == 'MESH']
print(f"\n[STEP3] append {len(mesh_appended)} 个 mesh")

# 量当前簇 bbox
pts = []
for o in mesh_appended:
    for v in o.bound_box:
        pts.append(o.matrix_world @ mathutils.Vector(v))
cur_mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
cur_mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
cur_center = (cur_mn + cur_mx) / 2
cur_size   = cur_mx - cur_mn
print(f"  cur bbox: center=({cur_center.x:.2f},{cur_center.y:.2f},{cur_center.z:.2f}) size=({cur_size.x:.2f},{cur_size.y:.2f},{cur_size.z:.2f})")

# === STEP 4: 等比缩放 + 平移 (root empty pivot) ===
sx = target_size.x / cur_size.x if cur_size.x > 0 else 1.0
sy = target_size.y / cur_size.y if cur_size.y > 0 else 1.0
sz = target_size.z / cur_size.z if cur_size.z > 0 else 1.0
uniform_scale = (sx + sy + sz) / 3.0
print(f"\n[STEP4] scale ratios: x={sx:.3f} y={sy:.3f} z={sz:.3f} → uniform={uniform_scale:.3f}")

# 用 Empty pivot
bpy.ops.object.empty_add(type='PLAIN_AXES', location=tuple(cur_center))
root = bpy.context.object
root.name = "__pivot__"

bpy.ops.object.select_all(action='DESELECT')
for o in mesh_appended:
    o.select_set(True)
bpy.context.view_layer.objects.active = root
bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

root.scale = (uniform_scale, uniform_scale, uniform_scale)
root.location = tuple(target_center)
bpy.context.view_layer.update()

bpy.ops.object.select_all(action='DESELECT')
for o in mesh_appended:
    o.select_set(True)
bpy.context.view_layer.objects.active = mesh_appended[0]
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.data.objects.remove(root, do_unlink=True)

# 验证
pts = []
for o in mesh_appended:
    for v in o.bound_box:
        pts.append(o.matrix_world @ mathutils.Vector(v))
nc = mathutils.Vector((sum(p.x for p in pts)/len(pts), sum(p.y for p in pts)/len(pts), sum(p.z for p in pts)/len(pts)))
nm = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
nx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
print(f"  变换后 bbox: center=({(nm.x+nx.x)/2:.2f},{(nm.y+nx.y)/2:.2f},{(nm.z+nx.z)/2:.2f}) size=({nx.x-nm.x:.2f},{nx.y-nm.y:.2f},{nx.z-nm.z:.2f})")

# === STEP 5: 重命名 R_lander_NN ===
mesh_appended.sort(key=lambda o: -len(o.data.polygons))
for i, o in enumerate(mesh_appended, 1):
    o["original_name"] = o.name
    o.name = f"R_lander_{i:02d}"

# === STEP 6: 派生 C_crashed_lander_NN ===
for i, src in enumerate(mesh_appended, 1):
    dup = src.copy()
    dup.data = src.data.copy()
    bpy.context.collection.objects.link(dup)
    dup.name = f"C_crashed_lander_{i:02d}"
    dup["original_name"] = f"DERIVED_FROM:{src.name}"
    dup.hide_render = True
    dup.display_type = 'WIRE'
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

# 清 TEMP
try:
    os.remove(TEMP)
    bk = TEMP + "1"
    if os.path.exists(bk): os.remove(bk)
except: pass

# === STEP 7: 保存 + 导出 ===
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
print(f"\n[SAVED .blend] {DST_BLEND}")
print(f"[SAVED .glb]   {DST_GLB}  ({sz/1024/1024:.2f} MB)")
