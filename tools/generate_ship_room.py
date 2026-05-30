"""
Blender Python script: assemble the ShipRoom opening cabin for SonarJam.

Run inside Blender:
    1. Open Blender
    2. Switch to Scripting workspace
    3. Open this file
    4. Run script

Result:
    - Scene: ShipRoom
    - Collections:
        * Render
        * Collision
        * Markers
        * Phantoms

This version assembles downloaded GLB assets and adds gameplay semantics:
    - imports the surveillance room and FPV goggles assets from tools/GLB
    - normalizes room height to 3m and goggles scale to human wearable size
    - places the goggles on the workbench as the interactable body-cam analogue
    - adds bright yellow screen glow planes, industrial work furniture, and markers
"""

import bpy
from math import radians
from mathutils import Vector
from pathlib import Path


SCENE_NAME = "ShipRoom"

COLLECTION_RENDER = "Render"
COLLECTION_COLLISION = "Collision"
COLLECTION_MARKERS = "Markers"
COLLECTION_PHANTOMS = "Phantoms"

ROOM_ASSET_PATH = Path(__file__).resolve().parent / "GLB" / "surveillance_room_scaled_3m.glb"
GOGGLES_ASSET_PATH = Path(__file__).resolve().parent / "GLB" / "tripo_fpv_dji_goggles_scaled_human_2m.glb"

ROOM_WIDTH = 6.0
ROOM_DEPTH = 4.0
ROOM_HEIGHT = 3.0
FLOOR_Y = 0.0
BENCH_X = 4.0
BENCH_Y = 1.0
BENCH_Z = 0.0
GOGGLES_X = 4.02
GOGGLES_Y = 1.06
GOGGLES_Z = 0.02


def rt(x: float, y: float, z: float) -> Vector:
    """
    Runtime coordinates are authored as (x, y=height, z=depth).
    Blender stays Z-up, so map them to (x, depth, height).
    """

    return Vector((x, z, y))


def purge_previous_generation() -> None:
    scene = bpy.data.scenes.get(SCENE_NAME)
    if scene is not None:
        bpy.data.scenes.remove(scene)
    try:
        bpy.ops.outliner.orphans_purge(do_recursive=True)
    except Exception:
        pass


def create_scene(name: str) -> bpy.types.Scene:
    scene = bpy.data.scenes.new(name)
    bpy.context.window.scene = scene
    return scene


def new_collection(scene: bpy.types.Scene, name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    scene.collection.children.link(collection)
    return collection


def unlink_from_all(obj: bpy.types.Object) -> None:
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)


