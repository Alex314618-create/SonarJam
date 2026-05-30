"""直接导出，不动 mesh"""
import bpy, os
ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")
bpy.ops.wm.open_mainfile(filepath=SRC)
bpy.ops.export_scene.gltf(
    filepath=DST,
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
sz = os.path.getsize(DST)
print(f"[EXPORTED] {DST}  ({sz/1024/1024:.2f} MB)")
