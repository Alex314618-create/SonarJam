"""
Blender Python script: generate a large-scale outdoor test map.

Goal:
    - open field / wilderness read
    - surrounding mountains
    - one enterable house
    - connected interior corridors and rooms
    - clean Render / Collision / Markers / Volumes collections

Usage:
    1. Open Blender
    2. Switch to Scripting
    3. Open this file
    4. Run
"""

import bpy
from math import radians
from mathutils import Vector


SCENE_NAME = "OutdoorTestMap"
LEVEL_SLUG = "outdoor_test_01"

COLLECTION_RENDER = "Render"
COLLECTION_COLLISION = "Collision"
COLLECTION_MARKERS = "Markers"
COLLECTION_VOLUMES = "Volumes"

WALL = 0.32
FLOOR = 0.18
ROOF = 0.18
DOOR_HEIGHT = 2.4
FRAME = 0.12


def purge_scene(name: str):
    scene = bpy.data.scenes.get(name)
    if scene is not None:
        bpy.data.scenes.remove(scene)
    try:
        bpy.ops.outliner.orphans_purge(do_recursive=True)
    except Exception:
        pass


def create_scene(name: str):
    scene = bpy.data.scenes.new(name)
    bpy.context.window.scene = scene
    return scene


def new_collection(scene, name: str):
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    return col


def unlink_from_all(obj):
    for col in list(obj.users_collection):
        col.objects.unlink(obj)


def set_semantics(obj, sj_id: str, sj_kind: str):
    obj["sj_id"] = sj_id
    obj["sj_kind"] = sj_kind


def cube(col, name: str, location: Vector, size: Vector, sj_id=None, sj_kind=None, display_type="TEXTURED"):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    if obj.data:
        obj.data.name = f"{name}_mesh"
    obj.scale = (size.x * 0.5, size.y * 0.5, size.z * 0.5)
    obj.display_type = display_type
    unlink_from_all(obj)
    col.objects.link(obj)
    if sj_id and sj_kind:
        set_semantics(obj, sj_id, sj_kind)
    return obj


def cone(col, name: str, location: Vector, radius1: float, depth: float, vertices=10, rotation=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0), sj_id=None, sj_kind=None):
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius1,
        radius2=0.0,
        depth=depth,
        location=location,
        rotation=rotation,
    )
    obj = bpy.context.active_object
    obj.name = name
    if obj.data:
        obj.data.name = f"{name}_mesh"
    obj.scale = scale
    unlink_from_all(obj)
    col.objects.link(obj)
    if sj_id and sj_kind:
        set_semantics(obj, sj_id, sj_kind)
    return obj


def empty(col, name: str, location: Vector, sj_id: str, sj_kind: str, rotation=(0.0, 0.0, 0.0), display_type="ARROWS", display_size=0.9):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = display_type
    obj.empty_display_size = display_size
    obj.location = location
    obj.rotation_euler = rotation
    col.objects.link(obj)
    set_semantics(obj, sj_id, sj_kind)
    return obj


def add_floor(render_col, collision_col, slug: str, center: Vector, size_xy: Vector, floor_z: float):
    loc = Vector((center.x, center.y, floor_z - FLOOR * 0.5))
    size = Vector((size_xy.x, size_xy.y, FLOOR))
    cube(render_col, f"R_{slug}_floor", loc, size, sj_id=f"map.{LEVEL_SLUG}.render.{slug}_floor", sj_kind="render_mesh")
    cube(collision_col, f"C_{slug}_floor", loc, size, sj_id=f"map.{LEVEL_SLUG}.collision.{slug}_floor", sj_kind="collision_mesh", display_type="WIRE")


def add_roof(render_col, slug: str, center: Vector, size_xy: Vector, roof_z: float):
    loc = Vector((center.x, center.y, roof_z + ROOF * 0.5))
    size = Vector((size_xy.x, size_xy.y, ROOF))
    cube(render_col, f"R_{slug}_roof", loc, size, sj_id=f"map.{LEVEL_SLUG}.render.{slug}_roof", sj_kind="render_mesh")


def _intervals(center_axis: float, span: float, openings):
    start = center_axis - span * 0.5
    end = center_axis + span * 0.5
    out = []
    for rel_center, width in openings:
        a = center_axis + rel_center - width * 0.5
        b = center_axis + rel_center + width * 0.5
        out.append((max(start, a), min(end, b)))
    out.sort(key=lambda p: p[0])
    return out