def select_only(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_transform(obj: bpy.types.Object) -> None:
    select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def set_origin_to(obj: bpy.types.Object, location: Vector) -> None:
    cursor = bpy.context.scene.cursor
    previous = cursor.location.copy()
    cursor.location = location
    select_only(obj)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")
    cursor.location = previous


def create_cube(
    collection: bpy.types.Collection,
    name: str,
    location: Vector,
    size: Vector,
    rotation=(0.0, 0.0, 0.0),
    display_type: str = "TEXTURED",
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    if obj.data:
        obj.data.name = f"{name}_mesh"
    obj.scale = (size.x * 0.5, size.y * 0.5, size.z * 0.5)
    obj.display_type = display_type
    unlink_from_all(obj)
    collection.objects.link(obj)
    apply_transform(obj)
    return obj


def create_empty(
    collection: bpy.types.Collection,
    name: str,
    location: Vector,
    rotation=(0.0, 0.0, 0.0),
    display_type: str = "ARROWS",
    display_size: float = 0.6,
) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = display_type
    obj.empty_display_size = display_size
    obj.location = location
    obj.rotation_euler = rotation
    collection.objects.link(obj)
    return obj


def create_material(
    name: str,
    base_color: tuple[float, float, float, float],
    roughness: float = 0.55,
    metallic: float = 0.0,
    emission_color: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = (300.0, 0.0)
    shader = nodes.new(type="ShaderNodeBsdfPrincipled")
    shader.location = (0.0, 0.0)
    shader.inputs["Base Color"].default_value = base_color
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    if emission_color is not None:
        shader.inputs["Emission Color"].default_value = emission_color
        shader.inputs["Emission Strength"].default_value = emission_strength
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def assign_material(obj: bpy.types.Object, material: bpy.types.Material) -> None:
    if obj.type != "MESH":
        return
    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)


def assign_material_recursive(root: bpy.types.Object, material: bpy.types.Material) -> None:
    for obj in [root] + list(root.children_recursive):
        assign_material(obj, material)


def join_named_parts(collection: bpy.types.Collection, name: str, parts: list[bpy.types.Object]) -> bpy.types.Object:
    if not parts:
        raise ValueError(f"Cannot join empty part list for {name}")
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    if obj.data:
        obj.data.name = f"{name}_mesh"
    unlink_from_all(obj)
    collection.objects.link(obj)
    apply_transform(obj)
    return obj


def ensure_asset(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing asset: {path}")


def imported_meshes() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]


def rename_imported_sequence(objs: list[bpy.types.Object], prefix: str) -> None:
    for index, obj in enumerate(sorted(objs, key=lambda o: o.name)):
        obj.name = f"{prefix}_{index:02d}"
        if obj.data:
            obj.data.name = f"{obj.name}_mesh"


def import_glb(path: Path) -> list[bpy.types.Object]:
    ensure_asset(path)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.import_scene.gltf(filepath=str(path))
    return imported_meshes()


def bbox_world(objs: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    mins = Vector((10_000.0, 10_000.0, 10_000.0))
    maxs = Vector((-10_000.0, -10_000.0, -10_000.0))
    for obj in objs:
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            mins.x = min(mins.x, world.x)
            mins.y = min(mins.y, world.y)
            mins.z = min(mins.z, world.z)
            maxs.x = max(maxs.x, world.x)
            maxs.y = max(maxs.y, world.y)
            maxs.z = max(maxs.z, world.z)
    return mins, maxs


def group_objects(collection: bpy.types.Collection, name: str, objs: list[bpy.types.Object]) -> bpy.types.Object:
    group = bpy.data.objects.new(name, None)
    group.empty_display_type = "PLAIN_AXES"
    collection.objects.link(group)
    for obj in objs:
        unlink_from_all(obj)
        collection.objects.link(obj)
        obj.parent = group
    return group


def apply_to_hierarchy(root: bpy.types.Object) -> None:
    for obj in [root] + list(root.children_recursive):
        if obj.type == "MESH":
            apply_transform(obj)


def move_hierarchy(root: bpy.types.Object, delta: Vector) -> None:
    root.location += delta


def import_room_asset(render_col: bpy.types.Collection) -> bpy.types.Object:
    room_meshes = import_glb(ROOM_ASSET_PATH)
    rename_imported_sequence(room_meshes, "R_room_asset_part")
    room_root = group_objects(render_col, "R_room_asset", room_meshes)

    mins, maxs = bbox_world(room_meshes)
    room_dims = maxs - mins
    # Asset already normalized to 3m high, but keep the intent explicit.
    if room_dims.z > 0.001:
        room_root.scale = (ROOM_HEIGHT / room_dims.z, ROOM_HEIGHT / room_dims.z, ROOM_HEIGHT / room_dims.z)

    # Center horizontally and drop the lowest point to floor.
    mins, maxs = bbox_world(room_meshes)
    center_x = (mins.x + maxs.x) * 0.5
    center_y = (mins.y + maxs.y) * 0.5
    delta = Vector((2.0 - center_x, 0.0 - center_y, FLOOR_Y - mins.z))
    move_hierarchy(room_root, delta)

    room_tint = create_material(
        "MAT_room_tint",
        (0.36, 0.37, 0.40, 1.0),
        roughness=0.72,
        metallic=0.06,
    )
    for obj in room_meshes:
        if not obj.data.materials:
            assign_material(obj, room_tint)
    return room_root


def create_collision_shell(collision_col: bpy.types.Collection) -> None:
    create_cube(collision_col, "C_floor", rt(2.0, -0.06, 0.0), Vector((ROOM_WIDTH, ROOM_DEPTH, 0.12)), display_type="WIRE")
    create_cube(collision_col, "C_ceiling", rt(2.0, 3.06, 0.0), Vector((ROOM_WIDTH, ROOM_DEPTH, 0.12)), display_type="WIRE")
    create_cube(collision_col, "C_wall_west", rt(-1.11, 1.5, 0.0), Vector((0.22, ROOM_DEPTH + 0.02, ROOM_HEIGHT + 0.04)), display_type="WIRE")
    create_cube(collision_col, "C_wall_east", rt(5.11, 1.5, 0.0), Vector((0.22, ROOM_DEPTH + 0.02, ROOM_HEIGHT + 0.04)), display_type="WIRE")
    create_cube(collision_col, "C_wall_north", rt(2.0, 1.5, -2.11), Vector((ROOM_WIDTH + 0.02, 0.22, ROOM_HEIGHT + 0.04)), display_type="WIRE")
    create_cube(collision_col, "C_wall_south", rt(2.0, 1.5, 2.11), Vector((ROOM_WIDTH + 0.02, 0.22, ROOM_HEIGHT + 0.04)), display_type="WIRE")
    create_cube(collision_col, "C_door_panel_east", rt(4.95, 1.08, 0.15), Vector((0.12, 1.20, 2.10)), display_type="WIRE")


def build_workbench(render_col: bpy.types.Collection, collision_col: bpy.types.Collection) -> None:
    parts = [
        create_cube(render_col, "R_workbench_top_part", rt(BENCH_X, 0.96, BENCH_Z), Vector((1.50, 0.80, 0.08))),
        create_cube(render_col, "R_workbench_back_part", rt(BENCH_X, 0.58, -0.35), Vector((1.34, 0.05, 0.70))),
        create_cube(render_col, "R_workbench_shelf_part", rt(BENCH_X, 0.34, 0.04), Vector((1.10, 0.42, 0.06))),
        create_cube(render_col, "R_workbench_drawer_left", rt(3.55, 0.60, 0.28), Vector((0.28, 0.22, 0.24))),
        create_cube(render_col, "R_workbench_drawer_right", rt(4.45, 0.60, 0.28), Vector((0.28, 0.22, 0.24))),
        create_cube(render_col, "R_workbench_tower", rt(4.06, 0.28, -0.25), Vector((0.36, 0.52, 0.24))),
    ]
    for index, (x, z) in enumerate(((3.34, 0.31), (4.66, 0.31), (3.34, -0.31), (4.66, -0.31))):
        parts.append(create_cube(render_col, f"R_workbench_leg_{index:02d}", rt(x, 0.44, z), Vector((0.08, 0.88, 0.08))))
    for index, x in enumerate((3.55, 4.45)):
        parts.append(create_cube(render_col, f"R_workbench_pull_{index:02d}", rt(x, 0.66, 0.40), Vector((0.14, 0.03, 0.03))))
    bench = join_named_parts(render_col, "R_workbench", parts)
    assign_material(
        bench,
        create_material("MAT_workbench", (0.32, 0.33, 0.35, 1.0), roughness=0.64, metallic=0.16),
    )
    create_cube(collision_col, "C_workbench", rt(BENCH_X, 0.50, BENCH_Z), Vector((1.56, 1.04, 0.86)), display_type="WIRE")


def build_chair(render_col: bpy.types.Collection, collision_col: bpy.types.Collection) -> None:
    seat = create_cube(render_col, "R_chair_seat_part", rt(2.88, 0.52, -0.04), Vector((0.38, 0.08, 0.38)))
    back = create_cube(render_col, "R_chair_back_part", rt(2.64, 0.95, -0.04), Vector((0.10, 0.70, 0.46)))
    post = create_cube(render_col, "R_chair_post_part", rt(2.88, 0.28, -0.04), Vector((0.08, 0.40, 0.08)))
    base = create_cube(render_col, "R_chair_base_part", rt(2.88, 0.08, -0.04), Vector((0.48, 0.06, 0.48)))
    arm_l = create_cube(render_col, "R_chair_arm_left", rt(2.84, 0.66, 0.28), Vector((0.24, 0.05, 0.06)))
    arm_r = create_cube(render_col, "R_chair_arm_right", rt(2.84, 0.66, -0.36), Vector((0.24, 0.05, 0.06)))
    chair = join_named_parts(render_col, "R_chair", [seat, back, post, base, arm_l, arm_r])
    assign_material(
        chair,
        create_material("MAT_chair", (0.28, 0.27, 0.29, 1.0), roughness=0.58, metallic=0.12),
    )
    create_cube(collision_col, "C_chair", rt(2.84, 0.58, -0.04), Vector((0.70, 1.16, 0.86)), display_type="WIRE")


def build_lockers(render_col: bpy.types.Collection, collision_col: bpy.types.Collection) -> None:
    specs = (
        ("a", 0.22, 1.28),
        ("b", 0.92, 1.28),
        ("c", 1.62, 1.28),
    )
    for letter, x, z in specs:
        parts = [
            create_cube(render_col, f"R_locker_{letter}_body_part", rt(x, 1.19, z), Vector((0.54, 2.22, 0.70))),
            create_cube(render_col, f"R_locker_{letter}_door_part", rt(x, 1.20, z - 0.33), Vector((0.46, 2.06, 0.04))),
            create_cube(render_col, f"R_locker_{letter}_plinth_part", rt(x, 0.04, z), Vector((0.50, 0.08, 0.64))),
            create_cube(render_col, f"R_locker_{letter}_top_part", rt(x, 2.33, z), Vector((0.58, 0.06, 0.72))),
            create_cube(render_col, f"R_locker_{letter}_handle", rt(x + 0.14, 1.00, z - 0.35), Vector((0.03, 0.30, 0.03))),
        ]
        for idx, ox in enumerate((-0.10, 0.0, 0.10)):
            parts.append(create_cube(render_col, f"R_locker_{letter}_vent_{idx:02d}", rt(x + ox, 1.68, z - 0.35), Vector((0.12, 0.02, 0.02))))
        locker = join_named_parts(render_col, f"R_locker_{letter}", parts)
        assign_material(
            locker,
            create_material("MAT_locker", (0.34, 0.35, 0.37, 1.0), roughness=0.70, metallic=0.10),
        )
        create_cube(collision_col, f"C_locker_{letter}", rt(x, 1.17, z), Vector((0.58, 2.34, 0.74)), display_type="WIRE")


def build_console(render_col: bpy.types.Collection, collision_col: bpy.types.Collection) -> None:
    parts = [
        create_cube(render_col, "R_console_base_part", rt(1.05, 0.18, -1.54), Vector((1.72, 0.34, 0.56))),
        create_cube(render_col, "R_console_body_part", rt(1.05, 0.48, -1.54), Vector((1.18, 0.28, 0.42))),
        create_cube(render_col, "R_console_face_part", rt(1.05, 0.92, -1.64), Vector((1.62, 0.18, 0.88)), rotation=(radians(-18.0), 0.0, 0.0)),
        create_cube(render_col, "R_console_tray_part", rt(1.05, 0.46, -1.24), Vector((0.96, 0.10, 0.16))),
    ]
    for idx, (x, y, z) in enumerate(((0.56, 0.89, -1.49), (0.83, 0.92, -1.52), (1.08, 0.95, -1.53), (1.34, 0.92, -1.50), (1.56, 0.89, -1.46))):
        parts.append(create_cube(render_col, f"R_console_key_{idx:02d}", rt(x, y, z), Vector((0.10, 0.03, 0.06))))
    console = join_named_parts(render_col, "R_console", parts)
    assign_material(
        console,
        create_material("MAT_console", (0.24, 0.25, 0.27, 1.0), roughness=0.52, metallic=0.14),
    )
    create_cube(collision_col, "C_console", rt(1.05, 0.64, -1.54), Vector((1.78, 1.28, 0.88)), display_type="WIRE")


def build_pipe_and_door(render_col: bpy.types.Collection) -> None:
    metal = create_material("MAT_pipe_door", (0.30, 0.31, 0.33, 1.0), roughness=0.46, metallic=0.22)
    for obj in (
        create_cube(render_col, "R_pipe_a", rt(1.70, 2.80, -1.30), Vector((4.10, 0.16, 0.16))),
        create_cube(render_col, "R_pipe_b", rt(3.95, 2.72, 0.00), Vector((0.12, 0.12, 2.36))),
        create_cube(render_col, "R_door_frame_east", rt(4.98, 1.14, 0.15), Vector((0.12, 2.28, 1.40))),
        create_cube(render_col, "R_door_panel_east", rt(4.95, 1.08, 0.15), Vector((0.08, 2.04, 1.10))),
    ):
        assign_material(obj, metal)


def build_screen_glow(render_col: bpy.types.Collection) -> None:
    bezel = create_material("MAT_screen_bezel", (0.06, 0.06, 0.07, 1.0), roughness=0.48, metallic=0.22)
    glow = create_material(
        "MAT_screen_glow_yellow",
        (0.95, 0.78, 0.16, 1.0),
        roughness=0.12,
        metallic=0.0,
        emission_color=(1.0, 0.92, 0.18, 1.0),
        emission_strength=8.0,
    )
    screen_a = create_cube(render_col, "R_screen_a", rt(0.58, 1.92, -1.90), Vector((0.88, 0.48, 0.02)))
    screen_b = create_cube(render_col, "R_screen_b", rt(1.62, 1.94, -1.90), Vector((1.02, 0.54, 0.02)))
    glow_a = create_cube(render_col, "R_screen_a_glow", rt(0.58, 1.92, -1.87), Vector((0.84, 0.44, 0.02)))
    glow_b = create_cube(render_col, "R_screen_b_glow", rt(1.62, 1.94, -1.87), Vector((0.98, 0.50, 0.02)))
    assign_material(screen_a, bezel)
    assign_material(screen_b, bezel)
    assign_material(glow_a, glow)
    assign_material(glow_b, glow)


def import_goggles_asset(phantoms_col: bpy.types.Collection) -> bpy.types.Object:
    goggles_meshes = import_glb(GOGGLES_ASSET_PATH)
    rename_imported_sequence(goggles_meshes, "P_button_yellow_bodycam_part")
    root = group_objects(phantoms_col, "P_button_yellow_bodycam", goggles_meshes)

    mins, maxs = bbox_world(goggles_meshes)
    center_x = (mins.x + maxs.x) * 0.5
    center_y = (mins.y + maxs.y) * 0.5
    delta = Vector((GOGGLES_X - center_x, GOGGLES_Z - center_y, GOGGLES_Y - mins.z))
    move_hierarchy(root, delta)
    root.rotation_euler = (radians(4.0), radians(-12.0), radians(8.0))
    set_origin_to(root, rt(GOGGLES_X, GOGGLES_Y, GOGGLES_Z))
    assign_material_recursive(
        root,
        create_material(
            "MAT_bodycam_goggles",
            (0.34, 0.22, 0.22, 1.0),
            roughness=0.62,
            metallic=0.08,
        ),
    )
    return root


def build_goggle_shadow(render_col: bpy.types.Collection) -> None:
    shadow = create_cube(render_col, "R_bodycam_shadow", rt(GOGGLES_X - 0.03, 1.002, GOGGLES_Z + 0.02), Vector((0.26, 0.004, 0.18)))
    assign_material(
        shadow,
        create_material("MAT_bodycam_shadow", (0.18, 0.12, 0.12, 1.0), roughness=1.0, metallic=0.0),
    )


def build_markers(markers_col: bpy.types.Collection) -> None:
    create_empty(markers_col, "M_spawn_main", rt(0.0, 1.0, 0.0), display_size=0.8)
    create_empty(markers_col, "M_trigger_bodycam", rt(3.45, 1.0, 0.15), display_type="SPHERE", display_size=0.30)
    create_empty(markers_col, "M_screen_a", rt(0.58, 1.92, -1.86), display_type="CUBE", display_size=0.18)
    create_empty(markers_col, "M_screen_b", rt(1.62, 1.94, -1.86), display_type="CUBE", display_size=0.20)


def configure_scene(scene: bpy.types.Scene) -> None:
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = 60
    scene.world.color = (0.02, 0.018, 0.016)


def validate_scene() -> None:
    required_names = {
        "R_room_asset",
        "R_workbench",
        "R_chair",
        "R_locker_a",
        "R_locker_b",
        "R_locker_c",
        "R_console",
        "R_screen_a",
        "R_screen_b",
        "R_screen_a_glow",
        "R_screen_b_glow",
        "R_pipe_a",
        "R_pipe_b",
        "R_door_frame_east",
        "R_door_panel_east",
        "C_floor",
        "C_ceiling",
        "C_wall_north",
        "C_wall_south",
        "C_wall_east",
        "C_wall_west",
        "C_workbench",
        "C_chair",
        "C_locker_a",
        "C_locker_b",
        "C_locker_c",
        "C_console",
        "C_door_panel_east",
        "P_button_yellow_bodycam",
        "M_spawn_main",
        "M_trigger_bodycam",
        "M_screen_a",
        "M_screen_b",
    }
    missing = [name for name in sorted(required_names) if bpy.data.objects.get(name) is None]
    if missing:
        raise RuntimeError(f"Missing required objects: {', '.join(missing)}")


def main() -> None:
    purge_previous_generation()
    scene = create_scene(SCENE_NAME)

    render_col = new_collection(scene, COLLECTION_RENDER)
    collision_col = new_collection(scene, COLLECTION_COLLISION)
    markers_col = new_collection(scene, COLLECTION_MARKERS)
    phantoms_col = new_collection(scene, COLLECTION_PHANTOMS)

    import_room_asset(render_col)
    create_collision_shell(collision_col)
    build_workbench(render_col, collision_col)
    build_chair(render_col, collision_col)
    build_lockers(render_col, collision_col)
    build_console(render_col, collision_col)
    build_pipe_and_door(render_col)
    build_screen_glow(render_col)
    import_goggles_asset(phantoms_col)
    build_goggle_shadow(render_col)
    build_markers(markers_col)

    configure_scene(scene)
    validate_scene()
    print(f"Generated scene '{SCENE_NAME}'")


if __name__ == "__main__":
    main()
