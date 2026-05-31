from __future__ import annotations

import shutil
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


ROOT = Path(r"C:\Users\ROG\Desktop\GameJam")
OUT = ROOT / "_temp_Blender" / "muddy_man_by_tripo.glb"
SRC = ROOT / "_temp_Blender" / "muddy_man_by_tripo_before_slant_cut.glb"
BROKEN_BACKUP = ROOT / "_temp_Blender" / "muddy_man_by_tripo_face_deleted_bad.glb"


def import_source() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.import_scene.gltf(filepath=str(SRC))


def mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def join_meshes(objects: list[bpy.types.Object]) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = "muddy_man_by_tripo"
    obj.data.name = "muddy_man_by_tripo_mesh"
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return obj


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    mn = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
    mx = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    return mn, mx


def slant_cut_legs(obj: bpy.types.Object) -> None:
    mn, mx = bounds(obj)
    height = mx.z - mn.z
    mid_x = (mn.x + mx.x) * 0.5
    base_cut = mn.z + height * 0.43
    slope = height * 1.35

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    to_delete = []
    for v in bm.verts:
        wp = obj.matrix_world @ v.co
        plane_z = base_cut + (wp.x - mid_x) * slope
        if wp.z < plane_z:
            to_delete.append(v)
    bmesh.ops.delete(bm, geom=to_delete, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def decimate_lightly(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new("slant cut game reduction", "DECIMATE")
    mod.ratio = 0.018
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.shade_flat()


def ground(obj: bpy.types.Object) -> None:
    min_z = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
    for v in obj.data.vertices:
        v.co.z -= min_z
    obj.data.update()


def cleanup_scene() -> None:
    for obj in list(bpy.context.scene.objects):
        if obj.type in {"EMPTY", "CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)


def export(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=str(OUT),
        export_format="GLB",
        use_selection=True,
        export_materials="EXPORT",
        export_animations=False,
    )


def main() -> None:
    if not SRC.exists():
        raise RuntimeError(f"Missing original backup: {SRC}")
    if OUT.exists() and not BROKEN_BACKUP.exists():
        shutil.copy2(OUT, BROKEN_BACKUP)

    import_source()
    obj = join_meshes(mesh_objects())
    slant_cut_legs(obj)
    decimate_lightly(obj)
    ground(obj)
    cleanup_scene()

    tris = sum(max(1, len(poly.vertices) - 2) for poly in obj.data.polygons)
    mn, mx = bounds(obj)
    print(
        f"Rebuilt from original backup with face preserved: verts={len(obj.data.vertices)} "
        f"tris={tris} min=({mn.x:.3f},{mn.y:.3f},{mn.z:.3f}) max=({mx.x:.3f},{mx.y:.3f},{mx.z:.3f}) "
        f"materials={[slot.material.name if slot.material else None for slot in obj.material_slots]}"
    )
    export(obj)


if __name__ == "__main__":
    main()
