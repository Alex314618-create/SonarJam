from __future__ import annotations

import json
import math
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "content" / "entities" / "bt.glb"


positions: list[tuple[float, float, float]] = []
indices: list[int] = []


def add_vertex(p: tuple[float, float, float]) -> int:
    positions.append(p)
    return len(positions) - 1


def add_tri(a: int, b: int, c: int) -> None:
    indices.extend((a, b, c))


def add_ellipsoid(
    center: tuple[float, float, float],
    radius: tuple[float, float, float],
    rings: int = 6,
    segments: int = 12,
) -> None:
    cx, cy, cz = center
    rx, ry, rz = radius
    verts: list[list[int]] = []

    top = add_vertex((cx, cy + ry, cz))
    bottom = add_vertex((cx, cy - ry, cz))

    for r in range(1, rings):
        phi = math.pi * r / rings
        y = cy + math.cos(phi) * ry
        rr = math.sin(phi)
        row: list[int] = []
        for s in range(segments):
            theta = math.tau * s / segments
            row.append(add_vertex((cx + math.cos(theta) * rx * rr, y, cz + math.sin(theta) * rz * rr)))
        verts.append(row)

    first = verts[0]
    for s in range(segments):
        add_tri(top, first[(s + 1) % segments], first[s])

    for r in range(len(verts) - 1):
        row = verts[r]
        nxt = verts[r + 1]
        for s in range(segments):
            a = row[s]
            b = row[(s + 1) % segments]
            c = nxt[s]
            d = nxt[(s + 1) % segments]
            add_tri(a, b, d)
            add_tri(a, d, c)

    last = verts[-1]
    for s in range(segments):
        add_tri(bottom, last[s], last[(s + 1) % segments])


