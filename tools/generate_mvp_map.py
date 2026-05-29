"""
Blender Python script: generate one MVP-capable authored map for the sonar game.

Run inside Blender:
    1. Open Blender
    2. Switch to Scripting workspace
    3. Open this file
    4. Run script

Result:
    - Scene: MVPMap
    - Collections:
        * Render
        * Collision
        * Markers
        * Volumes

This version is intentionally more structured than a box pile:
    - connected rooms and corridors with actual openings
    - a strong anchor hub
    - service loop and upper reread loop
    - basic industrial dressing
    - stable sj_id / sj_kind metadata
"""

import bpy
from math import radians
from mathutils import Vector


SCENE_NAME = "MVPMap"
LEVEL_SLUG = "earth_return_01"

COLLECTION_RENDER = "Render"
COLLECTION_COLLISION = "Collision"
COLLECTION_MARKERS = "Markers"
COLLECTION_VOLUMES = "Volumes"

WALL = 0.35
FLOOR = 0.18
CEILING = 0.18
DOOR_HEIGHT = 2.5
FRAME_THICK = 0.12


def purge_previous_generation():
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
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    return col


def unlink_from_all(obj: bpy.types.Object) -> None:
    for col in list(obj.users_collection):
        col.objects.unlink(obj)


def set_semantics(obj: bpy.types.Object, sj_id: str, sj_kind: str) -> None:
    obj["sj_id"] = sj_id
    obj["sj_kind"] = sj_kind


