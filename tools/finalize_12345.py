"""
finalize_12345.py — 最终修复 12345：
  Phase 1: 登陆仓 = 真 n1_rocket_block_a.original.glb，保留 native silver+red materials
  Phase 2: trees/rocks/grass bisect x=-59.4 west 侧清掉（地图已裁剪过）
"""
import bpy, bmesh, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC_12345 = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_12345.blend")
SRC_FINAL = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
N1_GLB    = os.path.join(ROOT, "_temp_Blender", "maps_54321", "n1_rocket_block_a.original.glb")
DST_BLEND = SRC_12345
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_12345.glb")

CULL_X = -59.4
INFLATE = 0.01

# === STEP A: 从 54321 (mountain_final) 读 R_shuttle target bbox ===
bpy.ops.wm.open_mainfile(filepath=SRC_FINAL)
shuttle_objs = [o for o in bpy.data.objects if o.name.startswith("R_shuttle_") and o.type == 'MESH']
pts = []
for o in shuttle_objs:
    for v in o.bound_box:
        pts.append(o.matrix_world @ mathutils.Vector(v))
target_mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
target_mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
target_center = (target_mn + target_mx) / 2
target_size   = target_mx - target_mn
print(f"[A] 54321 里 R_shuttle (target) bbox:")
print(f"   center=({target_center.x:.2f},{target_center.y:.2f},{target_center.z:.2f})")
print(f"   size=({target_size.x:.2f},{target_size.y:.2f},{target_size.z:.2f})")

# === STEP B: 打开 12345，删现有 R_lander_NN + C_crashed_lander_NN ===
bpy.ops.wm.open_mainfile(filepath=SRC_12345)
cleanup = []
for o in list(bpy.data.objects):
    if (o.name.startswith("R_lander_") or
        o.name.startswith("C_crashed_lander_")):
        cleanup.append(o.name)
        bpy.data.objects.remove(o, do_unlink=True)
print(f"\n[B] 清理 {len(cleanup)} 个错的 R_lander/C_crashed_lander")

# === STEP C: 导入 n1_rocket_block_a.original.glb ===
# 记录导入前对象列表
before_set = set(o.name for o in bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=N1_GLB)
after_set = set(o.name for o in bpy.data.objects)
imported_names = after_set - before_set
print(f"\n[C] 导入 n1_rocket_block_a 共 {len(imported_names)} 个对象")

imported_objs = [bpy.data.objects[n] for n in imported_names]
imported_meshes = [o for o in imported_objs if o.type == 'MESH']

# 量当前 bbox (native n1)
pts = []
for o in imported_meshes:
    for v in o.bound_box:
        pts.append(o.matrix_world @ mathutils.Vector(v))
cur_mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
cur_mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
cur_center = (cur_mn + cur_mx) / 2
cur_size   = cur_mx - cur_mn
print(f"  native bbox: center=({cur_center.x:.2f},{cur_center.y:.2f},{cur_center.z:.2f}) size=({cur_size.x:.2f},{cur_size.y:.2f},{cur_size.z:.2f})")

# === STEP D: 等比缩放 + 平移到 target bbox ===
sx = target_size.x / cur_size.x if cur_size.x > 0 else 1
sy = target_size.y / cur_size.y if cur_size.y > 0 else 1
sz = target_size.z / cur_size.z if cur_size.z > 0 else 1
uniform_scale = (sx + sy + sz) / 3.0
print(f"\n[D] scale ratios: x={sx:.3f} y={sy:.3f} z={sz:.3f} → uniform={uniform_scale:.3f}")

# 用 Empty pivot at native center
bpy.ops.object.empty_add(type='PLAIN_AXES', location=tuple(cur_center))
root = bpy.context.object
root.name = "__pivot__"

bpy.ops.object.select_all(action='DESELECT')
for o in imported_objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = root
bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

root.scale = (uniform_scale, uniform_scale, uniform_scale)
root.location = tuple(target_center)
bpy.context.view_layer.update()

# 解 parent (keep transform) + apply scale
bpy.ops.object.select_all(action='DESELECT')
for o in imported_meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = imported_meshes[0]
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# 删 root + 其他非 mesh imported（如父 Bloc-A.3ds empty）
bpy.data.objects.remove(root, do_unlink=True)
for o in list(imported_objs):
    if o.type != 'MESH' and o.name in bpy.data.objects:
        bpy.data.objects.remove(o, do_unlink=True)

