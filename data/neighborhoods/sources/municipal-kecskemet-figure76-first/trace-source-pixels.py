#!/usr/bin/env python3
"""Literal source-black 8-neighbor traces for Figure 76; no georeference.

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
SOURCE=OUT/'figure76-p161-xref184.jpeg'
SHA='9afccf14486eb5ed86581d07f9a588da4b53df6fa0c47cdbcaf6f667659055cd'
LIMIT=45
PAD=14
A=(41,895);B=(595,928);C=(691,623);D=(1364,446);E=(1338,719)
SECTIONS={
 'AB':[A,(62,924),(78,945),(96,961),(120,975),(145,984),(177,993),(210,1005),(246,1026),(306,1009),(370,990),(432,973),(500,955),(550,941),B],
 'BC':[B,(615,866),(632,807),(649,747),(668,689),C],
 'CA':[C,(654,602),(625,578),(591,548),(551,509),(526,512),(490,533),(448,561),(406,591),(367,619),(340,646),(326,683),(312,728),(300,765),(283,778),(252,781),(217,786),(183,808),(142,832),(103,855),(69,878),A],
 'CD':[C,(719,630),(751,632),(782,630),(815,623),(855,608),(904,587),(956,565),(1009,540),(1060,517),(1112,492),(1166,469),(1215,447),(1255,428),(1295,411),(1310,420),(1326,434),(1342,441),D],
 'DE':[D,(1351,487),(1337,526),(1325,561),(1322,601),(1322,645),(1323,687),E],
 'EB':[E,(1278,737),(1217,754),(1153,772),(1087,791),(1023,809),(957,827),(891,846),(827,864),(762,882),(697,900),(645,915),B],
 'D_OUT_E':[D,(1381,404),(1424,419),(1470,435),(1517,452),(1560,469),(1606,486),(1646,502),(1683,520),(1681,540),(1676,560),(1668,580),(1653,600),(1638,620),(1610,640),(1589,650),(1543,661),(1493,677),(1444,690),(1393,705),E],
}
RING_SECTIONS={'Külső Árpádváros':[('AB',False),('BC',False),('CA',False)],
               'Mezeiváros':[('CD',False),('DE',False),('EB',False),('BC',False)],
               'Ürgés':[('D_OUT_E',False),('DE',True)]}


def encode(value):return (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()


def main(check):
    import numpy as np
    from PIL import Image,ImageDraw
    from shapely.geometry import Polygon
    from shapely.validation import explain_validity
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=SHA:raise ValueError('Original source JPEG changed')
    source=Image.open(SOURCE).convert('RGB');rgb=np.asarray(source);value=rgb.max(axis=2);height,width=value.shape
    if (width,height)!=(1702,1204):raise ValueError('Source size changed')
    allowed=value<=LIMIT;snaps={}
    def snap(seed):
        if seed in snaps:return snaps[seed]
        x,y=seed;choices=[]
        for yy in range(max(0,y-8),min(height,y+9)):
            for xx in range(max(0,x-8),min(width,x+9)):
                if allowed[yy,xx]:choices.append(((xx-x)**2+(yy-y)**2+float(value[yy,xx])*.02,(xx,yy)))
        if not choices:raise ValueError('No actual black source pixel near seed '+str(seed))
        result=min(choices)[1];snaps[seed]=result;return result
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
      'source-pixel-rings.json':{'schemaVersion':1,'coordinateSystem':'Original embedded JPEG image pixel centers; x right/y down. These are NOT geographic coordinates.','sourceImage':SOURCE.name,'sourceImageSha256':SHA,'sourceImageSize':[width,height],'blackThresholdMaxRgb':LIMIT,'manualSeedCorridorPadPixels':PAD,'manualSeeds':SECTIONS,'actualSourcePixelSnaps':[{'manualSeed':a,'sourcePixel':b}for a,b in snaps.items()],'sharedSourcePaths':paths,'ringSourceSections':RING_SECTIONS,'rings':rings},
      'proof.json':{'schemaVersion':1,'sourceFigure':76,'sourcePdfPageOneBased':161,'printedPage':159,'sourceImageSha256':SHA,
                    'method':'Manual source-stroke seeds guide bounded Dijkstra traversal on literal maxRGB<=45 JPEG pixels. Every dense edge is an 8-neighbor source-pixel step; shared dividers are reused exactly in reverse.','records':records,'pairwisePixelInteriorOverlaps':overlaps,
                    'blueOrOtherLabelPixelWindowsAllowed':[],'allSourcePathsLiteralBlack':True,'sourceImageFrameUsedToClose':False,
                    'geometryRepairBufferSnapOrArbitraryChordUsed':False,'noteOnSeedSelection':'Snapping selects an actual nearby source pixel for a manual seed; no geographic geometry is snapped.','georeferencingPerformed':False,'absoluteAccuracyMeters':None,'usableForAddressAssignment':False,
                    'independentReviewStillRequired':True}}
    for filename,result in results.items():
        data=encode(result);p=OUT/filename
        if check:
            if not p.exists()or p.read_bytes()!=data:raise ValueError('Stale or missing artifact '+filename)
        else:p.write_bytes(data)
    if not check:
        preview=source.copy();draw=ImageDraw.Draw(preview)
        for color,(name,points)in zip(['#ff4444','#ffff00','#00ffff'],rings.items()):draw.line(points,fill=color,width=2)
        preview.save(OUT/'preview.png')
    print(json.dumps({'mode':'check'if check else'build','sourceOnlyFineCellCount':3,'records':records},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');main(p.parse_args().check)
