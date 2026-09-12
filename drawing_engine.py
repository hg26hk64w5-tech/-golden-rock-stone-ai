"""Review drawings with explicit geometry; never substitute guessed fixing coordinates."""
import math

NOTICE = 'PRELIMINARY - NOT FOR FABRICATION. Engineer to verify applicable Dubai Municipality and authority requirements; compliance is not certified.'

def build_drawings(p, result):
    entities, issues = [], []
    sheet='S01'
    def line(x,y,x2,y2,layer):
        entities.append(dict(type='LINE',x=x,y=y,x2=x2,y2=y2,layer=layer,sheet=sheet))
    def text(x,y,value,layer='GR_NOTES',height=22):
        entities.append(dict(type='TEXT',x=x,y=y,text=value,layer=layer,height=height,sheet=sheet))
    def rect(x,y,w,h,layer):
        for a,b,c,d in [(x,y,x+w,y),(x+w,y,x+w,y+h),(x+w,y+h,x,y+h),(x,y+h,x,y)]: line(a,b,c,d,layer)
    def rfi(field,message):
        issues.append(dict(field=field,status='RFI_REQUIRED',message=message))
    panels = result['shop_drawing']['panels']
    w,h = p.width_mm or 0,p.height_mm or 0
    if not panels:
        return dict(version=1,units='mm',status='RFI_REQUIRED',entities=[],channels=[],brackets=[],rfis=[])
    text(0,h+120,'S01 - STONE ELEVATION',height=40)
    if p.wall_module:
        text(0,h+70,'START: '+p.wall_module.start_boundary)
        text(max(0,w-500),h+70,'END: '+p.wall_module.end_boundary)
        if p.wall_module.end_boundary in ('door','window'):
            rfi('termination.'+p.wall_module.end_boundary,'This wall stops at the opening jamb. Head, jamb, sill/threshold and return depths require an opening survey and separate project-specific sections.')
    for panel in panels:
        x,y,pw,ph = (panel[k] for k in ['x_mm','y_mm','width_mm','height_mm'])
        rect(x,y,pw,ph,'GR_STONE')
        text(x+10,y+ph/2,panel['id'],height=min(24,pw/8,ph/5))
        text(x+10,y+ph/2-35,f'{pw:.1f} x {ph:.1f} x {panel["thickness_mm"]:g}',height=min(18,pw/22,ph/8))
    text(0,-80,f'Overall {w:g} x {h:g} mm; written dimensions govern.')
    text(0,-130,NOTICE,height=16)
    channels=[]
    brackets=[]
    ox=w+800
    sheet='S02'
    if p.system=='U':
        text(ox,h+120,'S02 - U-CHANNEL SETTING OUT',height=40)
        rect(ox,0,w,h,'GR_WALL_REFERENCE')
        c=p.channel_layout
        if p.wall_module and p.wall_module.channel_edge_offset_mm is not None:
            from cladding import ChannelLayout
            inset=p.wall_module.channel_edge_offset_mm
            pw=result['layout']['panel_width_mm']
            if inset*2+41>=pw:
                rfi('wall_module.channel_edge_offset_mm','Opposing channel profiles overlap; reduce the approved edge offset or change the panel module.')
                c=None
            else:
                xs=sorted({x for panel in panels for x in (panel['x_mm']+inset,panel['x_mm']+panel['width_mm']-inset)})
                c=ChannelLayout(x_positions_mm=xs,base_y_mm=c.base_y_mm if c else 0,large_bracket_levels_mm=c.large_bracket_levels_mm if c else [],small_bracket_levels_mm=c.small_bracket_levels_mm if c else [])
        if c is None:
            rfi('channel_layout','Enter channel X positions, base Y, and four large/four small bracket levels measured from the channel base. 2800mm channels are not inferred from short stone panels.')
        else:
            xs=c.x_positions_mm
            large,small=c.large_bracket_levels_mm,c.small_bracket_levels_mm
            valid=True
            brackets_valid=True
            def reject(field,message):
                nonlocal valid
                valid=False;rfi(field,message)
            if not xs or len(set(xs))!=len(xs): reject('channel_layout.x_positions_mm','Provide unique channel centre lines.')
            if any(x<20.5 or x>w-20.5 for x in xs): reject('channel_layout.x_positions_mm','41mm channel profile exceeds the wall width.')
            if c.base_y_mm<0 or c.base_y_mm+2800>h: reject('channel_layout.base_y_mm','The full 2800mm channel must fit the wall zone. Confirm actual channel lengths/continuity for shorter walls.')
            if len(large)!=4 or len(small)!=4:
                brackets_valid=False;rfi('channel_layout.bracket_levels','Exactly four large and four small reverse bracket levels are required per channel; bracket symbols are withheld.')
            elif len(set(large+small))!=8 or any(y<=0 or y>=2800 for y in large+small):
                brackets_valid=False;rfi('channel_layout.bracket_levels','Eight distinct bracket levels must lie strictly within the 2800mm channel.')
            elif not (sorted(large)[1]<min(small) and max(small)<sorted(large)[2]):
                brackets_valid=False;rfi('channel_layout.bracket_levels','Place two large brackets below and two above the four small reverse brackets.')
            if valid:
                for i,x in enumerate(sorted(xs)):
                    cid=f'U{i+1:03d}'
                    channel=dict(id=cid,x_mm=x,base_y_mm=c.base_y_mm,length_mm=2800,large_levels_mm=large if brackets_valid else [],small_levels_mm=small if brackets_valid else [])
                    channels.append(channel)
                    rect(ox+x-20.5,c.base_y_mm,41,2800,'GR_CHANNEL')
                    text(ox+x+30,c.base_y_mm+2800,cid,height=18)
                    for levels,layer in ([(large,'GR_LARGE_BRACKET'),(small,'GR_REVERSE_BRACKET')] if brackets_valid else []):
                        for level in levels:
                            y=c.base_y_mm+level
                            rect(ox+x-35,y-12,70,24,layer)
                            text(ox+x+45,y,f'{level:g}',height=14)
                for panel in panels:
                    supports=[c['id'] for c in channels if panel['x_mm']<c['x_mm']<panel['x_mm']+panel['width_mm'] and c['base_y_mm']<=panel['y_mm'] and c['base_y_mm']+2800>=panel['y_mm']+panel['height_mm']]
                    if len(supports)!=2: rfi('channel_layout.'+panel['id'],f'{panel["id"]}: {len(supports)} continuous channels intersect this panel; two are required.')
                if len(channels)!=2*len(panels): rfi('channel_layout.continuity','Shared continuous channels differ from the requested two separate 2.8m pieces per stone. Engineer/client must resolve this before quantities or fabrication are approved.')
                if p.u_channel_count is not None and p.u_channel_count!=len(channels): rfi('u_channel_count','Entered channel quantity differs from the drawn channel count.')
            rfi('channel_layout.engineering','Coordinates are user-entered, not a structural design. Verify loads, channel gauge, anchor group capacity, substrate and edge distances.')
        if not channels: text(ox+40,h/2,'RFI REQUIRED - CHANNEL POSITIONS NOT GENERATED')
        text(ox,-80,'U 41x41x41; length 2800; bracket symbols NTS; all coordinates from zone datum.')
        text(ox,-130,NOTICE,height=16)
    elif p.system in ('L','Z','OMEGA'):
        # Point-fixing systems attach brackets directly at each stone panel's corners
        # rather than to a continuous channel. The corner offsets are the SAME
        # fixing_top_offset_mm / fixing_bottom_offset_mm / fixing_side_offset_mm the
        # client already confirms in Fixing Details (and which are already validated
        # there against the panel size) -- this sheet only visualises that approved
        # input, it does not invent a new one. The one genuinely new decision for a
        # 3-point arrangement (which side gets two brackets) has no default and is
        # withheld until stated explicitly, matching the project's channel_layout
        # precedent of never assuming a fixing arrangement.
        text(ox,h+120,'S02 - BRACKET SETTING OUT',height=40)
        rect(ox,0,w,h,'GR_WALL_REFERENCE')
        top=p.fabrication.get('fixing_top_offset_mm')
        bottom=p.fabrication.get('fixing_bottom_offset_mm')
        side=p.fabrication.get('fixing_side_offset_mm')
        if top is None or bottom is None or side is None:
            rfi('bracket_layout','Enter fixing top, bottom and side offsets before bracket positions are drawn.')
        elif p.stone_fixings_per_piece is None:
            rfi('bracket_layout','Select stone fixings per piece (3 or 4) before bracket positions are drawn.')
        elif p.stone_fixings_per_piece == 4:
            for panel in panels:
                x,y,pw,ph = (panel[k] for k in ['x_mm','y_mm','width_mm','height_mm'])
                if 2*side>=pw or top+bottom>=ph: continue
                for bx,by in [(x+side,y+bottom),(x+pw-side,y+bottom),(x+side,y+ph-top),(x+pw-side,y+ph-top)]:
                    brackets.append(dict(panel=panel['id'],x_mm=bx,y_mm=by))
        elif p.stone_fixings_per_piece == 3:
            three = p.bracket_layout.three_point_side if p.bracket_layout else None
            if three is None:
                rfi('bracket_layout.three_point_side','State which side takes the two brackets (top or bottom) for 3-point fixing; this is not assumed.')
            else:
                for panel in panels:
                    x,y,pw,ph = (panel[k] for k in ['x_mm','y_mm','width_mm','height_mm'])
                    if 2*side>=pw or top+bottom>=ph: continue
                    pair_y = y+ph-top if three=='top' else y+bottom
                    single_y = y+bottom if three=='top' else y+ph-top
                    brackets.append(dict(panel=panel['id'],x_mm=x+side,y_mm=pair_y))
                    brackets.append(dict(panel=panel['id'],x_mm=x+pw-side,y_mm=pair_y))
                    brackets.append(dict(panel=panel['id'],x_mm=x+pw/2,y_mm=single_y))
        for b in brackets:
            rect(ox+b['x_mm']-15,b['y_mm']-15,30,30,'GR_BRACKET')
            text(ox+b['x_mm']+20,b['y_mm'],b['panel'],height=12)
        if not brackets: text(ox+40,h/2,'RFI REQUIRED - BRACKET POSITIONS NOT GENERATED')
        rfi('bracket_layout.engineering','Positions follow entered offsets, not a structural design. Verify loads, bracket size/gauge, anchor capacity, substrate and edge distances.')
        text(ox,-80,f'{(result.get("system") or {}).get("label","Selected bracket system")}; positions from approved fixing offsets; symbols NTS.')
        text(ox,-130,NOTICE,height=16)
    else:
        text(ox,h+120,'S02 - FIXING SETTING OUT',height=40)
        text(ox,0,'Installation system not yet selected; fixing detail RFI.')
    if p.system in ('U','L','Z','OMEGA'):
        # Build-up section is generic to the wall zone, not specific to U-Channel, so it
        # is shown for every installation system once one is selected.
        sx,sy=0,-1500
        sheet='S03'
        text(sx,sy+700,'S03 - TYPICAL BUILD-UP SECTION (SCHEMATIC)',height=32)
        t=p.material.thickness_mm
        scale=3
        layers=[('SUBSTRATE - thickness/site condition RFI',60,'GR_SUBSTRATE'),('CEMENTITIOUS WATERPROOFING 2 x 2mm',4,'GR_WATERPROOFING')]
        if p.rock_wool: layers.append(('ROCK WOOL 50mm - retention/fire classification RFI',50,'GR_INSULATION'))
        ref=p.survey.cavity_reference
        if p.system=='U':
            # Cavity fixed by the U-Channel system definition (see cladding.py); shown
            # even before the reference face is confirmed, exactly as before.
            gap=110-(50 if p.rock_wool and ref=='waterproofing_face' else 0)
            if ref:
                layers.append((f'REMAINING CAVITY {gap:g}mm; origin: {ref}',gap,'GR_CAVITY'))
            else:
                layers.append(('CAVITY 110mm - measurement origin RFI / gap NTS',60,'GR_CAVITY'))
        else:
            # L/Z/Omega cavity is whatever the survey confirms -- never the U figure.
            cavity_val = (result.get('setting_out') or {}).get('cavity_mm')
            if cavity_val is not None and ref:
                gap=cavity_val-(50 if p.rock_wool and ref=='waterproofing_face' else 0)
                layers.append((f'REMAINING CAVITY {gap:g}mm; origin: {ref}',gap,'GR_CAVITY'))
            else:
                layers.append(('CAVITY - width and measurement origin RFI (survey.cavity_mm)',60,'GR_CAVITY'))
        layers.append((f'STONE {t:g}mm',t,'GR_STONE'))
        x=sx
        for i,(label,width,layer) in enumerate(layers):
            rect(x,sy,width*scale,500,layer)
            if layer in ('GR_SUBSTRATE','GR_INSULATION'):
                for yy in range(0,480,35): line(x,sy+yy,x+width*scale,sy+yy+20,layer)
            tx=sx+1000;ty=sy+500-i*85
            line(x+width*scale/2,sy+250,tx-20,ty, 'GR_LEADERS')
            text(tx,ty,label,height=20)
            x+=width*scale
        text(sx,sy-70,'Channel/bracket/anchor attachment: project-specific geometry RFI; section enlarged, do not scale.',height=19)
        text(sx,sy-110,'Final stone sealer: approved breathable/non-staining product; compatibility and coverage RFI.',height=19)
        if p.system=='U':
            text(sx,sy-150,'Per channel: 4 large 100x100 + 4 reverse 50x100; 4 anchors per bracket. Pin diameter 5, embedment 20.',height=19)
        else:
            angles=(result.get('fixing_details') or {}).get('angles_per_stone_piece')
            label=(result.get('system') or {}).get('label','selected system')
            text(sx,sy-150,f'Per stone piece: {angles if angles is not None else "RFI"} {label} brackets; anchor and pin sizes per approved detail.',height=19)
    return dict(version=1,units='mm',status='PRELIMINARY',entities=entities,channels=channels,brackets=brackets,rfis=issues,
                channel_quantities=dict(drawn_channels=len(channels),length_m=len(channels)*2.8,large_brackets=len(channels)*4,small_brackets=len(channels)*4,anchors=len(channels)*32),
                bracket_quantities=dict(drawn_brackets=len(brackets),panels_covered=len({b['panel'] for b in brackets})),
                limitations=['Rectangular wall elevation only. Openings must be separately surveyed; no automatic DWG interpretation.', 'Window/door head, jamb, sill and threshold geometry remains RFI_REQUIRED.','No structural certification or fabrication release.'])

def to_dxf(drawing):
    out=['0','SECTION','2','HEADER','9','$INSUNITS','70','4','0','ENDSEC','0','SECTION','2','ENTITIES']
    for e in drawing['entities']:
        out+=['0',e['type'],'8',e['layer'],'10',str(e['x']),'20',str(e['y']),'30','0']
        if e['type']=='LINE': out+=['11',str(e['x2']),'21',str(e['y2']),'31','0']
        else: out+=['40',str(e['height']),'1',e['text'].replace('\n',' ').replace('\r',' ')]
    return '\n'.join(out+['0','ENDSEC','0','EOF'])+'\n'
