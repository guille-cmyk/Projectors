"""
Procedural 3D Mesh Generator for Projectors.
Builds an engineering-accurate physical projector chassis, optical lens assembly,
underside metric mounting points, and modular professional mounting hardware
(Universal Ceiling Spider Mount, Theatrical Truss Half-Coupler Clamp, Tabletop Feet).
"""

import math
from typing import List, Tuple
import bpy
import bmesh
from mathutils import Matrix, Vector

# Material Slot Indices
MAT_CHASSIS = 0
MAT_LENS_BARREL = 1
MAT_LENS_GLASS = 2
MAT_IO_PANEL = 3
MAT_MOUNT_METAL = 4
MAT_MOUNT_HARDWARE = 5
MAT_RUBBER_FEET = 6


def get_or_create_material(name: str, color: Tuple[float, float, float, float], metallic: float = 0.0,
                           roughness: float = 0.4, transmission: float = 0.0, ior: float = 1.45) -> bpy.types.Material:
    """Create or retrieve a Principled BSDF PBR material."""
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
        if 'Transmission Weight' in bsdf.inputs:
            bsdf.inputs['Transmission Weight'].default_value = transmission
        elif 'Transmission' in bsdf.inputs:
            bsdf.inputs['Transmission'].default_value = transmission
        if 'IOR' in bsdf.inputs:
            bsdf.inputs['IOR'].default_value = ior

        links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])
    return mat


def setup_projector_materials(obj: bpy.types.Object, chassis_color: str = 'WHITE') -> None:
    """Ensure all 7 material slots are assigned to the projector body mesh object."""
    body_color = (0.92, 0.92, 0.93, 1.0) if chassis_color == 'WHITE' else (0.05, 0.05, 0.05, 1.0)
    body_mat_name = f"Projector_Chassis_{chassis_color}"

    mats = [
        get_or_create_material(body_mat_name, body_color, metallic=0.05, roughness=0.35),
        get_or_create_material("Projector_Lens_Barrel", (0.03, 0.03, 0.03, 1.0), metallic=0.85, roughness=0.25),
        get_or_create_material("Projector_Lens_Glass", (0.85, 0.92, 1.0, 1.0), metallic=0.0, roughness=0.02, transmission=0.95, ior=1.52),
        get_or_create_material("Projector_IO_Panel", (0.02, 0.02, 0.02, 1.0), metallic=0.1, roughness=0.6),
        get_or_create_material("Projector_Mount_Metal", (0.08, 0.08, 0.09, 1.0), metallic=0.75, roughness=0.35),
        get_or_create_material("Projector_Mount_Hardware", (0.75, 0.75, 0.78, 1.0), metallic=0.95, roughness=0.15),
        get_or_create_material("Projector_Rubber_Feet", (0.02, 0.02, 0.02, 1.0), metallic=0.0, roughness=0.85),
    ]

    obj.data.materials.clear()
    for mat in mats:
        obj.data.materials.append(mat)


# ==============================================================================
# Procedural BMesh Primitives
# ==============================================================================

def add_box(bm: bmesh.types.BMesh, x_min: float, x_max: float, y_min: float, y_max: float,
            z_min: float, z_max: float, mat_idx: int = 0) -> List[bmesh.types.BMFace]:
    """Add an axis-aligned box with the given material index."""
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


def add_cylinder(bm: bmesh.types.BMesh, center: Tuple[float, float, float], radius: float,
                 depth: float, axis: str = 'Z', segments: int = 24, mat_idx: int = 0,
                 cap_ends: bool = True) -> List[bmesh.types.BMFace]:
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
        # Cap 1
        f1 = bm.faces.new(list(reversed(ring1_verts)))
        f1.material_index = mat_idx
        new_faces.append(f1)
        # Cap 2
        f2 = bm.faces.new(ring2_verts)
        f2.material_index = mat_idx
        new_faces.append(f2)

    return new_faces