# 验证
pts = []
for o in imported_meshes:
    for v in o.bound_box:
        pts.append(o.matrix_world @ mathutils.Vector(v))
new_mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
new_mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
nc = (new_mn + new_mx) / 2
ns = new_mx - new_mn
print(f"  变换后 bbox: center=({nc.x:.2f},{nc.y:.2f},{nc.z:.2f}) size=({ns.x:.2f},{ns.y:.2f},{ns.z:.2f})")
print(f"  目标 bbox:    center=({target_center.x:.2f},{target_center.y:.2f},{target_center.z:.2f}) size=({target_size.x:.2f},{target_size.y:.2f},{target_size.z:.2f})")

# === STEP E: 重命名 R_lander_NN ===
imported_meshes.sort(key=lambda o: -len(o.data.polygons))
for i, o in enumerate(imported_meshes, 1):
    o["original_name"] = o.name
    o.name = f"R_lander_{i:02d}"

# === STEP F: 派生 C_crashed_lander_NN ===
for i, src in enumerate(imported_meshes, 1):
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

print(f"\n[E,F] R_lander × {len(imported_meshes)} + C_crashed_lander × {len(imported_meshes)} 就绪（native 材质保留）")

# === STEP G: bisect trees/rocks/grass at x=-59.4 (cull west) ===
print(f"\n[G] bisect R_trees/rocks/grass at x={CULL_X}")
plane_co = mathutils.Vector((CULL_X, 0, 0))
plane_no = mathutils.Vector((1, 0, 0))

nature_objs = [o for o in bpy.data.objects
               if o.type == 'MESH'
               and any(o.name.startswith(p) for p in ("R_trees_", "R_rocks_", "R_grass_"))]

bisected = []
deleted_full = []
for obj in nature_objs:
    mw_inv = obj.matrix_world.inverted()
    local_co = mw_inv @ plane_co
    local_no = obj.matrix_world.to_quaternion().inverted() @ plane_no
    local_no.normalize()

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    before_v = len(bm.verts)
    if before_v == 0:
        bm.free()
        continue
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    try:
        bmesh.ops.bisect_plane(
            bm, geom=geom, dist=0.0001,
            plane_co=local_co, plane_no=local_no,
            clear_inner=True, clear_outer=False,
        )
    except Exception as e:
        bm.free()
        print(f"  [WARN] {obj.name}: {e}")
        continue
    # 简单封盖
    EPS = 0.005
    cut_plane_edges = [e for e in bm.edges if e.is_valid
                       and abs((e.verts[0].co - local_co).dot(local_no)) < EPS
                       and abs((e.verts[1].co - local_co).dot(local_no)) < EPS]
    if cut_plane_edges:
        try:
            bmesh.ops.holes_fill(bm, edges=cut_plane_edges, sides=0)
            still = [e for e in cut_plane_edges if e.is_valid and len(e.link_faces) < 2]
            if still:
                bmesh.ops.edgenet_fill(bm, edges=still, mat_nr=0, use_smooth=False, sides=0)
        except: pass
    after_v = len(bm.verts)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    if after_v == 0:
        deleted_full.append(obj.name)
    elif after_v < before_v:
        bisected.append((obj.name, before_v, after_v))

# 删空对象
for n in deleted_full:
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)

print(f"  全删: {len(deleted_full)}, 部分裁剪: {len(bisected)}")
for n in deleted_full:
    print(f"    fully deleted: {n}")
for n, b, a in bisected:
    pct = (1 - a/b) * 100
    print(f"    bisected {n}: {b} → {a} verts (-{pct:.0f}%)")

# === STEP H: 保存 + 导出 ===
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

# 终态
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
print(f"\n[FINAL] {len(meshes)} meshes")
from collections import Counter
cnt = Counter()
for o in meshes:
    cat = "_".join(o.name.split("_")[:2]) if "_" in o.name else o.name
    cnt[cat] += 1
for k, v in sorted(cnt.items()):
    print(f"  {k}: {v}")
