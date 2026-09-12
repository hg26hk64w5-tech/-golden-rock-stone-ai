import copy
import io
import os
import unittest
import zipfile
from fastapi.testclient import TestClient
from main import app
from cladding import PlanRequest, plan

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'AR-509.pdf')

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
        q=self.run_plan()['quantity_takeoff']['bracket_count'];self.assertEqual(q,{'u_channel_pieces':3,'u_channel_length_m':8.4,'large_brackets':12,'small_reverse_brackets':12,'total_brackets':24,'fischer_anchors':96,'anchor_system':'Fischer anchor + epoxy injection at each drilled hole'})
        f=self.run_plan()['fixing_details']; self.assertEqual(f['channels_per_stone_piece'],2); self.assertEqual(f['u_channel_length_m'],2.8); self.assertEqual(f['u_channel_length_per_stone_piece_m'],5.6); self.assertEqual(f['anchors_per_bracket'],4); self.assertEqual(f['anchors_per_stone_piece'],64)
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
    def test_project_option2_detail_profile(self):
        m=copy.deepcopy(BASE['material']);m['thickness_mm']=25
        r=self.run_plan(detail_profile='project_option2_25mm',material=m,horizontal_joint_mm=5,vertical_joint_mm=2,parapet_groove_width_mm=20,parapet_groove_depth_mm=5,corner_machine_cut_mm=5,groove_width_mm=10,groove_depth_mm=10)
        self.assertEqual(r['rules']['stone_thickness_mm'],25);self.assertEqual(r['rules']['joint_mm'],5);self.assertEqual(r['detail_sheet']['detail_numbers']['window_side'],2);self.assertEqual(r['detail_sheet']['profile_dimensions']['vertical_joint_mm'],2);self.assertFalse(any(x['field'] in {'detail_profile.material','horizontal_joint_mm','vertical_joint_mm','parapet_groove_width_mm','parapet_groove_depth_mm','corner_machine_cut_mm','groove'} for x in r['rfis']))
    def test_project_option2_missing_detail_data_is_rfi(self):
        m=copy.deepcopy(BASE['material']);m['thickness_mm']=25;r=self.run_plan(detail_profile='project_option2_25mm',material=m);self.assertIn('horizontal_joint_mm',self.fields(r));self.assertIn('groove',self.fields(r))

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
    @unittest.skipUnless(os.path.exists(FIXTURE), 'fixtures/AR-509.pdf sample drawing not present')
    def test_pdf_regression(self):
        with open(FIXTURE,'rb') as f: data=f.read()
        r=self.client.post('/analyze',files={'file':('elevation.pdf',data,'application/pdf')});self.assertEqual(r.status_code,200)
        body=r.json();self.assertIn('EWMB-01',body['detected_codes'])
        ewmb=next(m for m in body['materials'] if m['code']=='EWMB-01');self.assertEqual(ewmb['evidence'][0]['source'],'elevation.pdf')
    @unittest.skipUnless(os.path.exists(FIXTURE), 'fixtures/AR-509.pdf sample drawing not present')
    def test_pdf_regression_sheet_number_from_real_filename(self):
        # Regression test for a bug found while adding ZIP support: the endpoint used to
        # save the upload under tempfile's own randomised name before analysing it, which
        # silently defeated the "read the sheet number from the filename" shortcut for
        # every real upload (as opposed to a direct analyze_pdf(real_path) call in a
        # script/test) and could fall back to a mis-detected sheet like "TD-02" instead.
        # Uploading under the drawing's real name must resolve the correct sheet number.
        with open(FIXTURE,'rb') as f: data=f.read()
        r=self.client.post('/analyze',files={'file':('AR-509.pdf',data,'application/pdf')})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['sheet_number'],'AR-509')
    def test_invalid_pdf(self):
        self.assertEqual(self.client.post('/analyze',files={'file':('bad.pdf',b'not pdf','application/pdf')}).status_code,400)
    @unittest.skipUnless(os.path.exists(FIXTURE), 'fixtures/AR-509.pdf sample drawing not present')
    def test_upload_batch_builds_live_register(self):
        with open(FIXTURE,'rb') as f: data=f.read()
        r=self.client.post('/api/project/upload-batch',files=[('files',('AR-509.pdf',data,'application/pdf'))])
        self.assertEqual(r.status_code,200);body=r.json()
        self.assertIsNotNone(body['project_register']);self.assertEqual(body['project_register']['sheets_analyzed'],['AR-509'])
        stone_codes={z['material_code'] for z in body['project_register']['zones']}
        self.assertEqual(stone_codes,{'EWMB-01','EWST-01','EWST-02'})
        r2=self.client.get('/api/project/external-stone');self.assertEqual(r2.status_code,200)
        self.assertEqual(r2.json()['sheets_analyzed'],['AR-509'])
    @unittest.skipUnless(os.path.exists(FIXTURE), 'fixtures/AR-509.pdf sample drawing not present')
    def test_upload_batch_extracts_zip(self):
        # A project is often shared as one ZIP of the whole drawing package rather than
        # individual file picks. A PDF nested inside an uploaded ZIP (in a subfolder, as
        # real project exports usually are) must be analysed exactly like a directly
        # uploaded PDF, and macOS's "__MACOSX/" junk entries must not appear as files.
        with open(FIXTURE,'rb') as f: data=f.read()
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as zf:
            zf.writestr('ProjectPack/Drawings/AR-509.pdf', data)
            zf.writestr('__MACOSX/._AR-509.pdf', b'junk')
            zf.writestr('ProjectPack/notes.txt', b'some notes')
        r=self.client.post('/api/project/upload-batch',files=[('files',('ProjectFiles.zip',buf.getvalue(),'application/zip'))])
        self.assertEqual(r.status_code,200);body=r.json()
        self.assertFalse(any('__MACOSX' in f['file_name'] for f in body['files']))
        self.assertEqual(body['project_register']['sheets_analyzed'],['AR-509'])
        stone_codes={z['material_code'] for z in body['project_register']['zones']}
        self.assertEqual(stone_codes,{'EWMB-01','EWST-01','EWST-02'})
    def test_upload_batch_handles_corrupt_zip(self):
        r=self.client.post('/api/project/upload-batch',files=[('files',('bad.zip',b'not a real zip','application/zip'))])
        self.assertEqual(r.status_code,200);body=r.json()
        self.assertEqual(body['files'][0]['status'],'ANALYSIS_FAILED')
        self.assertEqual(len(body['analysis_errors']),1)

if __name__=='__main__': unittest.main(verbosity=2)
