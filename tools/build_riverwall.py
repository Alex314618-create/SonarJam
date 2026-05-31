"""
build_riverwall.py — 在 5.blend 里沿西岸 cull 线建一道垂直墙。

Specs:
  - 沿 X = -59.41 (湖岸 / cull 线)
  - 长 Y = [-110, 45] (覆盖玩家可达地形)
  - 高 Z = [0, 8] (水面 1.27 之上)
  - 厚度 0.3m
  - R_riverwall_structure_01 (人造 → yellow Structure tag)
  - C_riverwall_structure_01 (inflate 1cm → 碰撞 + sonar)
"""
import bpy, bmesh, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC = os.path.join(ROOT, "_temp_Blender", "更新与交付", "5&4.blend")
DST_BLEND = SRC
DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_loop5.glb")

SHORE_X     = -59.41
WALL_THICK  = 0.30
WALL_Y_MIN  = -110.0
WALL_Y_MAX  = 45.0
WALL_Z_MIN  = 0.0
WALL_Z_MAX  = 8.0
INFLATE     = 0.01

bpy.ops.wm.open_mainfile(filepath=SRC)

# 删旧的（如果重复跑）
for n in ("R_riverwall_structure_01", "C_riverwall_structure_01"):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)

# 建 R_ 墙
cx = SHORE_X + WALL_THICK / 2  # 墙体中心略东于岸线，西面正好在 SHORE_X
cy = (WALL_Y_MIN + WALL_Y_MAX) / 2
cz = (WALL_Z_MIN + WALL_Z_MAX) / 2
sx = WALL_THICK / 2
sy = (WALL_Y_MAX - WALL_Y_MIN) / 2
sz = (WALL_Z_MAX - WALL_Z_MIN) / 2

bpy.ops.mesh.primitive_cube_add(size=2, location=(cx, cy, cz))
wall = bpy.context.object
wall.scale = (sx, sy, sz)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
wall.name = "R_riverwall_structure_01"

# 材质：水泥灰 PBR（无贴图，但有颜色 + 粗糙度）
mat = bpy.data.materials.new(name="riverwall_concrete")
mat.use_nodes = True
bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.42, 0.42, 0.43, 1.0)  # 水泥灰
    bsdf.inputs['Roughness'].default_value = 0.85
    bsdf.inputs['Metallic'].default_value = 0.0
wall.data.materials.append(mat)

print(f"[R_] R_riverwall_structure_01")
print(f"   bbox center ≈ ({cx:.2f}, {cy:.2f}, {cz:.2f})")
print(f"   size ≈ ({2*sx:.2f}, {2*sy:.2f}, {2*sz:.2f})")
print(f"   material: 水泥灰 PBR ({tuple(round(v,2) for v in (0.42, 0.42, 0.43, 1.0))})")

# 建 C_ 副本：复制 R_ + 沿法向 +1cm
dup = wall.copy()
dup.data = wall.data.copy()
bpy.context.collection.objects.link(dup)
dup.name = "C_riverwall_structure_01"
dup["original_name"] = "DERIVED_FROM:R_riverwall_structure_01"
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

print(f"[C_] C_riverwall_structure_01 (沿法向 +1cm)")

# 保存 + 导出
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
sz_file = os.path.getsize(DST_GLB)
print(f"\n[SAVED .blend] {DST_BLEND}")
print(f"[SAVED .glb]   {DST_GLB}  ({sz_file/1024/1024:.2f} MB)")
