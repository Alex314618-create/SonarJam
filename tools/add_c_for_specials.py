"""为 1/2.blend 里用户新加的非规范命名 mesh 添加 C_ 副本"""
import bpy, bmesh, mathutils, os, sys

ROOT = r"C:\Users\ROG\Desktop\GameJam"
argv = sys.argv
sep = argv.index("--") if "--" in argv else -1
BLEND_NAME = argv[sep+1] if sep >= 0 else "1.blend"

SRC = os.path.join(ROOT, "_temp_Blender", "更新与交付", BLEND_NAME)
basename = os.path.splitext(BLEND_NAME)[0].replace("&", "_")
DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", f"scene_loop{basename}.glb")

INFLATE = 0.01

# 不同 blend 里要处理的对象
TARGETS_BY_BLEND = {
    "1.blend": [
        ("Special:Cilinder_shows_up", "C_special_cylinder_structure_01"),
        ("Sphere.001", "C_special_sphere_structure_01"),
    ],
    "2.blend": [
        ("Special:Cilinder_shows_up", "C_special_cylinder_structure_01"),
    ],
}

TARGETS = TARGETS_BY_BLEND.get(BLEND_NAME, [])
if not TARGETS:
    print(f"{BLEND_NAME}: 没有指定目标")
    sys.exit(0)

print(f"\n=== 处理 {BLEND_NAME} ===")
bpy.ops.wm.open_mainfile(filepath=SRC)

for orig_name, c_name in TARGETS:
    # 删旧
    old = bpy.data.objects.get(c_name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
        print(f"  删旧 {c_name}")

    src = bpy.data.objects.get(orig_name)
    if not src:
        print(f"  [WARN] 找不到 {orig_name}")
        continue

    # 复制
    dup = src.copy()
    dup.data = src.data.copy()
    bpy.context.collection.objects.link(dup)
    dup.name = c_name
    dup["original_name"] = f"DERIVED_FROM:{orig_name}"
    dup["sonarjam_kind"] = "proxy_inflated"
    dup.hide_render = True
    dup.display_type = 'WIRE'

    # 解 parent（保留世界变换）
    if dup.parent is not None:
        wm = dup.matrix_world.copy()
        dup.parent = None
        dup.matrix_world = wm

    # 沿法向 +1cm
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

    polys = len(dup.data.polygons)
    print(f"  + {c_name} ({polys} tri, structure token → 黄)")

# 保存 + 重导出 GLB
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
