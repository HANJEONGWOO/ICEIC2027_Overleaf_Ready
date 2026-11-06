#!/usr/bin/env python3
"""Draw the paper overview as editable, flat vector shapes.

Run: python figures/plot_kv_cache_overview.py
Requires numpy, matplotlib and Liberation Sans TrueType fonts.
The PowerPoint exporter uses only the stdlib.
No inference or parameter fitting is performed. Frozen levels and empirical
histograms, including their provenance, are read from the adjacent JSON files.
Outputs: PDF (paper), SVG, PNG (preview), and editable PPTX.
"""
from pathlib import Path
import json
import math

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon
from matplotlib import font_manager
from overview_pptx import write_pptx

HERE = Path(__file__).resolve().parent
LEVELS = json.loads((HERE / 'kv_cache_overview_levels.json').read_text())
DENSITY = json.loads((HERE / 'kv_cache_overview_density.json').read_text())
W, H = 1232, 500
INK = '#222222'
SECONDARY = '#555555'
BLUE = '#38668A'
GREEN = '#477B65'
BLUE_PALE = '#EAF0F5'
GREEN_PALE = '#EEF3EF'
COARSE = '#AB7448'
FINE_FILL = '#E3ECF5'
COARSE_FILL = '#F3E9DE'
LINE = '#8A8A8A'
GRAY = '#8B8B8B'
SCENE = {'width': W, 'height': H, 'font': 'Arial', 'shapes': []}

def rect(x, y, w, h, fill=None, stroke=None, lw=1):
    SCENE['shapes'].append(dict(type='rect', x=x, y=y, w=w, h=h,
                                fill=fill, stroke=stroke, lw=lw))

def line(points, color=LINE, lw=1, dash=False):
    SCENE['shapes'].append(dict(type='line', points=points, stroke=color, lw=lw, dash=dash))

def polygon(points, fill=None, stroke=None, lw=1):
    SCENE['shapes'].append(dict(type='polygon', points=points, fill=fill, stroke=stroke, lw=lw))

def circle(x, y, r, fill, stroke=None, lw=1):
    SCENE['shapes'].append(dict(type='circle', cx=x, cy=y, r=r, fill=fill, stroke=stroke, lw=lw))

def text(x, y, w, h, label, size=16, color=INK, bold=False, align='left', italic=False):
    SCENE['shapes'].append(dict(type='text', x=x, y=y, w=w, h=h, text=label,
                                size=size, color=color, bold=bold, align=align,
                                valign='middle', italic=italic))

def arrow(x1, y1, x2, y2, color=GRAY, lw=1.8, head=5):
    angle = math.atan2(y2-y1, x2-x1)
    line([[x1,y1],[x2,y2]], color, lw)
    polygon([[x2,y2], [x2-head*math.cos(angle)+head*.55*math.sin(angle),
                      y2-head*math.sin(angle)-head*.55*math.cos(angle)],
                     [x2-head*math.cos(angle)-head*.55*math.sin(angle),
                      y2-head*math.sin(angle)+head*.55*math.cos(angle)]], color)

# Plain panel titles and native shapes keep the figure easy to edit in PPT.
# This is a visual style, not a claim that the diagram was drawn without AI aid.
text(7, 3, 288, 29, '(a) KV cache budget', 21, bold=True)
text(328, 3, 287, 29, '(b) Layer allocation', 21, bold=True)
text(696, 3, 529, 29, '(c) Hardware-aware KV codecs', 21, bold=True)

# (a) The bar shows index storage only: K:V = 3:1 exactly.
for x,sub in ((41,'KV'),(136,'K'),(218,'V')):
    text(x,65,23,36,'B',29,italic=True)
    text(x+20,82,30,22,sub,17,italic=True)
text(99,66,28,36,'=',28,align='center')
text(178,66,25,36,'+',28,align='center')
rect(16,126,192,42,BLUE_PALE,INK,1.25)
rect(208,126,64,42,GREEN_PALE,INK,1.25)
text(16,126,192,42,'K: 6 bits (avg.)',18,align='center')
text(208,126,64,42,'V: 2',18,align='center')
text(1,178,288,25,'8 index bits per K/V pair (avg.)',17,align='center')

for x,label,color,pale,description,precision in (
    (17,'Key (K)',BLUE,BLUE_PALE,'Attention\nweights','K4 / K8'),
    (160,'Value (V)',GREEN,GREEN_PALE,'Weighted\nsum','V2'),
):
    text(x-7,229,121,26,label,19,bold=True,align='center')
    rect(x,270,106,70,pale,color,1.3)
    for i in range(1,5):
        line([[x+i*106/5,270],[x+i*106/5,340]],color,.7)
    for i in range(1,4):
        line([[x,270+i*70/4],[x+106,270+i*70/4]],color,.7)
    text(x-7,354,121,48,description,18,align='center')
    text(x-7,417,121,26,precision,20,color,bold=True,align='center')
arrow(289,280,319,280,INK,1.4,6)