def create_cube(
    collection: bpy.types.Collection,
    name: str,
    location: Vector,
    size: Vector,
    sj_id: str = None,
    sj_kind: str = None,
    display_type: str = "TEXTURED",
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    if obj.data:
        obj.data.name = f"{name}_mesh"
    obj.scale = (size.x * 0.5, size.y * 0.5, size.z * 0.5)
    obj.display_type = display_type
    unlink_from_all(obj)
    collection.objects.link(obj)
    if sj_id and sj_kind:
        set_semantics(obj, sj_id, sj_kind)
    return obj


def create_cylinder(
    collection: bpy.types.Collection,
    name: str,
    location: Vector,
    radius: float,
    depth: float,
    rotation=(0.0, 0.0, 0.0),
    vertices: int = 12,
    sj_id: str = None,
    sj_kind: str = None,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    if obj.data:
        obj.data.name = f"{name}_mesh"
    unlink_from_all(obj)
    collection.objects.link(obj)
    if sj_id and sj_kind:
        set_semantics(obj, sj_id, sj_kind)
    return obj


def create_empty(
    collection: bpy.types.Collection,
    name: str,
    location: Vector,
    sj_id: str,
    sj_kind: str,
    rotation=(0.0, 0.0, 0.0),
    display_type="ARROWS",
    display_size=0.75,
) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = display_type
    obj.empty_display_size = display_size
    obj.location = location
    obj.rotation_euler = rotation
    collection.objects.link(obj)
    set_semantics(obj, sj_id, sj_kind)
    return obj


def add_floor(render_col, collision_col, slug: str, center: Vector, size_xy: Vector, floor_z: float):
    loc = Vector((center.x, center.y, floor_z - FLOOR * 0.5))
    size = Vector((size_xy.x, size_xy.y, FLOOR))
    create_cube(
        render_col,
        f"R_{slug}_floor",
        loc,
        size,
        sj_id=f"map.{LEVEL_SLUG}.render.{slug}_floor",
        sj_kind="render_mesh",
    )
    create_cube(
        collision_col,
        f"C_{slug}_floor",
        loc,
        size,
        sj_id=f"map.{LEVEL_SLUG}.collision.{slug}_floor",
        sj_kind="collision_mesh",
        display_type="WIRE",
    )


def add_ceiling(render_col, slug: str, center: Vector, size_xy: Vector, ceiling_z: float):
    loc = Vector((center.x, center.y, ceiling_z + CEILING * 0.5))
    size = Vector((size_xy.x, size_xy.y, CEILING))
    create_cube(
        render_col,
        f"R_{slug}_ceiling",
        loc,
        size,
        sj_id=f"map.{LEVEL_SLUG}.render.{slug}_ceiling",
        sj_kind="render_mesh",
    )


def _opening_intervals(center_axis: float, span: float, openings):
    start = center_axis - span * 0.5
    end = center_axis + span * 0.5
    intervals = []
    for rel_center, width in openings:
        a = center_axis + rel_center - width * 0.5
        b = center_axis + rel_center + width * 0.5
        intervals.append((max(start, a), min(end, b)))
    intervals.sort(key=lambda x: x[0])
    return intervals


def add_door_frame_x(render_col, slug: str, side_slug: str, y: float, z_center: float, wall_height: float, open_start: float, open_end: float):
    frame_z = z_center - wall_height * 0.5 + DOOR_HEIGHT * 0.5
    post_z = frame_z
    post_size = Vector((FRAME_THICK, WALL + 0.06, DOOR_HEIGHT))
    left_x = open_start - FRAME_THICK * 0.5
    right_x = open_end + FRAME_THICK * 0.5
    create_cube(render_col, f"R_{slug}_{side_slug}_frame_l", Vector((left_x, y, post_z)), post_size)
    create_cube(render_col, f"R_{slug}_{side_slug}_frame_r", Vector((right_x, y, post_z)), post_size)
    lintel_height = max(0.18, wall_height - DOOR_HEIGHT)
    lintel_z = z_center + wall_height * 0.5 - lintel_height * 0.5
    create_cube(render_col, f"R_{slug}_{side_slug}_frame_top", Vector(((open_start + open_end) * 0.5, y, lintel_z)), Vector((open_end - open_start + FRAME_THICK * 2.0, WALL + 0.06, lintel_height)))


def add_door_frame_y(render_col, slug: str, side_slug: str, x: float, z_center: float, wall_height: float, open_start: float, open_end: float):
    frame_z = z_center - wall_height * 0.5 + DOOR_HEIGHT * 0.5
    post_size = Vector((WALL + 0.06, FRAME_THICK, DOOR_HEIGHT))
    low_y = open_start - FRAME_THICK * 0.5
    high_y = open_end + FRAME_THICK * 0.5
    create_cube(render_col, f"R_{slug}_{side_slug}_frame_l", Vector((x, low_y, frame_z)), post_size)
    create_cube(render_col, f"R_{slug}_{side_slug}_frame_r", Vector((x, high_y, frame_z)), post_size)
    lintel_height = max(0.18, wall_height - DOOR_HEIGHT)
    lintel_z = z_center + wall_height * 0.5 - lintel_height * 0.5
    create_cube(render_col, f"R_{slug}_{side_slug}_frame_top", Vector((x, (open_start + open_end) * 0.5, lintel_z)), Vector((WALL + 0.06, open_end - open_start + FRAME_THICK * 2.0, lintel_height)))


def add_wall_x(render_col, collision_col, slug: str, side_slug: str, center_x: float, y: float, z_center: float, span_x: float, height_z: float, openings):
    intervals = _opening_intervals(center_x, span_x, openings)
    cursor = center_x - span_x * 0.5
    for idx, (open_start, open_end) in enumerate(intervals):
        if open_start > cursor:
            seg_len = open_start - cursor
            seg_center = cursor + seg_len * 0.5
            size = Vector((seg_len, WALL, height_z))
            loc = Vector((seg_center, y, z_center))
            create_cube(render_col, f"R_{slug}_{side_slug}_{idx}", loc, size, sj_id=f"map.{LEVEL_SLUG}.render.{slug}_{side_slug}_{idx}", sj_kind="render_mesh")
            create_cube(collision_col, f"C_{slug}_{side_slug}_{idx}", loc, size, sj_id=f"map.{LEVEL_SLUG}.collision.{slug}_{side_slug}_{idx}", sj_kind="collision_mesh", display_type="WIRE")
        add_door_frame_x(render_col, slug, side_slug, y, z_center, height_z, open_start, open_end)
        cursor = open_end
    end = center_x + span_x * 0.5
    if end > cursor:
        seg_len = end - cursor
        seg_center = cursor + seg_len * 0.5
        size = Vector((seg_len, WALL, height_z))
        loc = Vector((seg_center, y, z_center))
        suffix = len(intervals)
        create_cube(render_col, f"R_{slug}_{side_slug}_{suffix}", loc, size, sj_id=f"map.{LEVEL_SLUG}.render.{slug}_{side_slug}_{suffix}", sj_kind="render_mesh")
        create_cube(collision_col, f"C_{slug}_{side_slug}_{suffix}", loc, size, sj_id=f"map.{LEVEL_SLUG}.collision.{slug}_{side_slug}_{suffix}", sj_kind="collision_mesh", display_type="WIRE")


def add_wall_y(render_col, collision_col, slug: str, side_slug: str, x: float, center_y: float, z_center: float, span_y: float, height_z: float, openings):
    intervals = _opening_intervals(center_y, span_y, openings)
    cursor = center_y - span_y * 0.5
    for idx, (open_start, open_end) in enumerate(intervals):
        if open_start > cursor:
            seg_len = open_start - cursor
            seg_center = cursor + seg_len * 0.5
            size = Vector((WALL, seg_len, height_z))
            loc = Vector((x, seg_center, z_center))
            create_cube(render_col, f"R_{slug}_{side_slug}_{idx}", loc, size, sj_id=f"map.{LEVEL_SLUG}.render.{slug}_{side_slug}_{idx}", sj_kind="render_mesh")
            create_cube(collision_col, f"C_{slug}_{side_slug}_{idx}", loc, size, sj_id=f"map.{LEVEL_SLUG}.collision.{slug}_{side_slug}_{idx}", sj_kind="collision_mesh", display_type="WIRE")
        add_door_frame_y(render_col, slug, side_slug, x, z_center, height_z, open_start, open_end)
        cursor = open_end
    end = center_y + span_y * 0.5
    if end > cursor:
        seg_len = end - cursor
        seg_center = cursor + seg_len * 0.5
        size = Vector((WALL, seg_len, height_z))
        loc = Vector((x, seg_center, z_center))
        suffix = len(intervals)
        create_cube(render_col, f"R_{slug}_{side_slug}_{suffix}", loc, size, sj_id=f"map.{LEVEL_SLUG}.render.{slug}_{side_slug}_{suffix}", sj_kind="render_mesh")
        create_cube(collision_col, f"C_{slug}_{side_slug}_{suffix}", loc, size, sj_id=f"map.{LEVEL_SLUG}.collision.{slug}_{side_slug}_{suffix}", sj_kind="collision_mesh", display_type="WIRE")


def add_room(
    render_col,
    collision_col,
    slug: str,
    center: Vector,
    size: Vector,
    openings=None,
    ceiling=True,
):
    if openings is None:
        openings = {}
    hx = size.x * 0.5
    hy = size.y * 0.5
    hz = size.z * 0.5
    floor_z = center.z - hz
    ceil_z = center.z + hz
    add_floor(render_col, collision_col, slug, center, Vector((size.x, size.y)), floor_z)
    if ceiling:
        add_ceiling(render_col, slug, center, Vector((size.x, size.y)), ceil_z)
    add_wall_x(render_col, collision_col, slug, "wall_north", center.x, center.y + hy + WALL * 0.5, center.z, size.x, size.z, openings.get("north", []))
    add_wall_x(render_col, collision_col, slug, "wall_south", center.x, center.y - hy - WALL * 0.5, center.z, size.x, size.z, openings.get("south", []))
    add_wall_y(render_col, collision_col, slug, "wall_east", center.x + hx + WALL * 0.5, center.y, center.z, size.y, size.z, openings.get("east", []))
    add_wall_y(render_col, collision_col, slug, "wall_west", center.x - hx - WALL * 0.5, center.y, center.z, size.y, size.z, openings.get("west", []))


def add_catwalk(render_col, collision_col, slug: str, center: Vector, size_xy: Vector, z: float):
    create_cube(render_col, f"R_{slug}_deck", Vector((center.x, center.y, z)), Vector((size_xy.x, size_xy.y, 0.15)), sj_id=f"map.{LEVEL_SLUG}.render.{slug}_deck", sj_kind="render_mesh")
    create_cube(collision_col, f"C_{slug}_deck", Vector((center.x, center.y, z)), Vector((size_xy.x, size_xy.y, 0.20)), sj_id=f"map.{LEVEL_SLUG}.collision.{slug}_deck", sj_kind="collision_mesh", display_type="WIRE")


def add_railing_strip(render_col, slug: str, center: Vector, size: Vector):
    create_cube(render_col, slug, center, size)


def add_catwalk_ring(render_col, collision_col):
    catwalks = [
        ("catwalk_north", Vector((0.0, 8.6, 6.2)), Vector((20.0, 1.4))),
        ("catwalk_south", Vector((0.0, -8.6, 6.2)), Vector((20.0, 1.4))),
        ("catwalk_east", Vector((10.4, 0.0, 6.2)), Vector((1.4, 15.8))),
        ("catwalk_west", Vector((-10.4, 0.0, 6.2)), Vector((1.4, 15.8))),
    ]
    for slug, center, size_xy in catwalks:
        add_catwalk(render_col, collision_col, slug, center, size_xy, center.z)

    # railings render only
    rails = [
        ("R_catwalk_north_rail_outer", Vector((0.0, 9.25, 6.85)), Vector((20.0, 0.12, 1.2))),
        ("R_catwalk_south_rail_outer", Vector((0.0, -9.25, 6.85)), Vector((20.0, 0.12, 1.2))),
        ("R_catwalk_east_rail_outer", Vector((11.05, 0.0, 6.85)), Vector((0.12, 15.8, 1.2))),
        ("R_catwalk_west_rail_outer", Vector((-11.05, 0.0, 6.85)), Vector((0.12, 15.8, 1.2))),
    ]
    for name, loc, size in rails:
        add_railing_strip(render_col, name, loc, size)

    # ramps
    ramps = [
        ("catwalk_ramp_sw", Vector((-8.8, -6.7, 3.35))),
        ("catwalk_ramp_se", Vector((8.8, -6.7, 3.35))),
    ]
    for slug, loc in ramps:
        r = create_cube(render_col, f"R_{slug}", loc, Vector((2.2, 6.5, 0.35)), sj_id=f"map.{LEVEL_SLUG}.render.{slug}", sj_kind="render_mesh")
        r.rotation_euler.x = radians(22.0)
        c = create_cube(collision_col, f"C_{slug}", loc, Vector((2.2, 6.5, 0.35)), sj_id=f"map.{LEVEL_SLUG}.collision.{slug}", sj_kind="collision_mesh", display_type="WIRE")
        c.rotation_euler.x = radians(22.0)


def add_industrial_dressing(render_col):
    # Airlock
    create_cube(render_col, "R_airlock_locker_bank", Vector((-41.2, 1.6, 1.2)), Vector((0.8, 2.2, 2.4)))
    create_cube(render_col, "R_airlock_console", Vector((-36.4, -1.5, 1.0)), Vector((1.0, 0.6, 2.0)))

    # Gallery ribs and duct
    for i, x in enumerate([-31.0, -27.0, -23.0, -19.0, -15.0]):
        create_cube(render_col, f"R_gallery_rib_{i:02d}", Vector((x, 0.0, 2.0)), Vector((0.18, 3.8, 4.0)))
    create_cube(render_col, "R_gallery_duct", Vector((-24.0, 0.0, 3.55)), Vector((22.0, 0.8, 0.6)))

    # Tank hall landmarks
    hall_tanks = [
        ("hall_tank_a", Vector((-6.0, 5.5, 2.6))),
        ("hall_tank_b", Vector((6.0, 5.5, 2.6))),
        ("hall_tank_c", Vector((-6.0, -5.5, 2.6))),
        ("hall_tank_d", Vector((6.0, -5.5, 2.6))),
    ]
    for slug, loc in hall_tanks:
        create_cylinder(render_col, f"R_{slug}", loc, radius=1.1, depth=5.2, sj_id=f"map.{LEVEL_SLUG}.render.{slug}", sj_kind="render_mesh")
    create_cube(render_col, "R_hall_bridge_grate", Vector((0.0, 0.0, 0.3)), Vector((5.0, 2.0, 0.2)))

    # Workshops
    workshop_props = [
        ("R_workshop_bench_a", Vector((15.2, 2.7, 0.8)), Vector((2.4, 0.8, 1.6))),
        ("R_workshop_bench_b", Vector((19.2, -2.8, 0.8)), Vector((2.8, 0.8, 1.6))),
        ("R_workshop_shelf_a", Vector((21.6, 3.2, 1.3)), Vector((0.6, 2.0, 2.6))),
        ("R_workshop_shelf_b", Vector((13.8, -3.0, 1.3)), Vector((0.6, 2.0, 2.6))),
        ("R_workshop_crates", Vector((17.4, 0.2, 0.9)), Vector((1.8, 1.6, 1.8))),
        ("R_workshop_ceiling_tray", Vector((18.0, 0.0, 4.3)), Vector((8.0, 0.45, 0.45))),
    ]
    for name, loc, size in workshop_props:
        create_cube(render_col, name, loc, size)

    # Quarters
    quarters_props = [
        ("R_quarters_bunk_a_low", Vector((-20.5, -8.0, 0.5)), Vector((2.4, 0.9, 0.6))),
        ("R_quarters_bunk_a_high", Vector((-20.5, -8.0, 1.5)), Vector((2.4, 0.9, 0.6))),
        ("R_quarters_bunk_b_low", Vector((-15.2, -11.4, 0.5)), Vector((2.4, 0.9, 0.6))),
        ("R_quarters_bunk_b_high", Vector((-15.2, -11.4, 1.5)), Vector((2.4, 0.9, 0.6))),
        ("R_quarters_lockers", Vector((-13.6, -8.0, 1.2)), Vector((0.8, 2.4, 2.4))),
        ("R_quarters_med_table", Vector((-17.8, -12.2, 0.75)), Vector((1.4, 0.8, 1.5))),
        ("R_quarters_partition", Vector((-18.0, -9.7, 1.5)), Vector((0.15, 4.6, 3.0))),
    ]
    for name, loc, size in quarters_props:
        create_cube(render_col, name, loc, size)

    # Pump room
    create_cylinder(render_col, "R_pump_core_a", Vector((-1.6, 22.0, 1.9)), radius=0.8, depth=3.8)
    create_cylinder(render_col, "R_pump_core_b", Vector((1.6, 22.0, 1.9)), radius=0.8, depth=3.8)
    create_cube(render_col, "R_pump_control_bank", Vector((0.0, 19.2, 1.2)), Vector((4.0, 0.8, 2.4)))
    create_cube(render_col, "R_pump_pipe_run", Vector((0.0, 24.0, 4.8)), Vector((7.0, 0.5, 0.5)))

    # Service loop
    for idx, x in enumerate([-12.0, -4.0, 4.0, 12.0]):
        create_cube(render_col, f"R_service_pipe_{idx:02d}", Vector((x, -22.0, 2.5)), Vector((0.4, 3.0, 0.4)))
    create_cube(render_col, "R_service_junction", Vector((18.0, -15.5, 1.2)), Vector((1.2, 0.8, 2.4)))


def build_map(render_col, collision_col, markers_col, volumes_col):
    # Core layout
    add_room(
        render_col, collision_col,
        "airlock",
        center=Vector((-40.0, 0.0, 2.0)),
        size=Vector((8.0, 6.0, 4.0)),
        openings={"east": [(0.0, 2.8)]},
    )
    add_room(
        render_col, collision_col,
        "sonar_gallery",
        center=Vector((-24.0, 0.0, 2.0)),
        size=Vector((24.0, 4.0, 4.0)),
        openings={
            "west": [(0.0, 2.8)],
            "east": [(0.0, 4.0)],
            "south": [(6.0, 2.6)],
        },
    )
    add_room(
        render_col, collision_col,
        "quarters_link",
        center=Vector((-18.0, -4.0, 2.0)),
        size=Vector((3.0, 4.0, 4.0)),
        openings={"north": [(0.0, 2.6)], "south": [(0.0, 2.6)]},
    )
    add_room(
        render_col, collision_col,
        "west_quarters",
        center=Vector((-18.0, -10.0, 2.5)),
        size=Vector((10.0, 8.0, 5.0)),
        openings={"north": [(0.0, 2.6)], "south": [(0.0, 2.6)]},
    )
    add_room(
        render_col, collision_col,
        "tank_hall",
        center=Vector((0.0, 0.0, 4.0)),
        size=Vector((24.0, 20.0, 8.0)),
        openings={
            "west": [(0.0, 4.0)],
            "east": [(0.0, 4.0)],
            "north": [(0.0, 4.0)],
            "south": [(0.0, 4.0)],
        },
        ceiling=False,
    )
    add_room(
        render_col, collision_col,
        "east_workshops",
        center=Vector((18.0, 0.0, 2.5)),
        size=Vector((12.0, 10.0, 5.0)),
        openings={"west": [(0.0, 4.0)], "south": [(0.0, 2.8)]},
    )
    add_room(
        render_col, collision_col,
        "north_link",
        center=Vector((0.0, 14.0, 3.0)),
        size=Vector((4.0, 8.0, 6.0)),
        openings={"south": [(0.0, 4.0)], "north": [(0.0, 3.2)]},
    )
    add_room(
        render_col, collision_col,
        "north_pump",
        center=Vector((0.0, 23.0, 3.0)),
        size=Vector((10.0, 10.0, 6.0)),
        openings={"south": [(0.0, 3.2)]},
    )
    add_room(
        render_col, collision_col,
        "south_link",
        center=Vector((0.0, -15.0, 2.0)),
        size=Vector((4.0, 10.0, 4.0)),
        openings={"north": [(0.0, 4.0)], "south": [(0.0, 3.0)]},
    )
    add_room(
        render_col, collision_col,
        "service_main",
        center=Vector((0.0, -22.0, 1.5)),
        size=Vector((40.0, 4.0, 3.0)),
        openings={"north": [(-18.0, 2.6), (0.0, 3.0), (18.0, 2.8)]},
    )
    add_room(
        render_col, collision_col,
        "service_branch_west",
        center=Vector((-18.0, -17.0, 1.5)),
        size=Vector((3.0, 6.0, 3.0)),
        openings={"north": [(0.0, 2.6)], "south": [(0.0, 2.6)]},
    )
    add_room(
        render_col, collision_col,
        "service_branch_east",
        center=Vector((18.0, -12.5, 1.5)),
        size=Vector((3.0, 15.0, 3.0)),
        openings={"north": [(0.0, 2.8)], "south": [(0.0, 2.8)]},
    )

    add_catwalk_ring(render_col, collision_col)
    add_industrial_dressing(render_col)

    # Markers
    create_empty(markers_col, "M_spawn_main", Vector((-40.0, 0.0, 1.0)), f"map.{LEVEL_SLUG}.marker.spawn_main", "marker_spawn")
    create_empty(markers_col, "M_reset_entry", Vector((-36.0, 0.0, 1.0)), f"map.{LEVEL_SLUG}.marker.reset_entry", "marker_reset")
    create_empty(markers_col, "M_reset_hub", Vector((0.0, -2.5, 1.0)), f"map.{LEVEL_SLUG}.marker.reset_hub", "marker_reset")
    create_empty(markers_col, "M_reset_north", Vector((0.0, 19.0, 1.0)), f"map.{LEVEL_SLUG}.marker.reset_north", "marker_reset")
    create_empty(markers_col, "M_trigger_gallery_exit", Vector((-12.5, 0.0, 1.0)), f"map.{LEVEL_SLUG}.marker.trigger_gallery_exit", "marker_trigger")
    create_empty(markers_col, "M_trigger_hub_arrival", Vector((-7.0, 0.0, 1.0)), f"map.{LEVEL_SLUG}.marker.trigger_hub_arrival", "marker_trigger")
    create_empty(markers_col, "M_trigger_service_loop", Vector((0.0, -21.0, 1.0)), f"map.{LEVEL_SLUG}.marker.trigger_service_loop", "marker_trigger")
    create_empty(markers_col, "M_echo_hint_tank_a", Vector((-6.0, 5.5, 1.0)), f"map.{LEVEL_SLUG}.marker.echo_hint_tank_a", "marker_echo")
    create_empty(markers_col, "M_echo_hint_service", Vector((12.0, -22.0, 1.0)), f"map.{LEVEL_SLUG}.marker.echo_hint_service", "marker_echo")
    create_empty(markers_col, "M_truth_edge_gallery", Vector((-22.0, 0.0, 1.0)), f"map.{LEVEL_SLUG}.marker.truth_edge_gallery", "marker_truth")
    create_empty(markers_col, "M_truth_edge_workshop", Vector((12.0, 2.0, 1.0)), f"map.{LEVEL_SLUG}.marker.truth_edge_workshop", "marker_truth")
    create_empty(markers_col, "M_end_escape", Vector((0.0, 26.0, 1.0)), f"map.{LEVEL_SLUG}.marker.end_escape", "marker_end")

    # Volumes
    create_cube(volumes_col, "V_bias_hall_core", Vector((0.0, 0.0, 3.0)), Vector((16.0, 14.0, 6.0)), f"map.{LEVEL_SLUG}.volume.bias_hall_core", "volume_bias", display_type="WIRE")
    create_cube(volumes_col, "V_bias_workshops", Vector((18.0, 0.0, 2.5)), Vector((7.0, 6.0, 4.0)), f"map.{LEVEL_SLUG}.volume.bias_workshops", "volume_bias", display_type="WIRE")
    create_cube(volumes_col, "V_truth_gallery", Vector((-22.0, 0.0, 1.5)), Vector((5.0, 3.0, 3.0)), f"map.{LEVEL_SLUG}.volume.truth_gallery", "volume_truth", display_type="WIRE")
    create_cube(volumes_col, "V_truth_quarters", Vector((-18.0, -10.0, 2.0)), Vector((4.0, 4.0, 3.0)), f"map.{LEVEL_SLUG}.volume.truth_quarters", "volume_truth", display_type="WIRE")
    create_cube(volumes_col, "V_trigger_echo_gate", Vector((0.0, 18.0, 1.5)), Vector((4.0, 4.0, 3.0)), f"map.{LEVEL_SLUG}.volume.trigger_echo_gate", "volume_trigger", display_type="WIRE")
    create_cube(volumes_col, "V_block_north_gate", Vector((0.0, 18.0, 1.75)), Vector((2.5, 1.0, 3.5)), f"map.{LEVEL_SLUG}.volume.block_north_gate", "volume_block", display_type="WIRE")
    create_cube(volumes_col, "V_bias_service_false_lead", Vector((18.0, -18.0, 1.5)), Vector((6.0, 3.5, 3.0)), f"map.{LEVEL_SLUG}.volume.bias_service_false_lead", "volume_bias", display_type="WIRE")


def configure_scene(scene: bpy.types.Scene):
    scene.unit_settings.system = "METRIC"
    scene.render.fps = 60
    scene.world.color = (0.01, 0.01, 0.015)


def main():
    purge_previous_generation()
    scene = create_scene(SCENE_NAME)

    render_col = new_collection(scene, COLLECTION_RENDER)
    collision_col = new_collection(scene, COLLECTION_COLLISION)
    markers_col = new_collection(scene, COLLECTION_MARKERS)
    volumes_col = new_collection(scene, COLLECTION_VOLUMES)

    build_map(render_col, collision_col, markers_col, volumes_col)
    configure_scene(scene)
    print(f"Generated scene '{SCENE_NAME}'")


if __name__ == "__main__":
    main()
