"""
further_optimize.py — 在 mountain_culled.blend 基础上再做一轮针对性优化。

目标（用户指令）：
  1. 倒塌建筑（Building #1/#6）破损细节没必要那么多面——sonar 看上去都差不多
     → 删除 *_concrete inner_*（碎混凝土碎块）
     → Metal_bar 类钢筋激进 0.4 ratio
     → inner_Metal inner（内部钢骨）再压一次 0.5 ratio
     → outer_paint / outer_Metal 主外壳 0.7 ratio 轻度抽稀
  2. 信号塔（TV antenna）优化，但不动「圆形卫星锅」
     → 只动 poly > 1000 的大件（基座 / yagi 杆 / 吊钩盘）
     → 跳过所有 Cone* / Referement*（潜在的卫星锅/反射器）
     → 跳过所有 < 1000 poly 的小件（动了也省不了多少，风险大）

源    : mountain_culled.blend  （不动）
输出  : mountain_further.blend
报告  : FURTHER_REPORT.md
"""

import bpy, math, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_culled.blend")
DST  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_further.blend")
REPORT = os.path.join(ROOT, "_temp_Blender", "我的工作区", "FURTHER_REPORT.md")

bpy.ops.wm.open_mainfile(filepath=SRC)

# 计数起点
before_meshes = [o for o in bpy.data.objects if o.type == 'MESH']
before_polys = sum(len(o.data.polygons) for o in before_meshes)
before_count = len(before_meshes)

# ============================================================
# Phase 1: 删除建筑破损碎块 (concrete inner)
# ============================================================
deleted = []
for o in list(bpy.data.objects):
    if o.type != 'MESH': continue
    orig = o.get("original_name", o.name)
    # 关键词：concrete inner = 倒下建筑里的碎混凝土块
    if "concrete inner" in orig.lower():
        polys = len(o.data.polygons)
        deleted.append((o.name, orig, polys))
        bpy.data.objects.remove(o, do_unlink=True)

print(f"[DELETE] 删除 {len(deleted)} 个破损碎混凝土对象")
for n, orig, p in deleted:
    print(f"  {n}  ({orig})  -{p} polys")

# ============================================================
# Phase 2: Decimate 建筑结构件
# ============================================================
# (substring_to_match_in_original_name, ratio, 说明)
BUILDING_RULES = [
    ("Metal bar",       0.40, "钢筋（破损细节，sonar 看不出差别）"),
    ("inner_Metal",     0.50, "内部钢骨（看不到）"),  # 已经在 normalize 时降到 0.2，这里在残料上再压
    ("outer_paint",     0.70, "外壳油漆"),
    ("outer_Metal_",    0.70, "外壳金属（不含 _bar / _inner）"),
]

# ============================================================
# Phase 3: Decimate 信号塔大件（卫星锅类豁免）
# ============================================================
# 跳过卫星锅候选：Cone* (圆锥/喇叭/可能的抛物面) + Referement* (refletor 反射板) + 所有 < 1000 poly
ANTENNA_SKIP_KEYWORDS = ["cone", "referement"]  # 全部小写
ANTENNA_MIN_POLY = 1000   # 小于这个数不动（动了省不了多少）
ANTENNA_RATIO = 0.40

