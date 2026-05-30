"""
fix_spawn_and_bones.py — 处理两个明确问题：

# 1. 精确出生点 (来自用户的 DEV 模式数据)
    用户给定 glTF Y-up 坐标:  X=+67.54, Y=+12.17, Z=+64.19, yaw=118°
    Blender Z-up 转换:
      Blender X = glTF X       =  67.54
      Blender Y = -glTF Z      = -64.19
      Blender Z =  glTF Y      =  12.17
    Blender empty rotation_euler.z = -yaw 弧度（因 Blender Y→-glTF Z 的轴翻转）
      to make engine read yaw=+118°, set Blender rot_z = -118°
    引擎已修改可读 spawn_yaw（src/content/mod.rs + world + player + game）

# 2. 骨头 C_ 大三角无像素
    现在的 C_corpse_bones_NN 是 R_bones_skeleton_NN 重度 decimate 到 ~50 tri 的结果——
    Decimate Collapse 会产出 sliver/翻面三角，sonar backface 命中失败 → 大面积空洞。
    解：用 icosphere primitive (subdivisions=1, 20 tri) 替代，按每个骨头的 bbox 缩放贴合。
    干净拓扑、所有法向朝外、无 sliver。
"""

import bpy, mathutils, math, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC       = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST_BLEND = SRC
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")

# 用户给定 (glTF Y-up)
SPAWN_GLTF = (67.54, 12.17, 64.19)
SPAWN_YAW_DEG = 118

INFLATE = 0.01

bpy.ops.wm.open_mainfile(filepath=SRC)

# ============================================================
# 1. 修 M_spawn
# ============================================================
# glTF → Blender 轴转换
spawn_blender = (SPAWN_GLTF[0], -SPAWN_GLTF[2], SPAWN_GLTF[1])

# 删任何旧的 M_spawn*
for o in list(bpy.data.objects):
    if o.name.startswith("M_spawn"):
        bpy.data.objects.remove(o, do_unlink=True)

spawn = bpy.data.objects.new("M_spawn", None)
spawn.location = spawn_blender
# Blender 的 Z-rotation = -engine_yaw（因 export Y→-Z 轴翻转）
spawn.rotation_euler = (0.0, 0.0, math.radians(-SPAWN_YAW_DEG))
spawn.empty_display_type = 'ARROWS'  # 显示三向箭头，方便验证朝向
spawn.empty_display_size = 3.0
bpy.context.collection.objects.link(spawn)
print(f"[M_spawn]")
print(f"  glTF target: X={SPAWN_GLTF[0]}, Y={SPAWN_GLTF[1]}, Z={SPAWN_GLTF[2]}, yaw={SPAWN_YAW_DEG}°")
print(f"  Blender XYZ: ({spawn_blender[0]:.2f}, {spawn_blender[1]:.2f}, {spawn_blender[2]:.2f})")
print(f"  Blender rot_z: -{SPAWN_YAW_DEG}° = {math.radians(-SPAWN_YAW_DEG):.4f} rad")

# ============================================================
# 2. 重做骨头 C_ — 干净 icosphere 替代 decimate 残骸
# ============================================================
# 删现有 C_corpse_bones_*
for o in list(bpy.data.objects):
    if o.name.startswith("C_corpse_bones_"):
        bpy.data.objects.remove(o, do_unlink=True)

# 用 R_bones_skeleton_NN 的世界 bbox 重建
bone_srcs = [o for o in bpy.data.objects if o.name.startswith("R_bones_skeleton_") and o.type == 'MESH']
print(f"\n[C_corpse_bones] 从 {len(bone_srcs)} 个 R_bones_skeleton_NN 重建 icosphere primitive")

for i, src in enumerate(bone_srcs, 1):
    # 计算世界 bbox
    bb = [src.matrix_world @ mathutils.Vector(v) for v in src.bound_box]
    mn = mathutils.Vector((min(p.x for p in bb), min(p.y for p in bb), min(p.z for p in bb)))
    mx = mathutils.Vector((max(p.x for p in bb), max(p.y for p in bb), max(p.z for p in bb)))
    cx = (mn.x + mx.x) / 2; cy = (mn.y + mx.y) / 2; cz = (mn.z + mx.z) / 2
    rx = max((mx.x - mn.x) / 2, 0.3)
    ry = max((mx.y - mn.y) / 2, 0.3)
    rz = max((mx.z - mn.z) / 2, 0.3)

    # 创建 icosphere subdivisions=1 → 20 tri，干净拓扑
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=1, radius=1.0, location=(cx, cy, cz)
    )
    obj = bpy.context.object
    # 缩放贴合 bbox
    obj.scale = (rx, ry, rz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    obj.name = f"C_corpse_bones_{i:02d}"
    obj["original_name"] = f"PRIMITIVE_FROM:{src.name}"
    obj["sonarjam_kind"] = "corpse_primitive"
    obj.hide_render = True
    obj.display_type = 'WIRE'

    # 沿法向膨胀 1cm（与其他 C_ 一致）
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    for v in bm.verts:
        v.co = v.co + v.normal * INFLATE
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    polys = len(obj.data.polygons)
    print(f"  {obj.name}: icosphere radii ({rx:.2f},{ry:.2f},{rz:.2f}), {polys} tri  (来源 {src.name})")

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
