#!/usr/bin/env python3
"""Figure75 Reptéri lakótelep source contour, strict-black initial attempt."""
import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
import sys
sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent
SOURCE = P / 'figure75-p158-xref180.jpeg'
SOURCE_SHA = '13c9a38ba1b554b7125064ffce3384eb813d9590b9f327a152f1da4b0de4c991'
LIMIT = 45
PAD = 14
A=(1368,184);B=(1503,180);C=(1460,252);D=(1368,248)
SECTIONS={
 'north':[A,(1400,183),(1440,182),(1470,181),B],
 'east':[B,(1494,195),(1485,212),(1473,231),C],
 'south':[C,(1430,252),(1412,249),(1390,248),D],
 'west':[D,(1368,230),(1368,220),(1368,210),(1368,198),A],
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
    component={(int(x),int(y))for y,x in np.argwhere(allowed)}
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
    rings={'Reptéri lakótelep':joined([('north',False),('east',False),('south',False),('west',False)])}
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
            'literalBlackImagePixelCount':len(component),
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
