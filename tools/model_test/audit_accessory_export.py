"""Compare source/export topology with exact-position normal seams welded in memory.

No coordinate rounding, mesh repair, or changes to either artifact.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh
from actor_core_offline import sha256


def inspect(path):
    mesh=trimesh.load(path,force='mesh',process=False)
    verts,inverse=np.unique(mesh.vertices,axis=0,return_inverse=True)
    welded=trimesh.Trimesh(vertices=verts,faces=inverse[mesh.faces],process=False)
    parts=welded.split(only_watertight=False)
    return {'sha256':sha256(path),'faces':len(mesh.faces),'raw_vertices':len(mesh.vertices),
            'exact_position_vertices':len(verts),'components':len(parts),
            'watertight':bool(welded.is_watertight),'winding_consistent':bool(welded.is_winding_consistent),
            'euler_number':int(welded.euler_number),
            'all_components_watertight':all(p.is_watertight for p in parts)}


def main():
    p=argparse.ArgumentParser()
    for arg in ['source','candidate','report']:
        p.add_argument('--'+arg,type=Path,required=True)
    args=p.parse_args()
    source,candidate=inspect(args.source),inspect(args.candidate)
    gates={name:source[name]==candidate[name] for name in ['faces','exact_position_vertices','components','euler_number']}
    gates.update({key:candidate[key] for key in ['watertight','winding_consistent','all_components_watertight']})
    result={'status':'pass' if all(gates.values()) else 'fail','source':source,'candidate':candidate,
            'gates':gates,'policy':'exact-position seam weld for audit only; no self-intersection or animation approval'}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
    return 0 if result['status']=='pass' else 2


if __name__=='__main__':
    raise SystemExit(main())