def add_tube(bm: bmesh.types.BMesh, p1: Vector, p2: Vector, radius: float,
             segments: int = 16, mat_idx: int = 0, cap_ends: bool = True) -> List[bmesh.types.BMFace]:
    """Add a 3D cylindrical pipe connecting two arbitrary 3D points p1 and p2."""
    v_diff = p2 - p1
    length = v_diff.length
    if length < 1e-6:
        return []

    direction = v_diff.normalized()
    # Find perpendicular vector
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


# ==============================================================================
# Sub-Assemblies
# ==============================================================================

def build_chassis_body(bm: bmesh.types.BMesh, width: float, height: float, depth: float,
                       x_c: float, y_c: float, z_front: float) -> None:
    """Build the main projector chassis body with front lens collar, vents, and details."""
    z_rear = z_front + depth
    x_min = x_c - width / 2.0
    x_max = x_c + width / 2.0
    y_min = y_c - height / 2.0
    y_max = y_c + height / 2.0

    # 1. Main outer housing box
    add_box(bm, x_min, x_max, y_min, y_max, z_front, z_rear, mat_idx=MAT_CHASSIS)

    # 2. Beveled top/side accent plate
    inset = 0.008
    add_box(bm, x_min + inset, x_max - inset, y_max - 0.002, y_max + 0.003,
            z_front + inset, z_rear - inset, mat_idx=MAT_CHASSIS)

    # 3. Front lens cowling recess (surrounds the lens at origin X=0, Y=0)
    lens_shroud_r = 0.048
    add_cylinder(bm, (0.0, 0.0, z_front + 0.004), radius=lens_shroud_r, depth=0.008,
                 axis='Z', segments=32, mat_idx=MAT_CHASSIS, cap_ends=True)

    # 4. Front cooling ventilation louvers (intake vents on opposite side of lens)
    vent_x_start = x_min + 0.03
    vent_x_end = min(x_c - 0.04, -0.05) if x_c >= 0 else x_min + width * 0.45
    if vent_x_end > vent_x_start:
        num_slats = 7
        slat_h = (height * 0.45) / num_slats
        y_slat_base = y_c - height * 0.22
        for s in range(num_slats):
            sy = y_slat_base + s * slat_h
            add_box(bm, vent_x_start, vent_x_end, sy, sy + slat_h * 0.65,
                    z_front - 0.002, z_front + 0.001, mat_idx=MAT_IO_PANEL)

    # 5. Side ventilation grilles (exhaust on right side)
    num_side_vents = 10
    side_vent_w = (depth * 0.5) / num_side_vents
    z_side_start = z_front + depth * 0.25
    for s in range(num_side_vents):
        sz = z_side_start + s * side_vent_w
        add_box(bm, x_max - 0.001, x_max + 0.002, y_c - height * 0.2, y_c + height * 0.2,
                sz, sz + side_vent_w * 0.6, mat_idx=MAT_IO_PANEL)

    # 6. Top control panel (buttons and LED indicators)
    panel_w = 0.065
    panel_d = 0.065
    panel_x = x_c + width * 0.22
    panel_z = z_rear - depth * 0.25
    # Recessed control bed
    add_box(bm, panel_x - panel_w / 2.0, panel_x + panel_w / 2.0,
            y_max + 0.001, y_max + 0.004,
            panel_z - panel_d / 2.0, panel_z + panel_d / 2.0, mat_idx=MAT_IO_PANEL)
    # Power Button
    add_cylinder(bm, (panel_x, y_max + 0.005, panel_z - 0.015), radius=0.007,
                 depth=0.003, axis='Y', segments=16, mat_idx=MAT_MOUNT_HARDWARE)
    # 4-way Nav Ring
    add_cylinder(bm, (panel_x, y_max + 0.005, panel_z + 0.012), radius=0.012,
                 depth=0.002, axis='Y', segments=16, mat_idx=MAT_CHASSIS)
    # Status LEDs (Power, Temp, Lamp)
    for led_i, led_x_off in enumerate([-0.018, 0.0, 0.018]):
        add_cylinder(bm, (panel_x + led_x_off, y_max + 0.005, panel_z - 0.026),
                     radius=0.0025, depth=0.002, axis='Y', segments=12, mat_idx=MAT_LENS_GLASS)

    # 7. Top lens zoom/focus access cavity
    add_box(bm, -0.028, 0.028, y_max - 0.008, y_max + 0.002,
            z_front + 0.015, z_front + 0.065, mat_idx=MAT_IO_PANEL)
    # Zoom wheel & Focus wheel
    add_cylinder(bm, (-0.012, y_max - 0.002, z_front + 0.035), radius=0.014,
                 depth=0.008, axis='X', segments=20, mat_idx=MAT_LENS_BARREL)
    add_cylinder(bm, (0.012, y_max - 0.002, z_front + 0.048), radius=0.014,
                 depth=0.008, axis='X', segments=20, mat_idx=MAT_LENS_BARREL)

    # 8. Rear I/O Connector Bay
    io_w = width * 0.70
    io_h = height * 0.55
    io_x_min = x_c - io_w / 2.0
    io_x_max = x_c + io_w / 2.0
    io_y_min = y_c - io_h / 2.0
    io_y_max = y_c + io_h / 2.0
    # Recessed I/O plate
    add_box(bm, io_x_min, io_x_max, io_y_min, io_y_max,
            z_rear - 0.006, z_rear + 0.001, mat_idx=MAT_IO_PANEL)

    # Ports inside I/O bay:
    # 2x HDMI Ports
    for h_i, hx in enumerate([io_x_min + 0.04, io_x_min + 0.08]):
        add_box(bm, hx - 0.010, hx + 0.010, y_c - 0.004, y_c + 0.004,
                z_rear - 0.008, z_rear - 0.003, mat_idx=MAT_MOUNT_HARDWARE)
    # USB-A Port
    add_box(bm, io_x_min + 0.12 - 0.008, io_x_min + 0.12 + 0.008, y_c - 0.003, y_c + 0.003,
            z_rear - 0.008, z_rear - 0.003, mat_idx=MAT_MOUNT_HARDWARE)
    # Audio 3.5mm Jack
    add_cylinder(bm, (io_x_min + 0.155, y_c, z_rear - 0.005), radius=0.004,
                 depth=0.004, axis='Z', segments=12, mat_idx=MAT_MOUNT_HARDWARE)
    # DB9 Serial Port
    add_box(bm, io_x_min + 0.19 - 0.015, io_x_min + 0.19 + 0.015, y_c - 0.006, y_c + 0.006,
            z_rear - 0.008, z_rear - 0.003, mat_idx=MAT_MOUNT_HARDWARE)
    # 3-Pin IEC AC Power Inlet (trapezoid/box)
    add_box(bm, io_x_max - 0.055, io_x_max - 0.020, y_c - 0.012, y_c + 0.012,
            z_rear - 0.010, z_rear - 0.003, mat_idx=MAT_CHASSIS)
    for pin_y in [-0.005, 0.005]:
        add_cylinder(bm, (io_x_max - 0.043, y_c + pin_y, z_rear - 0.006),
                     radius=0.0015, depth=0.006, axis='Z', segments=8, mat_idx=MAT_MOUNT_HARDWARE)
    add_cylinder(bm, (io_x_max - 0.031, y_c, z_rear - 0.006),
                 radius=0.0015, depth=0.006, axis='Z', segments=8, mat_idx=MAT_MOUNT_HARDWARE)
    # Kensington Lock Slot
    add_box(bm, io_x_max - 0.012, io_x_max - 0.005, y_c - 0.002, y_c + 0.005,
            z_rear - 0.008, z_rear, mat_idx=MAT_CHASSIS)


