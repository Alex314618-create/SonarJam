"""补 R_ruin_* → C_ruin_NN（含 ruin token → Structure / 黄色）"""
import bpy, bmesh, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST_BLEND = SRC
DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")

INFLATE = 0.01

bpy.ops.wm.open_mainfile(filepath=SRC)

# 删除任何旧的 C_ruin_*
old = [o.name for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("C_ruin_")]
for n in old:
    bpy.data.objects.remove(bpy.data.objects[n], do_unlink=True)
if old:
    print(f"[CLEANUP] 删除 {len(old)} 个旧 C_ruin_")

# 复制 R_ruin → C_ruin
srcs = [o for o in bpy.data.objects if o.name.startswith("R_ruin_") and o.type == 'MESH']
print(f"[DUP] {len(srcs)} 个 R_ruin → C_ruin")
for i, src in enumerate(srcs, 1):
    dup = src.copy()
    dup.data = src.data.copy()
    bpy.context.collection.objects.link(dup)
    dup.name = f"C_ruin_{i:02d}"
    dup["original_name"] = f"DERIVED_FROM:{src.name}"
    dup["sonarjam_kind"] = "proxy_inflated"
    dup.hide_render = True
    dup.display_type = 'WIRE'
    if dup.parent is not None:
        world_m = dup.parent.matrix_world @ dup.matrix_basis
        dup.parent = None
        dup.matrix_basis = world_m
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
    print(f"  {dup.name}  {len(dup.data.polygons)} tri  (from {src.name})")

bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB, export_format='GLB', export_materials='EXPORT',
    export_image_format='AUTO', export_apply=True, export_lights=False,
    export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"\n[SAVED .glb] {DST_GLB}  ({sz/1024/1024:.2f} MB)")
