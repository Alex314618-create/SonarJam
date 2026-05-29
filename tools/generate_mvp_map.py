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


def add_locker_bank(render_col, slug: str, center: Vector, count: int, width: float = 2.2, depth: float = 0.75, height: float = 2.3):
    body = cube(render_col, f"R_{slug}_body", center, Vector((width, depth, height)))
    unit_w = width / count
    # slightly inset face to create real door rhythm
    for i in range(count):
        x = center.x - width * 0.5 + unit_w * (i + 0.5)
        cube(render_col, f"R_{slug}_door_{i:02d}", Vector((x, center.y + depth * 0.48, center.z)), Vector((unit_w * 0.86, 0.05, height * 0.92)))
        cube(render_col, f"R_{slug}_vent_{i:02d}_a", Vector((x, center.y + depth * 0.51, center.z + 0.55)), Vector((unit_w * 0.45, 0.02, 0.03)))
        cube(render_col, f"R_{slug}_vent_{i:02d}_b", Vector((x, center.y + depth * 0.51, center.z + 0.40)), Vector((unit_w * 0.45, 0.02, 0.03)))
        cube(render_col, f"R_{slug}_handle_{i:02d}", Vector((x + unit_w * 0.28, center.y + depth * 0.53, center.z + 0.05)), Vector((0.03, 0.03, 0.28)))
    cube(render_col, f"R_{slug}_plinth", Vector((center.x, center.y, center.z - height * 0.5 - 0.05)), Vector((width * 0.98, depth * 0.96, 0.10)))
    return body


def add_console(render_col, slug: str, center: Vector, width: float = 1.8, depth: float = 0.9, height: float = 1.9):
    cube(render_col, f"R_{slug}_pedestal", Vector((center.x, center.y, center.z - 0.35)), Vector((width * 0.75, depth * 0.72, height * 0.45)))
    cube(render_col, f"R_{slug}_screen", Vector((center.x, center.y + depth * 0.15, center.z + 0.45)), Vector((width, depth * 0.35, height * 0.45)))
    cube(render_col, f"R_{slug}_panel_left", Vector((center.x - width * 0.33, center.y + depth * 0.42, center.z + 0.05)), Vector((0.12, 0.08, 0.35)))
    cube(render_col, f"R_{slug}_panel_right", Vector((center.x + width * 0.33, center.y + depth * 0.42, center.z + 0.02)), Vector((0.12, 0.08, 0.30)))
    cube(render_col, f"R_{slug}_base", Vector((center.x, center.y, center.z - height * 0.5)), Vector((width * 0.58, depth * 0.52, 0.12)))


def add_workbench(render_col, slug: str, center: Vector, width: float = 2.6, depth: float = 0.9, height: float = 1.0):
    top_z = center.z + height * 0.5 - 0.08
    leg_z = center.z - 0.05
    cube(render_col, f"R_{slug}_top", Vector((center.x, center.y, top_z)), Vector((width, depth, 0.16)))
    for sx in (-0.42, 0.42):
        for sy in (-0.35, 0.35):
            cube(render_col, f"R_{slug}_leg_{'l' if sx < 0 else 'r'}_{'f' if sy > 0 else 'b'}", Vector((center.x + width * sx, center.y + depth * sy, leg_z)), Vector((0.10, 0.10, height * 0.82)))
    cube(render_col, f"R_{slug}_undershelf", Vector((center.x, center.y, center.z - 0.18)), Vector((width * 0.82, depth * 0.72, 0.08)))
    cube(render_col, f"R_{slug}_backboard", Vector((center.x, center.y - depth * 0.45, center.z + 0.45)), Vector((width * 0.92, 0.05, 0.7)))


def add_shelf_rack(render_col, slug: str, center: Vector, width: float = 1.0, depth: float = 2.2, height: float = 2.5, levels: int = 4):
    half_w = width * 0.5
    half_d = depth * 0.5
    leg_h = height
    for sx in (-half_w + 0.06, half_w - 0.06):
        for sy in (-half_d + 0.06, half_d - 0.06):
            cube(render_col, f"R_{slug}_upright_{'l' if sx < 0 else 'r'}_{'f' if sy > 0 else 'b'}", Vector((center.x + sx, center.y + sy, center.z)), Vector((0.08, 0.08, leg_h)))
    for i in range(levels):
        z = center.z - height * 0.5 + 0.18 + i * ((height - 0.36) / max(1, levels - 1))
        cube(render_col, f"R_{slug}_shelf_{i:02d}", Vector((center.x, center.y, z)), Vector((width, depth, 0.08)))


