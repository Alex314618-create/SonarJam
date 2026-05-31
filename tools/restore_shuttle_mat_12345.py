"""把 12345 里 shuttle 的 Base Color tint 还原成白色（贴图原色），去掉末日做旧。"""
import bpy, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_12345.blend")
DST_BLEND = SRC
DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_12345.glb")

bpy.ops.wm.open_mainfile(filepath=SRC)

# 收集 R_shuttle 用到的材质
shuttle_mats = set()
for o in bpy.data.objects:
    if not o.name.startswith("R_shuttle_") or o.type != 'MESH': continue
    for slot in o.material_slots:
        if slot.material:
            shuttle_mats.add(slot.material)

print(f"[RESTORE] 还原 {len(shuttle_mats)} 个 shuttle 材质")
for mat in shuttle_mats:
    if not mat.use_nodes: continue
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf: continue
    # 还原 Base Color tint = 白色（不再压暗）→ glTF baseColorFactor=(1,1,1,1) → 贴图原色
    bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    # 还原合理 Roughness（非全漫反射）
    bsdf.inputs['Roughness'].default_value = 0.5
    # Metallic 留 0 (shuttle 烘焙 atlas 自带金属感，不需再加)
    print(f"  {mat.name}")

bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB, export_format='GLB', export_materials='EXPORT',
    export_image_format='AUTO', export_apply=True, export_lights=False,
    export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"\n[SAVED] {DST_GLB}  ({sz/1024/1024:.2f} MB)")
