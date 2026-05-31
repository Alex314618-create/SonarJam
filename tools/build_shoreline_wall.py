"""
build_shoreline_wall.py — 沿地形 R_terrain_02/03 与水面 Z=1.27 的交线建不规则的曲线墙。

算法:
  1. 对每个南侧地形 (R_terrain_02 + R_terrain_03):
     - bmesh.ops.bisect_plane 切一刀 Z=1.27（不删两侧，只为得到 cut 边）
     - 收集 geom_cut 里的 edges = 海岸线段
  2. 把所有 cut edges 在世界空间合成 wall_bm
  3. extrude_edge_only 向 +Z 拉 8m → 单面墙带
  4. solidify 0.3m → 厚度
  5. R_riverwall_structure_01 + C_riverwall_structure_01 (inflate 1cm)
"""
import bpy, bmesh, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC = os.path.join(ROOT, "_temp_Blender", "更新与交付", "5&4.blend")
DST_BLEND = SRC
DST_GLB = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_loop5.glb")

WATER_Z     = 1.27
WALL_HEIGHT = 8.0
WALL_THICK  = 0.30
INFLATE     = 0.01
SOUTH_TERRAINS = ["R_terrain_02", "R_terrain_03"]   # 南侧地形（含 SE + SW）

bpy.ops.wm.open_mainfile(filepath=SRC)

# 清旧的（如果存在）
for n in ("R_riverwall_structure_01", "C_riverwall_structure_01"):
    o = bpy.data.objects.get(n)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)
        print(f"  删旧 {n}")

# === STEP 1+2: 收集 cut edges ===
print(f"\n[STEP1] bisect 各南侧地形 at Z={WATER_Z}")
shore_edges = []  # list of (Vector v1_world, Vector v2_world)

for name in SOUTH_TERRAINS:
    obj = bpy.data.objects.get(name)
    if not obj:
        print(f"  [WARN] {name} 不存在")
        continue

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)   # 转到世界坐标

    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    result = bmesh.ops.bisect_plane(
        bm, geom=geom, dist=0.001,
        plane_co=mathutils.Vector((0, 0, WATER_Z)),
        plane_no=mathutils.Vector((0, 0, 1)),
        clear_inner=False, clear_outer=False,
    )
    cut_geom = result.get('geom_cut', [])
    n_edges_before = len(shore_edges)
    for g in cut_geom:
        if isinstance(g, bmesh.types.BMEdge):
            v1, v2 = g.verts
            # 确认两顶点都很接近 Z=WATER_Z
            if abs(v1.co.z - WATER_Z) < 0.05 and abs(v2.co.z - WATER_Z) < 0.05:
                shore_edges.append((v1.co.copy(), v2.co.copy()))
    print(f"  {name}: 收 {len(shore_edges) - n_edges_before} 条 cut edge")
    bm.free()

if not shore_edges:
    raise SystemExit("没找到任何 shoreline cut edge！可能地形不和 Z=1.27 相交")

print(f"\n  共收 {len(shore_edges)} 条 cut edge")

# === STEP 3: 构造 wall_bm ===
wall_bm = bmesh.new()
vert_dict = {}

def get_or_make_vert(co):
    key = (round(co.x, 3), round(co.y, 3), round(co.z, 3))
    if key in vert_dict:
        return vert_dict[key]
    v = wall_bm.verts.new(co)
    vert_dict[key] = v
    return v

bottom_edges = []
for v1c, v2c in shore_edges:
    bv1 = get_or_make_vert(v1c)
    bv2 = get_or_make_vert(v2c)
    if bv1 != bv2:
        try:
            e = wall_bm.edges.new((bv1, bv2))
            bottom_edges.append(e)
        except ValueError:
            pass  # 已存在
print(f"\n[STEP3] wall_bm 底边: {len(bottom_edges)} edges, {len(vert_dict)} verts")

# === STEP 4: extrude up ===
wall_bm.verts.ensure_lookup_table()
wall_bm.edges.ensure_lookup_table()
ext_result = bmesh.ops.extrude_edge_only(wall_bm, edges=bottom_edges)
new_verts = [g for g in ext_result['geom'] if isinstance(g, bmesh.types.BMVert)]
for v in new_verts:
    v.co.z += WALL_HEIGHT
print(f"[STEP4] 向上拉 {WALL_HEIGHT}m: {len(new_verts)} 个新顶点")

# === STEP 5: write to mesh + 加 solidify ===
mesh = bpy.data.meshes.new("R_riverwall_structure_01_mesh")
wall_bm.to_mesh(mesh)
wall_bm.free()

wall = bpy.data.objects.new("R_riverwall_structure_01", mesh)
bpy.context.collection.objects.link(wall)

# 材质：水泥灰
mat = bpy.data.materials.new(name="riverwall_concrete")
mat.use_nodes = True
bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.42, 0.42, 0.43, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    bsdf.inputs['Metallic'].default_value = 0.0
wall.data.materials.append(mat)

# 应用 Solidify
bpy.context.view_layer.objects.active = wall
mod = wall.modifiers.new(name='solidify', type='SOLIDIFY')
mod.thickness = WALL_THICK
mod.offset = 0.0  # 两侧等厚
try:
    bpy.ops.object.modifier_apply(modifier='solidify')
except Exception as e:
    print(f"  [WARN] solidify apply: {e}")

polys_after = len(wall.data.polygons)
print(f"[STEP5] solidify thickness={WALL_THICK}m, final polys={polys_after}")

# === STEP 6: 派生 C_ + inflate ===
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
print(f"[STEP6] C_riverwall_structure_01 派生 + inflate 1cm")

# 验证
import mathutils as _m
pts = [wall.matrix_world @ _m.Vector(v) for v in wall.bound_box]
mn = _m.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = _m.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
c = (mn+mx)/2; s = mx-mn
print(f"\n[WALL] bbox center=({c.x:.2f},{c.y:.2f},{c.z:.2f}) size=({s.x:.2f},{s.y:.2f},{s.z:.2f})")
print(f"   底缘 Z={mn.z:.2f}（水面 {WATER_Z}） 顶缘 Z={mx.z:.2f}")

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
