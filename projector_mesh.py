"""
Ultra-Lightweight Procedural 3D Mesh Generator for Projectors.
Generates ONLY:
1. The exact 8-vertex, 6-face Bounding Box of the projector chassis (width x height x depth),
   positioned so local (0, 0, 0) sits at the manufacturer-manual-evaluated physical FOV origin
   inside the bounding box.
2. A minimal 1D wire line (edge) signaling the mounting system and its installation centroid P_inst,
   keeping memory footprint near zero (8-12 vertices, 6 faces, 1 shared material).
"""

from typing import Dict, Tuple
import bpy
import bmesh
from mathutils import Vector


def get_or_create_box_material(chassis_color: str = 'WHITE') -> bpy.types.Material:
    """Create or retrieve a single lightweight shared material for the projector bounding box."""
    mat_name = f"Projector_Box_{chassis_color}"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        out_node = nodes.new(type='ShaderNodeOutputMaterial')
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        rgb = (0.90, 0.92, 0.95, 1.0) if chassis_color == 'WHITE' else (0.12, 0.13, 0.15, 1.0)
        bsdf.inputs['Base Color'].default_value = rgb
        bsdf.inputs['Roughness'].default_value = 0.4
        if 'Alpha' in bsdf.inputs:
            bsdf.inputs['Alpha'].default_value = 0.25
        if hasattr(mat, 'blend_method'):
            mat.blend_method = 'BLEND'
        mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 0.25)
        links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])
    return mat


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
    Compute the exact bounding box coordinates in local projector space where
    local (0, 0, 0) is the physical FOV origin inside the chassis.
    """
    d_fov_z = max(0.008, min(float(fov_origin_depth), float(depth) - 0.008))
    z_front = -d_fov_z
    z_rear = z_front + depth
    z_c = z_front + depth / 2.0

    max_off_x = max(0.0, width / 2.0 - 0.005)
    clamped_off_x = max(-max_off_x, min(float(lens_offset_x), max_off_x))
    x_c = -clamped_off_x
    x_min = x_c - width / 2.0
    x_max = x_c + width / 2.0

    is_inverted = bool(inverted) if mount_type in {'CEILING', 'TRUSS'} else False
    max_off_y = max(0.0, height / 2.0 - 0.005)
    clamped_off_y = max(-max_off_y, min(float(lens_offset_y), max_off_y))

    if is_inverted:
        y_c = clamped_off_y
        y_min = y_c - height / 2.0
        y_max = y_c + height / 2.0
        y_mount = y_max
        dir_y = 1.0
    else:
        y_c = -clamped_off_y
        y_min = y_c - height / 2.0
        y_max = y_c + height / 2.0
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
    """
    b = compute_chassis_bounds(
        width, height, depth, lens_offset_x, lens_offset_y,
        fov_origin_depth, mount_type, inverted
    )
    x_c, z_c, y_mount, dir_y = b["x_c"], b["z_c"], b["y_mount"], b["dir_y"]

    if mount_type == 'NONE':
        return Vector((0.0, 0.0, 0.0))
    elif mount_type == 'TABLETOP':
        return Vector((x_c, b["y_min"] - 0.025, z_c))
    elif mount_type == 'CEILING':
        return Vector((x_c, y_mount + dir_y * float(mount_pole_length), z_c))
    elif mount_type == 'TRUSS':
        return Vector((x_c, y_mount + dir_y * 0.085, z_c))

    return Vector((0.0, 0.0, 0.0))


def build_projector_mesh(
    mesh_obj: bpy.types.Object,
    width: float = 0.3805,
    height: float = 0.1217,
    depth: float = 0.2770,
    lens_offset_x: float = 0.0659,
    lens_offset_y: float = 0.0150,
    fov_origin_depth: float = 0.0510,
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
    Build ONLY the 8-vertex projector bounding box and a single line (wire edge)
    signaling the mounting system and its installation centroid P_inst.
    """
    mat = get_or_create_box_material(chassis_color)
    mesh_obj.data.materials.clear()
    mesh_obj.data.materials.append(mat)

    bm = bmesh.new()

    b = compute_chassis_bounds(
        width=width,
        height=height,
        depth=depth,
        lens_offset_x=lens_offset_x,
        lens_offset_y=lens_offset_y,
        fov_origin_depth=fov_origin_depth,
        mount_type=mount_type,
        inverted=inverted,
    )

    # 1. Strictly the 8-vertex, 6-face Bounding Box of the projector chassis
    x_min, x_max = b["x_min"], b["x_max"]
    y_min, y_max = b["y_min"], b["y_max"]
    z_min, z_max = b["z_front"], b["z_rear"]

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
        (0, 3, 2, 1),  # Front
        (4, 5, 6, 7),  # Back
        (0, 1, 5, 4),  # Bottom
        (2, 3, 7, 6),  # Top
        (0, 4, 7, 3),  # Left
        (1, 2, 6, 5),  # Right
    ]
    for idxs in face_indices:
        f = bm.faces.new([verts[i] for i in idxs])
        f.material_index = 0

    # 2. Only a wire line to signal the type of mounting system
    p_inst = compute_installation_centroid(
        width=width,
        height=height,
        depth=depth,
        lens_offset_x=lens_offset_x,
        lens_offset_y=lens_offset_y,
        fov_origin_depth=b["d_fov_z"],
        mount_type=mount_type,
        mount_pole_length=mount_pole_length,
        inverted=inverted,
    )

    x_c, z_c, y_mount = b["x_c"], b["z_c"], b["y_mount"]
    if mount_type in {'CEILING', 'TABLETOP'}:
        # Single vertical line from mounting surface center to installation centroid P_inst
        v_start = bm.verts.new((x_c, y_mount, z_c))
        v_end = bm.verts.new((p_inst.x, p_inst.y, p_inst.z))
        bm.edges.new((v_start, v_end))
    elif mount_type == 'TRUSS':
        # Single vertical stem line to P_inst + horizontal truss axis line through P_inst
        v_start = bm.verts.new((x_c, y_mount, z_c))
        v_end = bm.verts.new((p_inst.x, p_inst.y, p_inst.z))
        bm.edges.new((v_start, v_end))
        half_span = width * 0.45
        v_t1 = bm.verts.new((x_c - half_span, p_inst.y, z_c))
        v_t2 = bm.verts.new((x_c + half_span, p_inst.y, z_c))
        bm.edges.new((v_t1, v_t2))

    bm.to_mesh(mesh_obj.data)
    bm.free()
    mesh_obj.data.update()

    return p_inst