# ============================================================
# 执行 decimate
# ============================================================
def apply_decimate(obj, ratio, reason):
    before = len(obj.data.polygons)
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new(name='further_dec', type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    try:
        bpy.ops.object.modifier_apply(modifier='further_dec')
        after = len(obj.data.polygons)
        return (before, after, reason)
    except Exception as e:
        obj.modifiers.remove(mod)
        return (before, before, f"FAILED: {e}")

dec_log = []  # (name, original_name, before, after, ratio, reason)

# Building 部件
print("\n[DECIMATE] 建筑")
for o in [obj for obj in bpy.data.objects if obj.name.startswith("R_building_") and obj.type == 'MESH']:
    orig = o.get("original_name", o.name)
    matched = False
    for substr, ratio, reason in BUILDING_RULES:
        if substr.lower() in orig.lower():
            b, a, r = apply_decimate(o, ratio, reason)
            dec_log.append((o.name, orig, b, a, ratio, r))
            matched = True
            break
    if not matched:
        # outer_Glass / 没匹配的小件 → 跳过
        pass

# Antenna 部件
print("\n[DECIMATE] 信号塔（保护卫星锅）")
for o in [obj for obj in bpy.data.objects if obj.name.startswith("R_antenna_") and obj.type == 'MESH']:
    orig = o.get("original_name", o.name)
    polys = len(o.data.polygons)
    orig_lc = orig.lower()
    # 跳过卫星锅候选
    if any(kw in orig_lc for kw in ANTENNA_SKIP_KEYWORDS):
        dec_log.append((o.name, orig, polys, polys, None, "SKIP: 卫星锅候选（Cone/Referement）"))
        continue
    if polys < ANTENNA_MIN_POLY:
        # 小件跳过
        continue
    b, a, r = apply_decimate(o, ANTENNA_RATIO, "信号塔大件（非卫星锅）")
    dec_log.append((o.name, orig, b, a, ANTENNA_RATIO, r))

# ============================================================
# 保存
# ============================================================
bpy.ops.wm.save_as_mainfile(filepath=DST)

after_meshes = [o for o in bpy.data.objects if o.type == 'MESH']
after_polys = sum(len(o.data.polygons) for o in after_meshes)

print(f"\n[SAVED] {DST}")
print(f"[FINAL] meshes={len(after_meshes)}, polys={after_polys}")
print(f"  before: {before_count} meshes, {before_polys} polys")
print(f"  saved:  {len(deleted)} meshes ({sum(d[2] for d in deleted)} polys deleted)")
print(f"          {sum(b - a for _,_,b,a,r,_ in dec_log if r is not None and isinstance(r, float)) if dec_log else 0} polys decimated")

# ============================================================
# 报告
# ============================================================
lines = []
lines.append("# 进阶优化报告（further）")
lines.append("")
lines.append(f"- **源**：`mountain_culled.blend`（不动）")
lines.append(f"- **输出**：`mountain_further.blend`")
lines.append("")
lines.append("## 总览")
lines.append("")
lines.append(f"| 指标 | 之前 | 之后 | 变化 |")
lines.append(f"|---|---:|---:|---:|")
lines.append(f"| Mesh 数 | {before_count} | {len(after_meshes)} | -{before_count - len(after_meshes)} |")
lines.append(f"| 多边形数 | {before_polys} | {after_polys} | **-{before_polys - after_polys}** ({(before_polys - after_polys)/before_polys*100:.1f}%) |")
lines.append("")

if deleted:
    lines.append("## 1. 删除（建筑破损碎混凝土）")
    lines.append("")
    lines.append("> 关键词：`concrete inner` —— 这是倒塌建筑里的碎混凝土块，sonar 扫上去和实墙差不多，几何细节纯浪费。")
    lines.append("")
    lines.append("| 对象 | 原名 | 删除多边形 |")
    lines.append("|---|---|---:|")
    for n, orig, p in deleted:
        lines.append(f"| `{n}` | `{orig}` | {p} |")
    lines.append("")

lines.append("## 2. Decimate（保守 ratio，use_collapse_triangulate=True）")
lines.append("")
lines.append("### 建筑")
lines.append("")
lines.append("| 规则 | Ratio | 说明 |")
lines.append("|---|---|---|")
for substr, ratio, reason in BUILDING_RULES:
    lines.append(f"| `*{substr}*` | {ratio:.2f} | {reason} |")
lines.append("")
lines.append("### 信号塔")
lines.append("")
lines.append(f"- **跳过**（卫星锅候选 + 小件）：原名含 `Cone` 或 `Referement`，或 polys < {ANTENNA_MIN_POLY}")
lines.append(f"- **激进**（非卫星锅大件）：ratio = {ANTENNA_RATIO}")
lines.append("")
lines.append("### 详表")
lines.append("")
lines.append("| 对象 | 原名 | poly b→a | ratio | 说明 |")
lines.append("|---|---|---|---:|---|")
for name, orig, b, a, ratio, reason in sorted(dec_log, key=lambda x: -(x[2]-x[3] if x[4] is not None and isinstance(x[4], float) else 0)):
    ratio_str = f"{ratio:.2f}" if isinstance(ratio, float) else "—"
    lines.append(f"| `{name}` | `{orig}` | {b}→{a} | {ratio_str} | {reason} |")
lines.append("")

lines.append("## 3. 卫星锅保护说明")
lines.append("")
lines.append("**没有动**的 antenna 部件，按原名分类：")
lines.append("")
skipped_dish = [(n, o, b) for n, o, b, a, r, _ in dec_log if not isinstance(r, float)]
small_skipped = []
for o in after_meshes:
    if not o.name.startswith("R_antenna_"): continue
    orig = o.get("original_name", o.name)
    polys = len(o.data.polygons)
    matched_in_log = any(name == o.name for name, *_ in dec_log)
    if not matched_in_log and polys < ANTENNA_MIN_POLY:
        small_skipped.append((o.name, orig, polys))

if skipped_dish:
    lines.append("**A. 卫星锅候选（强制保留）**：")
    lines.append("")
    lines.append("| 对象 | 原名 | poly |")
    lines.append("|---|---|---:|")
    for n, orig, polys in skipped_dish:
        lines.append(f"| `{n}` | `{orig}` | {polys} |")
    lines.append("")

if small_skipped:
    lines.append(f"**B. 小件（< {ANTENNA_MIN_POLY} poly，动不动都差不多）**：共 {len(small_skipped)} 个，略。")
    lines.append("")

lines.append("## 4. 下一步")
lines.append("")
lines.append("1. 打开 `mountain_further.blend` 在 Blender 里目视核验：")
lines.append("   - 卫星锅完整无变形")
lines.append("   - 建筑外壳轮廓还认得出")
lines.append("   - 没有出现奇怪的拓扑撕裂")
lines.append("2. File → Export → glTF 2.0 → `content/levels/earth_return_01/scene.glb`")
lines.append("3. 架构师跑 `cargo run --release --bin glb_inspect ...` 校验")
lines.append("")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"[REPORT] {REPORT}")
