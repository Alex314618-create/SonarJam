"""
inflate_c.py — 把所有 C_ mesh 沿法向膨胀 1cm，确保永远在 R_ 外侧。

原因：
  - C_ 大多从 R_ 复制 + decimate 得来，顶点位置和 R_ 几近重合
  - 声呐 raycast 时 z-fight，有时打到 R_（被 depth 挡，无点云），有时打到 C_
  - 结果：扫描覆盖斑驳、有空洞
  - 解法：每个 C_ 顶点 += vertex.normal * 0.01 → 整体向外膨胀 1cm

实现细节：
  - 用 bmesh（background 模式更稳）
  - 先 recalc_face_normals(faces) 修正翻面
  - 再每个 vert += normal * INFLATE
  - 这样即使有少数翻面顶点，整体形状仍向外膨胀
"""
import bpy, bmesh, os

ROOT = r"C:\Users\ROG\Desktop\GameJam"
SRC       = os.path.join(ROOT, "_temp_Blender", "我的工作区", "mountain_final.blend")
DST_BLEND = SRC
DST_GLB   = os.path.join(ROOT, "content", "levels", "earth_return_01", "scene.glb")

INFLATE = 0.01  # 1cm 沿法向外推

bpy.ops.wm.open_mainfile(filepath=SRC)

c_objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("C_")]
print(f"[INFLATE] 对 {len(c_objs)} 个 C_ mesh 沿法向 +{INFLATE*100:.1f}cm")

ok = 0
fail = 0
for obj in c_objs:
    try:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        # 修法向（朝外）
        if len(bm.faces) > 0:
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.normal_update()
        # 沿顶点法向外推
        for v in bm.verts:
            v.co = v.co + v.normal * INFLATE
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        ok += 1
    except Exception as e:
        print(f"  [WARN] {obj.name}: {e}")
        fail += 1

print(f"  成功 {ok}, 失败 {fail}")

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
