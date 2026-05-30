import bpy, sys

SRC = '_temp_Blender/maps_54321/n1_rocket_block_a.original.glb'
DST = '_temp_Blender/maps_54321/n1_rocket_block_a.glb'
ANGLE_DEG = 10.0
COLLAPSE_RATIO = 0.12
WELD_DIST = 0.001
import math

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
before = sum(len(o.data.polygons) for o in meshes)

# Join all into one
bpy.ops.object.select_all(action='DESELECT')
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active
obj.name = 'rocket'

# Weld coincident verts so seams collapse together
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=WELD_DIST)
bpy.ops.object.mode_set(mode='OBJECT')

# Planar dissolve
m = obj.modifiers.new(name='dis', type='DECIMATE')
m.decimate_type = 'DISSOLVE'
m.angle_limit = math.radians(ANGLE_DEG)
m.use_dissolve_boundaries = False
bpy.ops.object.modifier_apply(modifier='dis')

# Collapse
m = obj.modifiers.new(name='col', type='DECIMATE')
m.decimate_type = 'COLLAPSE'
m.ratio = COLLAPSE_RATIO
m.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier='col')

after = len(obj.data.polygons)

print(f'BEFORE {before}')
print(f'AFTER  {after}')

bpy.ops.export_scene.gltf(
    filepath=DST,
    export_format='GLB',
    export_apply=True,
    export_yup=True,
    export_lights=False,
    export_image_format='NONE',
)
print('DONE')
