"""Export exact deployed scalar reconstruction levels for the paper overview."""
import argparse, hashlib, importlib.util, json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path('/home/hjw/git/ai-hub-models'));p.add_argument('--out',type=Path,default=Path(__file__).resolve().parent / 'kv_cache_overview_levels.json');a=p.parse_args()
base=a.repo/'src/qai_hub_models/models/templates/llm/turboquant'
def mod(name):
 spec=importlib.util.spec_from_file_location(name,base/f'{name}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
c=mod('constants');p=mod('structured_k8')
d={'distribution':{'model':'N(0,1/128)','d':128,'sigma':float(1/np.sqrt(128)),'empirical':False},'sources':{'lloyd_max':str(base/'constants.py'),'pu_k8':str(base/'structured_k8.py')},'source_sha256':{str(f.relative_to(a.repo)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [base/'constants.py',base/'structured_k8.py',base/'native_decoder.py']},'display_coordinate':'For standard-normal display use z=sqrt(128)*y, multiplying all levels and decision edges by sqrt(128).','note':'These are decoder scalar levels before per-vector norm-correction scale. The inherited Lloyd-Max encoder uses an affine FP16 reconstruction path that can differ slightly from decoder LUT values.'}
for bits,name in [(4,'lloyd_max_k4'),(2,'lloyd_max_v2')]:
 exact=np.array([float.fromhex(h) for h in c.CODEBOOK_HEX[(bits,128)]],dtype='<f8');assert hashlib.sha256(exact.tobytes()).hexdigest()==c.CODEBOOK_SHA256[(bits,128)]
 d[name]={'levels_fp64':exact.tolist(),'levels_fp16':exact.astype(np.float16).astype(np.float64).tolist(),'encoder_midpoints_fp64':((exact[:-1]+exact[1:])/2).tolist(),'sha256_fp64':c.CODEBOOK_SHA256[(bits,128)]}
d['pu_k8']={'coefficients':dict(zip(('a0','delta0','a1','delta1'),p.coefficients().tolist())),'levels_fp16':p.codebook().tolist(),'tau':p.region_boundary(),'decision_edges':p.boundaries().tolist(),'metadata':p.metadata()}
a.out.write_text(json.dumps(d,indent=2)+'\n');print(a.out)
