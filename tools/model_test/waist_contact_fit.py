"""Radial contact fit for closed waist rings; Blender-only geometry adapter.

The contact surface and front relief have separate budgets. This is geometric
classification, not semantic pouch segmentation or a skinning solution.
"""
import math
from mathutils import Vector


def sampled_containment(points, bvh, height, limit=1024):
    """Three-direction parity checks; uncertain votes fail closed, not pass."""
    if not points:
        raise ValueError('No containment samples')
    stride=max(1,len(points)//limit)
    samples=points[::stride][:limit]
    directions=[Vector(v).normalized() for v in [(1,.173,.317),(.237,1,.419),(.371,.293,1)]]
    inside=ambiguous=0
    # Must exceed the BVH construction epsilon (1e-6 world units) and float32
    # ray-origin error, otherwise the same triangle is counted repeatedly.
    epsilon=max(height*1e-5, 1e-5)
    for point in samples:
        votes=[]
        for direction in directions:
            origin=point.copy()
            count=0
            for _ in range(64):
                hit,_,_,_=bvh.ray_cast(origin,direction,height*4)
                if hit is None:
                    break
                count+=1
                origin=hit+direction*epsilon
            else:
                count=-1
            votes.append(None if count<0 else bool(count%2))
        if None in votes or len(set(votes))>1:
            ambiguous+=1
        elif votes[0]:
            inside+=1
    return {'sample_count':len(samples),'inside_count':inside,'ambiguous_count':ambiguous,
            'pass':inside==0 and ambiguous==0,'scope':'sampled_not_exhaustive'}


def fit_contact(objects, actor_bvh, accessory_bvh, center, height, clearance):
    bins=360
    inner=[]
    body=[]
    for i in range(bins):
        angle=math.tau*i/bins
        direction=Vector((math.cos(angle),math.sin(angle),0))
        _,_,_,belt_r=accessory_bvh.ray_cast(center,direction,height)
        _,_,_,body_r=actor_bvh.ray_cast(center,direction,height)
        if belt_r is None or body_r is None:
            raise ValueError('Contact fitting requires complete body and belt rings at waist height')
        inner.append(belt_r)
        body.append(body_r)
    # The whole part receives the same angular translation field, retaining
    # radial thickness and existing generated detail rather than flattening it.
    offsets=[b+clearance-a for a,b in zip(inner,body)]
    smoothed=[sum(offsets[(i+j)%bins] for j in range(-2,3))/5 for i in range(bins)]
    if max(abs(x) for x in smoothed)>.06*height:
        raise ValueError('Contact displacement exceeds 6% actor-height budget')
    max_move=0
    for obj in objects:
        for vertex in obj.data.vertices:
            p=obj.matrix_world@vertex.co
            radial=Vector((p.x-center.x,p.y-center.y,0))
            if radial.length<1e-8:
                raise ValueError('Accessory vertex lies on waist axis')
            angle=math.atan2(radial.y,radial.x)%math.tau
            index=angle/math.tau*bins
            i=int(index)%bins
            weight=index-int(index)
            move=smoothed[i]*(1-weight)+smoothed[(i+1)%bins]*weight
            vertex.co += radial.normalized()*move
            max_move=max(max_move,abs(move))
    return {'mode':'bidirectional_radial_contact','angular_bins':bins,
            'max_displacement_h':max_move/height,'source_inner_radius_h':[r/height for r in inner],
            'target_body_radius_h':[r/height for r in body]}


def audit_contact(objects, actor_bvh, accessory_bvh, center, height, low, high):
    gaps=[]
    missing=0
    for i in range(360):
        direction=Vector((math.cos(math.tau*i/360),math.sin(math.tau*i/360),0))
        _,_,_,a=actor_bvh.ray_cast(center,direction,height)
        _,_,_,b=accessory_bvh.ray_cast(center,direction,height)
        if a is None or b is None:
            missing+=1
        else:
            gaps.append((b-a)/height)
    outside=0
    max_relief=0
    unresolved=0
    for obj in objects:
        for vertex in obj.data.vertices:
            p=obj.matrix_world@vertex.co
            radial=Vector((p.x-center.x,p.y-center.y,0))
            direction=radial.normalized()
            origin=Vector((center.x,center.y,p.z))
            _,_,_,r=actor_bvh.ray_cast(origin,direction,height)
            if r is None:
                unresolved+=1
                continue
            relief=(radial.length-r)/height
            max_relief=max(max_relief,relief)
            # Existing sides/back/height remain bounded. Only the front-facing
            # relief is evaluated against a separate body-relative budget.
            front=direction.y < -.25
            bounded=(low.x-1e-5<=p.x<=high.x+1e-5 and low.z-1e-5<=p.z<=high.z+1e-5
                     and p.y<=high.y+1e-5 and (front or p.y>=low.y-1e-5))
            if not bounded or relief > (.065 if front else .03) or relief < 0:
                outside+=1
    gates={'contact_ring_complete':missing==0,
           'contact_gap_bounded':bool(gaps) and min(gaps)>=.003 and max(gaps)<=.015,
           'separate_relief_budget':outside==0 and unresolved==0}
    return {'gates':gates,'contact_gap_h_min':min(gaps) if gaps else None,
            'contact_gap_h_max':max(gaps) if gaps else None,'max_relief_h':max_relief,
            'violating_vertices':outside,'unresolved_body_rays':unresolved,
            'policy':{'contact_gap_h':[.003,.015],'front_relief_max_h':.065,'other_relief_max_h':.03,
                      'classification':'geometric_front_relief_not_semantic_pouch','animation_approved':False}}