def door_frame_x(render_col, slug: str, side_slug: str, y: float, z_center: float, wall_height: float, open_start: float, open_end: float):
    post_size = Vector((FRAME, WALL + 0.06, DOOR_HEIGHT))
    post_z = z_center - wall_height * 0.5 + DOOR_HEIGHT * 0.5
    cube(render_col, f"R_{slug}_{side_slug}_frame_l", Vector((open_start - FRAME * 0.5, y, post_z)), post_size)
    cube(render_col, f"R_{slug}_{side_slug}_frame_r", Vector((open_end + FRAME * 0.5, y, post_z)), post_size)
    lintel_h = max(0.18, wall_height - DOOR_HEIGHT)
    lintel_z = z_center + wall_height * 0.5 - lintel_h * 0.5
    cube(render_col, f"R_{slug}_{side_slug}_frame_top", Vector(((open_start + open_end) * 0.5, y, lintel_z)), Vector((open_end - open_start + FRAME * 2.0, WALL + 0.06, lintel_h)))


def door_frame_y(render_col, slug: str, side_slug: str, x: float, z_center: float, wall_height: float, open_start: float, open_end: float):
    post_size = Vector((WALL + 0.06, FRAME, DOOR_HEIGHT))
    post_z = z_center - wall_height * 0.5 + DOOR_HEIGHT * 0.5
    cube(render_col, f"R_{slug}_{side_slug}_frame_l", Vector((x, open_start - FRAME * 0.5, post_z)), post_size)
    cube(render_col, f"R_{slug}_{side_slug}_frame_r", Vector((x, open_end + FRAME * 0.5, post_z)), post_size)
    lintel_h = max(0.18, wall_height - DOOR_HEIGHT)
    lintel_z = z_center + wall_height * 0.5 - lintel_h * 0.5
    cube(render_col, f"R_{slug}_{side_slug}_frame_top", Vector((x, (open_start + open_end) * 0.5, lintel_z)), Vector((WALL + 0.06, open_end - open_start + FRAME * 2.0, lintel_h)))


def wall_x(render_col, collision_col, slug: str, side_slug: str, center_x: float, y: float, z_center: float, span_x: float, height_z: float, openings):
    intervals = _intervals(center_x, span_x, openings)
    cursor = center_x - span_x * 0.5
    for idx, (a, b) in enumerate(intervals):
        if a > cursor:
            seg_len = a - cursor
            seg_center = cursor + seg_len * 0.5
            size = Vector((seg_len, WALL, height_z))
            loc = Vector((seg_center, y, z_center))
            cube(render_col, f"R_{slug}_{side_slug}_{idx}", loc, size, sj_id=f"map.{LEVEL_SLUG}.render.{slug}_{side_slug}_{idx}", sj_kind="render_mesh")
            cube(collision_col, f"C_{slug}_{side_slug}_{idx}", loc, size, sj_id=f"map.{LEVEL_SLUG}.collision.{slug}_{side_slug}_{idx}", sj_kind="collision_mesh", display_type="WIRE")
        door_frame_x(render_col, slug, side_slug, y, z_center, height_z, a, b)
        cursor = b
    end = center_x + span_x * 0.5
    if end > cursor:
        seg_len = end - cursor
        seg_center = cursor + seg_len * 0.5
        size = Vector((seg_len, WALL, height_z))
        loc = Vector((seg_center, y, z_center))
        suffix = len(intervals)
        cube(render_col, f"R_{slug}_{side_slug}_{suffix}", loc, size, sj_id=f"map.{LEVEL_SLUG}.render.{slug}_{side_slug}_{suffix}", sj_kind="render_mesh")
        cube(collision_col, f"C_{slug}_{side_slug}_{suffix}", loc, size, sj_id=f"map.{LEVEL_SLUG}.collision.{slug}_{side_slug}_{suffix}", sj_kind="collision_mesh", display_type="WIRE")


