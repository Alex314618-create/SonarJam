import bpy
for o in bpy.data.objects:
    if "crashed" in o.name.lower():
        print(f"name={o.name!r}  type={o.type}  loc={tuple(o.location)}")
        if "original_name" in o:
            print(f"  original_name={o['original_name']!r}")
