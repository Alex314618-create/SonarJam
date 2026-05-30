"""
dup_r_to_c.py — 最简方案：每个 R_ 复制一份 → 沿法向 +1cm → 改名 C_<token>_NN。

为什么这是对的：
  - 形状和 R_ 完全一样，没任何 decimate sliver → 不会扫不上
  - 沿法向 +1cm → C_ 永远在 R_ 外侧 1cm，无 z-fight
  - C_ 命名含 building/ruin/wreck/debris/structure/corpse 等 token → Structure tag → 黄色

清理：所有 C_*_ruin / C_*_structure / C_wreck_* / C_corpse_bones_ 旧代理
保留：C_floor_terrain_* / C_terrain_* / C_crashed_shuttle_*（登陆仓特殊）

映射：
  R_building_alpha_   → C_building_alpha_ruin_NN    (yellow)
  R_building_beta_    → C_building_beta_ruin_NN     (yellow)
  R_antenna_          → C_antenna_structure_NN      (yellow)
  R_truck_rocket_     → C_wreck_rocket_NN           (yellow, N1 火箭"坠毁的飞机"非登陆仓)
  R_truck_debris_     → C_wreck_debris_NN           (yellow)
  R_wagon_            → C_wreck_wagon_NN            (yellow)
  R_bones_skeleton_   → C_corpse_bones_NN           (yellow, corpse→Structure 已改)
"""

import bpy, bmesh, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC       = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST_BLEND = SRC
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")

INFLATE = 0.01

KEEP_PREFIXES = ("C_floor_terrain_", "C_terrain_", "C_crashed_shuttle_")

CLUSTERS = [
    ("R_building_alpha_",   "C_building_alpha_ruin_"),
    ("R_building_beta_",    "C_building_beta_ruin_"),
    ("R_antenna_",          "C_antenna_structure_"),
    ("R_truck_rocket_",     "C_wreck_rocket_"),
    ("R_truck_debris_",     "C_wreck_debris_"),
    ("R_wagon_",            "C_wreck_wagon_"),
    ("R_bones_skeleton_",   "C_corpse_bones_"),
    ("R_ruin_",             "C_ruin_"),
]


def make_inflated_copy(src, new_name):
    dup = src.copy()
    dup.data = src.data.copy()
    bpy.context.collection.objects.link(dup)
    dup.name = new_name
    dup["original_name"] = f"DERIVED_FROM:{src.name}"
    dup["sonarjam_kind"] = "proxy_inflated"
    dup.hide_render = True
    dup.display_type = 'WIRE'

    # 解 parent，烘世界变换
    if dup.parent is not None:
        world_m = dup.parent.matrix_world @ dup.matrix_basis
        dup.parent = None
        dup.matrix_basis = world_m

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
    return dup


bpy.ops.wm.open_mainfile(filepath=SRC)

# 1. 清理旧 C_ 代理（除 keep 之外）
to_remove = [o.name for o in bpy.data.objects
             if o.type == 'MESH' and o.name.startswith("C_")
             and not any(o.name.startswith(k) for k in KEEP_PREFIXES)]
for n in to_remove:
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)
print(f"[CLEANUP] 删除 {len(to_remove)} 个旧 C_ 代理（盒子/icosphere/decimated）")

# 2. 每个 R_ 复制一份成 C_
print(f"\n[DUP+INFLATE]")
total_before = total_after = total_count = 0
for src_pre, c_pre in CLUSTERS:
    srcs = [o for o in bpy.data.objects
            if o.name.startswith(src_pre) and o.type == 'MESH']
    print(f"  {src_pre}* × {len(srcs)} → {c_pre}*")
    for i, src in enumerate(srcs, 1):
        before = len(src.data.polygons)
        new = make_inflated_copy(src, f"{c_pre}{i:02d}")
        after = len(new.data.polygons)
        total_before += before
        total_after += after
        total_count += 1

print(f"\n  总计 {total_count} 个新 C_，{total_after} tri（完全复刻 R_ 剪影）")

# 3. 保存 + 重导出
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

# 4. tag 分布预测
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("C_")]
def tag_of(n):
    nl = n.lower()
    if any(k in nl for k in ["danger","hazard","threat","trap","blood"]): return "Danger(红)"
    if any(k in nl for k in ["human","building","structure","ruin","camp","settlement","wreck","debris","corpse"]): return "Structure(黄)"
    return "Normal(青)"
from collections import defaultdict
tag_count = defaultdict(lambda: [0, 0])  # [obj_count, tri_count]
for o in meshes:
    t = tag_of(o.name)
    tag_count[t][0] += 1
    tag_count[t][1] += len(o.data.polygons)
print(f"\n[TAG 预测]")
for t, (n, p) in sorted(tag_count.items()):
    print(f"  {t}: {n} obj, {p} tri")