def build_lens_assembly(bm: bmesh.types.BMesh, z_front: float) -> None:
    """
    Build the optical lens assembly.
    Guarantees the front optical exit pupil glass sits exactly at (0, 0, 0).
    The lens barrel extends backward along +Z into the chassis body.
    """
    # 1. Main cylindrical lens shroud extending from Z=0.004 to Z=z_front+0.010
    outer_radius = 0.040
    barrel_depth = z_front + 0.006
    barrel_cz = barrel_depth / 2.0 + 0.004
    add_cylinder(bm, (0.0, 0.0, barrel_cz), radius=outer_radius, depth=barrel_depth,
                 axis='Z', segments=32, mat_idx=MAT_LENS_BARREL, cap_ends=True)

    # 2. Outer knurled focus grip ring (slightly larger diameter collar)
    grip_r = outer_radius + 0.0025
    add_cylinder(bm, (0.0, 0.0, 0.012), radius=grip_r, depth=0.010,
                 axis='Z', segments=32, mat_idx=MAT_LENS_BARREL, cap_ends=True)

    # 3. Inner stepped aperture collar
    inner_collar_r = 0.035
    add_cylinder(bm, (0.0, 0.0, 0.003), radius=inner_collar_r, depth=0.005,
                 axis='Z', segments=32, mat_idx=MAT_LENS_BARREL, cap_ends=True)

    # 4. Front optical exit pupil glass element centered at Z=0.001 (flush with origin Z=0)
    glass_r = 0.033
    add_cylinder(bm, (0.0, 0.0, 0.001), radius=glass_r, depth=0.002,
                 axis='Z', segments=32, mat_idx=MAT_LENS_GLASS, cap_ends=True)