def wall_y(render_col, collision_col, slug: str, side_slug: str, x: float, center_y: float, z_center: float, span_y: float, height_z: float, openings):
    intervals = _intervals(center_y, span_y, openings)
    cursor = center_y - span_y * 0.5
    for idx, (a, b) in enumerate(intervals):
        if a > cursor:
            seg_len = a - cursor
            seg_center = cursor + seg_len * 0.5
            size = Vector((WALL, seg_len, height_z))
            loc = Vector((x, seg_center, z_center))
            cube(render_col, f"R_{slug}_{side_slug}_{idx}", loc, size, sj_id=f"map.{LEVEL_SLUG}.render.{slug}_{side_slug}_{idx}", sj_kind="render_mesh")
            cube(collision_col, f"C_{slug}_{side_slug}_{idx}", loc, size, sj_id=f"map.{LEVEL_SLUG}.collision.{slug}_{side_slug}_{idx}", sj_kind="collision_mesh", display_type="WIRE")
        door_frame_y(render_col, slug, side_slug, x, z_center, height_z, a, b)
        cursor = b
    end = center_y + span_y * 0.5
    if end > cursor:
        seg_len = end - cursor
        seg_center = cursor + seg_len * 0.5
        size = Vector((WALL, seg_len, height_z))
        loc = Vector((x, seg_center, z_center))
        suffix = len(intervals)
        cube(render_col, f"R_{slug}_{side_slug}_{suffix}", loc, size, sj_id=f"map.{LEVEL_SLUG}.render.{slug}_{side_slug}_{suffix}", sj_kind="render_mesh")
        cube(collision_col, f"C_{slug}_{side_slug}_{suffix}", loc, size, sj_id=f"map.{LEVEL_SLUG}.collision.{slug}_{side_slug}_{suffix}", sj_kind="collision_mesh", display_type="WIRE")


def room(render_col, collision_col, slug: str, center: Vector, size: Vector, openings=None, roof=True):
    if openings is None:
        openings = {}
    hx = size.x * 0.5
    hy = size.y * 0.5
    hz = size.z * 0.5
    floor_z = center.z - hz
    roof_z = center.z + hz
    add_floor(render_col, collision_col, slug, center, Vector((size.x, size.y)), floor_z)
    if roof:
        add_roof(render_col, slug, center, Vector((size.x, size.y)), roof_z)
    wall_x(render_col, collision_col, slug, "north", center.x, center.y + hy + WALL * 0.5, center.z, size.x, size.z, openings.get("north", []))
    wall_x(render_col, collision_col, slug, "south", center.x, center.y - hy - WALL * 0.5, center.z, size.x, size.z, openings.get("south", []))
    wall_y(render_col, collision_col, slug, "east", center.x + hx + WALL * 0.5, center.y, center.z, size.y, size.z, openings.get("east", []))
    wall_y(render_col, collision_col, slug, "west", center.x - hx - WALL * 0.5, center.y, center.z, size.y, size.z, openings.get("west", []))


def house_layout(render_col, collision_col):
    # main shell broken into connected rooms to avoid overlap and ensure true connections
    room(
        render_col, collision_col,
        "house_foyer",
        center=Vector((0.0, -8.0, 2.4)),
        size=Vector((10.0, 8.0, 4.8)),
        openings={
            "south": [(0.0, 3.2)],
            "north": [(0.0, 3.2)],
        },
    )
    room(
        render_col, collision_col,
        "house_corridor",
        center=Vector((0.0, 4.0, 2.4)),
        size=Vector((4.0, 16.0, 4.8)),
        openings={
            "south": [(0.0, 3.2)],
            "north": [(0.0, 3.2)],
            "east": [(-3.5, 2.4), (3.5, 2.4)],
            "west": [(-3.5, 2.4), (3.5, 2.4)],
        },
    )
    room(
        render_col, collision_col,
        "house_room_west_south",
        center=Vector((-8.0, 0.5, 2.4)),
        size=Vector((8.0, 7.0, 4.8)),
        openings={"east": [(0.0, 2.4)]},
    )
    room(
        render_col, collision_col,
        "house_room_east_south",
        center=Vector((8.0, 0.5, 2.4)),
        size=Vector((8.0, 7.0, 4.8)),
        openings={"west": [(0.0, 2.4)]},
    )
    room(
        render_col, collision_col,
        "house_room_west_north",
        center=Vector((-8.0, 8.5, 2.4)),
        size=Vector((8.0, 7.0, 4.8)),
        openings={"east": [(0.0, 2.4)]},
    )
    room(
        render_col, collision_col,
        "house_room_east_north",
        center=Vector((8.0, 8.5, 2.4)),
        size=Vector((8.0, 7.0, 4.8)),
        openings={"west": [(0.0, 2.4)]},
    )
    room(
        render_col, collision_col,
        "house_backroom",
        center=Vector((0.0, 16.5, 2.4)),
        size=Vector((10.0, 5.0, 4.8)),
        openings={"south": [(0.0, 3.2)]},
    )


