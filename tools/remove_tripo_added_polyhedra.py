from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


ROOT = Path(r"C:\Users\ROG\Desktop\GameJam")
GLB = ROOT / "_temp_Blender" / "muddy_man_by_tripo.glb"


def import_glb() -> bpy.types.Object:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.import_scene.gltf(filepath=str(GLB))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(f"Expected one mesh, found {len(meshes)}")
    return meshes[0]


def remove_added_face_blocks(obj: bpy.types.Object) -> int:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    remove_faces = []
    for face in bm.faces:
        c = obj.matrix_world @ face.calc_center_median()
        # These boxes match only the deliberately added floating/polyhedral mud blocks
        # around the head. They leave the existing body and slanted leg cut untouched.
        is_front_block = -0.314 <= c.y <= -0.150 and 0.48 <= c.z <= 0.67
        is_back_block = 0.140 <= c.y <= 0.285 and 0.49 <= c.z <= 0.67
        is_left_side_block = -0.090 <= c.x <= -0.030 and -0.100 <= c.y <= 0.065 and 0.52 <= c.z <= 0.67
        is_right_side_block = 0.050 <= c.x <= 0.100 and -0.095 <= c.y <= 0.085 and 0.50 <= c.z <= 0.66
        if is_front_block or is_back_block or is_left_side_block or is_right_side_block:
            remove_faces.append(face)

    bmesh.ops.delete(bm, geom=remove_faces, context="FACES")
    removed = len(remove_faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return removed


def export_glb(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=str(GLB),
        export_format="GLB",
        use_selection=True,
        export_materials="EXPORT",
        export_animations=False,
    )


obj = import_glb()
removed = remove_added_face_blocks(obj)
tris = sum(max(1, len(poly.vertices) - 2) for poly in obj.data.polygons)
coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
mn = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
mx = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
print(
    f"Removed added polyhedra faces={removed}; remaining tris={tris}; "
    f"min=({mn.x:.3f},{mn.y:.3f},{mn.z:.3f}) max=({mx.x:.3f},{mx.y:.3f},{mx.z:.3f})"
)
export_glb(obj)