def add_crate_stack(render_col, slug: str, center: Vector, dims):
    # dims: list of (offset, size)
    for idx, (offset, size) in enumerate(dims):
        c = Vector((center.x + offset.x, center.y + offset.y, center.z + offset.z))
        cube(render_col, f"R_{slug}_crate_{idx:02d}", c, size)
        cube(render_col, f"R_{slug}_bandx_{idx:02d}", Vector((c.x, c.y, c.z)), Vector((size.x * 0.10, size.y * 1.02, size.z * 1.02)))
        cube(render_col, f"R_{slug}_bandy_{idx:02d}", Vector((c.x, c.y, c.z)), Vector((size.x * 1.02, size.y * 0.10, size.z * 1.02)))


def add_bunk_bed(render_col, slug: str, center: Vector, width: float = 2.4, depth: float = 0.95, height: float = 2.0):
    post_h = height
    for sx in (-width * 0.45, width * 0.45):
        for sy in (-depth * 0.42, depth * 0.42):
            cube(render_col, f"R_{slug}_post_{'l' if sx < 0 else 'r'}_{'f' if sy > 0 else 'b'}", Vector((center.x + sx, center.y + sy, center.z + 0.1)), Vector((0.08, 0.08, post_h)))
    for level, zoff in (("low", 0.18), ("high", 1.18)):
        cube(render_col, f"R_{slug}_{level}_frame", Vector((center.x, center.y, center.z - 0.35 + zoff)), Vector((width, depth, 0.10)))
        cube(render_col, f"R_{slug}_{level}_mattress", Vector((center.x, center.y, center.z - 0.26 + zoff)), Vector((width * 0.92, depth * 0.84, 0.16)))
    # ladder
    ladder_x = center.x + width * 0.50
    cube(render_col, f"R_{slug}_ladder_l", Vector((ladder_x, center.y - 0.20, center.z + 0.15)), Vector((0.05, 0.05, 1.7)))
    cube(render_col, f"R_{slug}_ladder_r", Vector((ladder_x, center.y + 0.20, center.z + 0.15)), Vector((0.05, 0.05, 1.7)))
    for i in range(4):
        z = center.z - 0.45 + 0.35 * i
        cube(render_col, f"R_{slug}_ladder_step_{i:02d}", Vector((ladder_x, center.y, z)), Vector((0.05, 0.42, 0.03)))


def add_tank_assembly(render_col, slug: str, center: Vector, radius: float = 1.1, height: float = 5.2):
    create_cylinder(render_col, f"R_{slug}_body", center, radius=radius, depth=height)
    create_cylinder(render_col, f"R_{slug}_cap_top", Vector((center.x, center.y, center.z + height * 0.48)), radius=radius * 0.92, depth=0.18)
    create_cylinder(render_col, f"R_{slug}_cap_bot", Vector((center.x, center.y, center.z - height * 0.48)), radius=radius * 0.92, depth=0.18)
    create_cylinder(render_col, f"R_{slug}_ring_top", Vector((center.x, center.y, center.z + height * 0.20)), radius=radius * 1.02, depth=0.08)
    create_cylinder(render_col, f"R_{slug}_ring_mid", Vector((center.x, center.y, center.z)), radius=radius * 1.02, depth=0.08)
    create_cylinder(render_col, f"R_{slug}_ring_bot", Vector((center.x, center.y, center.z - height * 0.20)), radius=radius * 1.02, depth=0.08)
    for sx in (-0.55, 0.55):
        for sy in (-0.55, 0.55):
            cube(render_col, f"R_{slug}_foot_{'n' if sy > 0 else 's'}_{'l' if sx < 0 else 'r'}", Vector((center.x + sx, center.y + sy, center.z - height * 0.5 - 0.3)), Vector((0.14, 0.14, 0.6)))
    # access ladder
    lx = center.x + radius + 0.12
    cube(render_col, f"R_{slug}_ladder_l", Vector((lx, center.y - 0.18, center.z)), Vector((0.05, 0.05, height * 0.9)))
    cube(render_col, f"R_{slug}_ladder_r", Vector((lx, center.y + 0.18, center.z)), Vector((0.05, 0.05, height * 0.9)))
    for i in range(6):
        z = center.z - height * 0.35 + i * (height * 0.12)
        cube(render_col, f"R_{slug}_ladder_step_{i:02d}", Vector((lx, center.y, z)), Vector((0.04, 0.34, 0.03)))