def orthonormal_basis(axis: tuple[float, float, float]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    ax, ay, az = axis
    length = math.sqrt(ax * ax + ay * ay + az * az)
    ux, uy, uz = ax / length, ay / length, az / length
    if abs(uy) < 0.9:
        vx, vy, vz = -uz, 0.0, ux
    else:
        vx, vy, vz = 1.0, 0.0, 0.0
    v_len = math.sqrt(vx * vx + vy * vy + vz * vz)
    vx, vy, vz = vx / v_len, vy / v_len, vz / v_len
    wx = uy * vz - uz * vy
    wy = uz * vx - ux * vz
    wz = ux * vy - uy * vx
    return (vx, vy, vz), (wx, wy, wz)


def add_cylinder_between(
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    segments: int = 12,
) -> None:
    sx, sy, sz = start
    ex, ey, ez = end
    axis = (ex - sx, ey - sy, ez - sz)
    v, w = orthonormal_basis(axis)
    start_ring: list[int] = []
    end_ring: list[int] = []

    for s in range(segments):
        theta = math.tau * s / segments
        ox = math.cos(theta) * v[0] * radius + math.sin(theta) * w[0] * radius
        oy = math.cos(theta) * v[1] * radius + math.sin(theta) * w[1] * radius
        oz = math.cos(theta) * v[2] * radius + math.sin(theta) * w[2] * radius
        start_ring.append(add_vertex((sx + ox, sy + oy, sz + oz)))
        end_ring.append(add_vertex((ex + ox, ey + oy, ez + oz)))

    start_center = add_vertex(start)
    end_center = add_vertex(end)
    for s in range(segments):
        a = start_ring[s]
        b = start_ring[(s + 1) % segments]
        c = end_ring[s]
        d = end_ring[(s + 1) % segments]
        add_tri(a, c, d)
        add_tri(a, d, b)
        add_tri(start_center, b, a)
        add_tri(end_center, c, d)


def add_box(center: tuple[float, float, float], size: tuple[float, float, float]) -> None:
    cx, cy, cz = center
    sx, sy, sz = (size[0] / 2.0, size[1] / 2.0, size[2] / 2.0)
    verts = [
        add_vertex((cx - sx, cy - sy, cz - sz)),
        add_vertex((cx + sx, cy - sy, cz - sz)),
        add_vertex((cx + sx, cy + sy, cz - sz)),
        add_vertex((cx - sx, cy + sy, cz - sz)),
        add_vertex((cx - sx, cy - sy, cz + sz)),
        add_vertex((cx + sx, cy - sy, cz + sz)),
        add_vertex((cx + sx, cy + sy, cz + sz)),
        add_vertex((cx - sx, cy + sy, cz + sz)),
    ]
    faces = [
        (0, 1, 2, 3),
        (5, 4, 7, 6),
        (4, 0, 3, 7),
        (1, 5, 6, 2),
        (3, 2, 6, 7),
        (4, 5, 1, 0),
    ]
    for a, b, c, d in faces:
        add_tri(verts[a], verts[b], verts[c])
        add_tri(verts[a], verts[c], verts[d])


def pad4(data: bytes, pad: bytes = b"\x00") -> bytes:
    return data + pad * ((4 - len(data) % 4) % 4)


def build() -> None:
    # Y-up glTF model: soles rest on y=0, total height is 1.7m.
    add_ellipsoid((0.0, 1.02, 0.0), (0.18, 0.34, 0.11), rings=6, segments=12)  # torso
    add_ellipsoid((0.0, 1.56, 0.0), (0.12, 0.14, 0.12), rings=6, segments=12)  # head

    add_cylinder_between((-0.10, 0.70, 0.0), (-0.10, 0.08, 0.0), 0.055)
    add_cylinder_between((0.10, 0.70, 0.0), (0.10, 0.08, 0.0), 0.055)
    add_box((-0.10, 0.035, 0.045), (0.16, 0.07, 0.22))
    add_box((0.10, 0.035, 0.045), (0.16, 0.07, 0.22))

    add_cylinder_between((-0.18, 1.25, 0.0), (-0.62, 1.25, 0.0), 0.045)
    add_cylinder_between((0.18, 1.25, 0.0), (0.62, 1.25, 0.0), 0.045)
    add_ellipsoid((-0.68, 1.25, 0.0), (0.055, 0.055, 0.055), rings=4, segments=10)
    add_ellipsoid((0.68, 1.25, 0.0), (0.055, 0.055, 0.055), rings=4, segments=10)

    min_pos = [min(p[i] for p in positions) for i in range(3)]
    max_pos = [max(p[i] for p in positions) for i in range(3)]

    index_bytes = struct.pack("<" + "H" * len(indices), *indices)
    vertex_bytes = struct.pack("<" + "f" * (len(positions) * 3), *(c for p in positions for c in p))
    index_offset = 0
    vertex_offset = len(pad4(index_bytes))
    blob = pad4(index_bytes) + pad4(vertex_bytes)

    gltf = {
        "asset": {"version": "2.0", "generator": "generate_bt_proto.py"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "BT_proto", "mesh": 0}],
        "meshes": [
            {
                "name": "BT_proto",
                "primitives": [
                    {
                        "attributes": {"POSITION": 1},
                        "indices": 0,
                        "mode": 4,
                    }
                ],
            }
        ],
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": index_offset, "byteLength": len(index_bytes), "target": 34963},
            {"buffer": 0, "byteOffset": vertex_offset, "byteLength": len(vertex_bytes), "target": 34962},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5123, "count": len(indices), "type": "SCALAR"},
            {
                "bufferView": 1,
                "componentType": 5126,
                "count": len(positions),
                "type": "VEC3",
                "min": min_pos,
                "max": max_pos,
            },
        ],
    }

    json_chunk = pad4(json.dumps(gltf, separators=(",", ":")).encode("utf-8"), b" ")
    bin_chunk = pad4(blob)
    total_length = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    header = struct.pack("<4sII", b"glTF", 2, total_length)
    chunks = (
        struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
        + struct.pack("<I4s", len(bin_chunk), b"BIN\x00")
        + bin_chunk
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(header + chunks)
    print(f"Wrote {OUT}")
    print(f"vertices={len(positions)} triangles={len(indices) // 3} height={max_pos[1] - min_pos[1]:.3f}m min={min_pos} max={max_pos}")


if __name__ == "__main__":
    build()
