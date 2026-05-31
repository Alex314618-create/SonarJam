"""设置 M_spawn 位置 + yaw"""
import bpy, math, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST_BLEND = SRC
DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")

# glTF Y-up coords (用户在 DEV HUD 里看到的值)
GX, GY, GZ = 81.39, 6.23, 70.16
YAW_DEG = 44

# glTF → Blender 轴转换
BX, BY, BZ = GX, -GZ, GY

bpy.ops.wm.open_mainfile(filepath=SRC)

# 删旧 M_spawn*
for o in list(bpy.data.objects):
    if o.name.startswith("M_spawn"):
        bpy.data.objects.remove(o, do_unlink=True)

spawn = bpy.data.objects.new("M_spawn", None)
spawn.location = (BX, BY, BZ)
spawn.rotation_euler = (0.0, 0.0, math.radians(-YAW_DEG))
spawn.empty_display_type = 'ARROWS'
spawn.empty_display_size = 3.0
bpy.context.collection.objects.link(spawn)

print(f"[M_spawn] glTF=({GX},{GY},{GZ}) yaw={YAW_DEG}°")
print(f"  Blender XYZ=({BX:.2f},{BY:.2f},{BZ:.2f}) rot_z={-YAW_DEG}°")

bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB, export_format='GLB', export_materials='EXPORT',
    export_image_format='AUTO', export_apply=True, export_lights=False,
    export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"[SAVED] {DST_GLB} ({sz/1024/1024:.2f} MB)")