def get_mounting_points(width: float, depth: float, x_c: float, z_front: float) -> List[Tuple[float, float]]:
    """Return the (X, Z) coordinates of the 4 underside mounting points."""
    z_c = z_front + depth / 2.0
    dx = width * 0.28
    dz = depth * 0.28
    return [
        (x_c - dx, z_c - dz),  # Front-Left
        (x_c + dx, z_c - dz),  # Front-Right
        (x_c - dx, z_c + dz),  # Rear-Left
        (x_c + dx, z_c + dz),  # Rear-Right
    ]


def build_mounting_inserts(bm: bmesh.types.BMesh, mount_pts: List[Tuple[float, float]], y_mount: float) -> None:
    """Build threaded brass mounting inserts on the underside mounting surface."""
    for px, pz in mount_pts:
        # Brass insert bezel
        add_cylinder(bm, (px, y_mount, pz), radius=0.007, depth=0.003,
                     axis='Y', segments=16, mat_idx=MAT_MOUNT_HARDWARE)
        # Threaded M4/M6 core recess
        add_cylinder(bm, (px, y_mount, pz), radius=0.003, depth=0.005,
                     axis='Y', segments=12, mat_idx=MAT_IO_PANEL)


# ==============================================================================
# Modular Mounting Hardware Options
# ==============================================================================

def build_tabletop_feet(bm: bmesh.types.BMesh, mount_pts: List[Tuple[float, float]], y_mount: float) -> None:
    """Build 4 adjustable knurled rubber leveling feet on the bottom surface."""
    for px, pz in mount_pts:
        # Threaded metal stud
        add_cylinder(bm, (px, y_mount - 0.006, pz), radius=0.003, depth=0.012,
                     axis='Y', segments=12, mat_idx=MAT_MOUNT_HARDWARE)
        # Knurled rubber foot pad
        add_cylinder(bm, (px, y_mount - 0.016, pz), radius=0.016, depth=0.012,
                     axis='Y', segments=24, mat_idx=MAT_RUBBER_FEET)
        # Foot base ring
        add_cylinder(bm, (px, y_mount - 0.021, pz), radius=0.013, depth=0.004,
                     axis='Y', segments=20, mat_idx=MAT_RUBBER_FEET)


