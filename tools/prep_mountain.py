"""
prep_mountain.py — 一次性把 MAP/1K.glb 处理成可手工建 C_ 的中间 .blend

Pipeline:
  1. import MAP/1K.glb  (untouched source)
  2. decimate 5 块石头 (material='pierre') -> ratio 0.1
  3. run normalize_mountain_naming.main()  -> 重命名 R_*, 删 skydome
  4. save as _temp_Blender/mountain_prep.blend

不重导 GLB —— 由用户在 Blender GUI 加完 C_ 后手动 Export。
"""
import bpy, sys, os, importlib.util

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC_GLB = os.path.join(ROOT, "MAP", "1K.glb")
OUT_BLEND = os.path.join(ROOT, "_temp_Blender", "mountain_prep.blend")
NORMALIZE_PY = os.path.join(ROOT, "tools", "normalize_mountain_naming.py")
ROCK_RATIO = 0.1

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)

# ---- 1. import GLB ----
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
print(f"[IMPORT] {SRC_GLB}")

# ---- 2. decimate rocks (material 'pierre') ----
rocks = []
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    for slot in obj.material_slots:
        if slot.material and slot.material.name == 'pierre':
            rocks.append(obj); break

print(f"\n[DECIMATE] 找到 {len(rocks)} 块石头, ratio={ROCK_RATIO}")
total_before = total_after = 0
for o in rocks:
    bpy.context.view_layer.objects.active = o
    before = len(o.data.polygons)
    mod = o.modifiers.new(name='dec', type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = ROCK_RATIO
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier='dec')
    after = len(o.data.polygons)
    total_before += before; total_after += after
    print(f"  {o.name:<48s}  {before:>7d} -> {after:>6d}")

print(f"  TOTAL: {total_before} -> {total_after}  (saved {total_before-total_after})")

# ---- 3. normalize naming + drop skydome ----
print("\n[NORMALIZE]")
spec = importlib.util.spec_from_file_location("normalize", NORMALIZE_PY)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.main()

# ---- 4. save .blend ----
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"\n[SAVED] {OUT_BLEND}")

# final summary
total_polys = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
r_count = sum(1 for o in bpy.data.objects if o.name.startswith('R_'))
c_count = sum(1 for o in bpy.data.objects if o.name.startswith('C_'))
print(f"\n[SUMMARY] meshes={r_count+c_count}, total polys={total_polys}, R_={r_count}, C_={c_count} (手建)")
