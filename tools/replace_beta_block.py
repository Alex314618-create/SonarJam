"""
replace_beta_block.py — 把指定 .blend 里的 R_building_beta 全簇 + 对应 C_，
换成一个实心长方体（同位置，南边内缩 SHRINK_NORTH 米）。

用法:
  blender -b --python replace_beta_block.py -- "2.blend"
"""
import bpy, bmesh, mathutils, os, sys

ROOT = r"C:\Users\ROG\Desktop\GameJam"
argv = sys.argv
sep = argv.index("--") if "--" in argv else -1
script_args = argv[sep+1:] if sep >= 0 else []
BLEND_NAME = script_args[0] if len(script_args) > 0 else "1.blend"

SRC = os.path.join(ROOT, "_temp_Blender", "更新与交付", BLEND_NAME)
basename = os.path.splitext(BLEND_NAME)[0].replace("&", "_")
DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", f"scene_loop{basename}.glb")

SHRINK_NORTH = 3.0   # 南面 +Y 缩 3m
INFLATE = 0.01

print(f"\n=== 处理 {BLEND_NAME} ===")
bpy.ops.wm.open_mainfile(filepath=SRC)

# 收集所有 beta-related 对象
beta_objs = [o for o in bpy.data.objects
             if o.type == 'MESH'
             and (o.name.startswith("R_building_beta_") or
                  o.name.startswith("C_building_beta_"))]
r_beta = [o for o in beta_objs if o.name.startswith("R_")]

if not r_beta:
    raise SystemExit(f"{BLEND_NAME}: 没找到 R_building_beta_*")

# 量原始 bbox（只用 R_）
pts = []
for o in r_beta:
    for v in o.bound_box:
        pts.append(o.matrix_world @ mathutils.Vector(v))
mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
print(f"  R_building_beta_* × {len(r_beta)} 当前 bbox: min={tuple(round(v,2) for v in mn)} max={tuple(round(v,2) for v in mx)}")

# 南面 +Y 缩 SHRINK_NORTH
new_mn = mathutils.Vector((mn.x, mn.y + SHRINK_NORTH, mn.z))
new_mx = mx
new_center = (new_mn + new_mx) / 2
new_size = new_mx - new_mn
print(f"  新长方体: center={tuple(round(v,2) for v in new_center)} size={tuple(round(v,2) for v in new_size)}")
print(f"  (南面 mn.y {mn.y:.2f} → {new_mn.y:.2f}, 净缩 {SHRINK_NORTH}m)")

# 删旧 beta 全簇
n_removed = 0
for o in beta_objs:
    bpy.data.objects.remove(o, do_unlink=True)
    n_removed += 1
print(f"  删 {n_removed} 个旧 R_/C_ building_beta")

# 创建 R_building_beta_block_01 (实心 cuboid)
bpy.ops.mesh.primitive_cube_add(size=2, location=tuple(new_center))
block = bpy.context.object
block.scale = (new_size.x / 2, new_size.y / 2, new_size.z / 2)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
block.name = "R_building_beta_block_01"

# 水泥灰材质
mat = bpy.data.materials.new(name="beta_block_concrete")
mat.use_nodes = True
bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.42, 0.42, 0.43, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    bsdf.inputs['Metallic'].default_value = 0.0
block.data.materials.append(mat)

# C_ 副本：复制 R_ + 沿法向 +1cm
dup = block.copy()
dup.data = block.data.copy()
bpy.context.collection.objects.link(dup)
dup.name = "C_building_beta_block_01"
dup["original_name"] = "DERIVED_FROM:R_building_beta_block_01"
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

print(f"  + R_building_beta_block_01 (R_, 12 tri, 黄色 Structure tag)")
print(f"  + C_building_beta_block_01 (沿法向 +1cm，碰撞 + sonar)")

# 保存 + 导出
bpy.ops.wm.save_as_mainfile(filepath=SRC)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB,
    export_format='GLB', export_materials='EXPORT',
    export_image_format='AUTO', export_apply=True, export_lights=False,
    export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"  [.blend] {SRC}")
print(f"  [.glb]   {DST_GLB}  ({sz/1024/1024:.2f} MB)")
