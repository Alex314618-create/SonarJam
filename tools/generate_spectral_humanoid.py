"""
Blender Python script: generate a 2-meter low-poly spectral humanoid
as one continuous mesh.

Intent:
    - Original eerie connected humanoid mesh
    - No top tether / head strand
    - Single mesh body generated from a mirrored edge skeleton + skin
    - More cohesive than primitive kitbash geometry

Usage:
    1. Open Blender
    2. Switch to Scripting
    3. Open this file
    4. Run
"""

import bpy
from mathutils import Vector


COLLECTION_NAME = "SpectralFigure"
OBJECT_NAME = "SpectralHumanoid"


def ensure_collection(name: str) -> bpy.types.Collection:
    existing = bpy.data.collections.get(name)
    if existing is not None:
        return existing
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def clear_collection(col: bpy.types.Collection) -> None:
    for obj in list(col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def unlink_from_all(obj: bpy.types.Object) -> None:
    for c in list(obj.users_collection):
        c.objects.unlink(obj)


def make_tar_material() -> bpy.types.Material:
    name = "MAT_SpectralTar"
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (500, 0)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (180, 80)
    principled.inputs["Base Color"].default_value = (0.015, 0.018, 0.022, 1.0)
    principled.inputs["Roughness"].default_value = 0.86
    principled.inputs["Specular IOR Level"].default_value = 0.18

    emission = nodes.new("ShaderNodeEmission")
    emission.location = (180, -140)
    emission.inputs["Color"].default_value = (0.06, 0.08, 0.10, 1.0)
    emission.inputs["Strength"].default_value = 0.35

    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-420, -20)
    noise.inputs["Scale"].default_value = 4.8
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.58

    musgrave = nodes.new("ShaderNodeTexMusgrave")
    musgrave.location = (-420, 180)
    musgrave.inputs["Scale"].default_value = 8.0
    musgrave.inputs["Detail"].default_value = 6.0

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-180, 0)
    ramp.color_ramp.elements[0].position = 0.38
    ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (0.28, 0.36, 0.40, 1.0)

    bump = nodes.new("ShaderNodeBump")
    bump.location = (-180, 180)
    bump.inputs["Strength"].default_value = 0.10
    bump.inputs["Distance"].default_value = 0.05

    mix = nodes.new("ShaderNodeMixShader")
    mix.location = (360, 0)

    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(musgrave.outputs["Fac"], bump.inputs["Height"])
    links.new(ramp.outputs["Color"], mix.inputs["Fac"])
    links.new(principled.outputs["BSDF"], mix.inputs[1])
    links.new(emission.outputs["Emission"], mix.inputs[2])
    links.new(bump.outputs["Normal"], principled.inputs["Normal"])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])

    return mat


def build_edge_skeleton_object(col: bpy.types.Collection) -> bpy.types.Object:
    """
    Create only the positive-X half plus centerline.
    Mirror modifier will generate the opposite side.
    """
    mesh = bpy.data.meshes.new(f"{OBJECT_NAME}_mesh")
    obj = bpy.data.objects.new(OBJECT_NAME, mesh)
    unlink_from_all(obj)
    col.objects.link(obj)

    # connected edge skeleton for a slumped, elongated humanoid
    verts = [
        (0.000, 0.000, 0.98),  # 0 pelvis
        (0.000, 0.010, 1.18),  # 1 lower spine
        (0.000, 0.025, 1.42),  # 2 upper spine
        (0.000, 0.040, 1.63),  # 3 chest
        (0.000, 0.045, 1.80),  # 4 neck
        (0.000, 0.055, 1.94),  # 5 head
        (0.000, 0.020, 2.08),  # 6 crown

        (0.170, 0.020, 1.58),  # 7 shoulder
        (0.270, 0.060, 1.42),  # 8 upper arm
        (0.340, 0.105, 1.15),  # 9 elbow
        (0.360, 0.130, 0.82),  # 10 wrist
        (0.340, 0.185, 0.58),  # 11 hand tip

        (0.105, 0.005, 0.96),  # 12 hip
        (0.120, 0.020, 0.74),  # 13 thigh
        (0.135, 0.045, 0.48),  # 14 knee
        (0.135, 0.070, 0.16),  # 15 ankle
        (0.150, 0.205, 0.02),  # 16 toe

        (0.115, -0.030, 1.52), # 17 rib flare
        (0.110, -0.035, 1.05), # 18 hip flare
        (0.090, 0.120, 1.92),  # 19 jaw / face volume
        (0.070, -0.010, 1.72), # 20 throat / collar swell
    ]

    edges = [
        (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6),
        (3, 7), (7, 8), (8, 9), (9, 10), (10, 11),
        (0, 12), (12, 13), (13, 14), (14, 15), (15, 16),
        (2, 17), (0, 18), (5, 19), (4, 20),
    ]

    mesh.from_pydata(verts, edges, [])
    mesh.update()
    return obj


