import os
import sys
import unittest
import bpy
from bpy.app.handlers import persistent
from bpy.types import Operator

try:
    from . import projector_central
except ImportError:
    _dir = os.path.dirname(os.path.abspath(__file__))
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
    import projector_central



class TestAddon(unittest.TestCase):
    def test_existence_of_operators(self):
        self.assertTrue(hasattr(bpy.ops.projector, 'create'))
        self.assertTrue(hasattr(bpy.ops.projector, 'delete'))
        self.assertTrue(hasattr(bpy.ops.projector, 'switch_to_cycles'))
        self.assertTrue(hasattr(bpy.ops.projector, 'apply_pc_model'))
        self.assertTrue(hasattr(bpy.ops.projector, 'download_pc_specs'))
        self.assertTrue(hasattr(bpy.ops.projector, 'rebuild_mesh'))
        self.assertTrue(hasattr(bpy.ops.projector, 'snap_pivot_to_cursor'))


class TestProjector(unittest.TestCase):
    def setUp(self):
        bpy.ops.projector.create()
        self.c = bpy.context.object  # Camera
        self.s = [ch for ch in self.c.children if ch.type == 'LIGHT'][0]  # Spot Light
        self.nodes = self.s.data.node_tree.nodes

    def test_correct_projector_creation(self):
        # Camera
        self.assertEqual(self.c.type, 'CAMERA')
        self.assertEqual(self.c.data.lens_unit, 'FOV')
        # Light
        self.assertEqual(self.s.type, 'LIGHT')
        self.assertEqual(self.s.data.type, 'SPOT')
        self.assertEqual(self.s.hide_select, True)
        self.assertAlmostEqual(self.s.data.shadow_soft_size, 0.0)
        self.assertAlmostEqual(
            self.s.data.cycles.use_multiple_importance_sampling, False)

    def test_existences_of_custom_properties(self):
        self.assertIn('proj_settings', self.c)
        self.assertIn('h_shift', self.c.proj_settings)
        self.assertIn('v_shift', self.c.proj_settings)
        self.assertIn('power', self.c.proj_settings)
        self.assertIn('projected_color', self.c.proj_settings)
        self.assertIn('projected_texture', self.c.proj_settings)
        self.assertIn('throw_ratio', self.c.proj_settings)
        self.assertIn('resolution', self.c.proj_settings)
        self.assertIn('use_custom_texture_res', self.c.proj_settings)
        # Optimal Depth Luminosity properties
        self.assertIn('depth_min', self.c.proj_settings)
        self.assertIn('depth_optimal', self.c.proj_settings)
        self.assertIn('depth_max', self.c.proj_settings)
        self.assertIn('depth_vis_mode', self.c.proj_settings)
        self.assertIn('depth_contour_step', self.c.proj_settings)
        self.assertIn('depth_contour_intensity', self.c.proj_settings)
        self.assertIn('depth_clip_to_fov', self.c.proj_settings)
        self.assertIn('depth_constant_brightness', self.c.proj_settings)
        self.assertIn('depth_zero_gradient', self.c.proj_settings)
        # ProjectorCentral properties
        self.assertTrue(hasattr(self.c.proj_settings, 'pc_brand'))
        self.assertTrue(hasattr(self.c.proj_settings, 'pc_model'))


    def test_update_throw_ratio(self):
        self.c.proj_settings.throw_ratio = 1
        self.assertEqual(self.c.proj_settings.throw_ratio, 1)
        self.assertAlmostEqual(self.c.data.angle, 0.9272952180016123, places=6)
        # Test if mapping nodes was updated correctly
        mapping_node = self.s.data.node_tree.nodes['Group'].node_tree.nodes['Mapping.001']
        if bpy.app.version < (2, 81):
            self.assertEqual(mapping_node.scale[0], 1)
            self.assertAlmostEqual(mapping_node.scale[1], 0.5625)
        else:
            self.assertEqual(mapping_node.inputs['Scale'].default_value[0], 1)
            self.assertAlmostEqual(
                mapping_node.inputs['Scale'].default_value[1], 0.5625)
        # Test 2
        self.c.proj_settings.throw_ratio = 0.8
        self.assertAlmostEqual(self.c.proj_settings.throw_ratio, 0.8)
        self.assertAlmostEqual(self.c.data.angle, 1.1171986306871249, places=6)
        if bpy.app.version < (2, 81):
            self.assertEqual(mapping_node.scale[0], 1.250)
            self.assertAlmostEqual(mapping_node.scale[1], 0.703125)
        else:
            self.assertEqual(
                mapping_node.inputs['Scale'].default_value[0], 1.250)
            self.assertAlmostEqual(
                mapping_node.inputs['Scale'].default_value[1], 0.703125)

    def test_update_lens_shift(self):
        self.c.proj_settings.throw_ratio = 1
        shift = 10  # 10%
        # x shift
        self.c.proj_settings.h_shift = shift
        self.assertAlmostEqual(self.c.data.shift_x, 0.1)
        # y shift is scaled by inverted aspect ratio: h/w = 1080/1920 = 0.5625
        self.c.proj_settings.v_shift = shift
        self.assertAlmostEqual(self.c.data.shift_y, 0.1 * (1080 / 1920))
        # Check correct update of mapping node
        mapping_node = self.s.data.node_tree.nodes['Group'].node_tree.nodes['Mapping.001']
        if bpy.app.version < (2, 81):
            self.assertAlmostEqual(mapping_node.translation[0], 0.1)
            self.assertAlmostEqual(mapping_node.translation[1], 0.1 * (1080 / 1920))
        else:
            self.assertAlmostEqual(
                mapping_node.inputs['Location'].default_value[0], 0.1)
            self.assertAlmostEqual(
                mapping_node.inputs['Location'].default_value[1], 0.1 * (1080 / 1920))

    def test_pixel_grid_on_off(self):
        # Turn Pixel Grid on
        self.c.proj_settings.show_pixel_grid = True
        links_as_node_names = [
            (link.from_node.name, link.to_node.name)
            for link in self.s.data.node_tree.links
        ]
        self.assertIn(('pixel_grid', 'Light Output'), links_as_node_names)
        self.assertNotIn(('Emission', 'Light Output'), links_as_node_names)

        # Turn Pixel Grid off
        self.c.proj_settings.show_pixel_grid = False
        links_as_node_names = [
            (link.from_node.name, link.to_node.name)
            for link in self.s.data.node_tree.links
        ]
        self.assertNotIn(('pixel_grid', 'Light Output'), links_as_node_names)
        self.assertIn(('Emission', 'Light Output'), links_as_node_names)

    def test_pixel_grid_resolution(self):
        nodes = self.s.data.node_tree.nodes['pixel_grid'].node_tree.nodes
        width, height = self.c.proj_settings.resolution.split('x')
        self.assertEqual(
            nodes['_width'].outputs[0].default_value, float(width))
        self.assertEqual(
            nodes['_height'].outputs[0].default_value, float(height))
        x, y = 1024, 768
        self.c.proj_settings.resolution = f'{x}x{y}'
        self.assertEqual(
            nodes['_width'].outputs[0].default_value, float(x))
        self.assertEqual(
            nodes['_height'].outputs[0].default_value, float(y))

    def test_update_power(self):
        new_power = 30
        self.c.proj_settings.power = new_power
        self.assertEqual(self.s.data.energy, new_power)

    def test_optimal_depth_texture_and_shader(self):
        # 1. Texture exists in bpy.data.images
        self.assertIn('_proj.tex.optimal_depth', bpy.data.images)
        img = bpy.data.images['_proj.tex.optimal_depth']
        self.assertTrue(img.use_fake_user)

        # 2. Shader node group exists
        self.assertIn('_Projectors-Addon_DepthLuminosity', bpy.data.node_groups)
        dl_group = bpy.data.node_groups['_Projectors-Addon_DepthLuminosity']
        self.assertIn('depth_lum', self.s.data.node_tree.nodes)

        # 3. Switch to optimal depth luminosity
        self.c.proj_settings.projected_texture = 'optimal_depth_luminosity'
        links_as_node_names = [
            (link.from_node.name, link.to_node.name)
            for link in self.s.data.node_tree.links
        ]
        self.assertIn(('depth_lum', 'Emission'), links_as_node_names)

        # 4. Update depth values
        self.c.proj_settings.depth_min = 2.0
        self.c.proj_settings.depth_optimal = 4.5
        self.c.proj_settings.depth_max = 9.0
        self.c.proj_settings.depth_vis_mode = 'HEATMAP'
        self.c.proj_settings.depth_contour_step = 0.5
        self.c.proj_settings.depth_contour_intensity = 0.8
        self.c.proj_settings.depth_clip_to_fov = True
        self.c.proj_settings.depth_constant_brightness = True
        self.c.proj_settings.depth_zero_gradient = True

        dl_node = self.s.data.node_tree.nodes['depth_lum']
        self.assertAlmostEqual(dl_node.inputs['Min Distance'].default_value, 2.0)
        self.assertAlmostEqual(dl_node.inputs['Optimal Distance'].default_value, 4.5)
        self.assertAlmostEqual(dl_node.inputs['Max Distance'].default_value, 9.0)
        self.assertAlmostEqual(dl_node.inputs['Mode'].default_value, 1.0)  # HEATMAP = 1.0
        self.assertAlmostEqual(dl_node.inputs['Contour Step'].default_value, 0.5)
        self.assertAlmostEqual(dl_node.inputs['Contour Intensity'].default_value, 0.8)
        self.assertAlmostEqual(dl_node.inputs['Constant Brightness'].default_value, 1.0)
        self.assertAlmostEqual(dl_node.inputs['Clip to FOV'].default_value, 1.0)

        # 5. Verify Zero Gradient (CONSTANT interpolation) on Color Ramp
        cr = dl_node.node_tree.nodes['Color Ramp']
        self.assertEqual(cr.color_ramp.interpolation, 'CONSTANT')
        self.assertEqual(len(cr.color_ramp.elements), 3)

    def test_projector_central_db_and_apply(self):
        # 1. Database loading
        db = projector_central.load_projectors_db()
        self.assertIn('benq-ht2050a', db)
        self.assertIn('epson-home_cinema_5050ub', db)

        # 2. Brands and models retrieval
        brands = projector_central.get_brands()
        self.assertIn('BenQ', brands)
        self.assertIn('Epson', brands)

        models = projector_central.get_models_for_brand('BenQ')
        model_ids = [m[0] for m in models]
        self.assertIn('benq-ht2050a', model_ids)

        # 3. Apply PC model specs
        self.c.proj_settings.pc_brand = 'BenQ'
        self.c.proj_settings.pc_model = 'benq-ht2050a'
        res = bpy.ops.projector.apply_pc_model()
        self.assertEqual(res, {'FINISHED'})

        # Verify applied values
        self.assertEqual(self.c.proj_settings.resolution, '1920x1080')
        self.assertEqual(self.c.proj_settings.power, 2200.0)
        self.assertAlmostEqual(self.c.proj_settings.throw_ratio, 1.325)
        self.assertAlmostEqual(self.c.proj_settings.depth_min, 1.34, places=4)
        self.assertAlmostEqual(self.c.proj_settings.depth_max, 7.65, places=4)

        self.assertEqual(self.c.proj_settings.model_name, 'BenQ HT2050A DLP Projector')

    def test_projector_central_html_parser(self):
        sample_html = """
        <html><body>
        <h1>Optoma Test Pro Projector</h1>
        <dl><dd>Brightness</dd><dt>3,500 Lumens (ANSI)</dt></dl>
        <dl><dd>Resolution</dd><dt>3840x2160</dt></dl>
        <dl><dd>Throw Ratio</dd><dt>1.20:1 - 1.60:1</dt></dl>
        <dl><dd>Throw Distance</dd><dt>3.0' - 20.0'</dt></dl>
        <dl><dd>Lens Shift</dd><dt>Vertical +/-15%</dt></dl>
        </body></html>
        """
        data = projector_central.parse_projectorcentral_html(sample_html, 'https://www.projectorcentral.com/optoma-test-pro.htm')
        self.assertEqual(data['lumens'], 3500)
        self.assertEqual(data['resolution'], '3840x2160')
        self.assertAlmostEqual(data['throw_ratio_min'], 1.20)
        self.assertAlmostEqual(data['throw_ratio_max'], 1.60)
        self.assertAlmostEqual(data['throw_ratio_default'], 1.40)
        self.assertAlmostEqual(data['lens_shift_v'], 15.0)
        self.assertAlmostEqual(data['throw_dist_min_m'], 0.91, places=2)
        self.assertAlmostEqual(data['throw_dist_max_m'], 6.10, places=2)

    def test_projector_3d_mesh_generation(self):
        from mathutils import Vector

        # 1. Check Projector.Visual child object and non-shadow-casting setup
        mesh_children = [ch for ch in self.c.children if ch.type == 'MESH']
        self.assertEqual(len(mesh_children), 1)
        body = mesh_children[0]
        self.assertTrue(body.name.endswith('.Visual'))
        self.assertFalse(body.visible_shadow)
        self.assertTrue(body.show_wire)

        # 2. Check simple bounding box view for BOTH projector and mounting system:
        # When mounted (CEILING, TRUSS, TABLETOP): 2 simple boxes = 16 vertices, 12 quad faces
        mesh_data = body.data
        for m_type in ('CEILING', 'TRUSS', 'TABLETOP'):
            self.c.proj_settings.mount_type = m_type
            self.assertEqual(len(mesh_data.polygons), 12)
            self.assertEqual(len(mesh_data.vertices), 16)
            self.assertEqual(len(mesh_data.edges), 24)

            # Verify local (0, 0, 0) is at the END of the mounting system in the attachment point!
            att_local = Vector(self.c["attachment_point_local"])
            self.assertAlmostEqual(att_local.length, 0.0, places=5)

            # Mount box is vertices 8..15; its attachment end face must lie at y = 0.0
            m_verts = [mesh_data.vertices[i].co for i in range(8, 16)]
            if m_type in ('CEILING', 'TRUSS'):
                self.assertAlmostEqual(max(v.y for v in m_verts), 0.0, places=5)
            else:  # TABLETOP
                self.assertAlmostEqual(min(v.y for v in m_verts), 0.0, places=5)
            # And the mount box X/Z center is at (0, 0)
            self.assertAlmostEqual((min(v.x for v in m_verts) + max(v.x for v in m_verts)) / 2.0, 0.0, places=5)
            self.assertAlmostEqual((min(v.z for v in m_verts) + max(v.z for v in m_verts)) / 2.0, 0.0, places=5)

        # Check NONE mount -> strictly 1 box (8 vertices, 12 edges, 6 quad faces)
        self.c.proj_settings.mount_type = 'NONE'
        self.assertEqual(len(mesh_data.polygons), 6)
        self.assertEqual(len(mesh_data.vertices), 8)
        self.assertEqual(len(mesh_data.edges), 12)

        # Restore CEILING
        self.c.proj_settings.mount_type = 'CEILING'

        # 3. Check strictly 1 shared material assigned for memory efficiency
        self.assertEqual(len(mesh_data.materials), 1)
        self.assertTrue(mesh_data.materials[0].name.startswith('Projector_Box_'))

        # 4. Verify Chassis Box (vertices 0..7) is a clean 6-face rectangular box with exact W x H x D measures
        c_verts = [mesh_data.vertices[vi].co for vi in range(8)]
        w_box = max(v.x for v in c_verts) - min(v.x for v in c_verts)
        h_box = max(v.y for v in c_verts) - min(v.y for v in c_verts)
        d_box = max(v.z for v in c_verts) - min(v.z for v in c_verts)
        self.assertAlmostEqual(w_box, self.c.proj_settings.chassis_width, places=4)
        self.assertAlmostEqual(h_box, self.c.proj_settings.chassis_height, places=4)
        self.assertAlmostEqual(d_box, self.c.proj_settings.chassis_depth, places=4)

        # 5. Verify Physical FOV Origin (and Projector.Spot.location) is strictly INSIDE the chassis box!
        fov_local = Vector(self.c["fov_origin_local"])
        self.assertAlmostEqual((Vector(self.s.location) - fov_local).length, 0.0, places=5)

        z_front = min(v.z for v in c_verts)
        z_rear = max(v.z for v in c_verts)
        d_fov_z = self.c.proj_settings.fov_origin_depth
        self.assertGreater(d_fov_z, 0.015)
        self.assertAlmostEqual(z_front, fov_local.z - d_fov_z, places=4)
        self.assertAlmostEqual(z_rear, fov_local.z + self.c.proj_settings.chassis_depth - d_fov_z, places=4)
        self.assertLess(min(v.x for v in c_verts), fov_local.x)
        self.assertGreater(max(v.x for v in c_verts), fov_local.x)
        self.assertLess(min(v.y for v in c_verts), fov_local.y)
        self.assertGreater(max(v.y for v in c_verts), fov_local.y)
        self.assertLess(z_front, fov_local.z)
        self.assertGreater(z_rear, fov_local.z)

    def test_texture_interpolation_point_cubic(self):
        # Default must be 'Closest' (Point filtering) so individual pixels are visible
        self.assertEqual(self.c.proj_settings.texture_interpolation, 'Closest')
        root_tree = self.s.data.node_tree
        group_img = root_tree.nodes['Group'].node_tree.nodes['Image Texture']
        custom_img = root_tree.nodes['Image Texture']
        depth_img = root_tree.nodes['depth_lum'].node_tree.nodes['Image Texture']
        self.assertEqual(group_img.interpolation, 'Closest')
        self.assertEqual(custom_img.interpolation, 'Closest')
        self.assertEqual(depth_img.interpolation, 'Closest')

        # Switch to 'Cubic' and verify all image texture nodes update
        self.c.proj_settings.texture_interpolation = 'Cubic'
        self.assertEqual(group_img.interpolation, 'Cubic')
        self.assertEqual(custom_img.interpolation, 'Cubic')
        self.assertEqual(depth_img.interpolation, 'Cubic')

        # Switch back to 'Closest'
        self.c.proj_settings.texture_interpolation = 'Closest'
        self.assertEqual(group_img.interpolation, 'Closest')

    def test_installation_centroid_pivot_kinematics(self):
        from mathutils import Vector

        # Test across all mounting systems: origin/pivot (0, 0, 0) is at the END of the mounting system
        for m_type in ('CEILING', 'TRUSS', 'TABLETOP'):
            self.c.proj_settings.mount_type = m_type
            self.c.proj_settings.pivot_at_installation = True
            bpy.context.view_layer.update()

            att_local = Vector(self.c["attachment_point_local"])
            fov_local = Vector(self.c["fov_origin_local"])
            p_inst_rel_fov = Vector(self.c["installation_centroid_local"])

            # Origin (0,0,0) IS the attachment point at the end of the mount!
            self.assertAlmostEqual(att_local.length, 0.0, places=5)
            self.assertGreater(fov_local.length, 0.02)
            self.assertAlmostEqual((fov_local + p_inst_rel_fov).length, 0.0, places=5)

            # Snap attachment pivot to 3D cursor at (1.5, -2.0, 3.0)
            bpy.context.scene.cursor.location = (1.5, -2.0, 3.0)
            bpy.ops.projector.snap_pivot_to_cursor()
            bpy.context.view_layer.update()

            target_world_pivot = Vector((1.5, -2.0, 3.0))

            # Rotate the projector through multiple 3D orientations:
            # The attachment point in world space MUST remain invariant at target_world_pivot,
            # while the internal FOV origin (spot.matrix_world.translation) orbits around it!
            for rot in [(0.0, 0.0, 0.0), (0.4, -0.3, 0.7), (-0.6, 0.5, -1.1)]:
                self.c.rotation_euler = rot
                bpy.context.view_layer.update()
                world_attach_now = self.c.matrix_world @ att_local
                world_fov_origin = self.s.matrix_world.translation
                self.assertAlmostEqual((world_attach_now - target_world_pivot).length, 0.0, places=4)
                self.assertAlmostEqual(
                    (world_fov_origin - world_attach_now).length,
                    fov_local.length,
                    places=4,
                )

        # When mount_type is NONE, origin (0,0,0) is directly at the internal FOV origin
        self.c.proj_settings.mount_type = 'NONE'
        bpy.context.view_layer.update()
        self.assertAlmostEqual(Vector(self.c["fov_origin_local"]).length, 0.0, places=5)
        self.assertAlmostEqual(Vector(self.s.location).length, 0.0, places=5)

    def test_sverchok_parametric_nodes(self):
        from mathutils import Vector

        # 1. Verify operator creates Sverchok node tree with SvProjectorSpecsNode and SvProjectorParametricNode
        res = bpy.ops.projector.create_sverchok_rig()
        self.assertEqual(res, {'FINISHED'})
        tree = bpy.data.node_groups.get("Projector_Parametric_Rig")
        self.assertIsNotNone(tree)

        n_specs = tree.nodes.get("Projector Specs & Model DB")
        n_rig = tree.nodes.get("Projector Parametric Rig")
        self.assertIsNotNone(n_specs)
        self.assertIsNotNone(n_rig)

        # 2. Configure specs node for Epson 5050UB on TRUSS mount and process
        n_specs.pc_brand = 'Epson'
        n_specs.pc_model = 'epson-home_cinema_5050ub'
        n_specs.mount_type = 'TRUSS'
        n_specs.texture_interpolation = 'Closest'
        n_specs.process()

        # 3. Feed a parametric attachment point (2.0, -4.0, 3.5) and target point (2.0, 0.0, 1.2)
        n_rig.inputs['Attachment Point'].sv_set([[(2.0, -4.0, 3.5)]])
        n_rig.inputs['Target Point'].sv_set([[(2.0, 0.0, 1.2)]])
        n_rig.use_target_aim = True
        n_rig.process()
        bpy.context.view_layer.update()

        sv_proj = bpy.data.objects.get("Projector_SV")
        self.assertIsNotNone(sv_proj)
        self.assertEqual(sv_proj.proj_settings.mount_type, 'TRUSS')
        self.assertAlmostEqual(sv_proj.proj_settings.chassis_width, 0.520, places=3)

        # Verify the projector's origin (the end of the truss mount attachment point) is at (2.0, -4.0, 3.5)
        self.assertAlmostEqual((sv_proj.matrix_world.translation - Vector((2.0, -4.0, 3.5))).length, 0.0, places=4)

        # Clean up Projector_SV
        bpy.ops.object.select_all(action='DESELECT')
        sv_proj.select_set(True)
        bpy.context.view_layer.objects.active = sv_proj
        bpy.ops.projector.delete()
        bpy.data.node_groups.remove(tree)

    def test_projector_visibility_and_rebuild_operator(self):
        body = [ch for ch in self.c.children if ch.type == 'MESH'][0]

        # Toggle visibility off
        self.c.proj_settings.show_projector_body = False
        self.assertTrue(body.hide_viewport)
        self.assertTrue(body.hide_render)

        # Toggle visibility on
        self.c.proj_settings.show_projector_body = True
        self.assertFalse(body.hide_viewport)
        self.assertFalse(body.hide_render)

        # Rebuild operator
        res = bpy.ops.projector.rebuild_mesh()
        self.assertEqual(res, {'FINISHED'})

    def tearDown(self):
        bpy.ops.object.select_all(action='DESELECT')
        if self.c and self.c.name in bpy.data.objects:
            self.c.select_set(True)
            bpy.context.view_layer.objects.active = self.c
            bpy.ops.projector.delete()


def run_tests():
    testLoader = unittest.TestLoader()
    testLoader.testMethodPrefix = "test"
    all_tests = testLoader.discover(".", pattern="test*")
    result = unittest.TextTestRunner(verbosity=2).run(all_tests)
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    run_tests()
