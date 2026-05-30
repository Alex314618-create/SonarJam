"""
fix_proxies_v3.py — 修复两个根本性架构问题。

# 问题 1：M_spawn 错位
  - N1 火箭 (R_truck_rocket_*) 才是登陆仓，位置 (-47, -57, 12) 已被架构师验证
  - 我之前误判成 shuttle，要回到 rocket
  - M_spawn 放在 N1 火箭东侧外缘（玩家出舱第一步）

# 问题 2：C_ 全是方块（无识别度）
  - 把所有 C_*_block_* / C_*_pole_* 砍掉
  - 重生成：复制对应 R_ 物件 → 解 parent 烘世界变换 → decimate 到 50-100 tri
  - 命名带正确 token 让引擎贴 HitTag：
      Danger:    corpse / danger / hazard / blood / threat / trap
      Structure: building / structure / ruin / wreck / debris / human / camp / settlement
  - 总 C_ tri 预算 < 30k

# 保留
  - C_floor_terrain_01 + C_terrain_01..04（地面代理还行，没被批）

# 引擎 verification
  跑 cargo run 看 console 第一行：
    [world] BVH: N 节点形状 (M C_/R_, 其中 X Danger / Y Structure + Z P_)
  应该看到：M 显著增加，X > 0（corpse bones），Y > 0（building/wreck）
"""

import bpy, os, mathutils

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC       = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST_BLEND = SRC
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")


def make_proxy(src, new_name, target_tri):
    """复制 src → 解 parent 烘世界变换 → decimate 到 target_tri → 改名"""
    dup = src.copy()
    dup.data = src.data.copy()
    bpy.context.collection.objects.link(dup)
    dup.name = new_name
    dup["original_name"] = f"DERIVED_FROM:{src.name}"
    dup["sonarjam_kind"] = "proxy"
    dup.hide_render = True
    dup.display_type = 'WIRE'

    # 解 parent，把 parent.matrix_world 烘进 dup.matrix_basis（保留世界位置）
    if dup.parent is not None:
        world_m = dup.parent.matrix_world @ dup.matrix_basis
        dup.parent = None
        dup.matrix_basis = world_m

    # decimate
    cur = len(dup.data.polygons)
    if cur > target_tri:
        bpy.context.view_layer.objects.active = dup
        ratio = max(0.005, target_tri / cur)
        mod = dup.modifiers.new(name='dec', type='DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        try:
            bpy.ops.object.modifier_apply(modifier='dec')
        except Exception as e:
            dup.modifiers.remove(mod)
            print(f"  [WARN] decimate failed on {new_name}: {e}")
    return dup, cur, len(dup.data.polygons)


bpy.ops.wm.open_mainfile(filepath=SRC)

# ============================================================
# A. 清理：所有 C_*_block_* / C_*_pole_* / 现有 C_crashed_shuttle_* / M_spawn
#    保留：C_floor_terrain_01, C_terrain_01..04
# ============================================================
keep_prefixes = ("C_floor_terrain_", "C_terrain_")
to_remove = []
for o in list(bpy.data.objects):
    n = o.name
    if n.startswith("M_spawn"):
        to_remove.append(n); continue
    if n.startswith("C_"):
        if any(n.startswith(k) for k in keep_prefixes):
            continue
        to_remove.append(n)

for n in to_remove:
    obj = bpy.data.objects.get(n)
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)
print(f"[CLEANUP] 删除 {len(to_remove)} 个对象（旧 C_ 方块代理 + 旧 M_spawn）")

# ============================================================
# B. 重生成 C_ 代理
# ============================================================
# 每个 cluster: (R_ prefix, C_ name template, 最多取几个源, 每个目标 tri)
CLUSTERS = [
    # 骨头：corpse token → Danger（显形红色）
    ("R_bones_skeleton_",  "C_corpse_bones_{:02d}",           None, 50),
    # Building #1 / #6 残骸：building+ruin token → Structure（粒子 ×3）
    ("R_building_alpha_",  "C_building_alpha_ruin_{:02d}",    4,    100),
    ("R_building_beta_",   "C_building_beta_ruin_{:02d}",     4,    100),
    # 信号塔：structure token → Structure
    ("R_antenna_",         "C_antenna_structure_{:02d}",      5,    80),
    # N1 火箭（登陆仓）：crashed token → 进 crashed_tris 做出生云源 + 普通碰撞
    ("R_truck_rocket_",    "C_crashed_rocket_{:02d}",         None, 60),
    # 卡车碎片：wreck+debris token → Structure
    ("R_truck_debris_",    "C_wreck_debris_{:02d}",           4,    60),
    # 破车：wreck token → Structure
    ("R_wagon_",           "C_wreck_wagon_{:02d}",            None, 60),
    # 航天飞机：wreck token（这架是另一处坠机残骸，不是登陆仓）→ Structure
    ("R_shuttle_",         "C_shuttle_wreck_{:02d}",          5,    80),
]

