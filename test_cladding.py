import copy
import unittest
import fitz
from fastapi.testclient import TestClient
from main import app
from cladding import PlanRequest, plan

BASE = {'system':'U','u_channel_count':3,'width_mm':3200,'height_mm':2100,'dimensions_verified':True,
        'material':{'name':'Travertine','slabs':[{'width_mm':2500,'height_mm':1400}],'kerf_mm':3,'edge_trim_mm':10},
        'survey':{'datum':'Grid A, positive outward','wall_offsets_mm':[-10,0,8], 'cavity_reference':'waterproofing_face','bracket_projection_mm':100,'projection_approved':True,'adjustment_capacity_mm':18}}

class CladdingTests(unittest.TestCase):
    def run_plan(self, **changes):
        p=copy.deepcopy(BASE);p.update(changes);return plan(PlanRequest(**p))
    def fields(self,r): return [x['field'] for x in r['rfis']]
    def test_empty_request_blocks_fabrication(self):
        r=plan(PlanRequest());self.assertEqual(r['status'],'RFI_REQUIRED');self.assertFalse(r['fabrication_released']);self.assertEqual(r['cutting_list']['items'],[])
    def test_u_brackets_per_channel(self):
        q=self.run_plan()['quantity_takeoff']['bracket_count'];self.assertEqual(q,{'u_channel_pieces':3,'large_brackets':12,'small_reverse_brackets':12,'total_brackets':24})
    def test_missing_channel_count_not_invented(self):
        r=self.run_plan(u_channel_count=None);self.assertIsNone(r['quantity_takeoff']['bracket_count']);self.assertIn('u_channel_count',self.fields(r))
    def test_all_systems(self):
        for system in ['L','Z','OMEGA','U']:
            r=self.run_plan(system=system);self.assertIsNotNone(r['system']);self.assertEqual(r['fixing_details']['pin_diameter_mm'],5);self.assertEqual(r['fixing_details']['pin_embedment_mm'],20)
    def test_height_limit_and_exact_coverage(self):
        r=self.run_plan();l=r['layout'];self.assertLessEqual(l['panel_height_mm'],700);self.assertAlmostEqual(l['panel_width_mm']*l['columns'],3200);self.assertAlmostEqual(l['panel_height_mm']*l['rows'],2100)
    def test_no_fixed_minimum(self):
        r=self.run_plan(width_mm=100);self.assertEqual(r['layout']['panel_width_mm'],100);self.assertIsNone(r['rules']['minimum_panel_width_mm'])
    def test_material_minimum_enforced(self):
        m=copy.deepcopy(BASE['material']);m['min_panel_width_mm']=200;r=self.run_plan(width_mm=100,material=m);self.assertIsNone(r['layout']);self.assertIn('panelization',self.fields(r))
    def test_material_before_panelization(self):
        self.assertIsNone(self.run_plan(material=None)['layout'])
    def test_missing_allowances(self):
        m=copy.deepcopy(BASE['material']);m.pop('kerf_mm');self.assertIsNone(self.run_plan(material=m)['layout'])
    def test_equalization_avoids_small_end_strip(self):
        r=self.run_plan(width_mm=2500);self.assertEqual(r['layout']['columns'],2);self.assertEqual(r['layout']['panel_width_mm'],1250)
    def test_joint_coverage(self):
        r=self.run_plan(joints_requested=True,joint_mm=5);l=r['layout'];self.assertAlmostEqual(l['panel_width_mm']*l['columns']+5*(l['columns']-1),3200)
    def test_joint_conflict_and_missing(self):
        self.assertIn('joint_mm',self.fields(self.run_plan(joint_mm=5)));self.assertIn('joint_mm',self.fields(self.run_plan(joints_requested=True)))
    def test_closest_point_setting_out(self):
        s=self.run_plan()['setting_out'];self.assertEqual(s['closest_wall_point_mm'],8);self.assertEqual(s['wall_deviation_mm'],18);self.assertEqual(s['final_stone_face_mm'],142);self.assertEqual(s['uniform_bracket_projection_mm'],100)
    def test_rock_wool_reference(self):
        s=copy.deepcopy(BASE['survey']);s['cavity_reference']='insulation_face';r=self.run_plan(rock_wool=True,survey=s);self.assertEqual(r['setting_out']['final_stone_face_mm'],192);self.assertEqual(r['quantity_takeoff']['rock_wool_m2'],6.72)
    def test_final_face_conflict(self):
        s=copy.deepcopy(BASE['survey']);s['final_stone_face_mm']=170;self.assertIn('survey.final_stone_face_mm',self.fields(self.run_plan(survey=s)))
    def test_cavity_conflict(self):
        s=copy.deepcopy(BASE['survey']);s['cavity_mm']=70;self.assertIn('survey.cavity_mm',self.fields(self.run_plan(survey=s)))
    def test_insufficient_adjustment(self):
        s=copy.deepcopy(BASE['survey']);s['adjustment_capacity_mm']=17;self.assertIn('survey.adjustment_capacity_mm',self.fields(self.run_plan(survey=s)))
    def test_waterproofing_and_corners(self):
        r=self.run_plan(corner='5mm then 45° Bird’s Mouth');self.assertEqual(r['rules']['waterproofing']['total_mm'],4);self.assertEqual(r['rules']['corner'],'5mm then 45° Bird’s Mouth')
    def test_unknown_scope(self):
        r=self.run_plan(environment='Internal');self.assertIsNone(r['layout']);self.assertIn('scope',self.fields(r))
    def test_conflicts_never_release(self):
        r=self.run_plan(conflicts=['Conflicting wall dimension']);self.assertIn('conflicts',self.fields(r));self.assertFalse(r['fabrication_released'])
    def test_overlapping_fixing_offsets(self):
        r=self.run_plan(fabrication={'fixing_top_offset_mm':400,'fixing_bottom_offset_mm':400,'fixing_side_offset_mm':900});self.assertIn('fabrication.fixing_offsets',self.fields(r));self.assertIn('fabrication.fixing_side_offset_mm',self.fields(r))
    def test_conflicting_material_limits(self):
        m=copy.deepcopy(BASE['material']);m.update(min_panel_width_mm=500,max_panel_width_mm=300);self.assertIn('material.panel_width_limits',self.fields(self.run_plan(material=m)))

