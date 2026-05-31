"""读原始 space_shuttle.glb 的真实 PBR 因子（baseColorFactor / metallic / roughness）"""
import json, struct

GLB = r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\我的工作区\C_s\space_shuttle.glb"

with open(GLB, 'rb') as f:
    magic, ver, length = struct.unpack('<4sII', f.read(12))
    chunk_len, chunk_type = struct.unpack('<I4s', f.read(8))
    js = f.read(chunk_len).decode('utf-8')
doc = json.loads(js)

mats = doc.get('materials', [])
print(f"=== {len(mats)} materials in space_shuttle.glb ===\n")
print(f"{'#':>3}  {'name':<28}  {'baseColorFactor':<35}  {'metal':<6}  {'rough':<6}  {'tex?':<5}")
print("-" * 95)
for i, m in enumerate(mats):
    name = m.get('name', '<unnamed>')
    pbr = m.get('pbrMetallicRoughness', {})
    bc = pbr.get('baseColorFactor', [1, 1, 1, 1])
    metal = pbr.get('metallicFactor', 1.0)
    rough = pbr.get('roughnessFactor', 1.0)
    has_tex = 'baseColorTexture' in pbr
    bc_str = f"({bc[0]:.2f},{bc[1]:.2f},{bc[2]:.2f},{bc[3]:.2f})"
    print(f"{i:>3}  {name[:28]:<28}  {bc_str:<35}  {metal:<6.2f}  {rough:<6.2f}  {'YES' if has_tex else 'NO':<5}")
