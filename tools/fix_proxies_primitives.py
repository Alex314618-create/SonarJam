"""
fix_proxies_primitives.py — 把 decimated 残破 C_ 全换成干净的 cube primitive。

用户反馈：
  - 卡车没法成像
  - 建筑钢筋/外露面只部分成像
  - 根因：和骨头一样，Decimate Collapse 产出 sliver/翻面 → sonar backface miss

解法：
  - 每个 problematic C_ 用 bbox-fitted cube primitive 替换
  - Cube = 12 tri，干净拓扑，全部法向朝外，无 sliver
  - 保留 silhouette 大体轮廓（人造建筑/卡车本来就是 boxy）

替换清单：
  C_building_alpha_ruin_*   → cube  (人造，建筑形状是 boxy)
  C_building_beta_ruin_*    → cube
  C_antenna_structure_*     → cube  (主体/吊钩/盘等都 boxy 包络)
  C_wreck_rocket_*          → cube  (N1 火箭部件，不是登陆仓)
  C_wreck_debris_*          → cube  (卡车碎件)
  C_wreck_wagon_*           → cube  (破车)

不动：
  C_corpse_bones_*          - 已是 20-tri icosphere（上一轮干净）
  C_crashed_shuttle_*       - 登陆仓，引擎需密集 mesh 采样 150k 点云
  C_terrain_*               - 地面，需保留形状
  C_floor_terrain_*         - 地面薄板
"""

import bpy, bmesh, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC       = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST_BLEND = SRC
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")

INFLATE = 0.01

REPLACE_PREFIXES = [
    "C_building_alpha_ruin_",
    "C_building_beta_ruin_",
    "C_antenna_structure_",
    "C_wreck_rocket_",
    "C_wreck_debris_",
    "C_wreck_wagon_",
]

bpy.ops.wm.open_mainfile(filepath=SRC)


def inflate_obj(obj, dist):
    """沿顶点法向外推 dist 米"""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if len(bm.faces) > 0:
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.normal_update()
    for v in bm.verts:
        v.co = v.co + v.normal * dist
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def replace_with_cube(old_obj):
    """以 old_obj 的世界 bbox 为模，删 old_obj，新建同名 cube"""
    # 计算世界 bbox
    bb = [old_obj.matrix_world @ mathutils.Vector(v) for v in old_obj.bound_box]
    mn = mathutils.Vector((min(p.x for p in bb), min(p.y for p in bb), min(p.z for p in bb)))
    mx = mathutils.Vector((max(p.x for p in bb), max(p.y for p in bb), max(p.z for p in bb)))
    cx = (mn.x + mx.x) / 2; cy = (mn.y + mx.y) / 2; cz = (mn.z + mx.z) / 2
    rx = max((mx.x - mn.x) / 2, 0.3)
    ry = max((mx.y - mn.y) / 2, 0.3)
    rz = max((mx.z - mn.z) / 2, 0.3)

    # 拷贝旧对象的元数据
    old_name = old_obj.name
    old_props = {k: old_obj.get(k) for k in old_obj.keys() if not k.startswith("_")}

    # 删旧
    bpy.data.objects.remove(old_obj, do_unlink=True)

    # 新建 cube primitive 12 tri
    bpy.ops.mesh.primitive_cube_add(size=2, location=(cx, cy, cz))
    obj = bpy.context.object
    obj.scale = (rx, ry, rz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    obj.name = old_name
    for k, v in old_props.items():
        obj[k] = v
    obj.hide_render = True
    obj.display_type = 'WIRE'

    # 沿法向 +1cm
    inflate_obj(obj, INFLATE)
    return obj


# 收集目标 (复制 list 避免迭代中修改)
targets = [o for o in list(bpy.data.objects)
           if o.type == 'MESH'
           and any(o.name.startswith(p) for p in REPLACE_PREFIXES)]

print(f"[REPLACE] {len(targets)} 个 problematic C_ 替换成 12-tri cube primitive")
by_cluster = {}
for o in targets:
    cluster = next((p for p in REPLACE_PREFIXES if o.name.startswith(p)), "?")
    by_cluster.setdefault(cluster, []).append(o.name)
for c, names in sorted(by_cluster.items()):
    print(f"  {c}* × {len(names)}")

before_total = sum(len(o.data.polygons) for o in targets)

replaced = []
for o in targets:
    name = o.name
    new_o = replace_with_cube(o)
    replaced.append(new_o.name)

after_total = sum(len(bpy.data.objects[n].data.polygons) for n in replaced if n in bpy.data.objects)
print(f"\n  poly: {before_total} → {after_total} (净减 {before_total - after_total})")

# ---- 保存 + 重导出 ----
bpy.ops.wm.save_as_mainfile(filepath=DST_BLEND)
print(f"\n[SAVED .blend] {DST_BLEND}")

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
sz = os.path.getsize(DST_GLB)
print(f"[SAVED .glb]   {DST_GLB}  ({sz/1024/1024:.2f} MB)")

# 统计 tag 分布预测
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("C_")]
def tag_of(n):
    nl = n.lower()
    if any(k in nl for k in ["danger","hazard","threat","trap","blood"]): return "Danger(红)"
    if any(k in nl for k in ["human","building","structure","ruin","camp","settlement","wreck","debris","corpse"]): return "Structure(黄)"
    return "Normal(青)"
from collections import defaultdict
tag_count = defaultdict(int)
for o in meshes:
    tag_count[tag_of(o.name)] += 1
print(f"\n[TAG 预测]")
for t, n in sorted(tag_count.items()):
    print(f"  {t}: {n} obj")
