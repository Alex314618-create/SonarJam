import bpy
from mathutils import Vector


obj = bpy.data.objects.get("BT_proto")
if obj is None or obj.type != "MESH":
    raise RuntimeError("BT_proto mesh not found")

world_min_z = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
for v in obj.data.vertices:
    v.co.z -= world_min_z / max(obj.scale.z, 0.0001)
obj.data.update()
bpy.context.view_layer.update()

world_min_z_after = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
world_max_z_after = max((obj.matrix_world @ v.co).z for v in obj.data.vertices)
print(f"Grounded BT_proto: min_z={world_min_z_after:.3f} max_z={world_max_z_after:.3f}")
bpy.ops.wm.save_as_mainfile(filepath=r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\BT.blend")
