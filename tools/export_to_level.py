"""把 mountain_further.blend 导成 content/levels/earth_return_01/scene.glb"""
import bpy, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_further.blend")
DST = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")

bpy.ops.wm.open_mainfile(filepath=SRC)

# 架构师指定的导出参数
bpy.ops.export_scene.gltf(
    filepath=DST,
    export_format='GLB',                # Format: glTF Binary
    export_materials='EXPORT',          # Materials: Export
    export_image_format='AUTO',         # Images: Automatic（嵌入 GLB）
    export_apply=True,                  # Apply Modifiers: ✓
    export_lights=False,                # Punctual Lights: ✗
    export_yup=True,                    # glTF 标准 +Y up
    export_extras=True,                 # 带上 custom properties（original_name / sonarjam_kind）
    use_visible=False,                  # 不限可见性，hide_render 的 C_/M_ 也导出
    use_renderable=False,               # 同上
)

# 报告
sz = os.path.getsize(DST)
print(f"\n[EXPORTED] {DST}")
print(f"  size: {sz} bytes ({sz/1024/1024:.2f} MB)")

# 统计场景内容
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
total_polys = sum(len(o.data.polygons) for o in meshes)
r = sum(1 for o in meshes if o.name.startswith("R_"))
c = sum(1 for o in meshes if o.name.startswith("C_"))
m = sum(1 for o in meshes if o.name.startswith("M_"))
print(f"  meshes: {len(meshes)} (R_={r}, C_={c}, M_={m})")
print(f"  polys: {total_polys}")