def house_dressing(render_col):
    props = [
        ("R_house_table_foyer", Vector((0.0, -9.4, 0.8)), Vector((2.0, 1.0, 1.4))),
        ("R_house_sideboard", Vector((3.1, -6.0, 1.0)), Vector((1.6, 0.6, 2.0))),
        ("R_house_room_west_south_bed", Vector((-8.5, 0.8, 0.55)), Vector((2.6, 1.6, 0.9))),
        ("R_house_room_east_south_shelf", Vector((10.8, 0.3, 1.2)), Vector((0.8, 2.2, 2.4))),
        ("R_house_room_west_north_crates", Vector((-8.2, 8.7, 0.8)), Vector((2.0, 1.6, 1.6))),
        ("R_house_room_east_north_console", Vector((8.8, 9.0, 1.0)), Vector((1.8, 0.8, 2.0))),
        ("R_house_backroom_generator", Vector((0.0, 16.8, 1.2)), Vector((3.2, 1.8, 2.4))),
        ("R_house_corridor_lightbox_01", Vector((0.0, -0.5, 4.45)), Vector((0.7, 0.7, 0.25))),
        ("R_house_corridor_lightbox_02", Vector((0.0, 7.0, 4.45)), Vector((0.7, 0.7, 0.25))),
    ]
    for name, loc, size in props:
        cube(render_col, name, loc, size)


def landscape(render_col, collision_col):
    # giant ground
    cube(render_col, "R_ground_main", Vector((0.0, 0.0, -0.5)), Vector((260.0, 260.0, 1.0)), sj_id=f"map.{LEVEL_SLUG}.render.ground_main", sj_kind="render_mesh")
    cube(collision_col, "C_ground_main", Vector((0.0, 0.0, -0.5)), Vector((260.0, 260.0, 1.0)), sj_id=f"map.{LEVEL_SLUG}.collision.ground_main", sj_kind="collision_mesh", display_type="WIRE")

    # raised plateau under house
    cube(render_col, "R_house_plateau", Vector((0.0, 2.0, 0.25)), Vector((44.0, 36.0, 1.5)), sj_id=f"map.{LEVEL_SLUG}.render.house_plateau", sj_kind="render_mesh")
    cube(collision_col, "C_house_plateau", Vector((0.0, 2.0, 0.25)), Vector((44.0, 36.0, 1.5)), sj_id=f"map.{LEVEL_SLUG}.collision.house_plateau", sj_kind="collision_mesh", display_type="WIRE")

    # approach path
    for i, y in enumerate([-48.0, -40.0, -32.0, -24.0]):
        cube(render_col, f"R_path_step_{i:02d}", Vector((0.0, y, 0.02)), Vector((6.0, 3.0, 0.10)))

    # surrounding mountains / ridges
    mountains = [
        ("mountain_w_01", Vector((-92.0, -15.0, 18.0)), 22.0, 38.0, (1.2, 1.0, 1.0)),
        ("mountain_w_02", Vector((-108.0, 24.0, 23.0)), 28.0, 46.0, (1.0, 1.3, 1.0)),
        ("mountain_e_01", Vector((96.0, -8.0, 20.0)), 24.0, 42.0, (1.1, 0.9, 1.0)),
        ("mountain_e_02", Vector((112.0, 34.0, 28.0)), 30.0, 56.0, (1.0, 1.1, 1.0)),
        ("mountain_n_01", Vector((-18.0, 104.0, 26.0)), 34.0, 52.0, (1.4, 1.0, 1.0)),
        ("mountain_n_02", Vector((36.0, 118.0, 34.0)), 42.0, 68.0, (1.2, 0.9, 1.0)),
        ("mountain_s_01", Vector((-32.0, -112.0, 22.0)), 26.0, 44.0, (1.3, 1.1, 1.0)),
        ("mountain_s_02", Vector((28.0, -126.0, 30.0)), 38.0, 60.0, (1.2, 1.0, 1.0)),
    ]
    for slug, loc, radius, depth, scale in mountains:
        cone(render_col, f"R_{slug}", loc, radius1=radius, depth=depth, vertices=8, scale=scale, sj_id=f"map.{LEVEL_SLUG}.render.{slug}", sj_kind="render_mesh")
        cone(collision_col, f"C_{slug}", loc, radius1=radius, depth=depth, vertices=8, scale=scale, sj_id=f"map.{LEVEL_SLUG}.collision.{slug}", sj_kind="collision_mesh",)

    # smaller hills around the plateau for near-field reading
    hills = [
        ("hill_sw", Vector((-34.0, -36.0, 4.0)), Vector((18.0, 14.0, 8.0))),
        ("hill_se", Vector((30.0, -34.0, 3.5)), Vector((16.0, 12.0, 7.0))),
        ("hill_nw", Vector((-36.0, 30.0, 4.2)), Vector((18.0, 14.0, 8.4))),
        ("hill_ne", Vector((34.0, 28.0, 3.7)), Vector((16.0, 12.0, 7.4))),
    ]
    for slug, loc, size in hills:
        cube(render_col, f"R_{slug}", loc, size, sj_id=f"map.{LEVEL_SLUG}.render.{slug}", sj_kind="render_mesh")
        cube(collision_col, f"C_{slug}", loc, size, sj_id=f"map.{LEVEL_SLUG}.collision.{slug}", sj_kind="collision_mesh", display_type="WIRE")


