"""
fix_nature_positions.py — 修 12345 里 trees/rocks/grass 位置错乱。

原因：build_12345.py 在 libraries.load 时没解父保留变换，父链 FBX 缩放丢失。

修法：
  1. 打开 mountain_mine，对每个 R_trees/rocks/grass mesh:
     parent_clear keep_transform + transform_apply (location+rotation+scale 全烘到 mesh data)
  2. 删其他对象，存 TEMP 干净 .blend
  3. 打开 mountain_12345，删现有破 R_trees/rocks/grass
  4. append TEMP 的干净版本
  5. 保存 + 重导出 GLB
"""
import bpy, os, mathutils

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC_12345 = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_12345.blend")
SRC_MINE  = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_mine.blend")
DST_BLEND = SRC_12345
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene_12345.glb")
TEMP      = os.path.join(ROOT, "_temp_Blender", "_nature_clean.blend")

PREFIXES = ("R_trees_", "R_rocks_", "R_grass_")

# === STEP 1: 在 mountain_mine 里把 R_trees/rocks/grass 烘世界变换 ===
bpy.ops.wm.open_mainfile(filepath=SRC_MINE)

targets = [o.name for o in bpy.data.objects
           if o.type == 'MESH' and any(o.name.startswith(p) for p in PREFIXES)]
print(f"[STEP1] mountain_mine 里 R_trees/rocks/grass: {targets}")

# 显示原始 world bbox 做参照
print(f"\n  原始世界 bbox（用 matrix_world）:")
for n in targets:
    o = bpy.data.objects[n]
    pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (mn+mx)/2; s = mx-mn
    print(f"    {n}: center=({c.x:.2f},{c.y:.2f},{c.z:.2f}) size=({s.x:.2f},{s.y:.2f},{s.z:.2f})")

# 对每个 target：parent_clear keep_transform + transform_apply 烘到 mesh data
for n in targets:
    obj = bpy.data.objects[n]
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if obj.parent is not None:
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    try:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    except Exception as e:
        print(f"  [WARN] {n} transform_apply: {e}")

# 删其他对象
for o in list(bpy.data.objects):
    if o.name not in targets:
        bpy.data.objects.remove(o, do_unlink=True)

# 验证烘完后的 bbox (应该 = 原来的)
print(f"\n  烘完世界 bbox:")
for n in targets:
    o = bpy.data.objects[n]
    pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (mn+mx)/2; s = mx-mn
    print(f"    {n}: center=({c.x:.2f},{c.y:.2f},{c.z:.2f}) size=({s.x:.2f},{s.y:.2f},{s.z:.2f})")

bpy.ops.wm.save_as_mainfile(filepath=TEMP)
print(f"\n  暂存 {TEMP}")

# === STEP 2: 打开 12345，删现有破的 R_trees/rocks/grass ===
bpy.ops.wm.open_mainfile(filepath=SRC_12345)
removed = []
for o in list(bpy.data.objects):
    if o.type == 'MESH' and any(o.name.startswith(p) for p in PREFIXES):
        removed.append(o.name)
        bpy.data.objects.remove(o, do_unlink=True)
print(f"\n[STEP2] 删 {len(removed)} 个破的 R_trees/rocks/grass")

# === STEP 3: append 干净版 ===
with bpy.data.libraries.load(TEMP, link=False) as (data_from, data_to):
    data_to.objects = list(data_from.objects)
appended = 0
for o in data_to.objects:
    if o is not None:
        bpy.context.collection.objects.link(o)
        appended += 1
print(f"[STEP3] append {appended} 个干净 R_trees/rocks/grass")

# 验证新位置
print(f"\n  append 后 12345 里位置:")
for o in bpy.data.objects:
    if o.type == 'MESH' and any(o.name.startswith(p) for p in PREFIXES):
        pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
        mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        c = (mn+mx)/2; s = mx-mn
        print(f"    {o.name}: center=({c.x:.2f},{c.y:.2f},{c.z:.2f}) size=({s.x:.2f},{s.y:.2f},{s.z:.2f})")

# 清 TEMP
try:
    os.remove(TEMP)
    bk = TEMP + "1"
    if os.path.exists(bk): os.remove(bk)
except: pass

# === STEP 4: 保存 + 导出 ===
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
sz = os.path.getsize(DST_GLB)
print(f"\n[SAVED .blend] {DST_BLEND}")
print(f"[SAVED .glb]   {DST_GLB}  ({sz/1024/1024:.2f} MB)")
