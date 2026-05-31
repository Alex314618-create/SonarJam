"""检查 n1_rocket_block_a.original.glb 原生 bbox + 材质"""
import bpy, mathutils, os

GLB = r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\maps_54321\n1_rocket_block_a.original.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)

print(f"\n=== {os.path.basename(GLB)} ===\n")
print(f"Total objects: {len(bpy.data.objects)}")

# Bbox 整体
all_pts = []
mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH']
for o in mesh_objs:
    for v in o.bound_box:
        all_pts.append(o.matrix_world @ mathutils.Vector(v))
if all_pts:
    mn = mathutils.Vector((min(p.x for p in all_pts), min(p.y for p in all_pts), min(p.z for p in all_pts)))
    mx = mathutils.Vector((max(p.x for p in all_pts), max(p.y for p in all_pts), max(p.z for p in all_pts)))
    c = (mn+mx)/2; s = mx-mn
    print(f"Combined bbox: center=({c.x:.2f},{c.y:.2f},{c.z:.2f}) size=({s.x:.2f},{s.y:.2f},{s.z:.2f})")
    print(f"  min=({mn.x:.2f},{mn.y:.2f},{mn.z:.2f}) max=({mx.x:.2f},{mx.y:.2f},{mx.z:.2f})")

print(f"\nMesh 列表 ({len(mesh_objs)}):")
for o in mesh_objs:
    pts = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (mn+mx)/2; s = mx-mn
    polys = len(o.data.polygons)
    par = o.parent.name if o.parent else "—"
    mats = [m.material.name for m in o.material_slots if m.material]
    print(f"  {o.name:<32s} polys={polys:>5} center=({c.x:5.2f},{c.y:5.2f},{c.z:5.2f}) size=({s.x:.2f},{s.y:.2f},{s.z:.2f}) parent={par}")
    print(f"      mat={mats}")

print(f"\n材质 + 贴图:")
for mat in bpy.data.materials:
    if mat.name in ("Dots Stroke",): continue
    if not mat.use_nodes: continue
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf: continue
    bc = bsdf.inputs['Base Color']
    if bc.is_linked:
        src = bc.links[0].from_node
        if src.type == 'TEX_IMAGE' and src.image:
            print(f"  {mat.name}: IMG {src.image.name} ({src.image.size[0]}x{src.image.size[1]}) packed={bool(src.image.packed_file)}")
        else:
            print(f"  {mat.name}: linked but not IMG ({src.type})")
    else:
        bcv = tuple(round(v,2) for v in bc.default_value)
        print(f"  {mat.name}: const {bcv}")
