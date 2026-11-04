"""Reproduce overview diagnostics from existing HTP KV captures; no inference.
Use existing CPU FP16-operation emulator for normalized/rotated coordinates,
as select_mixed_layers.py and evaluate_structured_k8_quality.py do. This is
not a claim that CPU reductions reproduce every HTP arithmetic bit.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
import torch
p=argparse.ArgumentParser()
p.add_argument('--repo',type=Path,default=Path('/home/hjw/git/ai-hub-models'))
p.add_argument('--captures',type=Path,default=Path('/mnt/d/ai-hub-models/binaries/turboquant/k_rotation_quality_20261006'))
p.add_argument('--out',type=Path,default=Path(__file__).resolve().parent / 'kv_cache_overview_density.json')
a=p.parse_args();sys.path.insert(0,str(a.repo/'src'))
from qai_hub_models.models.templates.llm.turboquant.reference import DenseQRRotation
from qai_hub_models.models.templates.llm.turboquant.config import get_profile

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rounded(t): return t.half().float()
torch.set_num_threads(4)
profile=get_profile('mixed_k6_v2_boundary_lm8_converged')
assert profile.block_size==128 and profile.rotation.value=='dense_qr'
assert (profile.key.seed,profile.value.seed)==(42,542)
manifest=json.loads((a.captures/'samples/manifest.json').read_text())
for name,key in [('data_manifest.json','data_manifest_sha256'),('capture_identity.json','capture_identity_sha256')]:
 assert digest(a.captures/name)==manifest[key]
meta=json.loads((a.captures/'data_manifest.json').read_text())
bins=np.linspace(-4.5,4.5,145)
positions=np.arange(31,1024,32)
groups={name:{'count':0,'hist_counts':np.zeros(144,dtype=np.int64),'raw_moment_sums':np.zeros(4),'min':float('inf'),'max':-float('inf'),'outside_count':0} for name in ['key_all','key_k4_middle','key_k8_boundary','value_all']}
matrices={key:rounded(torch.tensor(DenseQRRotation(seed,128).matrix().astype(np.float32))) for key,seed in [('k',42),('v',542)]}
records=[]
capture_reports=[]
for doc in [0,1]:
 report_path=a.captures/'reports'/f'validation_{doc}_capture.json'
 report=json.loads(report_path.read_text())
 assert report['context_length']==1024 and report['prompt_tokens']==1024 and report['scored_tokens']==1023
 capture_reports.append({'file':str(report_path.relative_to(a.captures)),'sha256':digest(report_path),'context_length':1024,'prompt_tokens':1024,'scored_tokens':1023})
 for layer in range(28):
  name=f'validation_{doc}_layer{layer:02d}.npz';path=a.captures/'samples'/name
  sha=digest(path);assert sha==manifest['sha256'][name]
  records.append({'file':name,'sha256':sha})
  with np.load(path) as data:
   for kind in ['k','v']:
    x=torch.tensor(data[kind][:,positions,:].astype(np.float32));assert tuple(x.shape)==(8,32,128)
    magnitude=x.abs().amax(-1,keepdim=True)
    pre=torch.where(magnitude>256,1/256,1.)
    maxpre=rounded(magnitude*pre)
    scaled=rounded(rounded(x*pre)/torch.where(maxpre>0,maxpre,1.))
    length=rounded(torch.sqrt(rounded(rounded(scaled*scaled).sum(-1,keepdim=True))))
    unit=rounded(scaled/torch.where(length>0,length,1.))
    y=rounded(unit@matrices[kind].T).numpy().astype(np.float64).ravel()*np.sqrt(128)
    assert np.isfinite(y).all()
    h=np.histogram(y,bins=bins)[0]
    moments=np.array([np.sum(y**q) for q in [1,2,3,4]])
    targets=['value_all'] if kind=='v' else ['key_all','key_k8_boundary' if layer<7 or layer>=21 else 'key_k4_middle']
    for target in targets:
     g=groups[target];g['count']+=y.size;g['hist_counts']+=h;g['raw_moment_sums']+=moments
     g['min']=min(g['min'],float(y.min()));g['max']=max(g['max'],float(y.max()));g['outside_count']+=int(y.size-h.sum())
for g in groups.values():
 m1,m2,m3,m4=g.pop('raw_moment_sums')/g['count'];v=m2-m1*m1
 g['mean']=float(m1);g['std']=float(np.sqrt(v));g['skewness']=float((m3-3*m1*m2+2*m1**3)/v**1.5)
 g['kurtosis']=float((m4-4*m1*m3+6*m1*m1*m2-3*m1**4)/v**2)
 g['density']=(g['hist_counts']/(g['count']*np.diff(bins))).tolist();g['hist_counts']=g['hist_counts'].tolist()
out={'description':'Observed Qwen3-1.7B KV captures transformed offline with existing FP16 normalization and fixed rotation emulator; not new device evaluation or coefficient fitting.','capture_source':str(a.captures),'capture_path_claim':meta['source'],'dataset':meta['dataset'],'dataset_revision':meta['revision'],'documents':meta['windows']['validation'],'layers_zero_based':list(range(28)),'tokens_per_document':1024,'sampled_token_positions_zero_based':positions.tolist(),'sampled_tokens_per_document_per_layer':32,'coordinate':'z=sqrt(128)*y, with y the normalized rotated coordinate','kv_heads':8,'head_dim':128,'rotation':'dense_qr','rotation_seeds':{'key':42,'value':542},'normalization':'FP16 operation-boundary emulator copied from select_mixed_layers.py; FP32 reductions and matrix multiplication between casts; no HTP bit-exact claim','gaussian_model':{'coordinate':'z','mean':0.,'variance':1.,'sigma':1.,'original_y_variance':1/128},'source_manifest_sha256':digest(a.captures/'samples/manifest.json'),'source_data_manifest_sha256':digest(a.captures/'data_manifest.json'),'source_capture_identity_sha256':digest(a.captures/'capture_identity.json'),'rotation_fp16_sha256':{k:hashlib.sha256(m.numpy().astype('<f2').tobytes()).hexdigest() for k,m in matrices.items()},'source_code_sha256':{str(p.relative_to(a.repo)):digest(p) for p in [a.repo/'src/qai_hub_models/models/templates/llm/turboquant/reference.py',a.repo/'scripts/llm/turboquant/select_mixed_layers.py',a.repo/'scripts/llm/turboquant/evaluate_structured_k8_quality.py']},'bin_edges':bins.tolist(),'groups':groups,'sample_files':records,'capture_reports':capture_reports,'padding_check':'Each source capture report records all 1,024 prompt tokens; sampled positions 31,63,...,1023 are valid tokens, not padded slots.'}
a.out.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:{i:g[i] for i in ['count','mean','std','skewness','kurtosis','min','max','outside_count']} for k,g in groups.items()},indent=2))
print(a.out)