class ApiTests(unittest.TestCase):
    def setUp(self): self.client=TestClient(app)
    def test_health_frontend_and_rules(self):
        for path in ['/health','/','/app.js','/api/cladding/rules']:
            self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(len(self.client.get('/api/cladding/rules').json()['workflow']),11)
    def test_plan_endpoint(self):
        r=self.client.post('/api/cladding/plan',json=BASE);self.assertEqual(r.status_code,200);self.assertEqual(r.json()['quantity_takeoff']['panel_count'],6)
    def test_invalid_dimension_and_system(self):
        for patch in [{'width_mm':-1},{'system':'bad'},{'u_channel_count':1.5},{'unexpected':10}]:
            self.assertEqual(self.client.post('/api/cladding/plan',json={**BASE,**patch}).status_code,422)
    def test_pdf_regression(self):
        with fitz.open() as doc:
            page=doc.new_page();page.insert_text((72,72),'EWMB-01 Beige Travertine Romano Classico +3.20');data=doc.tobytes()
        r=self.client.post('/analyze',files={'file':('elevation.pdf',data,'application/pdf')});self.assertEqual(r.status_code,200);self.assertIn('EWMB-01',r.json()['detected_codes']);self.assertEqual(r.json()['materials'][0]['evidence'][0]['source'],'elevation.pdf')
    def test_invalid_pdf(self):
        self.assertEqual(self.client.post('/analyze',files={'file':('bad.pdf',b'not pdf','application/pdf')}).status_code,400)

if __name__=='__main__': unittest.main(verbosity=2)
