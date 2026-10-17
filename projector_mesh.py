"""
Ultra-Lightweight Bounding Box Generator for Projectors & Mounting Systems.
Generates ONLY simple rectangular bounding boxes:
1. Projector Chassis Bounding Box (8 vertices, 6 quad faces) with manufacturer user manual
   measures (width x height x depth).
2. Mounting System Bounding Box (8 vertices, 6 quad faces when a mount is selected) extending
   from the chassis mounting surface to the attachment point at the end of the mount.

Coordinate & Origin Convention:
- When a mounting system is selected (and pivot_at_installation is True), local (0, 0, 0)
  is placed at the END of the mounting system in the attachment point, while the physical
  internal FOV origin (and Projector.Spot light) sits at V_fov_local = -P_attach_rel_fov
  strictly inside the projector chassis bounding box.
- When mount_type == 'NONE' (or pivot_at_installation is False), local (0, 0, 0) is placed
  directly at the physical internal FOV origin inside the projector chassis bounding box.
"""

from typing import Dict, List, Tuple
import bpy
import bmesh
from mathutils import Vector


def get_or_create_box_material(chassis_color: str = 'WHITE') -> bpy.types.Material:
    """Create or retrieve a single lightweight shared material for the bounding box view."""
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
            bsdf.inputs['Alpha'].default_value = 0.22
        if hasattr(mat, 'blend_method'):
            mat.blend_method = 'BLEND'
        mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 0.22)
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
    Compute the exact chassis bounding box coordinates in the internal FOV-origin frame
    where (0, 0, 0) is the physical optical FOV origin inside the chassis.
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
        y_mount = y_max if mount_type in {'CEILING', 'TRUSS'} else y_min
        dir_y = 1.0 if mount_type in {'CEILING', 'TRUSS'} else -1.0

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


