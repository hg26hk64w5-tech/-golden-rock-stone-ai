const $=id=>document.getElementById(id), value=id=>$(id)?$(id).value.trim():'', num=id=>value(id)===''?null:Number(value(id));
const notice = $('notice');
let current=0,result=null,rules=null,revision=0;
function show(n){current=n;document.querySelectorAll('[data-step]').forEach(e=>e.hidden=Number(e.dataset.step)!==n);document.querySelectorAll('nav button').forEach((e,i)=>e.classList.toggle('active',i===n));$('prev').disabled=n===0;$('next').disabled=n===10;}
function dirty(){revision++;result=null;$('json').disabled=true;$('csv').disabled=true;$('dxf').disabled=true;for(const id of ['drawing','detailSheet','setting','cutting','quantity','rfis'])$(id).replaceChildren();$('notice').textContent='Inputs changed. Calculate to refresh outputs.';}
$('form').addEventListener('input',dirty);$('prev').onclick=()=>show(Math.max(0,current-1));$('next').onclick=()=>show(Math.min(10,current+1));
$('thicknessProfile').addEventListener('change',()=>{$('thickness').value=$('thicknessProfile').value;dirty();});
function payload(){
 const slabs=value('slabs').split('\n').filter(x=>x.trim()).map(line=>{const parts=line.trim().split(/\s*[x×,]\s*/i);if(parts.length!==2||parts.some(x=>!x.trim()||!Number.isFinite(Number(x))))throw Error('Enter slab sizes as width × height, one per line.');return {width_mm:Number(parts[0]),height_mm:Number(parts[1])};});
 const points=value('points')?value('points').split(',').map(x=>{if(!x.trim()||!Number.isFinite(Number(x)))throw Error('Survey offsets must be comma-separated numbers.');return Number(x);}):[];
 const thicknessProfile=value('thicknessProfile'); const detailProfile=thicknessProfile==='25'?'project_option2_25mm':thicknessProfile==='30'?'project_custom_30mm':'external_standard_20mm';
 return {connection:{entry:value('connectionEntry')||'rear',support_face_from_wall_mm:num('supportFace'),stone_back_from_wall_mm:num('stoneBack')},wall_module:wallModuleInput(),channel_layout:channelInput(),bracket_layout:value('threePointSide')?{three_point_side:value('threePointSide')}:null,scope:value('scope'),environment:value('environment'),element:value('element'),zone:value('zone'),system:value('system')||null,u_channel_count:num('channelCount'),width_mm:num('width'),height_mm:num('height'),dimensions_verified:$('verified').checked,material_type:value('materialType')||null,material_weight_kg_m2:num('materialWeight'),material:value('material')?{name:value('material'),slabs,thickness_mm:Number(thicknessProfile||num('thickness')),min_panel_width_mm:num('minwidth'),max_panel_width_mm:num('maxwidth'),kerf_mm:num('kerf'),edge_trim_mm:num('trim')}:null,rock_wool:$('wool').checked,waterproofing:value('waterproofing'),joints_requested:$('joints').checked,joint_mm:num('joint'),corner:value('corner'),stone_fixings_per_piece:num('stoneFixings'),stone_fixing_type:value('stoneFixingType')||null,stone_density_kg_m3:num('density'),building_height_m:num('buildingHeight'),wind_pressure_kpa:num('windPressure'),building_irregular:false,wind_tunnel_completed:false,substrate_type:value('substrate')||null,anchor_capacity_kn:num('anchorCapacity'),fixing_spacing_mm:num('fixingSpacing'),allowable_deflection_mm:num('deflection'),detail_profile:detailProfile,horizontal_joint_mm:num('horizontalJoint'),vertical_joint_mm:num('verticalJoint'),parapet_groove_width_mm:num('parapetGrooveWidth'),parapet_groove_depth_mm:num('parapetGrooveDepth'),corner_machine_cut_mm:num('cornerMachineCut'),groove_width_mm:num('grooveWidth'),groove_depth_mm:num('grooveDepth'),survey:{datum:value('datum')||null,wall_offsets_mm:points,cavity_mm:num('cavity'),cavity_reference:value('reference')||null,final_stone_face_mm:num('face'),bracket_projection_mm:num('projection'),projection_approved:$('projectionApproved').checked,adjustment_capacity_mm:num('adjustment')},fabrication:Object.fromEntries(rules.fabrication_fields.map(f=>[f,num(f)])),fabrication_approved:$('fabricationApproved').checked,conflicts:value('conflicts').split('\n').filter(x=>x.trim())};
}
function download(name,content,type){const url=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function refreshProjectRegister(){return fetch('/api/project/external-stone').then(r=>r.json()).then(data=>{$('projectRegister').textContent=JSON.stringify(data,null,2);return data;}).catch(()=>{$('projectRegister').textContent='Project register unavailable.';});}
function useZone(z){
 $('zone').value=z.zone_id; $('verified').checked=false;
 show(2); dirty();
 const catIsStone=z.material_code!=='RFI-MATERIAL';
 $('materialType').value=catIsStone && /limestone/i.test(z.material_name)?'Limestone':catIsStone?'Travertine':'';
 $('material').value=catIsStone?z.material_name:'';
 if(z.thickness_mm){$('thickness').value=z.thickness_mm; if(z.thickness_mm===20)$('thicknessProfile').value='20'; else if(z.thickness_mm===25)$('thicknessProfile').value='25'; else if(z.thickness_mm===30)$('thicknessProfile').value='30';}
 const noteBox=$('zoneUseNote')||(()=>{const p=document.createElement('p');p.id='zoneUseNote';p.style.color='#e0bc78';$('form').querySelector('[data-step="2"]').append(p);return p;})();
 noteBox.textContent=`Auto-filled from sheet ${z.sheet}, code ${z.material_code}. Width/height, material and "verified" still need confirming from CAD/survey (${z.note})`;
}
function renderDetectedZones(register){
 const box=$('detectedZones'); if(!box) return;
 box.replaceChildren();
 if(!register || !register.zones || !register.zones.length){box.textContent='No natural-stone cladding code was detected in the uploaded PDFs.'; return;}
 const h=document.createElement('h3'); h.textContent=`Detected external stone/marble zones (${register.zones.length})`; box.append(h);
 for(const z of register.zones){
  const card=document.createElement('div'); card.className='card';
  const t=document.createElement('strong'); t.textContent=`${z.zone_id}`; card.append(t);
  const d=document.createElement('p'); d.textContent=`${z.material_name}${z.thickness_mm?` · ${z.thickness_mm}mm`:''} — sheet ${z.sheet} · confidence ${Math.round((z.confidence||0)*100)}% · openings detected ${z.opening_count||0}`; card.append(d);
  const n=document.createElement('p'); n.textContent=z.note; card.append(n);
  const b=document.createElement('button'); b.type='button'; b.textContent='Use this zone →'; b.onclick=()=>useZone(z); card.append(b);
  box.append(card);
 }
 if(register.rfi_required && register.rfi_required.length){
  const h2=document.createElement('h3'); h2.textContent='Open items from this analysis'; box.append(h2);
  for(const item of register.rfi_required){const p=document.createElement('p'); p.textContent='• '+item; box.append(p);}
 }
}
const projectFiles=$('projectFiles'); if(projectFiles){$('uploadBatch').onclick=async()=>{try{if(!projectFiles.files.length)throw Error('Select the project files first.');$('batchResult').textContent='Analyzing…';const fd=new FormData();for(const f of projectFiles.files)fd.append('files',f);const r=await fetch('/api/project/upload-batch',{method:'POST',body:fd});const data=await r.json();if(!r.ok)throw Error(JSON.stringify(data));$('batchResult').textContent=JSON.stringify({status:data.status,file_count:data.file_count,files:data.files,analysis_errors:data.analysis_errors},null,2);renderDetectedZones(data.project_register);if(data.project_register)await refreshProjectRegister();}catch(e){$('batchResult').textContent=e.message;}};}
function render(){
 $('notice').textContent=`${result.status} · ${result.quantity_takeoff.panel_count} panels · ${result.rfis.length} RFIs · NOT FOR FABRICATION`;
 $('rfis').replaceChildren(...result.rfis.map(r=>{const d=document.createElement('div');d.className='rfi';d.textContent=`${r.id} · ${r.field}: ${r.message}`;return d;}));
 $('setting').textContent=JSON.stringify({setting_out:result.setting_out,fixing_details:result.fixing_details,fixing_layout:result.fixing_layout,engineering_checklist:result.engineering_checklist,rules:result.rules},null,2);$('quantity').textContent=JSON.stringify(result.quantity_takeoff,null,2);
 const sheet=result.detail_sheet;const detail=document.createElement('div');detail.className='card';const title=document.createElement('h3');title.textContent=`${sheet.sheet_title} · ${sheet.profile}`;detail.append(title);const note=document.createElement('p');note.textContent=sheet.notes.join(' ');detail.append(note);const detailTable=document.createElement('table');for(const row of [['Detail','Purpose'],...sheet.details.map((name,i)=>[`Detail ${sheet.detail_numbers[name]} · ${name.replaceAll('_',' ')}`,name==='elevation'?'External elevations and panel pattern':'RFI REQUIRED: project-specific geometry not generated'])]){const tr=document.createElement('tr');for(const v of row){const td=document.createElement('td');td.textContent=v;tr.append(td);}detailTable.append(tr);}detail.append(detailTable);const dims=document.createElement('pre');dims.textContent=JSON.stringify(sheet.profile_dimensions,null,2);detail.append(dims);
 if(result.u_channel_detail){const u=document.createElement('div');u.className='card';const h=document.createElement('h3');h.textContent=result.u_channel_detail.sheet_title;u.append(h);const intro=document.createElement('p');intro.textContent='Separate channel setting-out and schematic build-up are available. Anchor/connection and opening details remain RFI_REQUIRED.';u.append(intro);const ut=document.createElement('table');for(const row of [['Item','Requirement'],['Channel section','SS316 U-Channel 41×41×41mm · 2.8m'],['Cavity','110mm'],['Stone relation','2 channels per stone piece'],['Large brackets','4 per channel · 100×100mm · 2 top + 2 bottom'],['Small reverse brackets','4 per channel · 50×100mm · between large brackets'],['Anchors','4 Fischer anchors per bracket + epoxy injection at each drilled hole'],['Pin','Ø5mm · 20mm embedment'],['Rock Wool','50mm when selected']]){const tr=document.createElement('tr');for(const v of row){const td=document.createElement('td');td.textContent=v;tr.append(td);}ut.append(tr);}u.append(ut);const us=document.createElement('pre');us.textContent=JSON.stringify({sections:result.u_channel_detail.sections,notes:result.u_channel_detail.notes},null,2);u.append(us);detail.append(u);} $('detailSheet').replaceChildren(detail);
 const panels=result.cutting_list.items,table=document.createElement('table');for(const row of [['Panel','Width mm','Height mm','Thickness mm'],...panels.map(p=>[p.id,p.width_mm.toFixed(3),p.height_mm.toFixed(3),p.thickness_mm])]){const tr=document.createElement('tr');for(const v of row){const td=document.createElement('td');td.textContent=v;tr.append(td);}table.append(tr);}$('cutting').replaceChildren(table);$('drawing').replaceChildren();
 if(panels.length){const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg'),w=Math.max(...panels.map(p=>p.x_mm+p.width_mm)),h=Math.max(...panels.map(p=>p.y_mm+p.height_mm));svg.setAttribute('viewBox',`-100 -100 ${w+200} ${h+250}`);svg.setAttribute('role','img');svg.setAttribute('aria-label','Preliminary panel elevation');for(const p of panels){const rect=document.createElementNS(ns,'rect');for(const [k,v] of Object.entries({x:p.x_mm,y:p.y_mm,width:p.width_mm,height:p.height_mm,fill:'#e5d1aa',stroke:'#695d43','stroke-width':2}))rect.setAttribute(k,v);svg.append(rect);if(panels.length<500){const t=document.createElementNS(ns,'text');t.setAttribute('x',p.x_mm+10);t.setAttribute('y',p.y_mm+35);t.setAttribute('font-size',Math.min(24,p.width_mm/6));t.textContent=p.id;svg.append(t);}}const note=document.createElementNS(ns,'text');note.setAttribute('y',h+65);note.setAttribute('font-size','24');note.textContent='PRELIMINARY — NOT FOR FABRICATION';svg.append(note);$('drawing').append(svg);}
 renderDrawingPackage(result.drawing_package);$('csv').disabled=!panels.length;$('json').disabled=false;$('dxf').disabled=!panels.length;
}
$('form').onsubmit=async e=>{e.preventDefault();$('calculate').disabled=true;try{const input=payload();dirty();const requestRevision=revision;$('notice').textContent='Calculating…';const response=await fetch('/api/cladding/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input)}),body=await response.json();if(!response.ok)throw Error(JSON.stringify(body.detail||body));if(revision!==requestRevision){notice.textContent='Inputs changed during calculation. Calculate again.';return;}result=body;result.input=input;render();}catch(e){$('notice').textContent=e.message;}finally{$('calculate').disabled=false;}};
$('json').onclick=()=>result&&download('golden-rock-review.json',JSON.stringify(result,null,2),'application/json');
$('dxf').onclick=async()=>{if(!result||!result.input)return;try{const r=await fetch('/api/cladding/export-dxf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(result.input)});if(!r.ok)throw Error('DXF export failed.');download('golden-rock-external-wall.dxf',await r.text(),'application/dxf');}catch(e){$('notice').textContent=e.message;}};
$('csv').onclick=()=>result&&download('preliminary-cutting-list.csv','Status,Panel,Width mm,Height mm,Thickness mm\n'+result.cutting_list.items.map(p=>['NOT FOR FABRICATION',p.id,p.width_mm,p.height_mm,p.thickness_mm].join(',')).join('\n'),'text/csv');
$('analyze').onclick=async()=>{try{const file=$('pdf').files[0];if(!file)throw Error('Select a PDF first.');const fd=new FormData();fd.append('file',file);$('pdfResult').textContent='Analyzing…';const response=await fetch('/analyze',{method:'POST',body:fd}),data=await response.json();if(!response.ok)throw Error(JSON.stringify(data));$('pdfResult').textContent=JSON.stringify(data,null,2);}catch(e){$('pdfResult').textContent=e.message;}};
fetch('/api/cladding/rules').then(r=>{if(!r.ok)throw Error('Unable to load rules');return r.json();}).then(data=>{rules=data;data.workflow.forEach((name,i)=>{const b=document.createElement('button');b.type='button';b.textContent=`${i+1}. ${name}`;b.onclick=()=>show(i);$('steps').append(b);});Object.entries(data.systems).forEach(([key,s])=>{const o=document.createElement('option');o.value=key;o.textContent=s.label;$('system').append(o);});data.fabrication_fields.forEach(f=>{const label=document.createElement('label');label.textContent=f.replaceAll('_',' ');const input=document.createElement('input');input.id=f;input.type='number';input.min='0';input.step='any';label.append(input);$('fabrication').append(label);});show(0);}).catch(e=>{$('notice').textContent=e.message;$('calculate').disabled=true;});
refreshProjectRegister();







// Coordinates are explicit project inputs. No default positions or implicit approval.
const channelBox=document.createElement('fieldset');
const channelLegend=document.createElement('legend');channelLegend.textContent='U-channel setting out (mm from wall lower-left datum)';channelBox.append(channelLegend);
for(const [id,label] of [['channelXs','Channel centre-line X positions, comma separated'],['channelBase','Channel base Y'],['channelLarge','Four large bracket levels from channel base: 2 bottom + 2 top'],['channelSmall','Four small reverse bracket levels between large brackets']]){
 const l=document.createElement('label');l.textContent=label;const i=document.createElement('input');i.id=id;i.type='text';l.append(i);channelBox.append(l);
}
const cn=document.createElement('p');cn.textContent='Each channel is 2800mm long. Leave fields blank for RFI. Enter measured/design coordinates; structural verification remains required. Openings are not handled by this rectangular-wall tool.';channelBox.append(cn);
$('fabrication').append(channelBox);
const moduleBox=document.createElement('fieldset');
moduleBox.innerHTML='<legend>تقسيم الجدار من الزاوية إلى الباب أو الشباك</legend><label><input id="moduleEnabled" type="checkbox"> تفعيل عرض الحجر 800–1000 مم (قابل للتعديل)</label><label>أقل عرض مفضل mm<input id="moduleMin" type="number" value="800"></label><label>أكبر عرض مفضل mm<input id="moduleMax" type="number" value="1000"></label><label>عدد القطع أفقياً (اتركه فارغاً للاختيار)<input id="moduleCols" type="number"></label><label>بُعد محور الشنال عن حافة الحجر mm — يحتاج اعتماداً<input id="moduleInset" type="number"></label><label>نهاية الجدار<select id="moduleEnd"><option value="wall_end">نهاية الجدار</option><option value="door">باب</option><option value="window">شباك</option><option value="corner">زاوية</option></select></label><p>أدخل عرض الجزء المصمت فقط من الزاوية إلى الفتحة. القطع فوق وتحت الفتحات تحتاج مناطق مستقلة. 4م = 4 قطع × 1000 مم مع 8 خطوط شنال، أو 5 × 800 مم مع 10 خطوط. مواقع البراكتات والامتداد الرأسي تحتاج تحققاً.</p>';
document.querySelector('[data-step="5"]').append(moduleBox);
function wallModuleInput(){return $('moduleEnabled').checked?{preferred_min_mm:num('moduleMin'),preferred_max_mm:num('moduleMax'),preferred_columns:num('moduleCols'),channel_edge_offset_mm:num('moduleInset'),start_boundary:'corner',end_boundary:value('moduleEnd')}:null;}
function channelInput(){
 if(!['channelXs','channelBase','channelLarge','channelSmall'].some(id=>value(id)))return null;
 const list=id=>!value(id)?[]:value(id).split(',').map(x=>{if(!x.trim()||!Number.isFinite(Number(x)))throw Error('Channel coordinates must be numeric, comma separated.');return Number(x);});
 if(!value('channelBase')||!Number.isFinite(Number(value('channelBase'))))throw Error('Enter channel base Y, including 0 when applicable.');
 return {x_positions_mm:list('channelXs'),base_y_mm:Number(value('channelBase')),large_bracket_levels_mm:list('channelLarge'),small_bracket_levels_mm:list('channelSmall')};
}
function renderDrawingPackage(d, selected='S01'){
 if(!d||!d.entities.length)return;
 const entities=d.entities.filter(e=>selected==='ALL'||e.sheet===selected);
 if(!entities.length){$('drawing').textContent='No drawing geometry for this sheet. Calculate again or review the RFIs.';return;}
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
 const xs=entities.flatMap(e=>[e.x,e.x2??e.x+(e.text?.length||0)*(e.height||0)*0.65]);
 const ys=entities.flatMap(e=>[e.y,e.y2??e.y]);
 const xmin=Math.min(...xs)-100,xmax=Math.max(...xs)+100,ymin=Math.min(...ys)-100,ymax=Math.max(...ys)+100;
 svg.setAttribute('viewBox',`${xmin} ${-ymax} ${xmax-xmin} ${ymax-ymin}`);svg.setAttribute('role','img');svg.setAttribute('aria-label','Stone, separate channel setting out and build-up section');
 for(const e of entities){const node=document.createElementNS(ns,e.type==='LINE'?'line':'text');
 const highlight={GR_CHANNEL:'#147ca0',GR_BRACKET:'#a03d14',GR_LARGE_BRACKET:'#a03d14',GR_REVERSE_BRACKET:'#c47a2e'}[e.layer]||'#333';
 if(e.type==='LINE'){for(const [k,v] of Object.entries({x1:e.x,y1:-e.y,x2:e.x2,y2:-e.y2,stroke:highlight,'stroke-width':2}))node.setAttribute(k,v);}
 else {node.setAttribute('x',e.x);node.setAttribute('y',-e.y);node.setAttribute('font-size',e.height);node.textContent=e.text;}svg.append(node);}
 const picker=document.createElement('select');picker.setAttribute('aria-label','Drawing sheet');
 for(const [key,label] of [['S01','واجهة الحجر'],['S02','مخطط التثبيت المنفصل (شنالات أو براكيت)'],['S03','مقطع العزل والحجر'],['ALL','جميع اللوحات']]){const o=document.createElement('option');o.value=key;o.textContent=label;picker.append(o);}
 picker.value=selected;picker.onchange=()=>renderDrawingPackage(d,picker.value);
 $('drawing').replaceChildren(picker,svg);
}