# (b) A layer group is a simple rectangle, with explicit K and V labels.
text(324,47,282,25,'Qwen3-1.7B (28 layers)',18,align='center')
for top,layers,kbits,pale in (
    (107,'Layers 1–7','K8',BLUE_PALE),
    (229,'Layers 8–21','K4','#F2F2F2'),
    (351,'Layers 22–28','K8',BLUE_PALE),
):
    rect(337,top,253,81,pale,INK,1.3)
    text(348,top+8,231,25,layers,20,bold=True,align='center')
    text(358,top+43,110,25,'V2',19,GREEN,align='center')
    text(490,top+43,78,25,kbits,19,BLUE if kbits=='K8' else INK,
         bold=True,align='center')
    line([[476,top+42],[476,top+68]],LINE,.8)
for a,b in ((192,224),(314,346)):
    arrow(463.5,a,463.5,b,INK,1.3,5)
text(322,449,286,25,'14 K8 layers + 14 K4 layers',17,align='center')
text(323,478,285,23,'V2 in all layers',17,GREEN,align='center')

# K4 is routed to Lloyd--Max; both K8 groups share the PU-K8 path.
# A white gap at the crossing means no junction; the filled dot is a merge.
k4_lane,k8_lane=613,654
k4_target,k8_target=103,247
line([[568,284.5],[k4_lane,284.5],[k4_lane,k4_target]],INK,1.4)
arrow(k4_lane,k4_target,686,k4_target,INK,1.4,5)
for source_y in (162.5,406.5):
    line([[568,source_y],[k8_lane,source_y]],'#FFFFFF',5)
    line([[568,source_y],[k8_lane,source_y]],BLUE,1.6)
line([[k8_lane,162.5],[k8_lane,406.5]],BLUE,1.6)
circle(k8_lane,k8_target,2.6,BLUE)
arrow(k8_lane,k8_target,686,k8_target,BLUE,1.6,5)

# (c) Numerical plots, without card outlines or decorative header bands.
line([[701,60],[728,60]],INK,1.6)
text(736,47,126,25,'Gaussian model',16)
line([[868,60],[895,60]],GRAY,1.6,True)
text(903,47,110,25,'KV samples',16)
circle(1043,60,3.1,BLUE)
text(1054,47,152,25,'Levels',17)

SCALE=math.sqrt(LEVELS['distribution']['d'])
assert LEVELS['distribution']['d']==DENSITY['head_dim']==128
bins=np.array(DENSITY['bin_edges'])
centers=(bins[:-1]+bins[1:])/2
tau_z=LEVELS['pu_k8']['tau']*SCALE

def quantizer(title_y,baseline,peak,title,count,level_key,sample_key,color,
              proposed=False):
    text(696,title_y,373,27,title,20,color if proposed else INK,bold=True)
    text(1091,title_y,125,27,f'{count} levels',17,SECONDARY,align='right')
    x0,x1=718,1200
    def xp(z): return x0+(z+4.5)/9*(x1-x0)
    def yp(p): return baseline-p/.42*peak
    zs=np.linspace(-4.5,4.5,181)
    model=np.exp(-zs*zs/2)/math.sqrt(2*math.pi)
    if proposed:
        for lo,hi,fill in ((-4.5,-tau_z,COARSE_FILL),
                           (-tau_z,tau_z,FINE_FILL),
                           (tau_z,4.5,COARSE_FILL)):
            region_z=np.r_[lo,zs[(zs>lo)&(zs<hi)],hi]
            region_p=np.exp(-region_z*region_z/2)/math.sqrt(2*math.pi)
            polygon([[xp(lo),baseline]]+
                    [[xp(float(z)),yp(float(p))] for z,p in zip(region_z,region_p)]+
                    [[xp(hi),baseline]],fill)
    else:
        polygon([[xp(-4.5),baseline]]+
                [[xp(float(z)),yp(float(p))] for z,p in zip(zs,model)]+
                [[xp(4.5),baseline]],BLUE_PALE if color==BLUE else GREEN_PALE)
    group=DENSITY['groups'][sample_key]
    density=group.get('density',group.get('density_per_bin'))
    if density is None: raise KeyError(f'No density found: {list(group)}')
    assert len(density)==len(centers)
    # Put captured-data traces on top: near agreement must not hide the data.
    line([[xp(float(z)),yp(float(p))] for z,p in zip(zs,model)],INK,1.6)
    line([[xp(float(z)),yp(float(p))] for z,p in zip(centers,density)],GRAY,1.45,True)
    arrow(x0,baseline,x1+6,baseline,INK,1,4)
    actual=np.array(LEVELS[level_key]['levels_fp16'])*SCALE
    assert len(actual)==count and np.all(np.diff(actual)>0)
    if proposed:
        for z in (-tau_z,tau_z):
            line([[xp(z),baseline-peak-10],[xp(z),baseline+7]],LINE,.85,True)
        # Show one out of every eight actual levels per magnitude region,
        # reflected about zero. Neutral, separated ticks replace the dense rug.
        # The codec retains all 256 levels; only the displayed markers are subsampled.
        positive=actual[actual>0]
        shown_positive=np.concatenate([
            positive[positive<tau_z][4::8],
            positive[positive>=tau_z][4::8],
        ])
        shown=np.r_[-shown_positive[::-1],shown_positive]
        assert len(shown)==32 and np.all(np.isin(shown,actual))
        for z in shown:
            line([[xp(float(z)),baseline-3.5],[xp(float(z)),baseline+3.5]],INK,1)
        left,right=xp(-tau_z),xp(tau_z)
        for l,r,label in ((x0,left,'Coarse'),(left,right,'Fine'),(right,x1,'Coarse')):
            text(l,title_y+31,r-l,23,label,17,
                 BLUE if label=='Fine' else COARSE,align='center')
        text(920,baseline+30,18,22,'Δ',18)
        text(933,baseline+40,12,16,'0',12)
        text(950,baseline+30,20,22,'<',18)
        text(975,baseline+30,18,22,'Δ',18)
        text(988,baseline+40,12,16,'1',12)
    else:
        for z in actual:
            circle(xp(float(z)),baseline,3.1,color,'#FFFFFF',.45)
    for z in (-4,0,4):
        line([[xp(z),baseline+2],[xp(z),baseline+6]],INK,.75)
        text(xp(z)-16,baseline+8,32,18,str(z).replace('-','−'),15,
             SECONDARY,align='center')
    text(x1+8,baseline-1,16,23,'z',17,italic=True)

