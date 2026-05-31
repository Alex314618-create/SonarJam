from __future__ import annotations

import math
import shutil
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(r"C:\Users\ROG\Desktop\GameJam")
BLEND_PATH = ROOT / "_temp_Blender" / "BT.blend"
BACKUP_PATH = ROOT / "_temp_Blender" / "BT_before_muddy_lowpoly.blend"


def remove_current_meshes(keep: bpy.types.Object | None = None) -> None:
    for obj in list(bpy.context.scene.objects):
        if obj.type == "MESH" and obj != keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def source_mesh_object() -> bpy.types.Object:
    candidates = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not candidates:
        raise RuntimeError("No mesh objects in source blend")
    return max(candidates, key=lambda obj: len(obj.data.polygons))


def world_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    mn = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    mx = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return mn, mx


def copy_upper_body(src: bpy.types.Object) -> bpy.types.Object:
    mn, mx = world_bounds(src)
    height = mx.z - mn.z
    cut_z = mn.z + height * 0.36
    keep_soft_z = cut_z + height * 0.05

    src_mesh = src.data
    new_verts: list[tuple[float, float, float]] = []
    vert_map: dict[int, int] = {}
    new_faces: list[list[int]] = []

    for poly in src_mesh.polygons:
        zs = [(src.matrix_world @ src_mesh.vertices[i].co).z for i in poly.vertices]
        if min(zs) < cut_z:
            continue
        face: list[int] = []
        for old_i in poly.vertices:
            if old_i not in vert_map:
                wp = src.matrix_world @ src_mesh.vertices[old_i].co
                if wp.z < keep_soft_z:
                    # Pull the severed lower edge into an uneven muddy skirt instead of a clean slice.
                    t = (keep_soft_z - wp.z) / max(keep_soft_z - cut_z, 0.001)
                    wp.z = cut_z + 0.035 * math.sin(wp.x * 31.0 + wp.y * 17.0) * t
                    wp.x *= 1.05 + 0.05 * t
                    wp.y *= 1.05 + 0.05 * t
                vert_map[old_i] = len(new_verts)
                new_verts.append(tuple(wp))
            face.append(vert_map[old_i])
        if len(face) >= 3:
            new_faces.append(face)

    mesh = bpy.data.meshes.new("BT_proto_mesh")
    mesh.from_pydata(new_verts, [], new_faces)
    mesh.update()
    obj = bpy.data.objects.new("BT_proto", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_mat(name: str, color: tuple[float, float, float, float], roughness: float, coat: float) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = 0.0
        if "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = coat
        if "Coat Roughness" in bsdf.inputs:
            bsdf.inputs["Coat Roughness"].default_value = 0.18
    return mat


def add_lumpy_blob(
    name: str,
    center: Vector,
    radius: Vector,
    rings: int,
    segments: int,
    phase: float,
    material: bpy.types.Material,
) -> bpy.types.Object:
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    def v(p: Vector) -> int:
        verts.append(tuple(p))
        return len(verts) - 1

    top = v(center + Vector((0, 0, radius.z)))
    bottom = v(center - Vector((0, 0, radius.z)))
    rows: list[list[int]] = []
    for r in range(1, rings):
        phi = math.pi * r / rings
        row: list[int] = []
        for s in range(segments):
            theta = math.tau * s / segments
            lump = 1.0 + 0.18 * math.sin(theta * 3.0 + phase) + 0.08 * math.cos(phi * 4.0 + theta)
            row.append(
                v(
                    Vector(
                        (
                            center.x + math.cos(theta) * math.sin(phi) * radius.x * lump,
                            center.y + math.sin(theta) * math.sin(phi) * radius.y * lump,
                            center.z + math.cos(phi) * radius.z * (1.0 + 0.08 * math.sin(theta + phase)),
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
    obj.data.materials.append(material)
    return obj


def add_mud_layers(body: bpy.types.Object, mud: bpy.types.Material) -> list[bpy.types.Object]:
    mn, mx = world_bounds(body)
    center = (mn + mx) * 0.5
    height = mx.z - mn.z
    width = mx.x - mn.x
    depth = mx.y - mn.y

    blobs: list[bpy.types.Object] = []
    # Mud skirt replaces legs/feet and hides the cut lower body.
    blobs.append(
        add_lumpy_blob(
            "BT_mud_skirt",
            Vector((center.x, center.y, mn.z + height * 0.08)),
            Vector((width * 0.34, depth * 0.62, height * 0.14)),
            5,
            10,
            0.7,
            mud,
        )
    )
    # Face-obscuring slabs and clods. These intentionally make facial features unreadable.
    blobs.extend(
        [
            add_lumpy_blob("BT_face_mud_front", Vector((center.x, mn.y - depth * 0.28, mx.z - height * 0.14)), Vector((width * 0.18, depth * 0.18, height * 0.10)), 4, 8, 1.4, mud),
            add_lumpy_blob("BT_face_mud_left", Vector((center.x - width * 0.08, mn.y - depth * 0.20, mx.z - height * 0.09)), Vector((width * 0.12, depth * 0.15, height * 0.08)), 4, 7, 2.1, mud),
            add_lumpy_blob("BT_chest_mud", Vector((center.x + width * 0.06, mn.y - depth * 0.22, mn.z + height * 0.58)), Vector((width * 0.20, depth * 0.20, height * 0.14)), 4, 8, 3.0, mud),
            add_lumpy_blob("BT_shoulder_mud_l", Vector((mn.x + width * 0.18, center.y, mn.z + height * 0.67)), Vector((width * 0.13, depth * 0.24, height * 0.10)), 4, 7, 4.2, mud),
            add_lumpy_blob("BT_shoulder_mud_r", Vector((mx.x - width * 0.18, center.y, mn.z + height * 0.66)), Vector((width * 0.13, depth * 0.24, height * 0.10)), 4, 7, 5.0, mud),
        ]
    )

    # Long vertical mud streaks attached to the torso.
    for i, xoff in enumerate([-0.15, -0.04, 0.08, 0.18]):
        blobs.append(
            add_lumpy_blob(
                f"BT_mud_drip_{i}",
                Vector((center.x + width * xoff, mn.y - depth * 0.27, mn.z + height * (0.32 + 0.08 * (i % 2)))),
                Vector((width * 0.045, depth * 0.06, height * 0.20)),
                4,
                6,
                i * 0.8,
                mud,
            )
        )
    return blobs


def join_objects(objects: list[bpy.types.Object], active: bpy.types.Object) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active
    bpy.ops.object.join()
    active.name = "BT_proto"
    active.data.name = "BT_proto_mesh"
    return active


def process_body(obj: bpy.types.Object, mud: bpy.types.Material) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(mud)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    displace_tex = bpy.data.textures.new("BT_mud_surface_noise", type="VORONOI")
    displace_tex.noise_scale = 0.42
    displace_tex.intensity = 0.35
    displace = obj.modifiers.new("muddy uneven surface", "DISPLACE")
    displace.strength = 0.018
    displace.texture = displace_tex
    bpy.ops.object.modifier_apply(modifier=displace.name)

    dec = obj.modifiers.new("low poly reduction", "DECIMATE")
    dec.ratio = 0.48
    dec.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=dec.name)

    bpy.ops.object.shade_flat()


def place_on_ground(obj: bpy.types.Object) -> None:
    mn, _ = world_bounds(obj)
    obj.location.z -= mn.z
    bpy.context.view_layer.update()


def final_lowpoly_pass(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    dec = obj.modifiers.new("final game low poly", "DECIMATE")
    dec.ratio = 0.13
    dec.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=dec.name)
    bpy.ops.object.shade_flat()


def main() -> None:
    if not BACKUP_PATH.exists():
        raise RuntimeError(f"Missing backup: {BACKUP_PATH}")

    shutil.copy2(BACKUP_PATH, BLEND_PATH)
    bpy.ops.wm.open_mainfile(filepath=str(BLEND_PATH))

    src = source_mesh_object()
    body = copy_upper_body(src)
    remove_current_meshes(keep=body)

    mud = make_mat("BT_wet_mud", (0.095, 0.062, 0.035, 1.0), roughness=0.34, coat=0.5)
    process_body(body, mud)
    blobs = add_mud_layers(body, mud)
    final = join_objects([body] + blobs, body)
    final_lowpoly_pass(final)
    place_on_ground(final)

    for obj in bpy.context.scene.objects:
        if obj.type == "EMPTY" and obj.name.startswith(("BT_Scanned", "ObjectCapture", "Geometry", "Materials")):
            bpy.data.objects.remove(obj, do_unlink=True)

    tri_count = sum(max(1, len(poly.vertices) - 2) for poly in final.data.polygons)
    mn, mx = world_bounds(final)
    print(
        f"Rebuilt {final.name}: verts={len(final.data.vertices)} polys={len(final.data.polygons)} "
        f"tris={tri_count} min={tuple(round(v, 3) for v in mn)} max={tuple(round(v, 3) for v in mx)}"
    )
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))


if __name__ == "__main__":
    main()