def add_pipe_run(render_col, slug: str, start: Vector, end: Vector, radius: float = 0.12, supports=3):
    delta = end - start
    if abs(delta.x) >= abs(delta.y):
        center = (start + end) * 0.5
        create_cylinder(render_col, f"R_{slug}_pipe", center, radius=radius, depth=abs(delta.x), rotation=(0.0, radians(90), 0.0), vertices=10)
        for i in range(supports):
            t = i / max(1, supports - 1)
            x = start.x + delta.x * t
            cube(render_col, f"R_{slug}_support_{i:02d}", Vector((x, start.y, start.z - 0.45)), Vector((0.10, 0.10, 0.9)))
    else:
        center = (start + end) * 0.5
        create_cylinder(render_col, f"R_{slug}_pipe", center, radius=radius, depth=abs(delta.y), rotation=(radians(90), 0.0, 0.0), vertices=10)
        for i in range(supports):
            t = i / max(1, supports - 1)
            y = start.y + delta.y * t
            cube(render_col, f"R_{slug}_support_{i:02d}", Vector((start.x, y, start.z - 0.45)), Vector((0.10, 0.10, 0.9)))


def add_partition_frame(render_col, slug: str, center: Vector, size: Vector):
    cube(render_col, f"R_{slug}_panel", center, size)
    cube(render_col, f"R_{slug}_top", Vector((center.x, center.y, center.z + size.z * 0.5)), Vector((size.x + 0.08, size.y + 0.08, 0.08)))
    cube(render_col, f"R_{slug}_bot", Vector((center.x, center.y, center.z - size.z * 0.5)), Vector((size.x + 0.08, size.y + 0.08, 0.08)))


