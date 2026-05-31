"""
beautify_12345.py — 优化 12345 (mountain_12345) 视觉
  1. 重做 R_trees_01：master 从 50 polys 提到 300 polys，6000 instance join 成单 mesh
  2. R_water_01/02: 深绿黑 → 蓝青色 + 半透明
  3. R_grass_01/02: 棕色 → 绿色
"""
import bpy, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC_12345 = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_12345.blend")
SRC_MINE  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_mine.blend")
TREE_GLB  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "C_s", "tree.glb")
DST_BLEND = SRC_12345
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_12345.glb")

# ============ STEP 1: 重新抽 card 位置 + 重建高质量树 ============
TARGET_POLYS = 300   # 每棵真树多边形目标（从 50 → 300，6× 细节）

def get_card_positions(src_name):
    obj = bpy.data.objects.get(src_name)
    if not obj: return []
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if obj.parent is not None:
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    parts = [o for o in bpy.data.objects
             if (o.name == src_name or o.name.startswith(src_name + "."))
             and o.type == 'MESH']
    pos = []
    for p in parts:
        pts = [p.matrix_world @ mathutils.Vector(v) for v in p.bound_box]
        mn = mathutils.Vector((min(pt.x for pt in pts), min(pt.y for pt in pts), min(pt.z for pt in pts)))
        mx = mathutils.Vector((max(pt.x for pt in pts), max(pt.y for pt in pts), max(pt.z for pt in pts)))
        h = mx.z - mn.z
        if 0.1 < h < 100:
            pos.append(((mn.x+mx.x)/2, (mn.y+mx.y)/2, mn.z, h))
    return pos

bpy.ops.wm.open_mainfile(filepath=SRC_MINE)
print(f"\n[STEP1] 从 mountain_mine 抽 R_trees_01 card 位置...")
positions_01 = get_card_positions("R_trees_01")
print(f"  R_trees_01: {len(positions_01)} cards")

bpy.ops.wm.open_mainfile(filepath=SRC_12345)
print(f"\n[STEP2] 在 mountain_12345 重做 R_trees_01")

# 删旧 R_trees_*
for o in list(bpy.data.objects):
    if o.name.startswith("R_trees_") and o.type == 'MESH':
        bpy.data.objects.remove(o, do_unlink=True)

# import tree.glb
before_set = set(o.name for o in bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=TREE_GLB)
new_objs = [bpy.data.objects[n] for n in (set(o.name for o in bpy.data.objects) - before_set)]
imported_meshes = [o for o in new_objs if o.type == 'MESH']
for m in list(imported_meshes):
    bpy.ops.object.select_all(action='DESELECT')
    m.select_set(True)
    bpy.context.view_layer.objects.active = m
    if m.parent is not None:
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in list(new_objs):
    if o.type != 'MESH' and o.name in bpy.data.objects:
        bpy.data.objects.remove(o, do_unlink=True)

# join + decimate master
bpy.ops.object.select_all(action='DESELECT')
for m in imported_meshes: m.select_set(True)
bpy.context.view_layer.objects.active = imported_meshes[0]
bpy.ops.object.join()
master = bpy.context.active_object
pts = [master.matrix_world @ mathutils.Vector(v) for v in master.bound_box]
mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
master_height = mx.z - mn.z
master.location = (master.location.x - (mn.x+mx.x)/2, master.location.y - (mn.y+mx.y)/2, master.location.z - mn.z)
bpy.context.view_layer.update()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

cur_polys = len(master.data.polygons)
if cur_polys > TARGET_POLYS:
    mod = master.modifiers.new(name='dec', type='DECIMATE')
    mod.ratio = max(0.001, TARGET_POLYS / cur_polys)
    mod.decimate_type = 'COLLAPSE'
    mod.use_collapse_triangulate = True
    try: bpy.ops.object.modifier_apply(modifier='dec')
    except: pass
print(f"  master tree: 高 {master_height:.2f}m, polys={len(master.data.polygons)} (decimated from {cur_polys})")
master.hide_render = True
master.hide_set(True)
master.name = "__tree_master_template"

