"""
Render Verification Suite for 3D Projector Model & Rigging System.
Renders high-quality Cycles images showcasing:
1. Ceiling Mount with Spider Arms, Gimbal, Drop Pole, and Ceiling Plate
2. Theatrical Truss Rigging with 50mm Half-Coupler Clamp & Safety Cable
3. Engineering Detail & Optical Origin Exit Pupil Alignment
"""

import math
import os
import sys
import bpy
from mathutils import Euler, Vector

# Ensure Projectors package is in sys.path
scratch_dir = '/home/gui/.gemini/antigravity/scratch'
if scratch_dir not in sys.path:
    sys.path.insert(0, scratch_dir)

import Projectors
Projectors.register()

OUT_DIR = '/home/gui/.gemini/antigravity/brain/54f171c9-5faa-480b-94b2-f766d7006a72'


def setup_base_scene():
    """Clear scene and setup basic studio environment with neutral grey background."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720

    # World background: bright clean studio ambiance
    world = scene.world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get('Background')
    if bg_node:
        bg_node.inputs['Color'].default_value = (0.25, 0.26, 0.28, 1.0)
        bg_node.inputs['Strength'].default_value = 0.8

    # Studio Lighting: Key light
    bpy.ops.object.light_add(type='AREA', location=(2.0, -1.0, 3.0))
    key = bpy.context.object
    key.data.energy = 800
    key.data.size = 2.0
    key.rotation_euler = (math.radians(35), math.radians(20), math.radians(-30))

    # Fill light
    bpy.ops.object.light_add(type='AREA', location=(-2.5, -2.0, 2.0))
    fill = bpy.context.object
    fill.data.energy = 400
    fill.data.size = 2.5

    # Rim light for edge definition
    bpy.ops.object.light_add(type='AREA', location=(0.0, 2.5, 2.5))
    rim = bpy.context.object
    rim.data.energy = 600
    rim.data.size = 2.0

    # Floor plane
    bpy.ops.mesh.primitive_plane_add(size=14.0, location=(0, 2.0, 0.0))
    floor = bpy.context.object
    fl_mat = bpy.data.materials.new('Floor_Studio')
    fl_mat.use_nodes = True
    fl_mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.15, 0.16, 0.18, 1.0)
    fl_mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.5
    floor.data.materials.append(fl_mat)


def render_ceiling_mount():
    """Render Projector with Universal Ceiling Spider Mount & Projection."""
    setup_base_scene()
    scene = bpy.context.scene

    # Ceiling slab at Z = 2.30m
    bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0, 1.5, 2.30))
    ceil = bpy.context.object
    c_mat = bpy.data.materials.new('Ceil_Studio')
    c_mat.use_nodes = True
    c_mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.35, 0.36, 0.38, 1.0)
    ceil.data.materials.append(c_mat)

    # Projection Target Screen at Y = 4.2m
    bpy.ops.mesh.primitive_plane_add(size=4.0, location=(0, 4.2, 1.4), rotation=(math.radians(90), 0, 0))
    screen = bpy.context.object
    s_mat = bpy.data.materials.new('Screen_Mat')
    s_mat.use_nodes = True
    s_mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1.0)
    s_mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    screen.data.materials.append(s_mat)

    # Create Projector
    # Note: in world coordinates, looking along +Y requires rx = 85 deg (5 deg downward tilt)
    bpy.ops.projector.create()
    proj = bpy.context.object
    proj.location = (0, 0.5, 1.70)
    proj.rotation_euler = (math.radians(85), 0, 0)

    proj_settings = proj.proj_settings
    proj_settings.mount_type = 'CEILING'
    proj_settings.mount_pole_length = 0.40
    proj_settings.mount_inverted = True
    proj_settings.chassis_color = 'WHITE'
    proj_settings.projected_texture = 'optimal_depth_luminosity'
    proj_settings.depth_vis_mode = 'COMBINED'
    proj_settings.power = 3000

    # Studio Camera looking at projector and mount
    cam_pos = Vector((1.4, -0.9, 1.85))
    target_pos = Vector((0.0, 0.6, 1.85))
    bpy.ops.object.camera_add(location=cam_pos)
    studio_cam = bpy.context.object
    scene.camera = studio_cam
    rot_quat = (target_pos - cam_pos).to_track_quat('-Z', 'Y')
    studio_cam.rotation_euler = rot_quat.to_euler()

    out_file = os.path.join(OUT_DIR, 'projector_3d_ceiling_mount.png')
    scene.render.filepath = out_file
    bpy.ops.render.render(write_still=True)
    print(f"Rendered ceiling mount to: {out_file}")


def render_truss_mount():
    """Render Projector with Theatrical 50mm Half-Coupler Truss Clamp & Safety Wire."""
    setup_base_scene()
    scene = bpy.context.scene

    # Target Screen at Y = 4.0m
    bpy.ops.mesh.primitive_plane_add(size=3.8, location=(0, 4.0, 1.4), rotation=(math.radians(90), 0, 0))
    screen = bpy.context.object
    s_mat = bpy.data.materials.new('Screen_Mat')
    s_mat.use_nodes = True
    s_mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1.0)
    screen.data.materials.append(s_mat)

    # Create Projector
    bpy.ops.projector.create()
    proj = bpy.context.object
    proj.location = (0, 0.5, 1.65)
    proj.rotation_euler = (math.radians(86), 0, 0)

    proj_settings = proj.proj_settings
    proj_settings.mount_type = 'TRUSS'
    proj_settings.mount_inverted = True
    proj_settings.chassis_color = 'WHITE'
    proj_settings.projected_texture = 'optimal_depth_luminosity'
    proj_settings.depth_vis_mode = 'COMBINED'
    proj_settings.power = 3000

    # Studio Camera close up on truss clamp and projector body
    cam_pos = Vector((-1.1, -0.6, 1.80))
    target_pos = Vector((0.0, 0.55, 1.70))
    bpy.ops.object.camera_add(location=cam_pos)
    studio_cam = bpy.context.object
    scene.camera = studio_cam
    rot_quat = (target_pos - cam_pos).to_track_quat('-Z', 'Y')
    studio_cam.rotation_euler = rot_quat.to_euler()

    out_file = os.path.join(OUT_DIR, 'projector_3d_truss_mount.png')
    scene.render.filepath = out_file
    bpy.ops.render.render(write_still=True)
    print(f"Rendered truss mount to: {out_file}")


def render_optical_origin_detail():
    """Render close-up engineering details: Optical Exit Pupil (0,0,0), Vents, I/O, Controls."""
    setup_base_scene()
    scene = bpy.context.scene

    # Create Projector (Desktop Feet mode to see tabletop feet and chassis details)
    bpy.ops.projector.create()
    proj = bpy.context.object
    proj.location = (0, 0, 0.95)
    proj.rotation_euler = (math.radians(90), 0, 0)

    proj_settings = proj.proj_settings
    proj_settings.mount_type = 'NONE'  # Tabletop feet
    proj_settings.chassis_color = 'WHITE'
    proj_settings.projected_texture = 'optimal_depth_luminosity'
    proj_settings.depth_vis_mode = 'COMBINED'
    proj_settings.power = 2500

    # Table surface beneath projector
    bpy.ops.mesh.primitive_plane_add(size=2.5, location=(0, 0.25, 0.79))
    table = bpy.context.object
    t_mat = bpy.data.materials.new('Table_Wood')
    t_mat.use_nodes = True
    t_mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.28, 0.18, 0.12, 1.0)
    t_mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.35
    table.data.materials.append(t_mat)

    # Camera angled closely at front lens and side louvers
    cam_pos = Vector((-0.65, -0.75, 1.15))
    target_pos = Vector((0.05, 0.15, 0.95))
    bpy.ops.object.camera_add(location=cam_pos)
    studio_cam = bpy.context.object
    scene.camera = studio_cam
    rot_quat = (target_pos - cam_pos).to_track_quat('-Z', 'Y')
    studio_cam.rotation_euler = rot_quat.to_euler()

    out_file = os.path.join(OUT_DIR, 'projector_optical_origin_verification.png')
    scene.render.filepath = out_file
    bpy.ops.render.render(write_still=True)
    print(f"Rendered optical origin detail to: {out_file}")


if __name__ == '__main__':
    render_ceiling_mount()
    render_truss_mount()
    render_optical_origin_detail()