def build_ceiling_mount(bm: bmesh.types.BMesh, mount_pts: List[Tuple[float, float]],
                       x_c: float, z_front: float, depth: float, y_mount: float,
                       pole_length: float, inverted: bool = True) -> None:
    """
    Build universal ceiling mount with spider arms, gimbal tilt assembly,
    extension drop column pipe, and ceiling attachment flange plate.
    When inverted (standard installation), arms face +Y towards the ceiling.
    """
    z_c = z_front + depth / 2.0
    dir_y = 1.0 if inverted else -1.0

    # 1. Articulated Spider Arms
    hub_y = y_mount + dir_y * 0.035
    hub_center = Vector((x_c, hub_y, z_c))

    # Central spider mounting hub disc
    add_cylinder(bm, (x_c, hub_y, z_c), radius=0.060, depth=0.006,
                 axis='Y', segments=32, mat_idx=MAT_MOUNT_METAL)

    # 4 Spider Arms connecting hub disc to mounting points
    for px, pz in mount_pts:
        mount_v = Vector((px, y_mount, pz))
        arm_start = hub_center + (mount_v - hub_center).normalized() * 0.040
        # Steel arm bracket
        add_tube(bm, arm_start, mount_v, radius=0.005, segments=12, mat_idx=MAT_MOUNT_METAL)
        # M4/M6 Socket Cap Screw & Washer at projector insert
        screw_pos = mount_v + Vector((0, dir_y * 0.005, 0))
        add_cylinder(bm, (screw_pos.x, screw_pos.y, screw_pos.z), radius=0.006, depth=0.006,
                     axis='Y', segments=12, mat_idx=MAT_MOUNT_HARDWARE)
        # Arm clamp bolt at hub
        add_cylinder(bm, (arm_start.x, hub_y + dir_y * 0.005, arm_start.z), radius=0.005, depth=0.006,
                     axis='Y', segments=12, mat_idx=MAT_MOUNT_HARDWARE)

    # 2. Gimbal / Swivel Tilt Bracket
    gimbal_y1 = hub_y + dir_y * 0.003
    gimbal_y2 = hub_y + dir_y * 0.055
    add_box(bm, x_c - 0.035, x_c + 0.035,
            min(gimbal_y1, gimbal_y2), max(gimbal_y1, gimbal_y2),
            z_c - 0.035, z_c + 0.035, mat_idx=MAT_MOUNT_METAL)
    # Tilt adjustment tension knobs on left and right
    for kx in [x_c - 0.040, x_c + 0.040]:
        add_cylinder(bm, (kx, (gimbal_y1 + gimbal_y2) / 2.0, z_c), radius=0.010, depth=0.008,
                     axis='X', segments=16, mat_idx=MAT_MOUNT_HARDWARE)

    # 3. Extension Drop Column (1.5" NPT Steel Pipe)
    pipe_radius = 0.024  # Standard ~48mm OD pipe
    pipe_start_y = gimbal_y2
    pipe_end_y = pipe_start_y + dir_y * pole_length
    p_start = Vector((x_c, pipe_start_y, z_c))
    p_end = Vector((x_c, pipe_end_y, z_c))
    add_tube(bm, p_start, p_end, radius=pipe_radius, segments=24, mat_idx=MAT_MOUNT_METAL)

    # Coupling ring collar at pipe joint
    add_cylinder(bm, (x_c, pipe_start_y + dir_y * 0.015, z_c), radius=pipe_radius + 0.005,
                 depth=0.020, axis='Y', segments=24, mat_idx=MAT_MOUNT_HARDWARE)

    # 4. Ceiling Attachment Flange Plate
    flange_size = 0.160
    flange_thick = 0.008
    flange_y1 = pipe_end_y
    flange_y2 = flange_y1 + dir_y * flange_thick
    add_box(bm, x_c - flange_size / 2.0, x_c + flange_size / 2.0,
            min(flange_y1, flange_y2), max(flange_y1, flange_y2),
            z_c - flange_size / 2.0, z_c + flange_size / 2.0, mat_idx=MAT_MOUNT_METAL)

    # 4 Anchor bolt slots in corners of ceiling plate
    d_bolt = flange_size * 0.38
    for bx in [x_c - d_bolt, x_c + d_bolt]:
        for bz in [z_c - d_bolt, z_c + d_bolt]:
            add_cylinder(bm, (bx, flange_y2 + dir_y * 0.003, bz), radius=0.006, depth=0.006,
                         axis='Y', segments=12, mat_idx=MAT_MOUNT_HARDWARE)


