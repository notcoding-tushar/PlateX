import numpy as np

from .constants import DOF, T1, T1S, T2, T2S, T3, T3S, US, VS, WS, U, V, W


def constrained_dofs(coords: np.ndarray, a: float, b: float, choicebc: int = 1, tol: float = 1e-9) -> np.ndarray:
    """Resolve constrained global DOF indices for the selected boundary condition (1-6)."""
    x0 = np.where(np.abs(coords[:, 0]) <= tol)[0]
    xa = np.where(np.abs(coords[:, 0] - a) <= tol)[0]
    y0 = np.where(np.abs(coords[:, 1]) <= tol)[0]
    yb = np.where(np.abs(coords[:, 1] - b) <= tol)[0]

    x_ss = (V, W, T2, T3, VS, WS, T2S, T3S)
    y_ss = (U, W, T1, T3, US, WS, T1S, T3S)
    all_dofs = tuple(range(DOF))
    fixed = set()

    def add(nodes, dofs):
        for node in nodes:
            base = int(node) * DOF
            fixed.update(base + int(dof) for dof in dofs)

    if choicebc == 1:  # SSSS
        for edge in (x0, xa):
            add(edge, x_ss)
        for edge in (y0, yb):
            add(edge, y_ss)
    elif choicebc == 2:  # CCCC
        for edge in (x0, xa, y0, yb):
            add(edge, all_dofs)
    elif choicebc == 3:  # SFSF
        for edge in (x0, xa):
            add(edge, x_ss)
        bl_corner = int(np.argmin(coords[:, 0] ** 2 + coords[:, 1] ** 2))
        tl_corner = int(np.argmin(coords[:, 0] ** 2 + (coords[:, 1] - b) ** 2))
        add([bl_corner, tl_corner], [U, US])
    elif choicebc == 4:  # FSFS
        for edge in (y0, yb):
            add(edge, y_ss)
        bl_corner = int(np.argmin(coords[:, 0] ** 2 + coords[:, 1] ** 2))
        br_corner = int(np.argmin((coords[:, 0] - a) ** 2 + coords[:, 1] ** 2))
        add([bl_corner, br_corner], [V, VS])
    elif choicebc == 5:  # SCSC
        for edge in (x0, xa):
            add(edge, x_ss)
        for edge in (y0, yb):
            add(edge, all_dofs)
    elif choicebc == 6:  # CSCS
        for edge in (y0, yb):
            add(edge, y_ss)
        for edge in (x0, xa):
            add(edge, all_dofs)
    else:
        raise ValueError("Boundary condition choice must be from 1 to 6.")

    # Plate kinematics of the reference (TSDT, Zidi et al. 2014): w is constant through the thickness
    # (eps_z = 0), so the thickness-stretching DOFs theta3, w0*, theta3* are zero at every node.
    add(range(coords.shape[0]), (T3, WS, T3S))

    return np.array(sorted(fixed), dtype=int)