def bounds_world(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    mins = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    maxs = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return mins, maxs


def point_inside_aabb(point: Vector, mins: Vector, maxs: Vector, pad_xy=0.0, pad_z=0.0) -> bool:
    return (
        mins.x - pad_xy <= point.x <= maxs.x + pad_xy
        and mins.y - pad_xy <= point.y <= maxs.y + pad_xy
        and mins.z - pad_z <= point.z <= maxs.z + pad_z
    )


def check_markers_not_in_collision(markers_col, collision_col):
    issues = []
    colliders = [(obj.name, *bounds_world(obj)) for obj in collision_col.objects if obj.type == "MESH"]
    for marker in markers_col.objects:
        p = marker.location.copy()
        for name, mins, maxs in colliders:
            if point_inside_aabb(p, mins, maxs, pad_xy=-0.01, pad_z=-0.01):
                issues.append(f"Marker {marker.name} intersects collision object {name}")
                break
    return issues


def sample_segment_clear(collision_col, a: Vector, b: Vector, z: float = 1.0, samples: int = 36):
    colliders = [(obj.name, *bounds_world(obj)) for obj in collision_col.objects if obj.type == "MESH"]
    for i in range(samples + 1):
        t = i / samples
        p = a.lerp(b, t)
        p.z = z
        for name, mins, maxs in colliders:
            if point_inside_aabb(p, mins, maxs, pad_xy=0.0, pad_z=0.0):
                # ignore floors below foot level
                if maxs.z < 0.35:
                    continue
                return name, p.copy()
    return None, None


def validate_key_paths(collision_col):
    issues = []
    paths = [
        ("spawn_to_gallery", [Vector((-40.0, 0.0, 1.0)), Vector((-24.0, 0.0, 1.0)), Vector((-12.0, 0.0, 1.0))]),
        ("gallery_to_hub", [Vector((-12.0, 0.0, 1.0)), Vector((-7.0, 0.0, 1.0)), Vector((0.0, 0.0, 1.0))]),
        ("hub_to_east", [Vector((0.0, 0.0, 1.0)), Vector((10.0, 0.0, 1.0)), Vector((18.0, 0.0, 1.0))]),
        ("hub_to_north", [Vector((0.0, 0.0, 1.0)), Vector((0.0, 14.0, 1.0)), Vector((0.0, 23.0, 1.0))]),
        ("hub_to_service", [Vector((0.0, 0.0, 1.0)), Vector((0.0, -15.0, 1.0)), Vector((0.0, -22.0, 1.0))]),
        ("service_to_west", [Vector((0.0, -22.0, 1.0)), Vector((-18.0, -22.0, 1.0)), Vector((-18.0, -17.0, 1.0)), Vector((-18.0, -10.0, 1.0))]),
    ]
    for path_name, nodes in paths:
        for a, b in zip(nodes, nodes[1:]):
            name, pt = sample_segment_clear(collision_col, a, b, z=1.0)
            if name:
                issues.append(f"Path {path_name} blocked by {name} near ({pt.x:.2f}, {pt.y:.2f}, {pt.z:.2f})")
                break
    return issues


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
    add_locker_bank(render_col, "airlock_locker_bank", Vector((-41.2, 1.6, 1.15)), count=3, width=2.1, depth=0.72, height=2.3)
    add_console(render_col, "airlock_console", Vector((-36.4, -1.5, 1.0)), width=1.2, depth=0.75, height=1.8)
    create_cube(render_col, "R_airlock_bench", Vector((-39.0, -1.9, 0.45)), Vector((2.0, 0.55, 0.90)))
    create_cube(render_col, "R_airlock_pipe_drop", Vector((-42.4, 0.0, 3.2)), Vector((0.28, 0.28, 1.6)))

    # Gallery ribs and duct
    for i, x in enumerate([-31.0, -27.0, -23.0, -19.0, -15.0]):
        create_cube(render_col, f"R_gallery_rib_{i:02d}", Vector((x, 0.0, 2.0)), Vector((0.18, 3.8, 4.0)))
    create_cube(render_col, "R_gallery_duct", Vector((-24.0, 0.0, 3.55)), Vector((22.0, 0.8, 0.6)))
    for x in [-29.0, -21.0, -13.0]:
        add_pipe_run(render_col, f"gallery_pipe_{int(x)}", Vector((x, -1.2, 2.9)), Vector((x, 1.2, 2.9)), radius=0.08, supports=2)

    # Tank hall landmarks
    hall_tanks = [
        ("hall_tank_a", Vector((-6.0, 5.5, 2.6))),
        ("hall_tank_b", Vector((6.0, 5.5, 2.6))),
        ("hall_tank_c", Vector((-6.0, -5.5, 2.6))),
        ("hall_tank_d", Vector((6.0, -5.5, 2.6))),
    ]
    for slug, loc in hall_tanks:
        add_tank_assembly(render_col, slug, loc, radius=1.1, height=5.2)
    create_cube(render_col, "R_hall_bridge_grate", Vector((0.0, 0.0, 0.3)), Vector((5.0, 2.0, 0.2)))
    add_pipe_run(render_col, "hall_pipe_north", Vector((-9.5, 8.8, 5.5)), Vector((9.5, 8.8, 5.5)), radius=0.12, supports=4)
    add_pipe_run(render_col, "hall_pipe_south", Vector((-9.5, -8.8, 5.2)), Vector((9.5, -8.8, 5.2)), radius=0.10, supports=4)
    create_cube(render_col, "R_hall_console_pillar", Vector((0.0, 0.0, 1.35)), Vector((1.1, 1.1, 2.7)))
    add_console(render_col, "hall_console_east", Vector((2.0, 0.0, 1.0)), width=1.0, depth=0.70, height=1.7)

    # Workshops
    add_workbench(render_col, "workshop_bench_a", Vector((15.2, 2.7, 0.55)), width=2.6, depth=0.85, height=1.1)
    add_workbench(render_col, "workshop_bench_b", Vector((19.2, -2.8, 0.55)), width=3.0, depth=0.90, height=1.05)
    add_shelf_rack(render_col, "workshop_shelf_a", Vector((21.6, 3.2, 1.25)), width=0.8, depth=2.0, height=2.5)
    add_shelf_rack(render_col, "workshop_shelf_b", Vector((13.8, -3.0, 1.25)), width=0.8, depth=2.0, height=2.5)
    add_crate_stack(
        render_col,
        "workshop_crates",
        Vector((17.2, 0.3, 0.55)),
        [
            (Vector((-0.45, 0.0, 0.0)), Vector((0.95, 0.95, 1.10))),
            (Vector((0.55, 0.0, 0.0)), Vector((1.05, 1.05, 1.10))),
            (Vector((0.0, 0.1, 1.05)), Vector((0.88, 0.88, 0.95))),
        ],
    )
    create_cube(render_col, "R_workshop_ceiling_tray", Vector((18.0, 0.0, 4.3)), Vector((8.0, 0.45, 0.45)))
    add_pipe_run(render_col, "workshop_pipe_a", Vector((14.0, 4.2, 3.9)), Vector((22.0, 4.2, 3.9)), radius=0.08, supports=3)
    add_console(render_col, "workshop_wall_console", Vector((22.6, -0.2, 1.0)), width=0.9, depth=0.55, height=1.6)

    # Quarters
    add_bunk_bed(render_col, "quarters_bunk_a", Vector((-20.5, -8.0, 1.0)), width=2.4, depth=0.95, height=2.0)
    add_bunk_bed(render_col, "quarters_bunk_b", Vector((-15.2, -11.4, 1.0)), width=2.4, depth=0.95, height=2.0)
    add_locker_bank(render_col, "quarters_lockers", Vector((-13.6, -8.0, 1.15)), count=3, width=2.1, depth=0.72, height=2.3)
    add_workbench(render_col, "quarters_med_table", Vector((-17.8, -12.2, 0.55)), width=1.6, depth=0.8, height=0.95)
    add_partition_frame(render_col, "quarters_partition", Vector((-18.0, -9.7, 1.5)), Vector((0.12, 4.6, 3.0)))
    create_cube(render_col, "R_quarters_curtain_rod", Vector((-18.0, -9.7, 2.85)), Vector((0.08, 4.8, 0.08)))

    # Pump room
    add_tank_assembly(render_col, "pump_core_a", Vector((-1.6, 22.0, 1.9)), radius=0.8, height=3.8)
    add_tank_assembly(render_col, "pump_core_b", Vector((1.6, 22.0, 1.9)), radius=0.8, height=3.8)
    add_console(render_col, "pump_control_bank", Vector((0.0, 19.2, 1.2)), width=4.0, depth=0.8, height=2.2)
    add_pipe_run(render_col, "pump_pipe_run_top", Vector((-3.5, 24.0, 4.8)), Vector((3.5, 24.0, 4.8)), radius=0.11, supports=4)
    add_pipe_run(render_col, "pump_pipe_vertical_left", Vector((-3.2, 24.0, 4.0)), Vector((-3.2, 20.5, 4.0)), radius=0.09, supports=2)
    add_pipe_run(render_col, "pump_pipe_vertical_right", Vector((3.2, 24.0, 4.0)), Vector((3.2, 20.5, 4.0)), radius=0.09, supports=2)
    create_cube(render_col, "R_pump_grate_platform", Vector((0.0, 22.0, 0.25)), Vector((5.4, 4.2, 0.15)))

    # Service loop
    for idx, x in enumerate([-12.0, -4.0, 4.0, 12.0]):
        add_pipe_run(render_col, f"service_pipe_{idx:02d}", Vector((x, -23.4, 2.5)), Vector((x, -20.6, 2.5)), radius=0.10, supports=2)
    create_cube(render_col, "R_service_junction_body", Vector((18.0, -15.5, 1.2)), Vector((1.2, 0.8, 2.4)))
    create_cube(render_col, "R_service_junction_face", Vector((18.0, -15.06, 1.25)), Vector((0.85, 0.05, 1.9)))
    create_cube(render_col, "R_service_hatch_frame", Vector((-18.0, -17.0, 1.2)), Vector((1.4, 0.10, 2.4)))
    create_cube(render_col, "R_service_hatch_panel", Vector((-18.0, -16.94, 1.2)), Vector((1.1, 0.04, 2.1)))


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


def run_validation(markers_col, collision_col):
    issues = []
    issues.extend(check_markers_not_in_collision(markers_col, collision_col))
    issues.extend(validate_key_paths(collision_col))
    if issues:
        print("=== MVPMap validation issues ===")
        for issue in issues:
            print(issue)
    else:
        print("=== MVPMap validation passed ===")


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
    run_validation(markers_col, collision_col)
    print(f"Generated scene '{SCENE_NAME}'")


if __name__ == "__main__":
    main()
