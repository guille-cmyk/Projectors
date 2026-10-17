"""
Procedural 3D Mesh Generator for Projectors.
Generates:
1. A clean, dimensionally accurate Chassis Box (width x height x depth) with zero decorative clutter.
2. Super-detailed physical FOV Origin geometry INSIDE the chassis box:
   - Principal Nodal Point / Exit Pupil at local (0, 0, 0) with 3-axis coordinate crosshairs & nodal rings.
   - Internal DMD / 3LCD / LCoS Imager Chip plane at Z = +f_eff with 4 conjugate chief rays converging to (0, 0, 0).
   - Internal FOV Frustum Pyramid expanding from (0, 0, 0) to the front chassis face at Z = -d_fov_z
     (accounting for throw ratio, aspect ratio, and horizontal/vertical lens shift).
   - Internal dimensional datum lines showing fov_origin_depth (Z), lens_offset_x (X), and lens_offset_y (Y)
     relative to the chassis box center and faces.
3. Schematic Installation Supports (CEILING, TRUSS, TABLETOP, NONE) and exact computation of the
   Installation Point Centroid P_inst used as the kinematic pivot point for the projector's FOV.
"""

import math
from typing import Dict, List, Tuple
import bpy
import bmesh
from mathutils import Vector

from . import projector_central

# Material Slot Indices (7 slots)
MAT_CHASSIS = 0
MAT_LENS_BARREL = 1
MAT_LENS_GLASS = 2
MAT_IO_PANEL = 3
MAT_MOUNT_METAL = 4
MAT_MOUNT_HARDWARE = 5
MAT_RUBBER_FEET = 6


