"""
strip_clutter.py — 删掉 R_trees / R_rocks / R_grass。

原因：
  - 这些 R_ 没有对应 C_，所以声呐没点云
  - 但 R_ 仍参与深度遮挡 → 声呐扫到它们后面的地面时，点云被前景 R_ 挡住
  - 结果是黑色"剪影空洞"，不是 smooth 地面
  - 用户要 smooth 地面，直接删 R_ 即可

保留：
  - R_terrain (实际地形)
  - R_snow (山顶雪)
  - R_water (湖面)
  - R_boat / R_bones / R_building / R_antenna / R_truck / R_wagon / R_shuttle
    （这些都有对应 C_ 代理，声呐能扫出形状，不会黑洞）
"""
import bpy, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC       = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST_BLEND = SRC
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")

CLUTTER_PREFIXES = ("R_trees_", "R_rocks_", "R_grass_")

bpy.ops.wm.open_mainfile(filepath=SRC)

# 收集所有要删的对象
to_remove = []
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith(CLUTTER_PREFIXES):
        polys = len(o.data.polygons)
        to_remove.append((o.name, polys))
        bpy.data.objects.remove(o, do_unlink=True)

# 清理孤立的 mesh 数据
removed_meshes = 0
for m in list(bpy.data.meshes):
    if m.users == 0:
        bpy.data.meshes.remove(m)
        removed_meshes += 1

print(f"[STRIP] 删除 {len(to_remove)} 个 R_ 杂物对象（树/石/草）")
saved_polys = 0
for n, p in to_remove:
    print(f"  - {n:<24s}  {p:>6d} polys")
    saved_polys += p
print(f"  累计减面: {saved_polys}")
print(f"  清理孤立 mesh data: {removed_meshes}")

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

# 验证
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
total = sum(len(o.data.polygons) for o in meshes)
r_count = sum(1 for o in meshes if o.name.startswith("R_"))
print(f"\n[FINAL] meshes={len(meshes)}, polys={total}, R_={r_count}")

# 列出还有什么 R_ 没动
r_kinds = {}
for o in meshes:
    if not o.name.startswith("R_"): continue
    # 取类别 = R_<cat>_NN 中的 cat
    parts = o.name.split("_")
    cat = parts[1] if len(parts) > 1 else "?"
    r_kinds[cat] = r_kinds.get(cat, 0) + 1
print(f"[R_ 类别保留]")
for k, v in sorted(r_kinds.items()):
    print(f"  R_{k:<14s} × {v}")
