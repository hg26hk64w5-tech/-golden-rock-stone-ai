"""External wall planning rules. Millimetres throughout; never infer fabrication details."""
import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

WORKFLOW = ['Scope', 'Internal/External', 'Area/Element', 'Installation System', 'Material', 'Panelization', 'Fixing Details', 'Shop Drawing', 'Cutting List', 'Quantity Takeoff', 'RFI']
SYSTEMS = {
    'L': {'label': 'L-Bracket SS316 50mm', 'nominal_mm': 50},
    'Z': {'label': 'Z-Bracket SS316 70mm', 'nominal_mm': 70},
    'OMEGA': {'label': 'Omega SS316 70mm', 'nominal_mm': 70},
    'U': {'label': 'U-Channel 41×41×41mm', 'channel_mm': [41,41,41], 'cavity_mm': 110},
}

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Slab(Strict):
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)

class MaterialSelection(Strict):
    name: str = Field(min_length=1)
    slabs: list[Slab] = Field(default_factory=list, max_length=100)
    thickness_mm: float = Field(default=20, gt=0)
    min_panel_width_mm: float | None = Field(default=None, gt=0)
    max_panel_width_mm: float | None = Field(default=None, gt=0)
    kerf_mm: float | None = Field(default=None, ge=0)
    edge_trim_mm: float | None = Field(default=None, ge=0)

class Survey(Strict):
    # Signed coordinates on one outward normal, relative to a common datum.
    wall_offsets_mm: list[float] = Field(default_factory=list, max_length=10000)
    datum: str | None = None
    cavity_mm: float | None = Field(default=None, gt=0)
    cavity_reference: Literal['waterproofing_face', 'insulation_face'] | None = None
    final_stone_face_mm: float | None = None
    bracket_projection_mm: float | None = Field(default=None, gt=0)
    projection_approved: bool = False
    adjustment_capacity_mm: float | None = Field(default=None, ge=0)

class PlanRequest(Strict):
    scope: str = 'Stone Works'
    environment: Literal['External','Internal'] = 'External'
    element: str = 'Wall Cladding'
    zone: str = 'Zone 1'
    system: Literal['L','Z','OMEGA','U'] | None = None
    u_channel_count: int | None = Field(default=None, gt=0, le=1000000, strict=True)
    width_mm: float | None = Field(default=None, gt=0, le=1000000)
    height_mm: float | None = Field(default=None, gt=0, le=1000000)
    dimensions_verified: bool = False
    material: MaterialSelection | None = None
    material_type: Literal['Travertine','Limestone'] | None = None
    material_weight_kg_m2: float | None = Field(default=None, gt=0)
    stone_density_kg_m3: float | None = Field(default=None, gt=0)
    building_height_m: float | None = Field(default=None, gt=0)
    wind_pressure_kpa: float | None = Field(default=None, gt=0)
    building_irregular: bool = False
    wind_tunnel_completed: bool = False
    substrate_type: str | None = None
    anchor_capacity_kn: float | None = Field(default=None, gt=0)
    fixing_spacing_mm: float | None = Field(default=None, gt=0)
    allowable_deflection_mm: float | None = Field(default=None, gt=0)
    rock_wool: bool = False
    waterproofing: Literal['MasterSeal 550','Sika','approved equivalent'] = 'MasterSeal 550'
    joints_requested: bool = False
    joint_mm: float | None = Field(default=None, ge=0)
    corner: Literal['45° mitre','5mm then 45° Bird’s Mouth'] = '45° mitre'
    stone_fixings_per_piece: Literal[3,4] | None = None
    stone_fixing_type: Literal['flat_bolt','L_angle','pin','L_bracket','Z_bracket','Omega_bracket','U_channel'] | None = None
    detail_profile: Literal['external_standard_20mm','project_option2_25mm','project_custom_30mm'] = 'external_standard_20mm'
    horizontal_joint_mm: float | None = Field(default=None, ge=0)
    vertical_joint_mm: float | None = Field(default=None, ge=0)
    parapet_groove_width_mm: float | None = Field(default=None, gt=0)
    parapet_groove_depth_mm: float | None = Field(default=None, gt=0)
    corner_machine_cut_mm: float | None = Field(default=None, gt=0)
    groove_width_mm: float | None = Field(default=None, gt=0)
    groove_depth_mm: float | None = Field(default=None, gt=0)
    detail_types: list[Literal['elevation','window_side','wall_corner','typical_crown','roof_balustrade_crown']] = Field(default_factory=lambda: ['elevation','window_side','wall_corner','typical_crown','roof_balustrade_crown'], max_length=20)
    survey: Survey = Field(default_factory=Survey)
    fabrication: dict[str, float | None] = Field(default_factory=dict)
    fabrication_approved: bool = False
    conflicts: list[str] = Field(default_factory=list)

