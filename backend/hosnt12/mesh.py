from typing import NamedTuple

import numpy as np


class MeshData(NamedTuple):
    coords: np.ndarray
    elements: np.ndarray
    node_map: dict[tuple[int, int], int]

def build_mesh(a: float, b: float, m: int, n: int) -> MeshData:
    """Generate structured Q8 mesh with bottom-to-top row numbering."""
    xs = np.linspace(0.0, a, 2 * m + 1)
    ys = np.linspace(0.0, b, 2 * n + 1)
    node_map: dict[tuple[int, int], int] = {}
    coords = []
    for j in range(2 * n + 1):
        for i in range(2 * m + 1):
            if i % 2 == 1 and j % 2 == 1:
                continue
            node_map[(i, j)] = len(coords)
            coords.append((xs[i], ys[j]))
    coords_arr = np.asarray(coords, dtype=float)

    elements = []
    for ey in range(n):
        for ex in range(m):
            i, j = 2 * ex, 2 * ey
            elements.append([
                node_map[(i, j + 2)],     # Node 1: top-left
                node_map[(i + 1, j + 2)], # Node 2: top-mid
                node_map[(i + 2, j + 2)], # Node 3: top-right
                node_map[(i + 2, j + 1)], # Node 4: right-mid
                node_map[(i + 2, j)],     # Node 5: bottom-right
                node_map[(i + 1, j)],     # Node 6: bottom-mid
                node_map[(i, j)],         # Node 7: bottom-left
                node_map[(i, j + 1)],     # Node 8: left-mid
            ])
    return MeshData(coords_arr, np.asarray(elements, dtype=int), node_map)
