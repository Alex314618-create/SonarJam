"""扫描 GLB 的 JSON 部分，确认 M_spawn 节点真的被导出了"""
import struct, json, sys

GLB = r"C:\Users\ROG\Desktop\GameJam\content\levels\earth_return_01\scene.glb"

with open(GLB, 'rb') as f:
    magic, ver, length = struct.unpack('<4sII', f.read(12))
    # chunk 0: JSON
    chunk_len, chunk_type = struct.unpack('<I4s', f.read(8))
    js = f.read(chunk_len).decode('utf-8')
doc = json.loads(js)

# 找所有 name 以 M_ 开头的 node
m_nodes = [(i, n) for i, n in enumerate(doc.get('nodes', [])) if (n.get('name','').startswith('M_'))]
print(f"M_* nodes in glTF: {len(m_nodes)}")
for i, n in m_nodes:
    has_mesh = 'mesh' in n
    pos = n.get('translation', [0,0,0])
    print(f"  [{i}] {n['name']:<28s}  has_mesh={has_mesh}  pos={pos}")

# crashed 检测
crashed = [n['name'] for n in doc.get('nodes', []) if 'crashed' in n.get('name','').lower()]
print(f"\nC_*crashed* nodes: {len(crashed)}")
for n in crashed[:3]:
    print(f"  - {n}")
if len(crashed) > 3:
    print(f"  ... +{len(crashed)-3} more")

# C_terrain
ct = [n['name'] for n in doc.get('nodes', []) if n.get('name','').startswith('C_terrain')]
print(f"\nC_terrain_* nodes: {len(ct)}")
for n in ct:
    print(f"  - {n}")