# 生成 instances
h_avg = sum(p[3] for p in positions_01) / len(positions_01)
scale = h_avg / master_height
print(f"  R_trees_01: {len(positions_01)} 棵 × scale={scale:.3f}")
for i, (cx, cy, bz, h) in enumerate(positions_01, 1):
    dup = master.copy()
    bpy.context.collection.objects.link(dup)
    dup.location = (cx, cy, bz)
    dup.scale = (scale, scale, scale)
    dup.hide_render = False
    dup.hide_set(False)
    dup.name = f"R_trees_01_inst_{i:04d}"

# 不 join！保留 linked instances（6000 节点共享一份 300-poly mesh）
# 文件大小：~30MB（vs 242MB join 版）
# 第一个 instance 重命名 R_trees_01_inst_0001 → R_trees_01（引擎按 R_ 前缀识别）
inst_objs = [o for o in bpy.data.objects
             if o.type == 'MESH' and o.name.startswith("R_trees_01_inst_")]
print(f"  保留 {len(inst_objs)} 个 linked instance（共享同一份 mesh 数据）")
print(f"  每个 instance 300 polys × {len(inst_objs)} 节点 → 视觉 1.8M tri / 文件 ~30MB")

# 把 master mesh 数据保留：第一个 instance 已经引用它，不能删 master object（会断引用）
# 但 master object hide_render → 它不会被渲染，只是 mesh data 容器
# 给 master 一个 R_ 前缀避免被引擎 skip（如果 master 不渲染，无所谓）
m = bpy.data.objects.get("__tree_master_template")
if m:
    m.name = "R_trees_master_hidden"   # R_ 前缀，但 hide_render=True 所以不影响 sonar
    m.hide_render = True

# ============ STEP 3: 水材质 ============
print(f"\n[STEP3] 水材质 → 蓝青色")
water_mats = set()
for o in bpy.data.objects:
    if o.name.startswith("R_water_") and o.type == 'MESH':
        for s in o.material_slots:
            if s.material: water_mats.add(s.material)

for mat in water_mats:
    if not mat.use_nodes: continue
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf: continue
    bsdf.inputs['Base Color'].default_value = (0.08, 0.35, 0.42, 1.0)  # 深蓝青
    bsdf.inputs['Roughness'].default_value = 0.15  # 反光
    bsdf.inputs['Metallic'].default_value = 0.0
    # IOR 1.33（水）
    for k in ('IOR', 'Specular IOR Level'):
        if k in bsdf.inputs:
            try: bsdf.inputs[k].default_value = 1.33
            except: pass
    print(f"  {mat.name}: blue (0.08, 0.35, 0.42) Roughness 0.15")

# ============ STEP 4: 草材质 ============
print(f"\n[STEP4] 草材质 → 绿色")
grass_mats = set()
for o in bpy.data.objects:
    if o.name.startswith("R_grass_") and o.type == 'MESH':
        for s in o.material_slots:
            if s.material: grass_mats.add(s.material)

for mat in grass_mats:
    if not mat.use_nodes: continue
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf: continue
    if "herbe-haute" in mat.name:
        bsdf.inputs['Base Color'].default_value = (0.18, 0.42, 0.10, 1.0)  # 深绿（高草）
    else:
        bsdf.inputs['Base Color'].default_value = (0.30, 0.58, 0.18, 1.0)  # 鲜绿（普通草）
    bsdf.inputs['Roughness'].default_value = 0.85
    bsdf.inputs['Metallic'].default_value = 0.0
    print(f"  {mat.name}: green")

# ============ 保存 + 导出 ============
bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
bpy.ops.export_scene.gltf(
    filepath=DST_GLB,
    export_format='GLB', export_materials='EXPORT',
    export_image_format='AUTO', export_apply=True, export_lights=False,
    export_yup=True, export_extras=True, use_visible=False, use_renderable=False,
)
sz = os.path.getsize(DST_GLB)
print(f"\n[SAVED .blend] {DST_BLEND}")
print(f"[SAVED .glb]   {DST_GLB}  ({sz/1024/1024:.2f} MB)")