def build_truss_mount(bm: bmesh.types.BMesh, mount_pts: List[Tuple[float, float]],
                     x_c: float, z_front: float, depth: float, y_mount: float,
                     inverted: bool = True) -> None:
    """
    Build theatrical/event rigging 50mm (2") Half-Coupler (cheeseborough) clamp,
    mounting spider adapter, and steel aircraft safety wire rope.
    """
    z_c = z_front + depth / 2.0
    dir_y = 1.0 if inverted else -1.0

    # 1. Spider mounting adapter plate
    hub_y = y_mount + dir_y * 0.035
    add_cylinder(bm, (x_c, hub_y, z_c), radius=0.055, depth=0.006,
                 axis='Y', segments=24, mat_idx=MAT_MOUNT_METAL)

    # 4 Spider Arms to mounting points
    for px, pz in mount_pts:
        mount_v = Vector((px, y_mount, pz))
        hub_v = Vector((x_c, hub_y, z_c))
        add_tube(bm, hub_v, mount_v, radius=0.005, segments=12, mat_idx=MAT_MOUNT_METAL)
        add_cylinder(bm, (px, y_mount + dir_y * 0.004, pz), radius=0.006, depth=0.006,
                     axis='Y', segments=12, mat_idx=MAT_MOUNT_HARDWARE)

    # 2. Heavy-Duty 50mm Half-Coupler Clamp
    clamp_base_y = hub_y + dir_y * 0.025
    # Adapter block
    add_box(bm, x_c - 0.025, x_c + 0.025,
            min(hub_y, clamp_base_y), max(hub_y, clamp_base_y),
            z_c - 0.025, z_c + 0.025, mat_idx=MAT_MOUNT_METAL)

    # Truss Chord Pipe (standard 50mm / 2" theatrical pipe along X)
    pipe_radius = 0.025  # 50mm diameter
    pipe_center_y = clamp_base_y + dir_y * (pipe_radius + 0.010)
    pipe_p1 = Vector((x_c - 0.25, pipe_center_y, z_c))
    pipe_p2 = Vector((x_c + 0.25, pipe_center_y, z_c))
    add_tube(bm, pipe_p1, pipe_p2, radius=pipe_radius, segments=24, mat_idx=MAT_MOUNT_HARDWARE)

    # Half-Coupler Clamp Body (wraps around the 50mm pipe)
    clamp_radius = pipe_radius + 0.008
    clamp_width = 0.050
    add_cylinder(bm, (x_c, pipe_center_y, z_c), radius=clamp_radius, depth=clamp_width,
                 axis='X', segments=24, mat_idx=MAT_MOUNT_METAL, cap_ends=False)

    # Clamp Hinge Pin on one side
    add_cylinder(bm, (x_c, pipe_center_y - dir_y * 0.022, z_c - 0.030), radius=0.005,
                 depth=clamp_width + 0.008, axis='X', segments=12, mat_idx=MAT_MOUNT_HARDWARE)

    # Heavy-Duty T-Bar Eyebolt & Tightening Handle
    bolt_y = pipe_center_y + dir_y * 0.040
    # Eyebolt shaft
    add_tube(bm, Vector((x_c, pipe_center_y, z_c + 0.032)),
             Vector((x_c, bolt_y, z_c + 0.032)), radius=0.006, segments=12, mat_idx=MAT_MOUNT_HARDWARE)
    # T-Bar wing handle
    add_tube(bm, Vector((x_c - 0.040, bolt_y, z_c + 0.032)),
             Vector((x_c + 0.040, bolt_y, z_c + 0.032)), radius=0.005, segments=12, mat_idx=MAT_MOUNT_HARDWARE)

    # 3. Aircraft Steel Safety Wire Rope
    # Looping from projector chassis safety bar around the truss pipe with carabiner
    safety_anchor = Vector((x_c - 0.10, y_mount, z_c + 0.05))
    safety_pipe_top = Vector((x_c - 0.06, pipe_center_y + dir_y * (pipe_radius + 0.015), z_c))
    add_tube(bm, safety_anchor, safety_pipe_top, radius=0.0025, segments=8, mat_idx=MAT_MOUNT_HARDWARE)
    add_tube(bm, safety_pipe_top, safety_anchor + Vector((0.03, 0, 0)), radius=0.0025, segments=8, mat_idx=MAT_MOUNT_HARDWARE)
    # Screw-lock carabiner body
    add_cylinder(bm, (safety_pipe_top.x, safety_pipe_top.y, safety_pipe_top.z), radius=0.006,
                 depth=0.018, axis='Z', segments=12, mat_idx=MAT_MOUNT_HARDWARE)