def compute_mount_box_and_attachment(
    width: float,
    height: float,
    depth: float,
    lens_offset_x: float,
    lens_offset_y: float,
    fov_origin_depth: float,
    mount_type: str,
    mount_pole_length: float,
    inverted: bool,
) -> Tuple[Dict[str, float], Vector]:
    """
    Compute the simple bounding box of the mounting system and the exact attachment point
    at the END of the mounting system (relative to the internal FOV origin).
    """
    b = compute_chassis_bounds(
        width, height, depth, lens_offset_x, lens_offset_y,
        fov_origin_depth, mount_type, inverted
    )
    x_c, z_c = b["x_c"], b["z_c"]

    if mount_type == 'CEILING':
        y_start = b["y_max"]
        pole_len = max(0.05, float(mount_pole_length))
        y_end = y_start + pole_len
        w_m = min(0.08, max(0.04, width * 0.22))
        d_m = min(0.08, max(0.04, depth * 0.22))
        mount_bounds = {
            "x_min": x_c - w_m / 2.0,
            "x_max": x_c + w_m / 2.0,
            "y_min": min(y_start, y_end),
            "y_max": max(y_start, y_end),
            "z_min": z_c - d_m / 2.0,
            "z_max": z_c + d_m / 2.0,
        }
        p_attach = Vector((x_c, y_end, z_c))
        return mount_bounds, p_attach

    elif mount_type == 'TRUSS':
        y_start = b["y_max"]
        truss_h = 0.10
        y_end = y_start + truss_h
        w_m = min(0.11, max(0.05, width * 0.28))
        d_m = min(0.11, max(0.05, depth * 0.28))
        mount_bounds = {
            "x_min": x_c - w_m / 2.0,
            "x_max": x_c + w_m / 2.0,
            "y_min": min(y_start, y_end),
            "y_max": max(y_start, y_end),
            "z_min": z_c - d_m / 2.0,
            "z_max": z_c + d_m / 2.0,
        }
        p_attach = Vector((x_c, y_end, z_c))
        return mount_bounds, p_attach

    elif mount_type == 'TABLETOP':
        y_start = b["y_min"]
        base_h = 0.025
        y_end = y_start - base_h
        w_m = width * 0.65
        d_m = depth * 0.65
        mount_bounds = {
            "x_min": x_c - w_m / 2.0,
            "x_max": x_c + w_m / 2.0,
            "y_min": min(y_start, y_end),
            "y_max": max(y_start, y_end),
            "z_min": z_c - d_m / 2.0,
            "z_max": z_c + d_m / 2.0,
        }
        p_attach = Vector((x_c, y_end, z_c))
        return mount_bounds, p_attach

    # NONE
    return {}, Vector((0.0, 0.0, 0.0))


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
    Return the attachment point at the end of the mounting system relative to the internal FOV origin.
    """
    _, p_attach = compute_mount_box_and_attachment(
        width, height, depth, lens_offset_x, lens_offset_y,
        fov_origin_depth, mount_type, mount_pole_length, inverted
    )
    return p_attach


def _box_verts_and_faces(
    x_min: float, x_max: float,
    y_min: float, y_max: float,
    z_min: float, z_max: float,
    offset: Vector,
    vert_offset: int = 0,
) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int, int]]]:
    ox, oy, oz = offset.x, offset.y, offset.z
    verts = [
        (x_min + ox, y_min + oy, z_min + oz),  # 0
        (x_max + ox, y_min + oy, z_min + oz),  # 1
        (x_max + ox, y_max + oy, z_min + oz),  # 2
        (x_min + ox, y_max + oy, z_min + oz),  # 3
        (x_min + ox, y_min + oz if False else y_min + oy, z_max + oz),  # 4
        (x_max + ox, y_min + oy, z_max + oz),  # 5
        (x_max + ox, y_max + oy, z_max + oz),  # 6
        (x_min + ox, y_max + oy, z_max + oz),  # 7
    ]
    faces = [
        (vert_offset + 0, vert_offset + 3, vert_offset + 2, vert_offset + 1),  # Front (-Z)
        (vert_offset + 4, vert_offset + 5, vert_offset + 6, vert_offset + 7),  # Back (+Z)
        (vert_offset + 0, vert_offset + 1, vert_offset + 5, vert_offset + 4),  # Bottom (-Y)
        (vert_offset + 2, vert_offset + 3, vert_offset + 7, vert_offset + 6),  # Top (+Y)
        (vert_offset + 0, vert_offset + 4, vert_offset + 7, vert_offset + 3),  # Left (-X)
        (vert_offset + 1, vert_offset + 2, vert_offset + 6, vert_offset + 5),  # Right (+X)
    ]
    return verts, faces


def generate_projector_bounding_boxes_data(
    width: float = 0.3805,
    height: float = 0.1217,
    depth: float = 0.2770,
    lens_offset_x: float = 0.0659,
    lens_offset_y: float = 0.0150,
    fov_origin_depth: float = 0.0510,
    mount_type: str = 'CEILING',
    mount_pole_length: float = 0.40,
    inverted: bool = True,
    pivot_at_installation: bool = True,
) -> Dict[str, object]:
    """
    Generate pure-Python vertex and quad face lists for the simple bounding box view
    of the projector chassis and the mounting system.

    When mount_type != 'NONE' and pivot_at_installation is True:
      - Local (0, 0, 0) is placed at the END of the mounting system in the attachment point.
      - fov_origin_local = -p_attach_rel_fov is the internal FOV origin inside the chassis box.
    Otherwise:
      - Local (0, 0, 0) is at the internal FOV origin inside the chassis box.
    """
    b = compute_chassis_bounds(
        width, height, depth, lens_offset_x, lens_offset_y,
        fov_origin_depth, mount_type, inverted
    )
    mount_bounds, p_attach_rel_fov = compute_mount_box_and_attachment(
        width, height, depth, lens_offset_x, lens_offset_y,
        b["d_fov_z"], mount_type, mount_pole_length, inverted
    )

    use_attachment_origin = (mount_type != 'NONE') and bool(pivot_at_installation)
    if use_attachment_origin:
        shift = -p_attach_rel_fov
        fov_origin_local = Vector(shift)
        attachment_point_local = Vector((0.0, 0.0, 0.0))
    else:
        shift = Vector((0.0, 0.0, 0.0))
        fov_origin_local = Vector((0.0, 0.0, 0.0))
        attachment_point_local = Vector(p_attach_rel_fov)

    verts, faces = _box_verts_and_faces(
        b["x_min"], b["x_max"],
        b["y_min"], b["y_max"],
        b["z_front"], b["z_rear"],
        offset=shift,
        vert_offset=0,
    )

    if mount_type in {'CEILING', 'TRUSS', 'TABLETOP'} and mount_bounds:
        m_verts, m_faces = _box_verts_and_faces(
            mount_bounds["x_min"], mount_bounds["x_max"],
            mount_bounds["y_min"], mount_bounds["y_max"],
            mount_bounds["z_min"], mount_bounds["z_max"],
            offset=shift,
            vert_offset=len(verts),
        )
        verts.extend(m_verts)
        faces.extend(m_faces)

    return {
        "verts": verts,
        "faces": faces,
        "fov_origin_local": fov_origin_local,
        "attachment_point_local": attachment_point_local,
        "p_attach_rel_fov": p_attach_rel_fov,
    }


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
    pivot_at_installation: bool = True,
) -> Dict[str, Vector]:
    """
    Build the simple bounding box mesh for the projector chassis (Box 1: 8 verts, 6 faces)
    and the mounting system (Box 2: 8 verts, 6 faces when mounted).
    Places local (0, 0, 0) at the end of the mounting system (attachment point) when a mount is selected.
    """
    mat = get_or_create_box_material(chassis_color)
    mesh_obj.data.materials.clear()
    mesh_obj.data.materials.append(mat)

    data = generate_projector_bounding_boxes_data(
        width=width,
        height=height,
        depth=depth,
        lens_offset_x=lens_offset_x,
        lens_offset_y=lens_offset_y,
        fov_origin_depth=fov_origin_depth,
        mount_type=mount_type,
        mount_pole_length=mount_pole_length,
        inverted=inverted,
        pivot_at_installation=pivot_at_installation,
    )

    bm = bmesh.new()
    bm_verts = [bm.verts.new(co) for co in data["verts"]]
    for f_idxs in data["faces"]:
        f = bm.faces.new([bm_verts[i] for i in f_idxs])
        f.material_index = 0

    bm.to_mesh(mesh_obj.data)
    bm.free()
    mesh_obj.data.update()

    return {
        "fov_origin_local": data["fov_origin_local"],
        "attachment_point_local": data["attachment_point_local"],
        "p_attach_rel_fov": data["p_attach_rel_fov"],
    }
