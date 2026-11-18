#!/usr/bin/env python3
"""Literal source-black 8-neighbor traces for Figure 78; no georeference.

Manual seeds select the municipal printed contour. Dijkstra paths follow only
actual original-JPEG pixels maxRGB<=45 inside narrow seed-guided corridors.
Shared source sections are traced once and reused exactly in reverse. There
are no allowed label crossings, gap bridges, frame edges, buffer or repair.
"""
import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
import sys
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
SOURCE=OUT/'figure78-p166-xref204.jpeg'
SHA='63a05d0c439ef62c8feea3ca0347f7d944b98676c030960a38ccd4a9788870fd'
LIMIT=45
PAD=14
A=(14,500);B=(427,441);C=(289,668);D=(185,757)
E=(638,382);F=(1298,300);G=(895,635);H=(1564,568);I=(1502,666);J=(1264,1057);L=(895,683)
SECTIONS={
 'AB':[A,(63,489),(120,473),(183,456),(246,451),(306,448),(366,444),B],
 'BC':[B,(428,484),(425,529),(414,563),(399,590),(378,613),(347,630),(318,649),C],
 'CD':[C,(263,689),(239,710),(212,734),D],
 'DA':[D,(165,728),(141,690),(114,648),(88,607),(62,566),(37,525),A],
 'BE':[B,(480,437),(531,424),(583,403),E],
 'EG':[E,(649,409),(669,441),(696,477),(727,510),(764,543),(805,578),(847,612),G],
 'GL':[G,(917,643),(906,663),L],
 'LC':[L,(870,731),(846,776),(821,825),(796,874),(755,856),(714,836),(680,888),(648,867),(620,848),(599,832),(571,811),(544,787),(504,830),(468,803),(440,778),(414,752),(397,740),(381,691),(373,678),(352,692),(335,699),(319,682),C],
 'EF':[E,(710,355),(778,345),(846,338),(911,329),(975,304),(1029,270),(1078,231),(1126,193),(1164,167),(1197,149),(1221,187),(1246,230),(1230,244),(1226,248),(1245,266),(1272,283),F],
 'FG':[F,(1248,326),(1197,364),(1148,404),(1097,446),(1047,488),(997,531),(946,578),G],
 'FH':[F,(1343,346),(1387,391),(1431,435),(1476,480),(1520,524),H],
 'HI':[H,(1542,608),(1520,636),I],
 'IJ':[I,(1477,716),(1446,763),(1415,811),(1384,859),(1353,906),(1323,955),(1293,1003),J],
 'JL':[J,(1214,1006),(1164,954),(1115,903),(1066,852),(1016,802),(965,750),(917,704),L],
}
RING_SECTIONS={'Alsócsalános':[('AB',False),('BC',False),('CD',False),('DA',False)],
               'Homokbánya':[('BE',False),('EG',False),('GL',False),('LC',False),('BC',True)],
               'Alsószéktó':[('EF',False),('FG',False),('EG',True)],
               'Szeleifalu':[('FH',False),('HI',False),('IJ',False),('JL',False),('GL',True),('FG',True)]}