def apply_skin_and_mirror(obj: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    skin = obj.modifiers.new("Skin", "SKIN")
    mirror = obj.modifiers.new("Mirror", "MIRROR")
    mirror.use_axis[0] = True
    mirror.use_axis[1] = False
    mirror.use_axis[2] = False
    mirror.use_clip = True
    mirror.merge_threshold = 0.001

    # initialize skin data
    bpy.ops.object.mode_set(mode="OBJECT")
    data = obj.data.skin_vertices[0].data
    radii = {
        0: 0.115,
        1: 0.108,
        2: 0.122,
        3: 0.155,
        4: 0.060,
        5: 0.105,
        6: 0.055,
        7: 0.090,
        8: 0.078,
        9: 0.060,
        10: 0.042,
        11: 0.030,
        12: 0.082,
        13: 0.074,
        14: 0.060,
        15: 0.043,
        16: 0.028,
        17: 0.070,
        18: 0.072,
        19: 0.052,
        20: 0.050,
    }
    for idx, v in enumerate(data):
        r = radii.get(idx, 0.05)
        v.radius = (r, r)

    try:
        skin.branch_smoothing = 0.35
    except Exception:
        pass

    bpy.ops.object.modifier_apply(modifier=skin.name)
    bpy.ops.object.modifier_apply(modifier=mirror.name)
    obj.select_set(False)


def sculpt_connected_mesh(obj: bpy.types.Object) -> None:
    """
    Cheap procedural shape refinement after skin generation.
    The goal is to push the mesh away from "stick figure tubes"
    toward a more cohesive spectral body.
    """
    mesh = obj.data
    for v in mesh.vertices:
        x, y, z = v.co.x, v.co.y, v.co.z

        # global forward slump
        if z > 1.0:
            v.co.y += 0.025 * ((z - 1.0) / 1.0)

        # compress crown a little
        if z > 2.0:
            v.co.x *= 0.82
            v.co.y *= 0.95

        # flatten and hollow face slightly
        if 1.82 < z < 2.02 and abs(x) < 0.11 and y > 0.02:
            v.co.y -= 0.06

        # subtle chest hollow
        if 1.42 < z < 1.66 and abs(x) < 0.14 and y > 0.00:
            falloff = 1.0 - min(1.0, abs(x) / 0.14)
            v.co.y -= 0.06 * falloff

        # shoulder rounding
        if 1.48 < z < 1.68 and abs(x) > 0.12:
            v.co.z += 0.015
            v.co.y -= 0.01

        # narrow waist
        if 1.08 < z < 1.32:
            v.co.x *= 0.92

        # widen hips just a touch
        if 0.88 < z < 1.06:
            v.co.x *= 1.06
            v.co.y -= 0.01

        # bend arms inward slightly
        if 0.70 < z < 1.55 and abs(x) > 0.24:
            v.co.x *= 0.97
            v.co.y += 0.03

        # taper wrists/hands
        if z < 0.75 and abs(x) > 0.26:
            v.co.x *= 0.94

        # legs closer together below knee
        if z < 0.55 and abs(x) > 0.06:
            v.co.x *= 0.93

        # extend feet forward
        if z < 0.06 and y > 0.08:
            v.co.y += 0.05
            v.co.z -= 0.02

    mesh.update()


def clean_mesh(obj: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.0005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()
    obj.select_set(False)


def assign_material(obj: bpy.types.Object) -> None:
    mat = make_tar_material()
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.world.color = (0.01, 0.01, 0.015)


def main():
    col = ensure_collection(COLLECTION_NAME)
    clear_collection(col)
    obj = build_edge_skeleton_object(col)
    apply_skin_and_mirror(obj)
    sculpt_connected_mesh(obj)
    clean_mesh(obj)
    assign_material(obj)
    configure_scene()
    print("Generated connected spectral humanoid:", OBJECT_NAME)


if __name__ == "__main__":
    main()