def add_markers_and_volumes(markers_col, volumes_col):
    empty(markers_col, "M_spawn_main", Vector((0.0, -60.0, 1.0)), f"map.{LEVEL_SLUG}.marker.spawn_main", "marker_spawn")
    empty(markers_col, "M_reset_field", Vector((0.0, -38.0, 1.0)), f"map.{LEVEL_SLUG}.marker.reset_field", "marker_reset")
    empty(markers_col, "M_reset_house_entry", Vector((0.0, -15.0, 1.0)), f"map.{LEVEL_SLUG}.marker.reset_house_entry", "marker_reset")
    empty(markers_col, "M_reset_backroom", Vector((0.0, 16.0, 1.0)), f"map.{LEVEL_SLUG}.marker.reset_backroom", "marker_reset")
    empty(markers_col, "M_trigger_house_entry", Vector((0.0, -12.0, 1.0)), f"map.{LEVEL_SLUG}.marker.trigger_house_entry", "marker_trigger")
    empty(markers_col, "M_trigger_corridor_mid", Vector((0.0, 4.0, 1.0)), f"map.{LEVEL_SLUG}.marker.trigger_corridor_mid", "marker_trigger")
    empty(markers_col, "M_echo_hint_field", Vector((18.0, -28.0, 1.0)), f"map.{LEVEL_SLUG}.marker.echo_hint_field", "marker_echo")
    empty(markers_col, "M_echo_hint_backroom", Vector((0.0, 16.0, 1.0)), f"map.{LEVEL_SLUG}.marker.echo_hint_backroom", "marker_echo")
    empty(markers_col, "M_truth_edge_foyer", Vector((0.0, -8.0, 1.0)), f"map.{LEVEL_SLUG}.marker.truth_edge_foyer", "marker_truth")
    empty(markers_col, "M_end_backroom", Vector((0.0, 18.5, 1.0)), f"map.{LEVEL_SLUG}.marker.end_backroom", "marker_end")

    cube(volumes_col, "V_bias_field", Vector((0.0, -30.0, 2.0)), Vector((70.0, 60.0, 5.0)), f"map.{LEVEL_SLUG}.volume.bias_field", "volume_bias", display_type="WIRE")
    cube(volumes_col, "V_bias_corridor", Vector((0.0, 4.0, 2.0)), Vector((6.0, 18.0, 4.0)), f"map.{LEVEL_SLUG}.volume.bias_corridor", "volume_bias", display_type="WIRE")
    cube(volumes_col, "V_truth_foyer", Vector((0.0, -8.0, 2.0)), Vector((8.0, 6.0, 4.0)), f"map.{LEVEL_SLUG}.volume.truth_foyer", "volume_truth", display_type="WIRE")
    cube(volumes_col, "V_trigger_echo_gate", Vector((0.0, 15.5, 2.0)), Vector((6.0, 4.0, 4.0)), f"map.{LEVEL_SLUG}.volume.trigger_echo_gate", "volume_trigger", display_type="WIRE")
    cube(volumes_col, "V_block_backroom", Vector((0.0, 14.0, 1.75)), Vector((2.4, 1.0, 3.5)), f"map.{LEVEL_SLUG}.volume.block_backroom", "volume_block", display_type="WIRE")


def configure_scene(scene):
    scene.unit_settings.system = "METRIC"
    scene.render.fps = 60
    scene.world.color = (0.01, 0.012, 0.018)


def main():
    purge_scene(SCENE_NAME)
    scene = create_scene(SCENE_NAME)
    render_col = new_collection(scene, COLLECTION_RENDER)
    collision_col = new_collection(scene, COLLECTION_COLLISION)
    markers_col = new_collection(scene, COLLECTION_MARKERS)
    volumes_col = new_collection(scene, COLLECTION_VOLUMES)

    landscape(render_col, collision_col)
    house_layout(render_col, collision_col)
    house_dressing(render_col)
    add_markers_and_volumes(markers_col, volumes_col)
    configure_scene(scene)
    print(f"Generated scene '{SCENE_NAME}'")


if __name__ == "__main__":
    main()
