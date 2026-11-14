#!/usr/bin/env python3
"""Literal Figure 73 black source-pixel contours for two missing quarters."""
import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
import sys
sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent
SOURCE = P / 'figure73-p143-xref172.jpeg'
SOURCE_SHA = '59cbd060c8010a396511cdec69848410b4fee8d6bd8e628500894b5e27565e9c'
LIMIT = 45
PAD = 14
A=(400,984); B=(275,861); C=(112,1040); D=(435,1232); F=(520,973); G=(609,1152)
SECTIONS = {
 'AB':[A,(386,974),(363,958),(338,936),(313,912),(292,887),B],
 'BC':[B,(249,885),(223,913),(202,939),(182,964),(160,993),(136,1023),C],
 'CD':[C,(133,1066),(158,1092),(187,1120),(219,1149),(247,1174),(275,1197),
       (303,1215),(332,1229),(361,1237),(388,1241),(414,1240),D],
 'DA':[D,(431,1216),(426,1202),(429,1178),(430,1158),(410,1158),(390,1158),
       (380,1155),(376,1147),(376,1120),(378,1096),(377,1089),(379,1065),
       (383,1041),(391,1031),(386,1025),(378,1021),(382,1014),(378,1011),
       (386,994),(389,988),A],
 'AF':[A,(419,991),(440,987),(463,981),(481,975),(499,970),F],
 'FG':[F,(522,1000),(528,1032),(538,1057),(546,1071),(560,1083),(576,1098),
       (587,1117),(597,1138),G],
 'GD':[G,(582,1163),(552,1176),(521,1189),(492,1201),(464,1219),D],
}

def encode(v):
    return (json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()

def build(check=False):
    import numpy as np
    from PIL import Image,ImageDraw
    from shapely.geometry import Polygon
    from shapely.validation import explain_validity
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=SOURCE_SHA:
        raise ValueError('Changed exact source JPEG')
    image=Image.open(SOURCE).convert('RGB');rgb=np.asarray(image);value=rgb.max(axis=2)
    height,width=value.shape;allowed=value<=LIMIT;anchors={}
    def anchor(p):
        if p in anchors:return anchors[p]
        x,y=p;cs=[]
        for yy in range(max(0,y-9),min(height,y+10)):
            for xx in range(max(0,x-9),min(width,x+10)):
                if allowed[yy,xx]:
                    cs.append(((xx-x)**2+(yy-y)**2+float(value[yy,xx])*.01,(xx,yy)))
        if not cs:raise ValueError('No actual black source pixel near '+str(p))
        anchors[p]=min(cs)[1];return anchors[p]
    # The main printed source-boundary network is one literal 8-connected
    # black component. This discards detached photographic dark specks when
    # looking up manual anchors; it never adds or changes an allowed pixel.
    start=anchor(A);stack=[start];component={start}
    while stack:
        x,y=stack.pop()
        for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
            q=x+dx,y+dy
            if 0<=q[0]<width and 0<=q[1]<height and allowed[q[1],q[0]] and q not in component:
                component.add(q);stack.append(q)
    allowed=np.zeros_like(allowed)
    for x,y in component:allowed[y,x]=True
    anchors={}
    def off_segment(p,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
        if not den:return math.dist(p,a)
        t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den))
        return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
    def path(a,b):
        lo=(max(0,min(a[0],b[0])-PAD),max(0,min(a[1],b[1])-PAD))
        hi=(min(width-1,max(a[0],b[0])+PAD),min(height-1,max(a[1],b[1])+PAD))
        best={a:0};back={};todo=[(0,a)]
        while todo:
            cost,u=heapq.heappop(todo)
            if cost!=best[u]:continue
            if u==b:break
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                v=u[0]+dx,u[1]+dy
                if not(lo[0]<=v[0]<=hi[0] and lo[1]<=v[1]<=hi[1]) or not allowed[v[1],v[0]]:continue
                off=off_segment(v,a,b)
                if off>PAD:continue
                nc=cost+math.hypot(dx,dy)*(1+float(value[v[1],v[0]])*.04)+off*off*.001
                if nc<best.get(v,float('inf')):
                    best[v]=nc;back[v]=u;heapq.heappush(todo,(nc,v))
        if b not in best:raise ValueError('Disconnected actual source stroke '+str((a,b)))
        result=[b]
        while result[-1]!=a:result.append(back[result[-1]])
        return result[::-1]
    paths={}
    for key,seeds in SECTIONS.items():
        points=[]
        for a,b in zip(seeds,seeds[1:]):
            part=path(anchor(a),anchor(b));points+=part if not points else part[1:]
        paths[key]=points
    def joined(parts):
        result=[]
        for key,reverse in parts:
            section=paths[key][::-1] if reverse else paths[key]
            if result and result[-1]!=section[0]:raise ValueError('Disconnected original-source sections')
            result+=section if not result else section[1:]
        return result
    rings={'Árpádváros':joined([('AB',False),('BC',False),('CD',False),('DA',False)]),
           'Kossuthváros':joined([('AF',False),('FG',False),('GD',False),('DA',False)])}
    records=[]
    for name,ring in rings.items():
        polygon=Polygon(ring)
        if ring[0]!=ring[-1] or not polygon.is_valid:
            raise ValueError(name+': '+explain_validity(polygon))
        if any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(ring,ring[1:])):
            raise ValueError('Non-adjacent source-pixel trace')
        if any(not allowed[y,x] for x,y in ring):raise ValueError('Non-source pixel')
        records.append({'name':name,'denseVertexCountIncludingClosure':len(ring),
                        'areaSourcePixelsSquared':polygon.area,'originalHoleCount':len(polygon.interiors),
                        'maxRgb':max(int(value[y,x]) for x,y in ring),
                        'touchesImageFrame':any(x in(0,width-1)or y in(0,height-1)for x,y in ring)})
    result={'schemaVersion':1,'sourceImageSha256':SOURCE_SHA,'sourceImageSize':[width,height],
            'coordinateConvention':'Integer exact original-image pixel indices, x right/y down, no half-pixel offset.',
            'maxRgbThreshold':LIMIT,'sourceAnchorLookupRadiusPixels':9,'guideCorridorWidthPixels':PAD,
            'literalBlackComponentPixelCount':len(component),
            'manualGuideSeeds':SECTIONS,'actualSourceAnchors':[{'manual':a,'actualBlackSourcePixel':b}for a,b in anchors.items()],
            'sections':paths,'rings':rings,'records':records,
            'everyDenseVertexIsActualBlackSourcePixel':True,'allSuccessivePixelsAre8Neighbors':True,
            'inventedClosingEdgeFrameClosureSnapBufferRepairOrGapFillingUsed':False,
            'geometryStatus':'Closed literal-source-pixel contours. Geographic registration has not been created by this script.',
            'absoluteAccuracyMeters':None,'usableForAddressAssignment':False}
    destination=P/'source-pixel-trace.json';data=encode(result)
    if check:
        if not destination.exists() or destination.read_bytes()!=data:raise ValueError('Stale source pixel trace')
    else:
        destination.write_bytes(data);preview=image.copy();draw=ImageDraw.Draw(preview)
        for color,ring in zip(['red','yellow'],rings.values()):draw.line(ring,fill=color,width=2)
        preview.save(P/'source-pixel-preview.png')
    print(json.dumps({'mode':'check'if check else'build','records':records},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    build(parser.parse_args().check)