def get_or_create_material(
    name: str,
    color: Tuple[float, float, float, float],
    metallic: float = 0.0,
    roughness: float = 0.4,
    transmission: float = 0.0,
    ior: float = 1.45,
    alpha: float = 1.0,
    emission_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    """Create or retrieve a Principled BSDF material with optional transparency and emission."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out_node = nodes.new(type='ShaderNodeOutputMaterial')
    out_node.location = (300, 0)
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)

    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    if 'Alpha' in bsdf.inputs:
        bsdf.inputs['Alpha'].default_value = alpha
    if 'Transmission Weight' in bsdf.inputs:
        bsdf.inputs['Transmission Weight'].default_value = transmission
    elif 'Transmission' in bsdf.inputs:
        bsdf.inputs['Transmission'].default_value = transmission
    if 'IOR' in bsdf.inputs:
        bsdf.inputs['IOR'].default_value = ior
    if 'Emission Color' in bsdf.inputs:
        bsdf.inputs['Emission Color'].default_value = emission_color
    elif 'Emission' in bsdf.inputs:
        bsdf.inputs['Emission'].default_value = emission_color
    if 'Emission Strength' in bsdf.inputs:
        bsdf.inputs['Emission Strength'].default_value = emission_strength

    if alpha < 1.0 or transmission > 0.0:
        if hasattr(mat, 'blend_method'):
            mat.blend_method = 'BLEND'
    mat.diffuse_color = (color[0], color[1], color[2], alpha)

    links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])
    return mat


def setup_projector_materials(obj: bpy.types.Object, chassis_color: str = 'WHITE') -> None:
    """Ensure all 7 material slots are assigned to the projector visual mesh object."""
    body_rgb = (0.90, 0.92, 0.95, 1.0) if chassis_color == 'WHITE' else (0.10, 0.11, 0.13, 1.0)
    body_mat_name = f"Projector_Chassis_{chassis_color}"

    mats = [
        # 0: Clean alpha-transparent chassis box so internal FOV origin is crystal clear without refraction noise
        get_or_create_material(
            body_mat_name, body_rgb, metallic=0.05, roughness=0.15,
            transmission=0.0, alpha=0.22
        ),
        # 1: Optical datum axes & internal reference struts (Crisp Gold/Yellow)
        get_or_create_material(
            "Projector_Lens_Barrel", (1.0, 0.78, 0.05, 1.0), metallic=0.2, roughness=0.2,
            emission_color=(1.0, 0.78, 0.05, 1.0), emission_strength=1.5
        ),
        # 2: Physical FOV Origin Nodal Point & Internal FOV Frustum Pyramid (Glowing Cyan)
        get_or_create_material(
            "Projector_Lens_Glass", (0.0, 0.95, 1.0, 1.0), metallic=0.0, roughness=0.1,
            transmission=0.4, alpha=0.85,
            emission_color=(0.0, 0.92, 1.0, 1.0), emission_strength=2.5
        ),
        # 3: Internal DMD / 3LCD Imager Sensor Plane (Emerald Green)
        get_or_create_material(
            "Projector_IO_Panel", (0.05, 0.95, 0.35, 1.0), metallic=0.3, roughness=0.2,
            emission_color=(0.05, 0.95, 0.35, 1.0), emission_strength=1.8
        ),
        # 4: Schematic Installation Support Structure (Steel Gray)
        get_or_create_material(
            "Projector_Mount_Metal", (0.22, 0.24, 0.27, 1.0), metallic=0.75, roughness=0.35
        ),
        # 5: Installation Centroid Pivot Marker & Lever Arm (Vibrant Magenta/Orange)
        get_or_create_material(
            "Projector_Mount_Hardware", (1.0, 0.18, 0.05, 1.0), metallic=0.2, roughness=0.2,
            emission_color=(1.0, 0.22, 0.05, 1.0), emission_strength=2.5
        ),
        # 6: Tabletop Support Pads
        get_or_create_material(
            "Projector_Rubber_Feet", (0.12, 0.12, 0.14, 1.0), metallic=0.1, roughness=0.8
        ),
    ]

    obj.data.materials.clear()
    for mat in mats:
        obj.data.materials.append(mat)


# ==============================================================================
# Procedural BMesh Primitives
# ==============================================================================

def add_box(
    bm: bmesh.types.BMesh,
    x_min: float, x_max: float,
    y_min: float, y_max: float,
    z_min: float, z_max: float,
    mat_idx: int = 0,
) -> List[bmesh.types.BMFace]:
    """Add an axis-aligned rectangular box with the given material index."""
    verts = [
        bm.verts.new((x_min, y_min, z_min)),  # 0
        bm.verts.new((x_max, y_min, z_min)),  # 1
        bm.verts.new((x_max, y_max, z_min)),  # 2
        bm.verts.new((x_min, y_max, z_min)),  # 3
        bm.verts.new((x_min, y_min, z_max)),  # 4
        bm.verts.new((x_max, y_min, z_max)),  # 5
        bm.verts.new((x_max, y_max, z_max)),  # 6
        bm.verts.new((x_min, y_max, z_max)),  # 7
    ]
    face_indices = [
        (0, 3, 2, 1),  # Front (Z min)
        (4, 5, 6, 7),  # Back (Z max)
        (0, 1, 5, 4),  # Bottom (Y min)
        (2, 3, 7, 6),  # Top (Y max)
        (0, 4, 7, 3),  # Left (X min)
        (1, 2, 6, 5),  # Right (X max)
    ]
    new_faces = []
    for idxs in face_indices:
        f = bm.faces.new([verts[i] for i in idxs])
        f.material_index = mat_idx
        new_faces.append(f)
    return new_faces


def add_cylinder(
    bm: bmesh.types.BMesh,
    center: Tuple[float, float, float],
    radius: float,
    depth: float,
    axis: str = 'Z',
    segments: int = 24,
    mat_idx: int = 0,
    cap_ends: bool = True,
) -> List[bmesh.types.BMFace]:
    """Add a cylinder along axis X, Y, or Z."""
    cx, cy, cz = center
    half_d = depth / 2.0
    ring1_verts = []
    ring2_verts = []

    for i in range(segments):
        th = 2.0 * math.pi * i / segments
        u = radius * math.cos(th)
        v = radius * math.sin(th)
        if axis == 'Z':
            p1 = (cx + u, cy + v, cz - half_d)
            p2 = (cx + u, cy + v, cz + half_d)
        elif axis == 'Y':
            p1 = (cx + u, cy - half_d, cz + v)
            p2 = (cx + u, cy + half_d, cz + v)
        else:  # 'X'
            p1 = (cx - half_d, cy + u, cz + v)
            p2 = (cx + half_d, cy + u, cz + v)
        ring1_verts.append(bm.verts.new(p1))
        ring2_verts.append(bm.verts.new(p2))

    new_faces = []
    for i in range(segments):
        i_next = (i + 1) % segments
        f = bm.faces.new([ring1_verts[i], ring1_verts[i_next], ring2_verts[i_next], ring2_verts[i]])
        f.material_index = mat_idx
        new_faces.append(f)

    if cap_ends:
        f1 = bm.faces.new(list(reversed(ring1_verts)))
        f1.material_index = mat_idx
        new_faces.append(f1)
        f2 = bm.faces.new(ring2_verts)
        f2.material_index = mat_idx
        new_faces.append(f2)

    return new_faces


def add_tube(
    bm: bmesh.types.BMesh,
    p1: Vector,
    p2: Vector,
    radius: float,
    segments: int = 12,
    mat_idx: int = 0,
    cap_ends: bool = True,
) -> List[bmesh.types.BMFace]:
    """Add a 3D cylindrical strut connecting two arbitrary 3D points p1 and p2."""
    v_diff = p2 - p1
    length = v_diff.length
    if length < 1e-6:
        return []

    direction = v_diff.normalized()
    up = Vector((0, 1, 0)) if abs(direction.y) < 0.9 else Vector((1, 0, 0))
    right = direction.cross(up).normalized()
    perp_up = right.cross(direction).normalized()

    ring1_verts = []
    ring2_verts = []
    for i in range(segments):
        th = 2.0 * math.pi * i / segments
        offset = (right * math.cos(th) + perp_up * math.sin(th)) * radius
        ring1_verts.append(bm.verts.new(p1 + offset))
        ring2_verts.append(bm.verts.new(p2 + offset))

    new_faces = []
    for i in range(segments):
        i_next = (i + 1) % segments
        f = bm.faces.new([ring1_verts[i], ring1_verts[i_next], ring2_verts[i_next], ring2_verts[i]])
        f.material_index = mat_idx
        new_faces.append(f)

    if cap_ends:
        f1 = bm.faces.new(list(reversed(ring1_verts)))
        f1.material_index = mat_idx
        new_faces.append(f1)
        f2 = bm.faces.new(ring2_verts)
        f2.material_index = mat_idx
        new_faces.append(f2)

    return new_faces


def add_octahedron_marker(
    bm: bmesh.types.BMesh,
    center: Vector,
    radius: float,
    mat_idx: int = 0,
) -> List[bmesh.types.BMFace]:
    """Add a precision 3D diamond/octahedron nodal marker centered at `center`."""
    cx, cy, cz = center.x, center.y, center.z
    v_top = bm.verts.new((cx, cy + radius, cz))
    v_bot = bm.verts.new((cx, cy - radius, cz))
    v_xp = bm.verts.new((cx + radius, cy, cz))
    v_xn = bm.verts.new((cx - radius, cy, cz))
    v_zp = bm.verts.new((cx, cy, cz + radius))
    v_zn = bm.verts.new((cx, cy, cz - radius))

    tris = [
        (v_top, v_zp, v_xp),
        (v_top, v_xp, v_zn),
        (v_top, v_zn, v_xn),
        (v_top, v_xn, v_zp),
        (v_bot, v_xp, v_zp),
        (v_bot, v_zn, v_xp),
        (v_bot, v_xn, v_zn),
        (v_bot, v_zp, v_xn),
    ]
    faces = []
    for tri in tris:
        f = bm.faces.new(tri)
        f.material_index = mat_idx
        faces.append(f)
    return faces


def add_frame_loop(
    bm: bmesh.types.BMesh,
    corners: List[Vector],
    radius: float,
    mat_idx: int = 0,
) -> None:
    """Connect a closed loop of 3D points with thin cylindrical struts."""
    n = len(corners)
    for i in range(n):
        add_tube(bm, corners[i], corners[(i + 1) % n], radius=radius, segments=8, mat_idx=mat_idx)


# ==============================================================================
# Coordinate Geometry & Centroid Evaluation
# ==============================================================================

def compute_chassis_bounds(
    width: float,
    height: float,
    depth: float,
    lens_offset_x: float,
    lens_offset_y: float,
    fov_origin_depth: float,
    mount_type: str,
    inverted: bool,
) -> Dict[str, float]:
    """
    Compute the exact chassis box coordinates in local projector space where
    local (0, 0, 0) is the physical FOV origin inside the chassis.

    Returns dict with:
        x_c, y_c, z_c: Center of the chassis box
        x_min, x_max, y_min, y_max, z_front, z_rear: Bounding planes of the chassis box
        y_mount: Y coordinate of the mounting face on the chassis box
        is_inverted: Whether the chassis is inverted (upside-down)
        dir_y: +1.0 if support extends along +Y (ceiling/truss inverted), -1.0 if along -Y
    """
    # Clamp fov_origin_depth so (0, 0, 0) is strictly inside the chassis box along Z
    d_fov_z = max(0.008, min(float(fov_origin_depth), float(depth) - 0.008))
    z_front = -d_fov_z
    z_rear = z_front + depth
    z_c = z_front + depth / 2.0

    # Horizontal offset: if lens is offset +X from chassis center, chassis center is at -lens_offset_x
    max_off_x = max(0.0, width / 2.0 - 0.008)
    clamped_off_x = max(-max_off_x, min(float(lens_offset_x), max_off_x))
    x_c = -clamped_off_x
    x_min = x_c - width / 2.0
    x_max = x_c + width / 2.0

    # Orientation & Vertical offset
    is_inverted = bool(inverted) if mount_type in {'CEILING', 'TRUSS'} else False
    max_off_y = max(0.0, height / 2.0 - 0.008)
    clamped_off_y = max(-max_off_y, min(float(lens_offset_y), max_off_y))

    if is_inverted:
        # Inverted: lens is shifted toward -Y relative to chassis center -> chassis center is at +clamped_off_y
        y_c = clamped_off_y
        y_min = y_c - height / 2.0
        y_max = y_c + height / 2.0
        y_mount = y_max
        dir_y = 1.0
    else:
        # Upright: lens is shifted toward +Y relative to chassis center -> chassis center is at -clamped_off_y
        y_c = -clamped_off_y
        y_min = y_c - height / 2.0
        y_max = y_c + height / 2.0
        if mount_type in {'CEILING', 'TRUSS'}:
            # Upright under ceiling/truss: mount attaches to top face (+Y) or bottom face (-Y)
            y_mount = y_min
            dir_y = -1.0
        else:
            # Tabletop / None: feet are on bottom face (-Y)
            y_mount = y_min
            dir_y = -1.0

    return {
        "x_c": x_c,
        "y_c": y_c,
        "z_c": z_c,
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
        "z_front": z_front,
        "z_rear": z_rear,
        "d_fov_z": d_fov_z,
        "y_mount": y_mount,
        "is_inverted": is_inverted,
        "dir_y": dir_y,
    }


def get_mounting_points(width: float, depth: float, x_c: float, z_c: float) -> List[Tuple[float, float]]:
    """Return the (X, Z) coordinates of the 4 chassis mounting points."""
    dx = width * 0.28
    dz = depth * 0.28
    return [
        (x_c - dx, z_c - dz),
        (x_c + dx, z_c - dz),
        (x_c - dx, z_c + dz),
        (x_c + dx, z_c + dz),
    ]


def compute_installation_centroid(
    width: float,
    height: float,
    depth: float,
    lens_offset_x: float,
    lens_offset_y: float,
    fov_origin_depth: float,
    mount_type: str,
    mount_pole_length: float,
    inverted: bool,
) -> Vector:
    """
    Evaluate the exact 3D centroid of the selected installation support point in local coordinates.
    - NONE: Returns Vector((0, 0, 0)) (pivot remains at the internal FOV origin).
    - TABLETOP: Centroid of the 4 tabletop support foot contact pads.
    - CEILING: Centroid of the ceiling structural attachment plate.
    - TRUSS: Centroid of the 50mm truss pipe / half-coupler clamp axis.
    """
    b = compute_chassis_bounds(
        width, height, depth, lens_offset_x, lens_offset_y,
        fov_origin_depth, mount_type, inverted
    )
    x_c, z_c, y_mount, dir_y = b["x_c"], b["z_c"], b["y_mount"], b["dir_y"]

    if mount_type == 'NONE':
        return Vector((0.0, 0.0, 0.0))
    elif mount_type == 'TABLETOP':
        # Centroid of the 4 tabletop support pads on the underside (-Y)
        foot_height = 0.020
        return Vector((x_c, b["y_min"] - foot_height, z_c))
    elif mount_type == 'CEILING':
        # Spider drop (0.045m) + pole_length + half of ceiling flange thickness (0.004m)
        flange_centroid_y = y_mount + dir_y * (0.045 + float(mount_pole_length) + 0.004)
        return Vector((x_c, flange_centroid_y, z_c))
    elif mount_type == 'TRUSS':
        # Spider adapter (0.035m) + coupler block (0.025m) + truss pipe radius (0.025m)
        truss_pipe_centroid_y = y_mount + dir_y * 0.085
        return Vector((x_c, truss_pipe_centroid_y, z_c))

    return Vector((0.0, 0.0, 0.0))


# ==============================================================================
# 1. Clean Dimensionally Accurate Chassis Box
# ==============================================================================

def build_simple_chassis_box(bm: bmesh.types.BMesh, bounds: Dict[str, float]) -> None:
    """
    Build strictly a clean rectangular box with the exact measures of the chassis
    (width x height x depth), without decorative vents, buttons, or ports.
    """
    add_box(
        bm,
        bounds["x_min"], bounds["x_max"],
        bounds["y_min"], bounds["y_max"],
        bounds["z_front"], bounds["z_rear"],
        mat_idx=MAT_CHASSIS,
    )


# ==============================================================================
# 2. Super-Detailed Physical FOV Origin Inside the Chassis
# ==============================================================================

def build_internal_fov_origin_assembly(
    bm: bmesh.types.BMesh,
    bounds: Dict[str, float],
    throw_ratio: float,
    aspect_ratio: float,
    h_shift_pct: float,
    v_shift_pct: float,
    imager_diagonal_inch: float,
) -> None:
    """
    Build the super-detailed physical FOV Origin assembly INSIDE the chassis box at (0, 0, 0):
    1. Principal Nodal Point / Exit Pupil marker (octahedron + orthogonal nodal rings + 3-axis crosshairs) at (0, 0, 0).
    2. Internal DMD / 3LCD Imager Chip plane at Z = +f_eff behind (0, 0, 0) with 4 conjugate chief rays.
    3. Internal FOV Frustum Pyramid expanding from (0, 0, 0) to the front chassis face at Z = -d_fov_z
       (including intermediate aperture plane and front exit window frame).
    4. Dimensional datum struts linking (0, 0, 0) to the chassis center (x_c, y_c, z_c) and front/rear faces.
    """
    d_fov_z = bounds["d_fov_z"]
    z_front = bounds["z_front"]  # = -d_fov_z
    z_rear = bounds["z_rear"]
    x_c, y_c, z_c = bounds["x_c"], bounds["y_c"], bounds["z_c"]
    depth = z_rear - z_front

    origin = Vector((0.0, 0.0, 0.0))
    tr = max(0.2, float(throw_ratio))
    ar = max(0.5, float(aspect_ratio))
    h_shift = float(h_shift_pct) / 100.0
    v_shift = float(v_shift_pct) / 100.0

    # Evaluate optical engine geometry inside chassis
    _, f_eff, s_w, s_h = projector_central.evaluate_fov_origin_depth(
        tr, depth, imager_diagonal_inch, ar
    )
    # Ensure imager plane Z = +f_eff stays strictly inside the rear face of the chassis
    z_imager = min(f_eff, max(0.012, z_rear - 0.008))
    scale_imager = z_imager / f_eff if f_eff > 1e-6 else 1.0
    imager_w = max(0.012, s_w * scale_imager)
    imager_h = max(0.008, s_h * scale_imager)

    # --- A. Principal Nodal Point Marker & 3-Axis Crosshair at (0, 0, 0) ---
    add_octahedron_marker(bm, origin, radius=0.006, mat_idx=MAT_LENS_GLASS)

    # Principal Plane H' circular nodal ring at Z = 0
    add_cylinder(
        bm, (0.0, 0.0, 0.0), radius=0.014, depth=0.0018,
        axis='Z', segments=24, mat_idx=MAT_LENS_GLASS, cap_ends=False
    )
    # Orthogonal nodal rings (X and Y axes)
    add_cylinder(
        bm, (0.0, 0.0, 0.0), radius=0.010, depth=0.0014,
        axis='X', segments=20, mat_idx=MAT_LENS_GLASS, cap_ends=False
    )
    add_cylinder(
        bm, (0.0, 0.0, 0.0), radius=0.010, depth=0.0014,
        axis='Y', segments=20, mat_idx=MAT_LENS_GLASS, cap_ends=False
    )

    # Local 3-Axis Precision Crosshairs at (0, 0, 0)
    axis_len = 0.024
    strut_r = 0.0010
    add_tube(bm, Vector((-axis_len, 0.0, 0.0)), Vector((axis_len, 0.0, 0.0)), radius=strut_r, segments=8, mat_idx=MAT_LENS_BARREL)
    add_tube(bm, Vector((0.0, -axis_len, 0.0)), Vector((0.0, axis_len, 0.0)), radius=strut_r, segments=8, mat_idx=MAT_LENS_BARREL)

    # Optical Axis Centerline from Imager Plane (+f_eff) through Nodal Point (0,0,0) to Front Face (-d_fov_z)
    add_tube(bm, Vector((0.0, 0.0, z_imager)), Vector((0.0, 0.0, z_front)), radius=0.0012, segments=10, mat_idx=MAT_LENS_BARREL)

    # --- B. Internal FOV Frustum Pyramid from (0, 0, 0) to Front Chassis Face (Z = z_front) ---
    # At distance d_fov_z along -Z, projected width is d_fov_z / tr, height is width / ar
    w_front = d_fov_z / tr
    h_front = w_front / ar
    # Apply lens shift offsets
    cx_front = w_front * h_shift
    cy_front = h_front * v_shift

    # Clamp front aperture frame slightly inside chassis outer bounds if extreme shift/wide angle
    half_w = w_front / 2.0
    half_h = h_front / 2.0
    front_corners = [
        Vector((cx_front - half_w, cy_front - half_h, z_front)),
        Vector((cx_front + half_w, cy_front - half_h, z_front)),
        Vector((cx_front + half_w, cy_front + half_h, z_front)),
        Vector((cx_front - half_w, cy_front + half_h, z_front)),
    ]

    # 4 Primary Frustum Rays from internal FOV origin (0, 0, 0) to the front chassis face
    ray_r = 0.0013
    for fc in front_corners:
        add_tube(bm, origin, fc, radius=ray_r, segments=8, mat_idx=MAT_LENS_GLASS)

    # Rectangular FOV Exit Aperture Frame on the front face of the chassis box (Z = z_front)
    add_frame_loop(bm, front_corners, radius=0.0016, mat_idx=MAT_LENS_GLASS)

    # Intermediate FOV Cross-Section Frame halfway between (0, 0, 0) and front face (Z = z_front / 2)
    mid_corners = [c * 0.5 for c in front_corners]
    add_frame_loop(bm, mid_corners, radius=0.0010, mat_idx=MAT_LENS_GLASS)

    # --- C. Internal Imager / Sensor Plane (DMD / 3LCD) at Z = +z_imager ---
    # Conjugate shift on the imager side is inverted (-h_shift, -v_shift)
    cx_img = -imager_w * h_shift
    cy_img = -imager_h * v_shift
    img_hw = imager_w / 2.0
    img_hh = imager_h / 2.0

    # Thin imager chip wafer box at Z = +z_imager
    add_box(
        bm,
        cx_img - img_hw, cx_img + img_hw,
        cy_img - img_hh, cy_img + img_hh,
        z_imager, z_imager + 0.0025,
        mat_idx=MAT_IO_PANEL,
    )

    imager_corners = [
        Vector((cx_img - img_hw, cy_img - img_hh, z_imager)),
        Vector((cx_img + img_hw, cy_img - img_hh, z_imager)),
        Vector((cx_img + img_hw, cy_img + img_hh, z_imager)),
        Vector((cx_img - img_hw, cy_img + img_hh, z_imager)),
    ]
    add_frame_loop(bm, imager_corners, radius=0.0010, mat_idx=MAT_LENS_BARREL)

    # 4 Conjugate Chief Rays from Imager corners converging to the FOV Origin (0, 0, 0)
    for ic in imager_corners:
        add_tube(bm, ic, origin, radius=0.0009, segments=8, mat_idx=MAT_IO_PANEL)

    # --- D. Internal Chassis Coordinate Datum Struts (Offsets to Chassis Center & Rear Face) ---
    datum_r = 0.0009
    chassis_center = Vector((x_c, y_c, z_c))
    # Marker at geometric center of the chassis box
    add_octahedron_marker(bm, chassis_center, radius=0.0045, mat_idx=MAT_LENS_BARREL)

    # Orthogonal offset path from Chassis Center (x_c, y_c, z_c) -> (x_c, y_c, 0) -> (x_c, 0, 0) -> FOV Origin (0, 0, 0)
    p_z0 = Vector((x_c, y_c, 0.0))
    p_y0 = Vector((x_c, 0.0, 0.0))
    add_tube(bm, chassis_center, p_z0, radius=datum_r, segments=8, mat_idx=MAT_LENS_BARREL)
    if (p_y0 - p_z0).length > 1e-4:
        add_tube(bm, p_z0, p_y0, radius=datum_r, segments=8, mat_idx=MAT_LENS_BARREL)
    if (origin - p_y0).length > 1e-4:
        add_tube(bm, p_y0, origin, radius=datum_r, segments=8, mat_idx=MAT_LENS_BARREL)

    # Rear datum line from imager plane to rear chassis face along optical axis
    add_tube(bm, Vector((0.0, 0.0, z_imager + 0.0025)), Vector((0.0, 0.0, z_rear)), radius=0.0008, segments=8, mat_idx=MAT_LENS_BARREL)


# ==============================================================================
# 3. Schematic Installation Supports & Installation Centroid Pivot Marker
# ==============================================================================

def build_pivot_centroid_marker(bm: bmesh.types.BMesh, p_inst: Vector) -> None:
    """
    Build a high-visibility 3D Gimbal Pivot Marker at the installation point centroid P_inst
    and a kinematic lever-arm line connecting P_inst to the internal FOV origin (0, 0, 0).
    """
    origin = Vector((0.0, 0.0, 0.0))
    # Central diamond marker at P_inst
    add_octahedron_marker(bm, p_inst, radius=0.012, mat_idx=MAT_MOUNT_HARDWARE)

    # 3 Orthogonal Gimbal Pivot Rings around P_inst (sized to surround truss/ceiling support centroid)
    for ax in ('X', 'Y', 'Z'):
        add_cylinder(
            bm, (p_inst.x, p_inst.y, p_inst.z),
            radius=0.038, depth=0.0028,
            axis=ax, segments=28, mat_idx=MAT_MOUNT_HARDWARE, cap_ends=False
        )

    # 3-Axis Pivot Crosshairs at P_inst
    cross_len = 0.052
    add_tube(bm, p_inst + Vector((-cross_len, 0, 0)), p_inst + Vector((cross_len, 0, 0)), radius=0.0018, segments=8, mat_idx=MAT_MOUNT_HARDWARE)
    add_tube(bm, p_inst + Vector((0, -cross_len, 0)), p_inst + Vector((0, cross_len, 0)), radius=0.0018, segments=8, mat_idx=MAT_MOUNT_HARDWARE)
    add_tube(bm, p_inst + Vector((0, 0, -cross_len)), p_inst + Vector((0, 0, cross_len)), radius=0.0018, segments=8, mat_idx=MAT_MOUNT_HARDWARE)

    # Direct Kinematic Lever-Arm Vector Line from Installation Centroid P_inst to Internal FOV Origin (0, 0, 0)
    if (p_inst - origin).length > 1e-4:
        add_tube(bm, p_inst, origin, radius=0.0020, segments=10, mat_idx=MAT_MOUNT_HARDWARE)


def build_tabletop_support(
    bm: bmesh.types.BMesh,
    mount_pts: List[Tuple[float, float]],
    y_min: float,
    p_inst: Vector,
) -> None:
    """Build 4 clean tabletop leveling feet and connect them to the tabletop installation centroid."""
    foot_h = 0.020
    y_foot_center = y_min - foot_h / 2.0
    for px, pz in mount_pts:
        add_cylinder(
            bm, (px, y_foot_center, pz), radius=0.012, depth=foot_h,
            axis='Y', segments=16, mat_idx=MAT_RUBBER_FEET
        )
        # Reference strut on contact plane from each foot base to tabletop installation centroid
        foot_contact = Vector((px, y_min - foot_h, pz))
        add_tube(bm, foot_contact, p_inst, radius=0.0012, segments=8, mat_idx=MAT_MOUNT_METAL)


def build_ceiling_support(
    bm: bmesh.types.BMesh,
    mount_pts: List[Tuple[float, float]],
    x_c: float,
    z_c: float,
    y_mount: float,
    dir_y: float,
    pole_length: float,
) -> None:
    """Build a clean schematic ceiling spider mount, drop column, and ceiling plate."""
    hub_y = y_mount + dir_y * 0.045
    hub_v = Vector((x_c, hub_y, z_c))

    # 4 spider struts from chassis mount points to hub
    for px, pz in mount_pts:
        add_tube(bm, Vector((px, y_mount, pz)), hub_v, radius=0.004, segments=10, mat_idx=MAT_MOUNT_METAL)

    # Extension drop pipe from hub to ceiling plate
    pipe_end_y = hub_y + dir_y * float(pole_length)
    add_tube(bm, hub_v, Vector((x_c, pipe_end_y, z_c)), radius=0.016, segments=16, mat_idx=MAT_MOUNT_METAL)

    # Clean rectangular ceiling structural plate (thickness 0.008m, centered at P_inst)
    flange_w = 0.140
    flange_y1 = pipe_end_y
    flange_y2 = pipe_end_y + dir_y * 0.008
    add_box(
        bm,
        x_c - flange_w / 2.0, x_c + flange_w / 2.0,
        min(flange_y1, flange_y2), max(flange_y1, flange_y2),
        z_c - flange_w / 2.0, z_c + flange_w / 2.0,
        mat_idx=MAT_MOUNT_METAL,
    )


def build_truss_support(
    bm: bmesh.types.BMesh,
    mount_pts: List[Tuple[float, float]],
    x_c: float,
    z_c: float,
    y_mount: float,
    dir_y: float,
) -> None:
    """Build a clean schematic truss spider adapter, coupler block, and 50mm truss chord pipe."""
    hub_y = y_mount + dir_y * 0.035
    hub_v = Vector((x_c, hub_y, z_c))

    # 4 spider struts from chassis mount points to adapter hub
    for px, pz in mount_pts:
        add_tube(bm, Vector((px, y_mount, pz)), hub_v, radius=0.004, segments=10, mat_idx=MAT_MOUNT_METAL)

    # Coupler stem connecting hub to truss pipe axis
    pipe_center_y = y_mount + dir_y * 0.085
    add_box(
        bm,
        x_c - 0.020, x_c + 0.020,
        min(hub_y, pipe_center_y), max(hub_y, pipe_center_y),
        z_c - 0.020, z_c + 0.020,
        mat_idx=MAT_MOUNT_METAL,
    )

    # 50mm (r = 0.025m) truss chord pipe along X axis, centered at P_inst = (x_c, pipe_center_y, z_c)
    pipe_p1 = Vector((x_c - 0.22, pipe_center_y, z_c))
    pipe_p2 = Vector((x_c + 0.22, pipe_center_y, z_c))
    add_tube(bm, pipe_p1, pipe_p2, radius=0.025, segments=20, mat_idx=MAT_MOUNT_METAL)

    # Half-coupler collar around the truss pipe at x_c
    add_cylinder(
        bm, (x_c, pipe_center_y, z_c), radius=0.031, depth=0.044,
        axis='X', segments=20, mat_idx=MAT_MOUNT_METAL
    )


# ==============================================================================
# Master Mesh Generation Entry Point
# ==============================================================================

def build_projector_mesh(
    mesh_obj: bpy.types.Object,
    width: float = 0.380,
    height: float = 0.121,
    depth: float = 0.277,
    lens_offset_x: float = 0.085,
    lens_offset_y: float = 0.012,
    fov_origin_depth: float = 0.062,
    imager_diagonal_inch: float = 0.65,
    throw_ratio: float = 1.325,
    aspect_ratio: float = 16.0 / 9.0,
    h_shift_pct: float = 0.0,
    v_shift_pct: float = 0.0,
    mount_type: str = 'CEILING',
    mount_pole_length: float = 0.40,
    chassis_color: str = 'WHITE',
    inverted: bool = True,
) -> Vector:
    """
    Build the complete 3D projector visual mesh in `mesh_obj` and return the
    exact Installation Point Centroid `P_inst` in local coordinates.

    Physical Coordinate Architecture:
    - Local (0, 0, 0) is the physical optical origin of the FOV (front principal nodal point)
      strictly INSIDE the chassis box at depth `fov_origin_depth` behind the front face.
    - Front face of the chassis box sits at Z = -fov_origin_depth < 0.
    - Rear face of the chassis box sits at Z = depth - fov_origin_depth > 0.
    - When a support (CEILING, TRUSS, TABLETOP) is selected, returns the exact centroid
      `P_inst` of that installation point so the parent projector's pivot constraint
      rotates the FOV around `P_inst`.
    """
    setup_projector_materials(mesh_obj, chassis_color)

    bm = bmesh.new()

    bounds = compute_chassis_bounds(
        width=width,
        height=height,
        depth=depth,
        lens_offset_x=lens_offset_x,
        lens_offset_y=lens_offset_y,
        fov_origin_depth=fov_origin_depth,
        mount_type=mount_type,
        inverted=inverted,
    )

    # 1. Simple, Dimensionally Accurate Chassis Box (W x H x D)
    build_simple_chassis_box(bm, bounds)

    # 2. Super-Detailed Physical FOV Origin Assembly Inside the Chassis
    build_internal_fov_origin_assembly(
        bm=bm,
        bounds=bounds,
        throw_ratio=throw_ratio,
        aspect_ratio=aspect_ratio,
        h_shift_pct=h_shift_pct,
        v_shift_pct=v_shift_pct,
        imager_diagonal_inch=imager_diagonal_inch,
    )

    # 3. Schematic Installation Support & Installation Centroid Pivot Marker
    mount_pts = get_mounting_points(width, depth, bounds["x_c"], bounds["z_c"])
    p_inst = compute_installation_centroid(
        width=width,
        height=height,
        depth=depth,
        lens_offset_x=lens_offset_x,
        lens_offset_y=lens_offset_y,
        fov_origin_depth=bounds["d_fov_z"],
        mount_type=mount_type,
        mount_pole_length=mount_pole_length,
        inverted=inverted,
    )

    if mount_type == 'TABLETOP':
        build_tabletop_support(bm, mount_pts, bounds["y_min"], p_inst)
        build_pivot_centroid_marker(bm, p_inst)
    elif mount_type == 'CEILING':
        build_ceiling_support(
            bm, mount_pts, bounds["x_c"], bounds["z_c"],
            bounds["y_mount"], bounds["dir_y"], mount_pole_length
        )
        build_pivot_centroid_marker(bm, p_inst)
    elif mount_type == 'TRUSS':
        build_truss_support(
            bm, mount_pts, bounds["x_c"], bounds["z_c"],
            bounds["y_mount"], bounds["dir_y"]
        )
        build_pivot_centroid_marker(bm, p_inst)

    # Finalize BMesh into Mesh data
    bm.to_mesh(mesh_obj.data)
    bm.free()
    mesh_obj.data.update()

    return p_inst
