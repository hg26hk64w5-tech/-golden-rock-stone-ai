import copy
import unittest
from fastapi.testclient import TestClient
from main import app
from cladding import PlanRequest, plan

BASE={'system':'U','width_mm':4000,'height_mm':2800,'dimensions_verified':True,'rock_wool':True,
      'material':{'name':'Travertine','slabs':[{'width_mm':2000,'height_mm':2000}],'kerf_mm':3,'edge_trim_mm':10},
      'wall_module':{'channel_edge_offset_mm':100},
      'survey':{'datum':'A','wall_offsets_mm':[0,5],'cavity_reference':'waterproofing_face'},
      'channel_layout':{'x_positions_mm':[],'base_y_mm':0,'large_bracket_levels_mm':[100,200,2600,2700],'small_bracket_levels_mm':[600,1100,1600,2100]}}

class DrawingTests(unittest.TestCase):
    def run_case(self, **patch):
        data=copy.deepcopy(BASE);data.update(patch);return plan(PlanRequest(**data))
    def test_four_metre_eight_channel_lines(self):
        r=self.run_case();self.assertEqual(r['wall_module']['columns'],4)
        self.assertEqual(r['wall_module']['panel_width_mm'],1000)
        self.assertEqual(len(r['drawing_package']['channels']),8)
        self.assertEqual([c['x_mm'] for c in r['drawing_package']['channels']],[100,900,1100,1900,2100,2900,3100,3900])
    def test_four_metre_ten_channel_lines(self):
        r=self.run_case(wall_module={'preferred_columns':5,'channel_edge_offset_mm':100})
        self.assertEqual(r['wall_module']['panel_width_mm'],800)
        self.assertEqual(len(r['drawing_package']['channels']),10)
        for c in r['drawing_package']['channels']:
            self.assertEqual(len(c['large_levels_mm']),4);self.assertEqual(len(c['small_levels_mm']),4)
    def test_variable_wall_widths(self):
        for width,columns in [(3200,4),(3600,4),(4500,5),(5200,6),(7800,8)]:
            r=self.run_case(width_mm=width)
            self.assertEqual(r['wall_module']['columns'],columns)
            self.assertAlmostEqual(r['wall_module']['panel_width_mm']*columns,width)
            self.assertEqual(len(r['drawing_package']['channels']),2*columns)
    def test_slab_limit_prevents_impossible_module(self):
        m=copy.deepcopy(BASE['material']);m['slabs'][0]['width_mm']=700
        self.assertIsNone(self.run_case(material=m)['layout'])
    def test_no_fixed_min_without_module(self):
        self.assertIsNotNone(self.run_case(wall_module=None,width_mm=300)['layout'])
    def test_short_wall_blocks_2800_channel(self):
        r=self.run_case(height_mm=2000)
        self.assertEqual(r['drawing_package']['channels'],[])
        self.assertTrue(any(i['field']=='channel_layout.base_y_mm' for i in r['rfis']))
    def test_missing_inset_does_not_invent_channels(self):
        r=self.run_case(wall_module={},channel_layout=None)
        self.assertEqual(r['drawing_package']['channels'],[])
    def test_bad_brackets_withhold_bracket_symbols(self):
        c=copy.deepcopy(BASE['channel_layout']);c['large_bracket_levels_mm']=[100,200,200,2700]
        r=self.run_case(channel_layout=c)
        self.assertEqual(len(r['drawing_package']['channels']),8)
        self.assertFalse(any(e['layer']=='GR_LARGE_BRACKET' for e in r['drawing_package']['entities']))
    def test_unselected_u_does_not_draw_u(self):
        r=self.run_case(system='L');self.assertEqual(r['drawing_package']['channels'],[])
    def test_thickness_30_setting_out(self):
        m=copy.deepcopy(BASE['material']);m['thickness_mm']=30
        r=self.run_case(material=m,detail_profile='project_custom_30mm',horizontal_joint_mm=0,vertical_joint_mm=0)
        self.assertEqual(r['setting_out']['final_stone_face_mm'],149)
        self.assertFalse(any(i['field']=='material.thickness_mm' for i in r['rfis']))
    def test_separate_dxf_layers_and_dimensions(self):
        r=TestClient(app).post('/api/cladding/export-dxf',json=BASE)
        self.assertEqual(r.status_code,200)
        for token in ['GR_STONE','GR_CHANNEL','GR_INSULATION','GR_WATERPROOFING','S03','$INSUNITS','NOT FOR FABRICATION']:
            self.assertIn(token,r.text)
        pairs=r.text.splitlines();self.assertEqual(len(pairs)%2,0)
        # Every channel LINE lies in the separate sheet, beyond the wall width.
        records=r.text.split('0\nLINE\n')[1:]
        channel_lines=[v for v in records if v.startswith('8\nGR_CHANNEL\n')]
        self.assertEqual(len(channel_lines),32)
        for rec in channel_lines:
            self.assertGreater(float(rec.split('10\n')[1].splitlines()[0]),4000)
    def test_never_certifies(self):
        r=self.run_case();self.assertFalse(r['fabrication_released']);self.assertEqual(r['status'],'RFI_REQUIRED')

Z_BASE={'system':'Z','width_mm':4000,'height_mm':2800,'dimensions_verified':True,'rock_wool':True,
        'material':{'name':'Travertine','slabs':[{'width_mm':2000,'height_mm':2000}],'kerf_mm':3,'edge_trim_mm':10},
        'survey':{'datum':'A','wall_offsets_mm':[0,5],'cavity_mm':80,'cavity_reference':'waterproofing_face'},
        'stone_fixings_per_piece':4,'stone_fixing_type':'Z_bracket',
        'fabrication':{'fixing_top_offset_mm':100,'fixing_bottom_offset_mm':100,'fixing_side_offset_mm':100}}