# ==============================================================================
# Master Mesh Generation Entry Point
# ==============================================================================

def build_projector_mesh(mesh_obj: bpy.types.Object, width: float = 0.380, height: float = 0.121,
                         depth: float = 0.277, lens_offset_x: float = 0.085,
                         mount_type: str = 'CEILING', mount_pole_length: float = 0.40,
                         chassis_color: str = 'WHITE', inverted: bool = True) -> None:
    """
    Build the complete 3D projector mesh in the target mesh object.
    
    Optical Origin Alignment:
    - Front optical lens glass element is placed at (0, 0, 0).
    - Spotlight/Frustum projection looks along -Z.
    - Lens barrel extends along +Z from Z=0 to Z=z_front.
    - Chassis front face sits at Z=z_front (0.025m).
    - Chassis extends from Z=z_front to Z=z_front+depth.
    - Lens center is at X=0. Chassis center is at X = -lens_offset_x.
    - Inverted mounting: For CEILING and TRUSS, the projector is inverted so mounting
      inserts face +Y towards the ceiling/truss pipe, matching professional AV rigging.
    """
    setup_projector_materials(mesh_obj, chassis_color)

    bm = bmesh.new()

    z_front = 0.025
    x_c = -lens_offset_x

    # Determine orientation
    # For tabletop (NONE), projector is right-side up: top is +Y, bottom is -Y
    # For CEILING / TRUSS: when inverted=True, projector is upside down:
    # bottom face with mounting holes faces +Y (towards ceiling/truss)
    is_inverted = inverted if mount_type in {'CEILING', 'TRUSS'} else False

    if is_inverted:
        # Inverted: chassis top faces -Y, chassis bottom faces +Y
        y_top = -0.045
        y_bottom = y_top + height
        y_c = (y_top + y_bottom) / 2.0
        y_mount = y_bottom
    else:
        # Right-side up: chassis top faces +Y, chassis bottom faces -Y
        y_top = 0.045
        y_bottom = y_top - height
        y_c = (y_top + y_bottom) / 2.0
        y_mount = y_bottom

    # 1. Main Chassis Body
    build_chassis_body(bm, width, height, depth, x_c, y_c, z_front)

    # 2. Optical Lens Assembly (centered at X=0, Y=0, Z=0)
    build_lens_assembly(bm, z_front)

    # 3. Underside Mounting Points & Inserts
    mount_pts = get_mounting_points(width, depth, x_c, z_front)
    build_mounting_inserts(bm, mount_pts, y_mount)

    # 4. Modular Mounting Hardware
    if mount_type == 'NONE':
        build_tabletop_feet(bm, mount_pts, y_mount)
    elif mount_type == 'CEILING':
        build_ceiling_mount(bm, mount_pts, x_c, z_front, depth, y_mount, mount_pole_length, inverted=is_inverted)
    elif mount_type == 'TRUSS':
        build_truss_mount(bm, mount_pts, x_c, z_front, depth, y_mount, inverted=is_inverted)

    # Finalize BMesh into Mesh data
    bm.to_mesh(mesh_obj.data)
    bm.free()
    mesh_obj.data.update()