FABRICATION_FIELDS = ['bracket_thickness_mm', 'anchor_diameter_mm', 'anchor_embedment_mm', 'hole_diameter_mm', 'pin_length_mm', 'pin_edge_distance_mm', 'fixing_top_offset_mm', 'fixing_bottom_offset_mm', 'fixing_side_offset_mm', 'corner_return_mm']

def plan(p: PlanRequest):
    rfis = []
    def rfi(field, message):
        rfis.append({'id': f'RFI-{len(rfis)+1:03d}', 'field':field, 'status':'RFI_REQUIRED', 'message':message})
    if p.environment != 'External' or p.element != 'Wall Cladding':
        rfi('scope', 'Only External Wall Cladding is implemented in this release.')
    for conflict in p.conflicts:
        rfi('conflicts', conflict)
    if not p.system: rfi('system', 'Client must select the installation system.')
    if not p.width_mm or not p.height_mm or not p.dimensions_verified:
        rfi('dimensions', 'Verified wall width and height are required.')
    if not p.material or not p.material.name.strip() or not p.material.slabs:
        rfi('material', 'Select material and available slab sizes before panelization.')
    if p.material and p.material.thickness_mm != 20:
        if not (p.detail_profile == 'project_option2_25mm' and p.material.thickness_mm == 25):
            rfi('material.thickness_mm', 'Stone thickness conflicts with the selected detail profile.')
    profile = {'external_standard_20mm': {'label':'External standard - 20mm stone','stone_thickness_mm':20,'horizontal_joint_mm':0,'vertical_joint_mm':0}, 'project_option2_25mm': {'label':'Project Option 2 - 25mm stone with grooves','stone_thickness_mm':25,'horizontal_joint_mm':5,'vertical_joint_mm':2}, 'project_custom_30mm': {'label':'Project-specific - 30mm stone','stone_thickness_mm':30,'horizontal_joint_mm':0,'vertical_joint_mm':0}}[p.detail_profile]
    if p.detail_profile == 'project_option2_25mm':
        if p.material is None or p.material.thickness_mm != 25: rfi('detail_profile.material', 'Project Option 2 requires 25mm stone.')
        if p.horizontal_joint_mm != 5: rfi('horizontal_joint_mm', 'Project Option 2 requires 5mm horizontal joints.')
        if p.vertical_joint_mm != 2: rfi('vertical_joint_mm', 'Project Option 2 requires 2mm vertical joints.')
        if p.parapet_groove_width_mm not in (20,): rfi('parapet_groove_width_mm', 'Project Option 2 parapet groove width is 20mm.')
        if p.parapet_groove_depth_mm not in (5,10): rfi('parapet_groove_depth_mm', 'Project Option 2 parapet groove depth must be 5mm or 10mm by detail.')
        if p.corner_machine_cut_mm != 5: rfi('corner_machine_cut_mm', 'Project Option 2 corner machine cut is 5mm.')
        if p.groove_width_mm != 10 or p.groove_depth_mm != 10: rfi('groove', 'Project Option 2 groove is 10mm × 10mm and requires approved mockup glue.')
    else:
        if p.horizontal_joint_mm not in (None,0): rfi('horizontal_joint_mm', 'The standard profile defaults to no joints unless the project requests them.')
    if p.detail_profile == 'project_custom_30mm':
        if p.material is None or p.material.thickness_mm != 30: rfi('detail_profile.material', 'The 30mm profile requires 30mm stone.')
        if p.horizontal_joint_mm is None: rfi('horizontal_joint_mm', 'Enter the approved horizontal joint for the 30mm project profile.')
        if p.vertical_joint_mm is None: rfi('vertical_joint_mm', 'Enter the approved vertical joint for the 30mm project profile.')
    if p.material and p.material.min_panel_width_mm is not None and p.material.max_panel_width_mm is not None and p.material.min_panel_width_mm > p.material.max_panel_width_mm:
        rfi('material.panel_width_limits', 'Minimum panel width exceeds material maximum.')
    if p.joints_requested and (p.joint_mm is None or p.joint_mm <= 0):
        rfi('joint_mm', 'Project-requested joints need an explicit positive dimension.')
    if not p.joints_requested and p.joint_mm not in (None,0):
        rfi('joint_mm', 'Joint dimension conflicts with no-joints default.')
    joint = (p.joint_mm or 0) if p.joints_requested else profile['horizontal_joint_mm']
    for field in FABRICATION_FIELDS:
        value = p.fabrication.get(field)
        if value is None or not math.isfinite(value) or value <= 0:
            rfi('fabrication.'+field, 'Missing or invalid fabrication dimension; obtain approved detail.')
    for field in p.fabrication:
        if field not in FABRICATION_FIELDS: rfi('fabrication.'+field, 'Unrecognized fabrication dimension; clarify its meaning.')
    if not p.fabrication_approved: rfi('fabrication_approved', 'Fixing layout, anchors, corner geometry and structural suitability require approved detail.')
    if p.fabrication.get('pin_length_mm') is not None and p.fabrication['pin_length_mm'] < 20:
        rfi('fabrication.pin_length_mm', 'Pin length cannot be shorter than the 20mm embedment.')
    s = p.survey
    setting = None
    if not s.wall_offsets_mm or not s.datum or not s.datum.strip():
        rfi('survey', 'Survey points and a common datum with positive outward normal are required.')
    cavity = 110 if p.system == 'U' else s.cavity_mm
    if p.system == 'U' and s.cavity_mm not in (None,110): rfi('survey.cavity_mm', 'U-Channel cavity must be 110mm.')
    if cavity is None: rfi('survey.cavity_mm', 'Confirm cavity; nominal bracket size is not a cavity dimension.')
    if s.cavity_reference is None: rfi('survey.cavity_reference', 'Confirm whether cavity is measured from waterproofing or insulation face.')
    if p.rock_wool and s.cavity_reference == 'waterproofing_face' and cavity is not None and cavity < 50:
        rfi('survey.cavity_mm', '50mm rock wool cannot fit inside this cavity.')
    if s.wall_offsets_mm and cavity is not None and s.cavity_reference:
        closest = max(s.wall_offsets_mm)
        deviation = closest-min(s.wall_offsets_mm)
        face = closest + 4 + (50 if p.rock_wool and s.cavity_reference == 'insulation_face' else 0) + cavity + 20
        setting = {'datum':s.datum, 'closest_wall_point_mm':closest, 'wall_deviation_mm':deviation, 'final_stone_face_mm':face, 'cavity_mm':cavity, 'cavity_reference':s.cavity_reference, 'uniform_bracket_projection_mm':s.bracket_projection_mm, 'zone':p.zone, 'system':p.system}
        if s.final_stone_face_mm is not None and abs(s.final_stone_face_mm-face) > 0.01:
            rfi('survey.final_stone_face_mm', 'Requested final face conflicts with closest wall point and build-up.')
        if s.adjustment_capacity_mm is None or s.adjustment_capacity_mm < deviation:
            rfi('survey.adjustment_capacity_mm', 'Approved adjustment capacity must accommodate wall deviation without varying bracket projection.')
    if s.bracket_projection_mm is None or not s.projection_approved:
        rfi('survey.bracket_projection_mm', 'Approve one uniform bracket projection for this system/zone; do not derive it from nominal bracket size.')
    panels, layout = [], None
    m = p.material
    if m and (m.kerf_mm is None or m.edge_trim_mm is None):
        rfi('material.cutting_allowances', 'Confirm saw kerf and slab edge trim before cutting optimization.')
    can_panelize = (p.environment == 'External' and p.element == 'Wall Cladding' and p.width_mm and p.height_mm and p.dimensions_verified and m and m.slabs and m.kerf_mm is not None and m.edge_trim_mm is not None)
    if can_panelize:
        choices = []
        for index, slab in enumerate(m.slabs):
            usable_w = slab.width_mm-2*m.edge_trim_mm-m.kerf_mm
            usable_h = min(700, slab.height_mm-2*m.edge_trim_mm-m.kerf_mm)
            if m.max_panel_width_mm is not None: usable_w = min(usable_w,m.max_panel_width_mm)
            if usable_w <= 0 or usable_h <= 0: continue
            cols = max(1,math.ceil((p.width_mm+joint)/(usable_w+joint)))
            rows = max(1,math.ceil((p.height_mm+joint)/(usable_h+joint)))
            w = (p.width_mm-(cols-1)*joint)/cols
            h = (p.height_mm-(rows-1)*joint)/rows
            if w <= 0 or h <= 0 or (m.min_panel_width_mm is not None and w < m.min_panel_width_mm): continue
            # Equal redistribution avoids narrow end strips. No fixed minimum width.
            choices.append((cols*rows,-w,index,cols,rows,w,h))
        if not choices: rfi('panelization', 'No layout fits the material slab sizes and selected material limits.')
        else:
            count,_,index,cols,rows,w,h = min(choices)
            if count > 10000: rfi('panelization', 'More than 10,000 panels; split into smaller zones.')
            else:
                layout = {'columns':cols,'rows':rows,'panel_width_mm':w,'panel_height_mm':h,'slab_index':index,'method':'Equalized grid: minimize panel count, then maximize width; grain direction preserved; no slab nesting claim.'}
                top = p.fabrication.get('fixing_top_offset_mm')
                bottom = p.fabrication.get('fixing_bottom_offset_mm')
                side = p.fabrication.get('fixing_side_offset_mm')
                if top is not None and bottom is not None and top+bottom >= h:
                    rfi('fabrication.fixing_offsets', 'Top and bottom offsets overlap or exceed panel height.')
                if side is not None and 2*side >= w:
                    rfi('fabrication.fixing_side_offset_mm', 'Opposing side offsets overlap or exceed panel width.')
                for row in range(rows):
                    for col in range(cols):
                        panels.append({'id':f'P{row+1}-{col+1}','x_mm':col*(w+joint),'y_mm':row*(h+joint),'width_mm':w,'height_mm':h,'thickness_mm':profile['stone_thickness_mm']})
    fixing = {'pin_diameter_mm':5,'pin_embedment_mm':20,'uniform_projection_per':'system/zone'}
    if p.stone_fixings_per_piece is None:
        rfi('stone_fixings_per_piece', 'Select 3 or 4 flat bolts, L-angles or pins per stone piece.')
    if p.stone_fixing_type is None:
        rfi('stone_fixing_type', 'Select the approved stone fixing type: flat bolt, L-angle or pin.')
    fixing['stone_fixings_per_piece'] = p.stone_fixings_per_piece
    fixing['stone_fixing_type'] = p.stone_fixing_type
    angle_map = {'L_bracket':3,'Z_bracket':4,'Omega_bracket':4,'U_channel':4}
    fixing['angles_per_stone_piece'] = angle_map.get(p.stone_fixing_type)
    if p.stone_fixing_type in angle_map and p.stone_fixings_per_piece is not None and p.stone_fixings_per_piece != angle_map[p.stone_fixing_type]:
        rfi('stone_fixings_per_piece', f'{p.stone_fixing_type} requires {angle_map[p.stone_fixing_type]} angles per stone piece.')
    if p.system == 'U':
        fixing.update({'channels_per_stone_piece':2,'u_channel_length_m':2.8,'u_channel_length_mm':2800,'large_brackets':{'count':4,'size_mm':[100,100],'positions':'2 top + 2 bottom per U-Channel'},'small_reverse_brackets':{'count':4,'size_mm':[50,100],'positions':'between large brackets per U-Channel'}})
        fixing['large_brackets_per_stone_piece'] = 8
        fixing['small_reverse_brackets_per_stone_piece'] = 8
        fixing['anchors_per_bracket'] = 4
        fixing['anchor_system'] = 'Fischer anchor with epoxy injection to seal/isolate each drilled hole'
        fixing['anchors_per_stone_piece'] = 64
        fixing['u_channel_length_per_stone_piece_m'] = 5.6
        fixing['quantity_basis'] = '2 U-Channel pieces per stone piece, each 2.8m long; each channel uses 4 large and 4 small reverse brackets (8 + 8 per stone piece)'
        if p.u_channel_count is None:
            rfi('u_channel_count', 'Enter verified total U-Channel pieces: each stone piece requires 2 channels, with 4 large and 4 small reverse brackets per channel.')
    elif p.system:
        rfi('fixing.count', 'Confirm bracket quantity and arrangement for the selected L/Z/Omega system.')
    u_channel_detail = None
    if p.system == 'U':
        u_channel_detail = {
            'status': 'PRELIMINARY — NOT FOR FABRICATION',
            'sheet_title': 'Separate U-Channel fixing detail',
            'channel_section': {'profile': 'U-Channel SS316', 'size_mm': [41, 41, 41], 'length_m': 2.8, 'cavity_mm': 110, 'stone_thickness_mm': profile['stone_thickness_mm']},
            'insulation': {'type': 'Rock Wool', 'thickness_mm': 50, 'included_when_selected': p.rock_wool},
            'bracket_schedule': [
                {'type': 'Large bracket', 'size_mm': [100,100], 'quantity_per_channel': 4, 'positions': '2 top + 2 bottom'},
                {'type': 'Small reverse bracket', 'size_mm': [50,100], 'quantity_per_channel': 4, 'positions': 'equally distributed between large brackets'},
            ],
            'anchor_detail': {'anchor': 'Fischer', 'anchors_per_bracket': 4, 'hole_sealing': 'Epoxy injection at each drilled hole', 'pin_diameter_mm': 5, 'pin_embedment_mm': 20},
            'panel_relation': '2 U-Channels per stone piece; 4 large + 4 small brackets per channel',
            'sections': ['U-channel vertical section', 'top bracket section', 'bottom bracket section', 'reverse bracket section', 'stone-to-channel interface', 'waterproofing and Rock Wool build-up'],
            'corner_intersection': {'projection_mm': 110, 'projection_m': 0.11, 'requirement': 'Required 110mm projection at the meeting point of corner returns.'},
            'notes': ['Keep bracket projection uniform by system/zone.', 'Corner intersection projection is fixed at 110mm (11cm) and must be shown at every applicable corner return.', 'Confirm substrate, anchor capacity, edge distances and final spacing by engineer.', 'This sheet is separate from the stone panel elevation and is not for fabrication.']
        }
    quantities = None
    if p.system == 'U' and p.u_channel_count is not None:
        total_brackets = 8*p.u_channel_count
        quantities = {'u_channel_pieces':p.u_channel_count,'u_channel_length_m':round(2.8*p.u_channel_count,3),'large_brackets':4*p.u_channel_count,'small_reverse_brackets':4*p.u_channel_count,'total_brackets':total_brackets,'fischer_anchors':4*total_brackets,'anchor_system':'Fischer anchor + epoxy injection at each drilled hole'}
    fixing_layout = []
    if p.system == 'U' and layout:
        for panel in panels:
            w, h = panel['width_mm'], panel['height_mm']
            channels = [round(w*0.25,3), round(w*0.75,3)]
            for x in channels:
                fixing_layout.append({'panel_id':panel['id'],'channel_x_mm':round(panel['x_mm']+x,3),'channel_length_m':2.8,'large_brackets_y_mm':[round(panel['y_mm']+0.1*h,3),round(panel['y_mm']+0.9*h,3)],'small_reverse_brackets_y_mm':[round(panel['y_mm']+0.26*h,3),round(panel['y_mm']+0.42*h,3),round(panel['y_mm']+0.58*h,3),round(panel['y_mm']+0.74*h,3)],'distribution_method':'Two channels at quarter points; 4 large brackets near top/bottom and 4 small reverse brackets equally distributed between them. Final spacing requires engineer approval.'})
    elif p.system == 'U':
        rfi('fixing_layout', 'Provide panel dimensions and approved spacing to distribute the two U-Channels and brackets.')
    status = 'RFI_REQUIRED' if rfis else 'REVIEW_REQUIRED'
    area = p.width_mm*p.height_mm/1e6 if p.width_mm and p.height_mm and p.dimensions_verified else None
    detail_sheet = {'status':'PRELIMINARY — NOT FOR FABRICATION','profile':profile['label'],'sheet_title':'External cladding pattern drawings','detail_numbers':{name:i+1 for i,name in enumerate(p.detail_types)},'details':p.detail_types,'notes':['Do not scale; use written dimensions only.','All dimensions in millimetres; levels in metres.','Verify site dimensions before production.','Coordinate discrepancies between drawings, specification and BOQ with the designer.','Window side, wall corner, typical crown and roof balustrade crown require approved fixing and waterproofing details.','NOTE: These drawings are prepared in line with Dubai Municipality requirements and the governing systems for facade works. Final issue remains subject to engineer and authority review and approval.'],'profile_dimensions':{'stone_thickness_mm':profile['stone_thickness_mm'],'horizontal_joint_mm':p.horizontal_joint_mm if p.detail_profile == 'project_option2_25mm' else joint,'vertical_joint_mm':p.vertical_joint_mm,'parapet_groove_width_mm':p.parapet_groove_width_mm,'parapet_groove_depth_mm':p.parapet_groove_depth_mm,'corner_machine_cut_mm':p.corner_machine_cut_mm,'groove_width_mm':p.groove_width_mm,'groove_depth_mm':p.groove_depth_mm,'glue_mockup_required':p.detail_profile == 'project_option2_25mm'}}
    rules = {'detail_profile':p.detail_profile,'stone_thickness_mm':profile['stone_thickness_mm'],'max_panel_height_mm':700,'minimum_panel_width_mm':m.min_panel_width_mm if m else None,'joint_mm':joint,'vertical_joint_mm':p.vertical_joint_mm,'corner':p.corner,'corner_intersection_projection_mm':110,'material_type':p.material_type,'material_weight_kg_m2':p.material_weight_kg_m2 if p.material_weight_kg_m2 is not None else (70 if p.material_type in ('Travertine','Limestone') else None),'waterproofing':{'type':'cementitious','product':p.waterproofing,'coats':2,'coat_thickness_mm':2,'total_mm':4},'rock_wool_mm':50 if p.rock_wool else 0,'engineering_notice':'These preliminary drawings are structured against Dubai Municipality requirements and governing facade systems; final design remains subject to engineer and authority review/approval.'}
    if p.system == 'U':
        rules.update({'u_channels_per_stone_piece':2,'u_channel_length_m':2.8,'u_channel_length_per_stone_piece_m':5.6,'large_brackets_per_stone_piece':8,'small_reverse_brackets_per_stone_piece':8,'fischer_anchors_per_bracket':4,'fischer_anchors_per_stone_piece':64})
    engineering_checklist = [
        {'id':'ENG-01','item':'Substrate description, strength and anchor zones','status':'RFI_REQUIRED'},
        {'id':'ENG-02','item':'Stone weight, wind load, pull-out, shear and deflection checks','status':'RFI_REQUIRED'},
        {'id':'ENG-03','item':'Building movement, expansion and thermal joint coordination','status':'RFI_REQUIRED'},
        {'id':'ENG-04','item':'Waterproofing continuity, flashings, drips, weeps and drainage','status':'REVIEW_REQUIRED'},
        {'id':'ENG-05','item':'Rock Wool classification, retention and cavity fire barriers','status':'RFI_REQUIRED'},
        {'id':'ENG-06','item':'Window and door head, sill/threshold and jamb terminations','status':'RFI_REQUIRED'},
        {'id':'ENG-07','item':'Stone tolerances, channel alignment and installation tolerances','status':'RFI_REQUIRED'},
        {'id':'ENG-08','item':'Vein/grain direction, bookmatch sequence and extra waste','status':'REVIEW_REQUIRED'},
        {'id':'ENG-09','item':'Material certificates and compatibility of anchors, epoxy and sealants','status':'RFI_REQUIRED'},
        {'id':'ENG-10','item':'Approved mockup, method statement, ITP and hold points','status':'RFI_REQUIRED'},
        {'id':'ENG-11','item':'MEP, glazing, doors, roof, balustrade and lightning protection coordination','status':'RFI_REQUIRED'},
        {'id':'ENG-12','item':'Revision history, engineer comments, as-built and maintenance access','status':'REVIEW_REQUIRED'},
    ]
    return {'status':status,'fabrication_released':False,'workflow':WORKFLOW,'zone':p.zone,'system':SYSTEMS.get(p.system),'rules':rules,'engineering_checklist':engineering_checklist,'setting_out':setting,'fixing_details':fixing,'fixing_layout':fixing_layout,'layout':layout,'shop_drawing':{'status':'PRELIMINARY — NOT FOR FABRICATION','panels':panels,'detail_sheet':detail_sheet,'fixing_layout':fixing_layout,'engineering_checklist':engineering_checklist,'u_channel_detail':u_channel_detail},'detail_sheet':detail_sheet,'u_channel_detail':u_channel_detail,'cutting_list':{'status':'PRELIMINARY — NOT FOR FABRICATION','items':panels},'quantity_takeoff':{'status':'PRELIMINARY','gross_wall_m2':area,'stone_net_m2':sum(x['width_mm']*x['height_mm'] for x in panels)/1e6 if panels else None,'panel_count':len(panels),'waterproofing_m2':area,'waterproofing_coat_m2':2*area if area is not None else None,'rock_wool_m2':area if p.rock_wool else 0,'bracket_count':quantities,'note':'Gross rectangular zone; openings, slab stock/nesting, waste and fixing quantities require project details.'},'rfis':rfis}


