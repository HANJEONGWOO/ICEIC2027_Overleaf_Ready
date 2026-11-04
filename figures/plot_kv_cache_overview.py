#!/usr/bin/env python3
"""Draw the paper overview as editable, flat vector shapes.

Run: python figures/plot_kv_cache_overview.py
Requires numpy and matplotlib; the PowerPoint exporter uses only the stdlib.
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
from overview_pptx import write_pptx

HERE = Path(__file__).resolve().parent
LEVELS = json.loads((HERE / 'kv_cache_overview_levels.json').read_text())
DENSITY = json.loads((HERE / 'kv_cache_overview_density.json').read_text())
QUANTIZER_OFFSET = 32  # Reserve a visible routing channel between stages 2 and 3.
W, H = 1200 + QUANTIZER_OFFSET, 500
INK = '#253449'
SECONDARY = '#596777'
BLUE = '#3766BD'
GREEN = '#367F68'
BLUE_PALE = '#EDF3FB'
GREEN_PALE = '#EEF5F1'
LINE = '#CFD6DE'
GRAY = '#8F9BA7'
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

def heading(x, width, number, label):
    rect(x, 5, 24, 24, BLUE)
    text(x, 5, 24, 24, str(number), 16, '#FFFFFF', True, 'center')
    text(x+34, 2, width-34, 30, label, 20, bold=True)
    line([[x,40],[x+width,40]], LINE, 1)

heading(0, 288, 1, 'Asymmetric KV budget')
heading(321, 283, 2, 'Boundary allocation')
heading(638 + QUANTIZER_OFFSET, 562, 3, 'Bit-width-aware quantizer selection')
for x in (304,):
    line([[x,55],[x,233]], LINE, .8)
    line([[x,269],[x,496]], LINE, .8)
    arrow(x-10,251,x+10,251,SECONDARY,1.6,6)

# 1. Budget: a true 3:1 index-bit ratio, flat tensor slices, concise motivation.
text(0,49,288,23,'Split the index-storage budget',16,SECONDARY,align='center')
# Native text runs keep mathematical subscripts editable and avoid Unicode
# subscript-glyph substitution across Matplotlib / PowerPoint fonts.
for x,sub in ((49,'KV'),(134,'K'),(210,'V')):
    text(x,84,21,37,'B',28,italic=True)
    text(x+20,100,25,20,sub,16,italic=True)
text(98,84,28,37,'=',27,align='center')
text(174,84,24,37,'+',27,align='center')
rect(16,139,192,37,BLUE)
rect(208,139,64,37,GREEN)
text(16,139,192,37,'K: 6 bits (avg.)',17,'#FFFFFF',True,'center')
text(208,139,64,37,'V: 2',17,'#FFFFFF',True,'center')
text(0,183,288,25,'8 index bits per K/V pair on average',15,SECONDARY,align='center')
for x, label, color, pale, description, precision, detail in (
    (8,'Keys (K)',BLUE,BLUE_PALE,'Attention\nweights','K4 / K8','6 bits on average'),
    (153,'Values (V)',GREEN,GREEN_PALE,'Weighted\nsum','V2','2 bits per value'),
):
    rect(x,228,127,235,'#FFFFFF',LINE,1)
    rect(x,228,127,33,pale)
    rect(x,228,3,33,color)
    text(x+5,229,117,31,label,18,color,True,'center')
    text(x+6,269,115,43,description,16,align='center')
    # Each outline is a KV-head slice, rather than a shaded 3-D object.
    for offset in (8,4,0):
        rect(x+19+offset,332-offset,80,56,'#FFFFFF',color,.8)
    rect(x+19,332,80,56,pale,color,.9)
    for i in range(1,6): line([[x+19+i*80/6,332],[x+19+i*80/6,388]],color,.55)
    for i in range(1,4): line([[x+19,332+i*14],[x+99,332+i*14]],color,.55)
    text(x+25,394,55,22,'T × d',15,SECONDARY,italic=True)
    text(x+63,403,35,17,'head',10,SECONDARY,italic=True)
    text(x+4,420,119,23,precision,20,color,True,'center')
    text(x+3,445,121,16,detail,13.5,SECONDARY,align='center')
text(0,475,288,21,'One matrix per KV head',15,SECONDARY,align='center')

# 2. Group exact layer ranges without pretending a group is a single layer.
text(321,49,283,23,'28-layer Qwen3-1.7B',16,SECONDARY,align='center')
for top, layers, precision, color, pale in (
    (96,'Layers 1–7','K8 / V2',BLUE,BLUE_PALE),
    (221,'Layers 8–21','K4 / V2',SECONDARY,'#F3F5F7'),
    (346,'Layers 22–28','K8 / V2',BLUE,BLUE_PALE),
):
    rect(339,top,247,100,pale,LINE,1)
    rect(339,top,4,100,color)
    text(350,top+6,225,26,layers,18,bold=True,align='center')
    rect(353,top+38,144,25,'#FFFFFF',LINE,.8)
    rect(502,top+38,70,25,'#FFFFFF',LINE,.8)
    text(353,top+38,144,25,'Self-attention',15,align='center')
    text(502,top+38,70,25,'FFN',15,align='center')
    # Explicit K output ports make the per-layer codec choice visible.
    # V2 is fixed independently of the K4/K8 assignment.
    text(353,top+70,135,25,'Values: V2',15,GREEN)
    rect(510,top+70,62,25,'#FFFFFF',color,1)
    text(510,top+70,62,25,precision.split(' / ')[0],19,color,True,'center')
for a,b in ((199,216),(324,341)): arrow(462.5,a,462.5,b,GRAY,1.5,5)
text(321,463,283,22,'K8: 14 layers  ·  K4: 14 layers',15.5,align='center')
text(321,484,283,16,'V2 in every layer',14,SECONDARY,align='center')

# Fixed selection routes, not tensor flow between quantizers.  The neutral K4
# route stays left of the blue K8 bus so that only one crossover is required.
# Its white break denotes no connection; the only dot is the true K8 merge.
k4_lane, k8_lane = 608, 641
k4_target, k8_target = 97, 228
target_x = 638 + QUANTIZER_OFFSET
line([[572,303.5],[k4_lane,303.5],[k4_lane,k4_target]],SECONDARY,1.8)
arrow(k4_lane,k4_target,target_x,k4_target,SECONDARY,1.8,5.5)
for source_y in (178.5,428.5):
    # The white underlay also opens a clean output port in the layer-group box.
    line([[572,source_y],[k8_lane,source_y]],'#FFFFFF',5.5)
    line([[572,source_y],[k8_lane,source_y]],BLUE,2)
line([[k8_lane,178.5],[k8_lane,428.5]],BLUE,2)
circle(k8_lane,k8_target,3,BLUE)
arrow(k8_lane,k8_target,target_x,k8_target,BLUE,2,5.5)

# 3. Exact FP16 levels plus modeled / sampled distributions on a common axis.
stage3_shape_start = len(SCENE['shapes'])
line([[648,62],[675,62]],INK,1.7)
text(681,49,145,25,'Gaussian model',14,SECONDARY)
line([[835,62],[862,62]],GRAY,1.3,True)
text(868,49,125,25,'KV samples',14,SECONDARY)
circle(1025,62,2.5,BLUE)
text(1036,49,155,25,'Reconstruction levels',14,SECONDARY)

SCALE = math.sqrt(LEVELS['distribution']['d'])
assert LEVELS['distribution']['d'] == DENSITY['head_dim'] == 128
bins = np.array(DENSITY['bin_edges'])
centers = (bins[:-1] + bins[1:]) / 2
tau = LEVELS['pu_k8']['tau']
tau_z = tau*SCALE

def quantizer(top, height, title, count, level_key, sample_key, color, baseline, peak,
              action, proposed=False):
    rect(638,top,562,height,'#FFFFFF',LINE,1)
    rect(638,top,562,30,BLUE_PALE if proposed else '#F3F5F7')
    if proposed: rect(638,top,4,height,BLUE)
    text(650,top+2,395,27,title,18.5,color if proposed else INK,True)
    text(1053,top+2,133,27,f'{count} levels',14.5,SECONDARY,align='right')
    x0,x1=656,1007
    def xp(z): return x0+(z+4.5)/9*(x1-x0)
    def yp(p): return baseline-p/.42*peak
    zs=np.linspace(-4.5,4.5,181)
    model=np.exp(-zs*zs/2)/math.sqrt(2*math.pi)
    polygon([[xp(-4.5),baseline]]+[[xp(float(z)),yp(float(p))] for z,p in zip(zs,model)]+[[xp(4.5),baseline]],
            BLUE_PALE if color==BLUE else GREEN_PALE)
    group=DENSITY['groups'][sample_key]
    density=group.get('density',group.get('density_per_bin'))
    if density is None: raise KeyError(f'No density found: {list(group)}')
    assert len(density)==len(centers)
    line([[xp(float(z)),yp(float(p))] for z,p in zip(centers,density)],GRAY,1.3,True)
    line([[xp(float(z)),yp(float(p))] for z,p in zip(zs,model)],INK,1.7)
    line([[x0,baseline],[x1+5,baseline]],SECONDARY,.8)
    polygon([[x1+7,baseline],[x1+2,baseline-2],[x1+2,baseline+2]],SECONDARY)
    actual=np.array(LEVELS[level_key]['levels_fp16'])*SCALE
    assert len(actual)==count and np.all(np.diff(actual)>0)
    if proposed:
        # Every one of the 256 levels is rendered: no decorative subsampling.
        for z in actual:
            inner=abs(z)<tau_z
            line([[xp(float(z)),baseline-3.7],[xp(float(z)),baseline+4.5]],BLUE if inner else '#6E85A5',.55)
        for z in (-tau_z,tau_z):
            line([[xp(z),top+53],[xp(z),baseline+6]],'#94A6BE',.8,True)
        left, right=xp(-tau_z),xp(tau_z)
        for l,r,label in ((x0,left,'Coarse'),(left,right,'Fine'),(right,x1,'Coarse')):
            text(l,top+32,r-l,23,label,13.5,BLUE if label=='Fine' else SECONDARY,
                 label=='Fine','center')
        text(x0,baseline+22,x1-x0,19,'Two spacings: Δ₀ < Δ₁',14,SECONDARY,align='center')
    else:
        for z in actual: circle(xp(float(z)),baseline,2.5,color,'#FFFFFF',.45)
    for z in (-4,0,4):
        line([[xp(z),baseline+1],[xp(z),baseline+4]],SECONDARY,.6)
        text(xp(z)-13,baseline+5,26,16,str(z).replace('-','−'),12.5,SECONDARY,align='center')
    text(x1+7,baseline+1,16,18,'z',14,SECONDARY,italic=True)
    ybox=top+42
    rect(1033,ybox,152,62,'#F7F9FB',LINE,.8)
    text(1038,ybox+4,142,54,action,16,align='center')
    if proposed:
        text(1029,top+112,161,26,'ℓ⁺ = aᵣ + kΔᵣ',20,BLUE,align='center')
        text(1029,top+140,161,16,'Arithmetic reconstruction',12.5,SECONDARY,align='center')

quantizer(82,120,'K4 · Lloyd–Max',16,'lloyd_max_k4','key_k4_middle',BLUE,177,48,
          'Threshold indexing\n+ level lookup')
quantizer(213,162,'K8 · PU-K8 (ours)',256,'pu_k8','key_k8_boundary',BLUE,326,54,
          'Arithmetic indexing\n+ HVX decoding',True)
quantizer(386,114,'V2 · Lloyd–Max',4,'lloyd_max_v2','value_all',GREEN,477,44,
          'Threshold indexing\n+ level lookup')

# Translate stage 3 as one unit: plotted distributions, level spacing, labels,
# and all internal proportions remain unchanged.
for shape in SCENE['shapes'][stage3_shape_start:]:
    if 'x' in shape:
        shape['x'] += QUANTIZER_OFFSET
    if 'cx' in shape:
        shape['cx'] += QUANTIZER_OFFSET
    if 'points' in shape:
        shape['points'] = [[x + QUANTIZER_OFFSET, y] for x, y in shape['points']]

def render():
    # Keep the same two-column width, with a dedicated layer-to-codec channel.
    inches=7.16
    factor=inches*72/W
    plt.rcParams.update({'font.family':'Lato','pdf.fonttype':42,'ps.fonttype':42,
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
    plt.close(fig)
    write_pptx(SCENE,HERE/'kv_cache_overview.pptx')
    print('Created overview PDF / SVG / PNG / editable PPTX; exact levels: 16 / 256 / 4.')

if __name__=='__main__':
    render()