def encode(value):return (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()


def main(check):
    import numpy as np
    from PIL import Image,ImageDraw
    from shapely.geometry import Polygon
    from shapely.validation import explain_validity
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=SHA:raise ValueError('Original source JPEG changed')
    source=Image.open(SOURCE).convert('RGB');rgb=np.asarray(source);value=rgb.max(axis=2);height,width=value.shape
    if (width,height)!=(1698,1202):raise ValueError('Source size changed')
    allowed=value<=LIMIT;snaps={}
    def snap(seed):
        if seed in snaps:return snaps[seed]
        x,y=seed;choices=[]
        for yy in range(max(0,y-8),min(height,y+9)):
            for xx in range(max(0,x-8),min(width,x+9)):
                if allowed[yy,xx]:choices.append(((xx-x)**2+(yy-y)**2+float(value[yy,xx])*.02,(xx,yy)))
        if not choices:raise ValueError('No actual black source pixel near seed '+str(seed))
        result=min(choices)[1];snaps[seed]=result;return result
    start=snap(A);component={start};todo=[start]
    while todo:
        x,y=todo.pop()
        for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
            point=x+dx,y+dy
            if 0<=point[0]<width and 0<=point[1]<height and allowed[point[1],point[0]]and point not in component:
                component.add(point);todo.append(point)
    allowed=np.zeros_like(allowed)
    for x,y in component:allowed[y,x]=True
    snaps={}
    def distance(p,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
        if not den:return math.dist(p,a)
        t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den))
        return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
    def route(a,b):
        lo=(max(0,min(a[0],b[0])-PAD),max(0,min(a[1],b[1])-PAD))
        hi=(min(width-1,max(a[0],b[0])+PAD),min(height-1,max(a[1],b[1])+PAD))
        best={a:0};back={};todo=[(0,a)]
        while todo:
            score,u=heapq.heappop(todo)
            if score!=best[u]:continue
            if u==b:break
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                v=(u[0]+dx,u[1]+dy)
                if not(lo[0]<=v[0]<=hi[0]and lo[1]<=v[1]<=hi[1])or not allowed[v[1],v[0]]:continue
                off=distance(v,a,b)
                if off>PAD:continue
                new=score+math.hypot(dx,dy)*(1+float(value[v[1],v[0]])*.04)+off*off*.001
                if new<best.get(v,float('inf')):best[v]=new;back[v]=u;heapq.heappush(todo,(new,v))
        if b not in best:raise ValueError('Actual black source path disconnected '+str((a,b)))
        points=[b]
        while points[-1]!=a:points.append(back[points[-1]])
        return points[::-1]
    paths={}
    for key,seeds in SECTIONS.items():
        result=[]
        for a,b in zip(seeds,seeds[1:]):
            part=route(snap(a),snap(b));result.extend(part if not result else part[1:])
        paths[key]=result
        print(key,len(result))
    rings={};polygons={};records=[]
    for name,sections in RING_SECTIONS.items():
        points=[]
        for key,reverse in sections:
            section=paths[key][::-1]if reverse else paths[key]
            if points and points[-1]!=section[0]:raise ValueError('Original source sections do not connect')
            points.extend(section if not points else section[1:])
        if points[0]!=points[-1]:raise ValueError('Open original source circuit')
        if any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(points,points[1:])):raise ValueError('Non-neighbor source edge')
        if any(not allowed[y,x]for x,y in points):raise ValueError('Nonblack source vertex')
        poly=Polygon(points)
        if not poly.is_valid:raise ValueError(name+': '+explain_validity(poly))
        rings[name]=points;polygons[name]=poly
        records.append({'name':name,'denseSourceVertexCountIncludingClosure':len(points),'closed':True,
                        'valid':True,'interiorRingCount':len(poly.interiors),'sourcePixelArea':poly.area,
                        'sourcePixelBounds':list(poly.bounds),'allVerticesActualSourceBlackPixels':True,
                        'maximumMaxRgbOnTrace':max(int(value[y,x])for x,y in points),
                        'everyStep8Neighbor':True,'minimumDistanceToImageFramePixels':min(min(x,y,width-1-x,height-1-y)for x,y in points),
                        'addedClosureOrBridgeEdgeCount':0,'georeferencingPerformed':False})
    overlaps=[]
    for i,a in enumerate(polygons):
        for b in list(polygons)[i+1:]:
            area=polygons[a].intersection(polygons[b]).area
            if area!=0:raise ValueError('Pixel cell interiors overlap')
            overlaps.append({'a':a,'b':b,'intersectionAreaPixelsSquared':area})
    results={
      'source-pixel-rings.json':{'schemaVersion':1,'coordinateSystem':'Original embedded JPEG image pixel centers; x right/y down. These are NOT geographic coordinates.','sourceImage':SOURCE.name,'sourceImageSha256':SHA,'sourceImageSize':[width,height],'blackThresholdMaxRgb':LIMIT,'manualSeedCorridorPadPixels':PAD,'literalBlackComponentPixelCount':len(component),'manualSeeds':SECTIONS,'actualSourcePixelSnaps':[{'manualSeed':a,'sourcePixel':b}for a,b in snaps.items()],'sharedSourcePaths':paths,'ringSourceSections':RING_SECTIONS,'rings':rings},
      'proof.json':{'schemaVersion':1,'sourceFigure':78,'sourcePdfPageOneBased':166,'printedPage':164,'sourceImageSha256':SHA,
                    'method':'Manual source-stroke seeds guide bounded Dijkstra traversal on literal maxRGB<=45 JPEG pixels. Every dense edge is an 8-neighbor source-pixel step; shared dividers are reused exactly in reverse.','records':records,'pairwisePixelInteriorOverlaps':overlaps,
                    'blueOrOtherLabelPixelWindowsAllowed':[],'blackComponentSelectionAddsPixelsOrClosesGaps':False,'allSourcePathsLiteralBlack':True,'sourceImageFrameUsedToClose':False,
                    'geometryRepairBufferSnapOrArbitraryChordUsed':False,'noteOnSeedSelection':'Snapping selects an actual nearby source pixel for a manual seed; no geographic geometry is snapped.','georeferencingPerformed':False,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,
                    'independentReviewStillRequired':True}}
    for filename,result in results.items():
        data=encode(result);p=OUT/filename
        if check:
            if not p.exists()or p.read_bytes()!=data:raise ValueError('Stale or missing artifact '+filename)
        else:p.write_bytes(data)
    if not check:
        preview=source.copy();draw=ImageDraw.Draw(preview)
        for color,(name,points)in zip(['#ff4444','#ffff00','#00ffff','#ff55ff'],rings.items()):draw.line(points,fill=color,width=2)
        preview.save(OUT/'preview.png')
    print(json.dumps({'mode':'check'if check else'build','sourceOnlyFineCellCount':len(rings),'records':records},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');main(p.parse_args().check)
