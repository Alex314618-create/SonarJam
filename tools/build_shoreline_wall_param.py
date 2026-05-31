"""
build_shoreline_wall_param.py — 接受 BLEND_NAME + TILT_DEG，建海岸墙后导 GLB。
通过环境变量 / sys.argv 传参。
"""
import bpy, bmesh, mathutils, math, os, sys

ROOT = r"C:\Users\ROG\Desktop\GameJam"

# 解析参数（-- 之后）
argv = sys.argv
sep = argv.index("--") if "--" in argv else -1
script_args = argv[sep+1:] if sep >= 0 else []
BLEND_NAME = script_args[0] if len(script_args) > 0 else "5&4.blend"
TILT_DEG   = float(script_args[1]) if len(script_args) > 1 else 0.0

SRC = os.path.join(ROOT, "_temp_Blender", "更新与交付", BLEND_NAME)
DST_BLEND = SRC
# 文件名映射 GLB
basename = os.path.splitext(BLEND_NAME)[0].replace("&", "_")
DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", f"scene_loop{basename}.glb")

WATER_Z     = 1.27
WALL_HEIGHT = 8.0
WALL_THICK  = 0.30
INFLATE     = 0.01
SOUTH_TERRAINS = ["R_terrain_02", "R_terrain_03"]

print(f"\n=== build wall for {BLEND_NAME}, TILT={TILT_DEG}° ===")
bpy.ops.wm.open_mainfile(filepath=SRC)

for n in ("R_riverwall_structure_01", "C_riverwall_structure_01"):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)

# 收 cut edges
shore_edges = []
for name in SOUTH_TERRAINS:
    obj = bpy.data.objects.get(name)
    if not obj: continue
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    result = bmesh.ops.bisect_plane(
        bm, geom=geom, dist=0.001,
        plane_co=mathutils.Vector((0, 0, WATER_Z)),
        plane_no=mathutils.Vector((0, 0, 1)),
        clear_inner=False, clear_outer=False,
    )
    for g in result.get('geom_cut', []):
        if isinstance(g, bmesh.types.BMEdge):
            v1, v2 = g.verts
            if abs(v1.co.z - WATER_Z) < 0.05 and abs(v2.co.z - WATER_Z) < 0.05:
                shore_edges.append((v1.co.copy(), v2.co.copy()))
    bm.free()

if not shore_edges:
    raise SystemExit(f"{BLEND_NAME}: 没找到 shoreline cut edge")
print(f"  收 {len(shore_edges)} 条 cut edge")

# 构造 wall_bm
wall_bm = bmesh.new()
vert_dict = {}
def get_or_make_vert(co):
    key = (round(co.x, 3), round(co.y, 3), round(co.z, 3))
    if key in vert_dict: return vert_dict[key]
    v = wall_bm.verts.new(co)
    vert_dict[key] = v
    return v

bottom_edges = []
for v1c, v2c in shore_edges:
    bv1 = get_or_make_vert(v1c)
    bv2 = get_or_make_vert(v2c)
    if bv1 != bv2:
        try:
            bottom_edges.append(wall_bm.edges.new((bv1, bv2)))
        except ValueError: pass

wall_bm.verts.ensure_lookup_table()
wall_bm.edges.ensure_lookup_table()
ext_result = bmesh.ops.extrude_edge_only(wall_bm, edges=bottom_edges)
new_verts = [g for g in ext_result['geom'] if isinstance(g, bmesh.types.BMVert)]

# 向上 + tilt
tilt_rad = math.radians(TILT_DEG)
y_per_z = math.tan(tilt_rad)
for v in new_verts:
    v.co.z += WALL_HEIGHT
    v.co.y += WALL_HEIGHT * y_per_z   # 向 +Y (北) 倾斜
print(f"  向上 {WALL_HEIGHT}m + 向北倾斜 {TILT_DEG}° (顶部 +Y {WALL_HEIGHT*y_per_z:.2f}m)")

mesh = bpy.data.meshes.new("R_riverwall_structure_01_mesh")
wall_bm.to_mesh(mesh)
wall_bm.free()
wall = bpy.data.objects.new("R_riverwall_structure_01", mesh)
bpy.context.collection.objects.link(wall)

mat = bpy.data.materials.new(name="riverwall_concrete")
mat.use_nodes = True
bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.42, 0.42, 0.43, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    bsdf.inputs['Metallic'].default_value = 0.0
wall.data.materials.append(mat)

bpy.context.view_layer.objects.active = wall
mod = wall.modifiers.new(name='solidify', type='SOLIDIFY')
mod.thickness = WALL_THICK
mod.offset = 0.0
try:
    bpy.ops.object.modifier_apply(modifier='solidify')
except Exception as e:
    print(f"  [WARN] solidify: {e}")

# C_
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

bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB, export_format='GLB', export_materials='EXPORT',
    export_image_format='AUTO', export_apply=True, export_lights=False,
    export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"  [.blend] {DST_BLEND}")
print(f"  [.glb]   {DST_GLB}  ({sz/1024/1024:.2f} MB)")
