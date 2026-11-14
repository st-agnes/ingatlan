#!/usr/bin/env python3
"""Literal Figure74 black source-pixel contour for Hunyadiváros proper."""
import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
import sys
sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent
SOURCE = P / 'figure74-p154-xref176.jpeg'
SOURCE_SHA = '1ecb076700d1be46f1712ca2c0ca1ed986581a99e5d5592b95b0b4511de30cd2'
LIMIT = 45
PAD = 14
A=(350,633)
SECTIONS = {
 'north-east': [A,(373,648),(400,667),(423,683),(442,697),(431,714),(423,727),(448,745),(471,762),(496,735),(523,706),(550,678),(586,641),(608,664),(631,687),(648,705),(655,700),(678,716),(700,737),(727,753),(707,780),(738,808),(769,838),(802,867),(826,888),(845,905),(829,922),(806,937),(786,951),(765,964),(772,979),(767,984),(781,997),(789,1007),(788,1018),(814,1043),(841,1067),(867,1090),(890,1110),(900,1121),(902,1138),(885,1152),(871,1165),(861,1176),(849,1171),(836,1192),(823,1213),(799,1206)],
 'economic-divider':[(799,1206),(804,1189),(808,1175),(809,1160),(803,1147),(786,1133),(771,1120),(763,1112),(762,1111),(759,1109),(740,1092),(715,1071),(688,1050),(659,1032),(628,1015),(594,997),(588,999),(574,1017),(560,1040),(545,1065),(526,1086),(504,1106),(500,1111),(482,1141),(466,1165),(454,1188)],
 'south-west':[(454,1188),(434,1202),(412,1218),(390,1239),(368,1259),(350,1232),(330,1205),(310,1176),(291,1148),(270,1119),(250,1088),(231,1061),(214,1037),(199,1013),(215,1008),(233,1002),(244,979),(254,955),(272,934),(292,914),(310,886),(292,864),(278,845),(269,844),(262,855),(243,846),(225,837),(219,851),(206,849),(207,822),(208,797),(209,784),(214,785),(222,763),(233,737),(244,713),(260,687),(280,660),(289,661),(302,638),(313,618),(327,623),(332,615),A]
}

# The source economic-divider is overprinted by three short pieces of the blue
# label. Keep their bounded manual continuations separate from literal black
# tracing. They are inferred connectors, not source-black evidence.
GAP_ENDPOINTS=[((771,1120),(763,1112)),((762,1111),(759,1109)),((504,1106),(500,1111))]
def connector(a,b):
    n=max(abs(b[0]-a[0]),abs(b[1]-a[1]))
    return [(round(a[0]+(b[0]-a[0])*i/n),round(a[1]+(b[1]-a[1])*i/n))for i in range(n+1)]

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
    # Disconnected source-black components are all retained. Only the three
    # enumerated text-overprint intervals may use a manual inferred connector.
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
            if (a,b)in GAP_ENDPOINTS:
                if anchor(a)!=a or anchor(b)!=b:raise ValueError('Changed literal connector endpoint')
                part=connector(a,b)
            else:part=path(anchor(a),anchor(b))
            points+=part if not points else part[1:]
        paths[key]=points
    def joined(parts):
        result=[]
        for key,reverse in parts:
            section=paths[key][::-1] if reverse else paths[key]
            if result and result[-1]!=section[0]:raise ValueError('Disconnected original-source sections')
            result+=section if not result else section[1:]
        return result
    rings={'Hunyadiváros':joined([('north-east',False),('economic-divider',False),('south-west',False)])}
    records=[]
    for name,ring in rings.items():
        polygon=Polygon(ring)
        if ring[0]!=ring[-1] or not polygon.is_valid:
            raise ValueError(name+': '+explain_validity(polygon))
        if any(max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1 for a,b in zip(ring,ring[1:])):
            raise ValueError('Non-adjacent source-pixel trace')
        inferred_pixels={q for a,b in GAP_ENDPOINTS for q in connector(a,b)[1:-1]}
        if any(not allowed[y,x]and(x,y)not in inferred_pixels for x,y in ring):raise ValueError('Unrecorded non-black source pixel')
        records.append({'name':name,'denseVertexCountIncludingClosure':len(ring),
                        'areaSourcePixelsSquared':polygon.area,'originalHoleCount':len(polygon.interiors),
                        'maximumMaxRgbAllVertices':max(int(value[y,x]) for x,y in ring),
                        'strictBlackSourceVertexCountIncludingClosure':sum(bool(allowed[y,x])for x,y in ring),
                        'inferredNonBlackVertexCount':sum(not bool(allowed[y,x])for x,y in ring),
                        'touchesImageFrame':any(x in(0,width-1)or y in(0,height-1)for x,y in ring)})
    result={'schemaVersion':1,'sourceImageSha256':SOURCE_SHA,'sourceImageSize':[width,height],
            'coordinateConvention':'Integer exact original-image pixel indices, x right/y down, no half-pixel offset.',
            'maxRgbThreshold':LIMIT,'sourceAnchorLookupRadiusPixels':9,'guideCorridorWidthPixels':PAD,
            'literalBlackImagePixelCount':len(component),
            'manualGuideSeeds':SECTIONS,'actualSourceAnchors':[{'manual':a,'actualBlackSourcePixel':b}for a,b in anchors.items()],
            'sections':paths,'rings':rings,'records':records,
            'sourceTextOverprintInferences':[{'id':'blue-overprint-'+str(i+1),'sourceBlackEndpoints':[a,b],'inferredPixelPath':connector(a,b),'endpointDistancePixels':math.dist(a,b),'confidence':'low','sourcePixelWindow':[min(a[0],b[0])-1,min(a[1],b[1])-1,max(a[0],b[0])+1,max(a[1],b[1])+1],'alternativePixelPaths':[[a]+[(x+dx,y+dy)for x,y in connector(a,b)]+[b]for dx,dy in[(1,0),(-1,0)]],'inferenceReason':'A short visible dark boundary approaches and leaves the blue source label; the strict black mask is interrupted by the annotation. The chosen continuation is a manual bounded hypothesis, not an observed black stroke or surveyed accuracy bound.'}for i,(a,b)in enumerate(GAP_ENDPOINTS)],
            'everyDenseVertexIsActualBlackSourcePixel':False,'allSuccessivePixelsAre8Neighbors':True,
            'frameClosureSnapBufferRepairOrSimplificationUsed':False,'manualSourceTextOverprintGapInferenceUsed':True,
            'geometryStatus':'Closed mostly literal-source-pixel contour with three explicit low-confidence blue-text-overprint inferences. Geographic registration has not been created by this script.',
            'absoluteAccuracyMeters':None,'usableForAddressAssignment':False}
    destination=P/'source-pixel-trace.json';data=encode(result)
    if check:
        if not destination.exists() or destination.read_bytes()!=data:raise ValueError('Stale source pixel trace')
    else:
        destination.write_bytes(data);preview=image.copy();draw=ImageDraw.Draw(preview)
        for ring in rings.values():draw.line(ring,fill='red',width=2)
        for a,b in GAP_ENDPOINTS:draw.line(connector(a,b),fill='yellow',width=3)
        preview.save(P/'source-pixel-preview.png')
    print(json.dumps({'mode':'check'if check else'build','records':records},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    build(parser.parse_args().check)
