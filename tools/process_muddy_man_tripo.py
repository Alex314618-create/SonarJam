from __future__ import annotations

import math
import shutil
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


ROOT = Path(r"C:\Users\ROG\Desktop\GameJam")
SRC = ROOT / "_temp_Blender" / "muddy_man_by_tripo.glb"
BACKUP = ROOT / "_temp_Blender" / "muddy_man_by_tripo_before_slant_cut.glb"


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


def material() -> bpy.types.Material:
    mat = bpy.data.materials.get("BT_wet_mud") or bpy.data.materials.new("BT_wet_mud")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.095, 0.061, 0.035, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.36
        bsdf.inputs["Metallic"].default_value = 0.0
        if "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = 0.45
        if "Coat Roughness" in bsdf.inputs:
            bsdf.inputs["Coat Roughness"].default_value = 0.2
    return mat


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


def add_lumpy_blob(
    name: str,
    center: Vector,
    radius: Vector,
    rings: int,
    segments: int,
    phase: float,
    mat: bpy.types.Material,
) -> bpy.types.Object:
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    def add(p: Vector) -> int:
        verts.append(tuple(p))
        return len(verts) - 1

    top = add(center + Vector((0.0, 0.0, radius.z)))
    bottom = add(center - Vector((0.0, 0.0, radius.z)))
    rows: list[list[int]] = []
    for r in range(1, rings):
        phi = math.pi * r / rings
        row = []
        for s in range(segments):
            theta = math.tau * s / segments
            lump = 1.0 + 0.16 * math.sin(theta * 3.0 + phase) + 0.08 * math.cos(phi * 5.0 + theta)
            row.append(
                add(
                    Vector(
                        (
                            center.x + math.cos(theta) * math.sin(phi) * radius.x * lump,
                            center.y + math.sin(theta) * math.sin(phi) * radius.y * lump,
                            center.z + math.cos(phi) * radius.z * (1.0 + 0.05 * math.sin(theta + phase)),
                        )
                    )
                )
            )
        rows.append(row)

    for s in range(segments):
        faces.append((top, rows[0][s], rows[0][(s + 1) % segments]))
    for r in range(len(rows) - 1):
        for s in range(segments):
            faces.append((rows[r][s], rows[r + 1][s], rows[r + 1][(s + 1) % segments], rows[r][(s + 1) % segments]))
    for s in range(segments):
        faces.append((bottom, rows[-1][(s + 1) % segments], rows[-1][s]))

    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def add_face_mud(obj: bpy.types.Object, mat: bpy.types.Material) -> list[bpy.types.Object]:
    mn, mx = bounds(obj)
    center = (mn + mx) * 0.5
    height = mx.z - mn.z
    width = mx.x - mn.x
    depth = mx.y - mn.y
    head_z = mx.z - height * 0.12

    # Cover both likely front/back directions so the face is unreadable regardless of model orientation.
    return [
        add_lumpy_blob("face_mud_front", Vector((center.x, mn.y - depth * 0.05, head_z)), Vector((width * 0.24, depth * 0.20, height * 0.13)), 5, 9, 0.3, mat),
        add_lumpy_blob("face_mud_back", Vector((center.x, mx.y + depth * 0.05, head_z)), Vector((width * 0.22, depth * 0.18, height * 0.11)), 4, 8, 1.5, mat),
        add_lumpy_blob("face_mud_left", Vector((mn.x + width * 0.23, center.y, head_z + height * 0.02)), Vector((width * 0.12, depth * 0.22, height * 0.10)), 4, 7, 2.4, mat),
        add_lumpy_blob("face_mud_right", Vector((mx.x - width * 0.23, center.y, head_z - height * 0.01)), Vector((width * 0.12, depth * 0.22, height * 0.10)), 4, 7, 3.1, mat),
    ]


def join_all(objects: list[bpy.types.Object], active: bpy.types.Object) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active
    bpy.ops.object.join()
    active.name = "muddy_man_by_tripo"
    active.data.name = "muddy_man_by_tripo_mesh"
    return active


def decimate(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new("muddy low poly", "DECIMATE")
    mod.ratio = 0.018
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.shade_flat()


def ground(obj: bpy.types.Object) -> None:
    min_z = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
    for v in obj.data.vertices:
        v.co.z -= min_z
    obj.data.update()


def cleanup_scene(obj: bpy.types.Object) -> None:
    for scene_obj in list(bpy.context.scene.objects):
        if scene_obj.type in {"EMPTY", "CAMERA", "LIGHT"}:
            bpy.data.objects.remove(scene_obj, do_unlink=True)


def export(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=str(SRC),
        export_format="GLB",
        use_selection=True,
        export_materials="EXPORT",
        export_animations=False,
    )


def main() -> None:
    if not BACKUP.exists():
        shutil.copy2(SRC, BACKUP)

    import_source()
    obj = join_meshes(mesh_objects())
    mat = material()
    obj.data.materials.clear()
    obj.data.materials.append(mat)

    slant_cut_legs(obj)
    blobs = add_face_mud(obj, mat)
    obj = join_all([obj] + blobs, obj)
    decimate(obj)
    ground(obj)
    cleanup_scene(obj)

    tris = sum(max(1, len(poly.vertices) - 2) for poly in obj.data.polygons)
    mn, mx = bounds(obj)
    print(
        f"Processed muddy_man_by_tripo: verts={len(obj.data.vertices)} tris={tris} "
        f"min=({mn.x:.3f},{mn.y:.3f},{mn.z:.3f}) max=({mx.x:.3f},{mx.y:.3f},{mx.z:.3f})"
    )
    export(obj)


if __name__ == "__main__":
    main()