proxy_log = []
total_before = total_after = 0
for prefix, tmpl, max_n, tgt in CLUSTERS:
    srcs = [o for o in bpy.data.objects if o.name.startswith(prefix) and o.type == 'MESH']
    if not srcs:
        print(f"  [SKIP] {prefix}* 找不到源")
        continue
    srcs.sort(key=lambda o: -len(o.data.polygons))
    if max_n is not None:
        srcs = srcs[:max_n]
    print(f"\n[CLUSTER] {prefix}* → {tmpl.split('{')[0]}* (取 {len(srcs)} 个源, 目标 ≤{tgt} tri/件)")
    for i, src in enumerate(srcs, 1):
        new_name = tmpl.format(i)
        _, before, after = make_proxy(src, new_name, tgt)
        proxy_log.append((new_name, src.name, before, after))
        total_before += before
        total_after += after
        print(f"  {new_name:<32s}  {before:>6} → {after:>4}  (from {src.name})")

print(f"\n[PROXY TOTAL] {total_before} → {total_after} tris")

# ============================================================
# C. M_spawn_lander 在 N1 火箭东侧外缘
# ============================================================
rocket_main = bpy.data.objects.get("R_truck_rocket_01")
if rocket_main:
    bb = [rocket_main.matrix_world @ mathutils.Vector(v) for v in rocket_main.bound_box]
    cx = sum(p.x for p in bb)/8
    cy = sum(p.y for p in bb)/8
    cz_min = min(p.z for p in bb)
    cx_east = max(p.x for p in bb) + 1.5  # 东侧外缘 +1.5m
    spawn = bpy.data.objects.new("M_spawn", None)  # 严格 M_spawn（按架构师要求）
    spawn.location = (cx_east, cy, cz_min + 0.5)
    spawn.empty_display_type = 'PLAIN_AXES'
    spawn.empty_display_size = 2.0
    bpy.context.collection.objects.link(spawn)
    print(f"\n[M_spawn] 放在 Blender XYZ ({cx_east:.2f}, {cy:.2f}, {cz_min+0.5:.2f})")
    print(f"  火箭东侧外缘 +1.5m，玩家出舱第一步")
else:
    print(f"\n[WARN] 找不到 R_truck_rocket_01，M_spawn 没放！")

# ============================================================
# D. 保存 + 重导出
# ============================================================
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

# ============================================================
# E. 终态报告
# ============================================================
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
c_meshes = [o for o in meshes if o.name.startswith("C_")]
c_tris = sum(len(o.data.polygons) for o in c_meshes)
crashed = [o for o in c_meshes if "crashed" in o.name.lower()]
crashed_tris = sum(len(o.data.polygons) for o in crashed)
total = sum(len(o.data.polygons) for o in meshes)

# 验证 tag 分布
def tag_of(n):
    nl = n.lower()
    if any(k in nl for k in ["danger","hazard","corpse","threat","trap","blood"]): return "Danger"
    if any(k in nl for k in ["human","building","structure","ruin","camp","settlement","wreck","debris"]): return "Structure"
    return "Normal"

danger = [o for o in c_meshes if tag_of(o.name) == "Danger"]
structure = [o for o in c_meshes if tag_of(o.name) == "Structure"]
normal = [o for o in c_meshes if tag_of(o.name) == "Normal"]

print(f"\n[FINAL]")
print(f"  total meshes: {len(meshes)}, total polys: {total}")
print(f"  C_ 对象: {len(c_meshes)}, C_ tris: {c_tris} (预算 < 30k)")
print(f"  其中 crashed: {len(crashed)} obj, {crashed_tris} tris")
print(f"  HitTag 预测:")
print(f"    Danger    × {len(danger)}: {[o.name for o in danger][:5]}{'...' if len(danger)>5 else ''}")
print(f"    Structure × {len(structure)}: {[o.name for o in structure][:5]}{'...' if len(structure)>5 else ''}")
print(f"    Normal    × {len(normal)}: {[o.name for o in normal][:5]}{'...' if len(normal)>5 else ''}")
