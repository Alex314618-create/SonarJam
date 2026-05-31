"""把 12345 里 R_lander_NN 绕 X 轴旋转 -90° 让它"躺下"（不再像葱插在地里）"""
import bpy, bmesh, math, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_12345.blend")
DST_BLEND = SRC
DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_12345.glb")

ROT_X_DEG = -90  # 让 Z 长轴 → Y 长轴

bpy.ops.wm.open_mainfile(filepath=SRC)

# 同时旋转 R_lander 和 C_crashed_lander（它们重合）
targets = [o for o in bpy.data.objects
           if o.type == 'MESH'
           and (o.name.startswith("R_lander_") or o.name.startswith("C_crashed_lander_"))]

if not targets:
    raise SystemExit("没找到 R_lander_NN")

# 算簇中心作 pivot
pts = []
for o in targets:
    for v in o.bound_box:
        pts.append(o.matrix_world @ mathutils.Vector(v))
mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
center = (mn + mx) / 2
size = mx - mn
print(f"[BEFORE] {len(targets)} objs, center=({center.x:.2f},{center.y:.2f},{center.z:.2f}) size=({size.x:.2f},{size.y:.2f},{size.z:.2f})")

# 用 Empty pivot at center, parent all → rotate → unparent + bake
bpy.ops.object.empty_add(type='PLAIN_AXES', location=tuple(center))
pivot = bpy.context.object
pivot.name = "__rot_pivot__"

bpy.ops.object.select_all(action='DESELECT')
for o in targets:
    o.select_set(True)
bpy.context.view_layer.objects.active = pivot
bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

pivot.rotation_euler = (math.radians(ROT_X_DEG), 0, 0)
bpy.context.view_layer.update()

bpy.ops.object.select_all(action='DESELECT')
for o in targets:
    o.select_set(True)
bpy.context.view_layer.objects.active = targets[0]
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
bpy.data.objects.remove(pivot, do_unlink=True)

# 验证
pts = []
for o in targets:
    for v in o.bound_box:
        pts.append(o.matrix_world @ mathutils.Vector(v))
mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
nc = (mn + mx) / 2
ns = mx - mn
print(f"[AFTER ] center=({nc.x:.2f},{nc.y:.2f},{nc.z:.2f}) size=({ns.x:.2f},{ns.y:.2f},{ns.z:.2f})")

# 保存 + 导出
bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB, export_format='GLB', export_materials='EXPORT',
    export_image_format='AUTO', export_apply=True, export_lights=False,
    export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"\n[SAVED] {DST_GLB}  ({sz/1024/1024:.2f} MB)")
