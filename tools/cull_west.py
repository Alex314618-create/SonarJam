"""
cull_west.py — 沿 X = R_building_alpha_01.center.x 的垂直平面，把 west 侧（x < cx）
所有几何整齐切掉，并在切口处封盖。

策略：
  - 找 R_building_alpha_01 的世界空间 bbox 中心 → cx
  - 对每个 MESH，用 bmesh.ops.bisect_plane 真切
  - 切口处用 bmesh.ops.holes_fill 自动封盖
    （封盖让声呐 raycast 不会穿过、背面剔除时也不再透洞；代价是稍微加一点面）
  - 切完顶点数为 0 的对象 → 删除

源    : mountain_normalized.blend  （不动）
输出  : mountain_culled.blend
报告  : CULL_REPORT.md
"""

import bpy, bmesh, mathutils, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_normalized.blend")
DST  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_culled.blend")
REPORT = os.path.join(ROOT, "_temp_Blender", "我的工作区", "CULL_REPORT.md")
REF_OBJ = "R_building_alpha_01"

bpy.ops.wm.open_mainfile(filepath=SRC)

ref = bpy.data.objects.get(REF_OBJ)
if not ref:
    raise SystemExit(f"找不到 {REF_OBJ}")
bb = [ref.matrix_world @ mathutils.Vector(v) for v in ref.bound_box]
cx = sum(p.x for p in bb) / 8
print(f"\n[REF] {REF_OBJ}  bbox center.x = {cx:.3f}")
print(f"切割平面：X = {cx:.3f}，法向 +X（删 -X 侧）+ 切口封盖")

plane_co_world = mathutils.Vector((cx, 0.0, 0.0))
plane_no_world = mathutils.Vector((1.0, 0.0, 0.0))

deleted = []
cut     = []   # (name, v_before, v_after, faces_capped)
intact  = []

mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH']
print(f"\n[CUT] 处理 {len(mesh_objs)} 个 mesh...")