quantizer(89,191,53,'Lloyd–Max K4',16,'lloyd_max_k4','key_k4_middle',BLUE)
quantizer(233,342,53,'PU-K8 (ours)',256,'pu_k8','key_k8_boundary',BLUE,True)
quantizer(399,472,43,'Lloyd–Max V2',4,'lloyd_max_v2','value_all',GREEN)

def render():
    # Keep the same two-column width, with a dedicated layer-to-codec channel.
    # Liberation Sans uses Arial-compatible metrics; register installed fonts
    # explicitly so an old Matplotlib font cache cannot silently change layout.
    for font_path in font_manager.findSystemFonts():
        font_manager.fontManager.addfont(str(font_path))
    font_manager.findfont('Liberation Sans', fallback_to_default=False)
    inches=7.16
    factor=inches*72/W
    plt.rcParams.update({'font.family':'Liberation Sans','pdf.fonttype':42,'ps.fonttype':42,
                         'svg.fonttype':'none','savefig.facecolor':'white'})
    fig=plt.figure(figsize=(inches,inches*H/W))
    ax=fig.add_axes((0,0,1,1),xlim=(0,W),ylim=(H,0))
    ax.axis('off')
    for s in SCENE['shapes']:
        t=s['type']
        edge=s.get('stroke') or 'none'
        fill=s.get('fill') or 'none'
        lw=s.get('lw',1)*factor
        if t=='rect':
            ax.add_patch(Rectangle((s['x'],s['y']),s['w'],s['h'],facecolor=fill,edgecolor=edge,linewidth=lw))
        elif t=='circle':
            ax.add_patch(Circle((s['cx'],s['cy']),s['r'],facecolor=fill,edgecolor=edge,linewidth=lw))
        elif t=='polygon':
            ax.add_patch(Polygon(s['points'],closed=True,facecolor=fill,edgecolor=edge,linewidth=lw))
        elif t=='line':
            p=np.array(s['points'])
            ax.plot(p[:,0],p[:,1],color=edge,linewidth=lw,
                    linestyle=(0,(2.8,2.2)) if s.get('dash') else '-',solid_capstyle='butt',dash_capstyle='butt')
        elif t=='text':
            align=s.get('align','left')
            x=s['x']+{'left':0,'center':.5,'right':1}[align]*s['w']
            ax.text(x,s['y']+s['h']/2,s['text'],ha=align,va='center',
                    fontsize=s['size']*factor,color=s['color'],fontweight='bold' if s.get('bold') else 'normal',
                    fontstyle='italic' if s.get('italic') else 'normal',linespacing=1.2)
    for ext in ('pdf','svg','png'):
        metadata={'Creator':'Matplotlib; native editable vector diagram'}
        if ext=='pdf': metadata.update(CreationDate=None,ModDate=None)
        if ext=='svg': metadata={'Date':None,'Creator':'Native editable vector diagram'}
        fig.savefig(HERE/f'kv_cache_overview.{ext}',dpi=400,metadata=metadata)
        if ext=='svg':
            path=HERE/'kv_cache_overview.svg'
            path.write_text('\n'.join(row.rstrip() for row in path.read_text().splitlines())+'\n')
    plt.close(fig)
    write_pptx(SCENE,HERE/'kv_cache_overview.pptx')
    print('Created overview PDF / SVG / PNG / editable PPTX; codec levels: 16 / 256 / 4; PU-K8 displays 32 representative ticks.')

if __name__=='__main__':
    render()
