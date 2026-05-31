"""把 1/2.blend 的 R_building_beta_block_01 + C_ 南面退到 Y=-70，让南墙边出 5m 通道。"""
import bpy, bmesh, mathutils, os, sys

ROOT = r"C:\Users\ROG\Desktop\GameJam"

argv = sys.argv
sep = argv.index("--") if "--" in argv else -1
BLEND = argv[sep+1] if sep >= 0 else "1.blend"

SRC = os.path.join(ROOT, "_temp_Blender", "更新与交付", BLEND)
basename = os.path.splitext(BLEND)[0].replace("&", "_")
if BLEND == "1.blend":
    DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_loop5.glb")  # 1 → loop5
elif BLEND == "2.blend":
    DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_loop4.glb")  # 2 → loop4
else:
    DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", f"scene_loop{basename}.glb")

NEW_SOUTH_Y = -70.0   # 新南边缘
INFLATE = 0.01

bpy.ops.wm.open_mainfile(filepath=SRC)
print(f"\n=== 处理 {BLEND} ===")

# 量当前 R_building_beta_block_01 bbox
r_block = bpy.data.objects.get("R_building_beta_block_01")
if not r_block:
    raise SystemExit(f"{BLEND}: 没找到 R_building_beta_block_01")

pts = [r_block.matrix_world @ mathutils.Vector(v) for v in r_block.bound_box]
mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
print(f"  旧 R_block: Y=[{mn.y:.2f}, {mx.y:.2f}] center=({(mn.x+mx.x)/2:.2f},{(mn.y+mx.y)/2:.2f},{(mn.z+mx.z)/2:.2f}) size=({mx.x-mn.x:.2f},{mx.y-mn.y:.2f},{mx.z-mn.z:.2f})")

# 新 bbox：南面退到 NEW_SOUTH_Y，北面/东西/高度不变
new_mn = mathutils.Vector((mn.x, NEW_SOUTH_Y, mn.z))
new_mx = mx
new_center = (new_mn + new_mx) / 2
new_size = new_mx - new_mn
print(f"  新 R_block: Y=[{new_mn.y:.2f}, {new_mx.y:.2f}] center=({new_center.x:.2f},{new_center.y:.2f},{new_center.z:.2f}) size=({new_size.x:.2f},{new_size.y:.2f},{new_size.z:.2f})")
print(f"  南面 Y={mn.y:.2f} → {NEW_SOUTH_Y:.2f}（往北退 {NEW_SOUTH_Y - mn.y:.2f}m）")

# 删旧 R_ + C_
for n in ("R_building_beta_block_01", "C_building_beta_block_01"):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)

# 重建 R_block 长方体
bpy.ops.mesh.primitive_cube_add(size=2, location=tuple(new_center))
block = bpy.context.object
block.scale = (new_size.x / 2, new_size.y / 2, new_size.z / 2)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
block.name = "R_building_beta_block_01"

mat = bpy.data.materials.new(name="beta_block_concrete")
mat.use_nodes = True
bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.42, 0.42, 0.43, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    bsdf.inputs['Metallic'].default_value = 0.0
block.data.materials.append(mat)

# C_ 副本
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

print(f"  + R_building_beta_block_01 (12 tri)")
print(f"  + C_building_beta_block_01 (沿法向 +1cm)")

# 保存 + 导出
bpy.ops.wm.save_as_mainfile(filepath=SRC)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB, export_format='GLB', export_materials='EXPORT',
    export_image_format='AUTO', export_apply=True, export_lights=False,
    export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"  [.blend] {SRC}")
print(f"  [.glb]   {DST_GLB}  ({sz/1024/1024:.2f} MB)")