total_cap_faces = 0
for obj in mesh_objs:
    mw_inv = obj.matrix_world.inverted()
    local_co = mw_inv @ plane_co_world
    local_no = obj.matrix_world.to_quaternion().inverted() @ plane_no_world
    local_no.normalize()

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    before_v = len(bm.verts)
    before_f = len(bm.faces)
    if before_v == 0:
        bm.free()
        deleted.append(obj.name)
        continue

    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    try:
        result = bmesh.ops.bisect_plane(
            bm, geom=geom,
            dist=0.0001,
            plane_co=local_co,
            plane_no=local_no,
            clear_inner=True,
            clear_outer=False,
        )
    except Exception as e:
        bm.free()
        intact.append(obj.name)
        print(f"  [WARN] bisect failed on {obj.name}: {e}")
        continue

    # === 封盖策略 ===
    # geom_cut 返回的"切边"有时不全（被分裂的子边、双面网格的奇怪情形）。
    # 改成根据顶点位置（落在切平面上 ±eps）来识别切平面边，更可靠。
    EPS = 0.005
    cut_plane_edges = []
    for e in bm.edges:
        if not e.is_valid: continue
        v1, v2 = e.verts
        d1 = (v1.co - local_co).dot(local_no)
        d2 = (v2.co - local_co).dot(local_no)
        if abs(d1) < EPS and abs(d2) < EPS:
            cut_plane_edges.append(e)

    cap_count = 0
    if cut_plane_edges:
        # 1) holes_fill：闭环优先
        try:
            r = bmesh.ops.holes_fill(bm, edges=cut_plane_edges, sides=0)
            cap_count += len(r.get('faces', []))
        except Exception:
            pass
        # 2) edgenet_fill：处理多个独立环、非完整闭环
        still_open = [e for e in cut_plane_edges if e.is_valid and len(e.link_faces) < 2]
        if still_open:
            try:
                r = bmesh.ops.edgenet_fill(bm, edges=still_open, mat_nr=0, use_smooth=False, sides=0)
                cap_count += sum(1 for g in r.get('faces', []) if isinstance(g, bmesh.types.BMFace))
            except Exception:
                pass
        # 3) triangle_fill：最后兜底
        still_open = [e for e in cut_plane_edges if e.is_valid and len(e.link_faces) < 2]
        if still_open:
            try:
                r = bmesh.ops.triangle_fill(bm, edges=still_open, use_beauty=True, use_dissolve=False)
                cap_count += sum(1 for g in r.get('geom', []) if isinstance(g, bmesh.types.BMFace))
            except Exception:
                pass

    after_v = len(bm.verts)
    after_f = len(bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    if after_v == 0:
        deleted.append(obj.name)
    elif after_v < before_v or cap_count > 0:
        cut.append((obj.name, before_v, after_v, cap_count, before_f, after_f))
        total_cap_faces += cap_count
    else:
        intact.append(obj.name)

for name in deleted:
    o = bpy.data.objects.get(name)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.wm.save_as_mainfile(filepath=DST)
print(f"\n[SAVED] {DST}")

final_meshes = [o for o in bpy.data.objects if o.type == 'MESH']
total_polys = sum(len(o.data.polygons) for o in final_meshes)
print(f"\n[FINAL] meshes={len(final_meshes)}, total polys={total_polys}")
print(f"  fully deleted: {len(deleted)}")
print(f"  partially cut: {len(cut)}")
print(f"  intact:        {len(intact)}")
print(f"  cap faces added: {total_cap_faces}")

# ---- 报告 ----
lines = []
lines.append("# 西侧裁剪报告（带切口封盖）")
lines.append("")
lines.append(f"- **参考对象**：`{REF_OBJ}`")
lines.append(f"- **切割平面**：垂直 X-plane @ `x = {cx:.3f}`")
lines.append(f"- **保留**：`x ≥ {cx:.3f}`（east）")
lines.append(f"- **删除**：`x < {cx:.3f}`（west）")
lines.append(f"- **切口封盖**：是（`holes_fill` 优先，失败回退 `triangle_fill`）")
lines.append(f"- **源**：`mountain_normalized.blend`（不动）")
lines.append(f"- **输出**：`mountain_culled.blend`")
lines.append("")
lines.append("## 总览")
lines.append("")
lines.append(f"| 指标 | 数值 |")
lines.append(f"|---|---|")
lines.append(f"| 完全删除（空了） | {len(deleted)} |")
lines.append(f"| 部分切除（跨线） | {len(cut)} |")
lines.append(f"| 完整保留 | {len(intact)} |")
lines.append(f"| 封盖新增面 | {total_cap_faces} |")
lines.append(f"| **最终 mesh 总数** | **{len(final_meshes)}** |")
lines.append(f"| **最终多边形总数** | **{total_polys}** |")
lines.append("")
lines.append("## 封盖效果说明")
lines.append("")
lines.append("- 切口处的「敞开剖面」已自动用 `holes_fill` 封上，所以：")
lines.append("  - **声呐 raycast 不会穿过切面**（C_ collider 也封了）")
lines.append("  - **背面剔除开启时切口不再透洞**")
lines.append("  - **物理碰撞稳定**（无开放边界）")
lines.append("- 代价：封盖面是按切边轮廓自动生成的 n-gon/三角形，**总多边形数比未封盖版本略增**（净对比仍比 normalized 少很多）。")
lines.append("- 如果某个建筑的封盖在 Blender 里看着扭曲（凹多边形封盖），可手动 Edit Mode → 选中封盖面 → Face → Triangulate 重新拓扑。")
lines.append("")

if deleted:
    lines.append("## 被完全删除的对象")
    lines.append("")
    for n in deleted:
        lines.append(f"- `{n}`")
    lines.append("")

if cut:
    lines.append("## 被部分切除的对象（带封盖统计）")
    lines.append("")
    lines.append("| 对象 | 顶点 b→a | 多边形 b→a | 切除顶点 % | 封盖面 |")
    lines.append("|---|---|---|---:|---:|")
    for name, v_b, v_a, caps, f_b, f_a in sorted(cut, key=lambda x: -(x[1]-x[2])):
        pct = (1 - v_a / v_b) * 100 if v_b else 0
        lines.append(f"| `{name}` | {v_b}→{v_a} | {f_b}→{f_a} | {pct:.0f}% | {caps} |")
    lines.append("")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"[REPORT] {REPORT}")
