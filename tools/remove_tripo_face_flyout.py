from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


ROOT = Path(r"C:\Users\ROG\Desktop\GameJam")
GLB = ROOT / "_temp_Blender" / "muddy_man_by_tripo.glb"


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=str(GLB))

obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
bm = bmesh.new()
bm.from_mesh(obj.data)
bm.faces.ensure_lookup_table()

remove_faces = []
for face in bm.faces:
    c = obj.matrix_world @ face.calc_center_median()
    # Remove only the head-area protruding patches that came from the added face-cover blobs.
    # Keep the central head/body mass and the existing slanted leg cut unchanged.
    front_flyout = c.z > 0.37 and c.y < -0.112
    back_flyout = c.z > 0.36 and c.y > 0.112
    left_flyout = c.z > 0.38 and c.x < -0.078
    right_flyout = c.z > 0.50 and c.x > 0.082
    if front_flyout or back_flyout or left_flyout or right_flyout:
        remove_faces.append(face)

bmesh.ops.delete(bm, geom=remove_faces, context="FACES")
removed = len(remove_faces)
bm.to_mesh(obj.data)
bm.free()
obj.data.update()

bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

tris = sum(max(1, len(poly.vertices) - 2) for poly in obj.data.polygons)
coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
mn = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
mx = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
print(
    f"Removed face flyout faces={removed}; remaining tris={tris}; "
    f"min=({mn.x:.3f},{mn.y:.3f},{mn.z:.3f}) max=({mx.x:.3f},{mx.y:.3f},{mx.z:.3f})"
)

bpy.ops.export_scene.gltf(
    filepath=str(GLB),
    export_format="GLB",
    use_selection=True,
    export_materials="EXPORT",
    export_animations=False,
)
