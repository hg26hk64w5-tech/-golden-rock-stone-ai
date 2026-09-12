"""Client-confirmed geometry, separate from structural approval and hole design."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class Connection(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    entry: Literal['rear','top_pin'] = 'rear'
    support_face_from_wall_mm: float | None = Field(default=None, gt=0)
    # For a vertical pin its stone-back plane cannot be derived from pin penetration.
    stone_back_from_wall_mm: float | None = Field(default=None, gt=0)

def resolve_connection(p, rfi):
    t=p.material.thickness_mm if p.material else None
    embed={20:8,30:14}.get(t)
    projection=50 if p.system=='L' else 40 if p.system in ('U','Z','OMEGA') else None
    support=110 if p.system=='U' else p.connection.support_face_from_wall_mm
    if p.system=='U' and p.connection.support_face_from_wall_mm not in (None,110):
        rfi('connection.support_face_from_wall_mm','U outer face is 110mm from structural wall face; supplied value conflicts.')
        support=None
    if embed is None:
        rfi('connection.embedment_mm','Confirmed penetration is 8mm for 20mm stone and 14mm for 30mm stone. Other thicknesses, including 25mm, require clarification.')
    if support is None:
        rfi('connection.support_face_from_wall_mm','Confirm wall-to-outer-bracket-face distance. Nominal bracket size is not this dimension.')
    back=None
    if p.connection.entry=='rear' and None not in (support,projection,embed):
        back=support+projection-embed
        supplied=p.connection.stone_back_from_wall_mm
        if supplied is not None and abs(supplied-back)>0.01:
            rfi('connection.stone_back_from_wall_mm','Supplied stone back conflicts with support face + screw projection - embedment.')
            back=None
    elif p.connection.entry=='top_pin':
        back=p.connection.stone_back_from_wall_mm
        if back is None:
            rfi('connection.stone_back_from_wall_mm','Top pin penetration is vertical. Enter the horizontal stone-back plane; do not subtract vertical embedment from horizontal projection.')
        elif support is not None and back<=support:
            rfi('connection.stone_back_from_wall_mm','Stone back intersects the support face. Confirm top-pin connection geometry.')
            back=None
    if p.fabrication.get('bracket_thickness_mm') not in (None,3):
        rfi('fabrication.bracket_thickness_mm','Client-confirmed bracket metal thickness is 3mm.')
    pin_length=p.fabrication.get('pin_length_mm')
    if embed is not None and pin_length is not None and pin_length<embed:
        rfi('fabrication.pin_length_mm','Pin length is shorter than required penetration.')
    return dict(rules_revision='client-confirmed-1.6',entry=p.connection.entry,metal_thickness_mm=3,
                channel_length_mm=2800 if p.system=='U' else None,support_face_from_wall_mm=support,
                screw_projection_mm=projection,pin_diameter_mm=5,embedment_mm=embed,
                stone_thickness_mm=t,stone_back_from_wall_mm=back,
                final_stone_face_from_wall_mm=back+t if back is not None and t is not None else None,
                reference='structural_wall_face',waterproofing_mm=4,rock_wool_mm=50 if p.rock_wool else 0,
                note='Client geometry, not structural approval. Waterproofing/insulation lie inside the wall-to-support distance; do not add them again. Screw and hole dimensions are distinct.')