class BracketLayoutTests(unittest.TestCase):
    """L/Z/Omega point-fixing systems: brackets at panel corners from the SAME
    fixing_top/bottom/side offsets already confirmed in Fixing Details. Mirrors the
    channel_layout tests above -- nothing is drawn until the required input exists,
    and the one genuinely new decision (which side takes two brackets for a 3-point
    arrangement) is never assumed."""
    def run_case(self, **patch):
        data=copy.deepcopy(Z_BASE);data.update(patch);return plan(PlanRequest(**data))
    def test_four_point_uses_confirmed_offsets_not_new_input(self):
        r=self.run_case()
        panels=r['shop_drawing']['panels']
        self.assertEqual(len(r['drawing_package']['brackets']),4*len(panels))
        self.assertFalse(any(i['field']=='bracket_layout' for i in r['rfis']))
        pw,ph=r['layout']['panel_width_mm'],r['layout']['panel_height_mm']
        p1=[b for b in r['drawing_package']['brackets'] if b['panel']=='P1-1']
        self.assertEqual(sorted((round(b['x_mm'],3),round(b['y_mm'],3)) for b in p1),
                          sorted([(100.0,100.0),(round(pw-100,3),100.0),(100.0,round(ph-100,3)),(round(pw-100,3),round(ph-100,3))]))
    def test_missing_offsets_withholds_brackets(self):
        r=self.run_case(fabrication={})
        self.assertEqual(r['drawing_package']['brackets'],[])
        self.assertTrue(any(i['field']=='bracket_layout' for i in r['rfis']))
    def test_three_point_side_has_no_default(self):
        r=self.run_case(system='L',stone_fixings_per_piece=3,stone_fixing_type='L_bracket')
        self.assertEqual(r['drawing_package']['brackets'],[])
        self.assertTrue(any(i['field']=='bracket_layout.three_point_side' for i in r['rfis']))
    def test_three_point_top_pairs_two_at_top(self):
        r=self.run_case(system='L',stone_fixings_per_piece=3,stone_fixing_type='L_bracket',bracket_layout={'three_point_side':'top'})
        panels=r['shop_drawing']['panels'];pw,ph=r['layout']['panel_width_mm'],r['layout']['panel_height_mm']
        self.assertEqual(len(r['drawing_package']['brackets']),3*len(panels))
        p1=[b for b in r['drawing_package']['brackets'] if b['panel']=='P1-1']
        pair=[b for b in p1 if abs(b['y_mm']-(ph-100))<1e-6];single=[b for b in p1 if abs(b['y_mm']-100)<1e-6]
        self.assertEqual(len(pair),2);self.assertEqual(len(single),1)
        self.assertAlmostEqual(single[0]['x_mm'],pw/2)
    def test_three_point_bottom_mirrors_top(self):
        r=self.run_case(system='L',stone_fixings_per_piece=3,stone_fixing_type='L_bracket',bracket_layout={'three_point_side':'bottom'})
        p1=[b for b in r['drawing_package']['brackets'] if b['panel']=='P1-1']
        ph=r['layout']['panel_height_mm']
        pair=[b for b in p1 if abs(b['y_mm']-100)<1e-6];single=[b for b in p1 if abs(b['y_mm']-(ph-100))<1e-6]
        self.assertEqual(len(pair),2);self.assertEqual(len(single),1)
    def test_non_u_cavity_uses_survey_value_not_110(self):
        # Z_BASE cavity_mm=80 with 50mm rock wool taken from the waterproofing face
        # leaves a 30mm remaining gap -- same subtraction the U branch already does,
        # just against the real surveyed 80mm rather than the U system's fixed 110mm.
        r=self.run_case()
        texts=[e['text'] for e in r['drawing_package']['entities'] if e.get('text') and 'CAVITY' in e['text']]
        self.assertEqual(len(texts),1)
        self.assertIn('30',texts[0])
        self.assertNotIn('110',texts[0])
    def test_non_u_cavity_without_rockwool_shows_full_surveyed_value(self):
        r=self.run_case(rock_wool=False)
        texts=[e['text'] for e in r['drawing_package']['entities'] if e.get('text') and 'CAVITY' in e['text']]
        self.assertEqual(len(texts),1)
        self.assertIn('80',texts[0])
        self.assertNotIn('110',texts[0])
    def test_non_u_cavity_unconfirmed_does_not_fabricate_110(self):
        r=self.run_case(survey={**Z_BASE['survey'],'cavity_reference':None})
        texts=[e['text'] for e in r['drawing_package']['entities'] if e.get('text') and 'CAVITY' in e['text']]
        self.assertEqual(len(texts),1)
        self.assertNotIn('110',texts[0])
    def test_u_channel_system_unaffected_by_bracket_feature(self):
        # Same BASE fixture used by the channel_layout tests above must be untouched.
        r=DrawingTests().run_case()
        self.assertEqual(len(r['drawing_package']['channels']),8)
        self.assertEqual(r['drawing_package']['brackets'],[])
    def test_dxf_export_includes_bracket_layer(self):
        r=TestClient(app).post('/api/cladding/export-dxf',json=Z_BASE)
        self.assertEqual(r.status_code,200)
        self.assertIn('GR_BRACKET',r.text)

if __name__=='__main__': unittest.main()
