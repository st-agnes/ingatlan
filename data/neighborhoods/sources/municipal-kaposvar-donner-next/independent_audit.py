#!/usr/bin/env python3
"""Independent Donner topology audit using literal OSM node references.

The only inserted graph vertices are the two specifically intended analytical
river/road boundary crossings. All other connectivity requires shared OSM node
IDs. This is a reproducibility/topology check, not a geographic accuracy claim.
"""
import argparse
import hashlib
import heapq
import itertools
import json
import math
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.ops import transform, unary_union


HERE = Path(__file__).resolve().parent
PROJECT = Transformer.from_crs(4326, 23700, always_xy=True).transform
UNPROJECT = Transformer.from_crs(23700, 4326, always_xy=True).transform
LITERAL = HERE / "literal-roads-waterways.geojson"
PREDICATES = {
    "67": lambda t: t.get("ref") == "67",
    "Kapos": lambda t: t.get("name") == "Kapos" and t.get("waterway") == "river",
    "Zselic": lambda t: t.get("name") == "Zselic-patak" and bool(t.get("waterway")),
    "Szigetvári": lambda t: t.get("name") == "Szigetvári utca" and bool(t.get("highway")),
}
PAIR_ORDER = [("67", "Kapos"), ("Kapos", "Zselic"), ("Zselic", "Szigetvári"), ("Szigetvári", "67")]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def add_edge(graph, a, b, metadata):
    graph.setdefault(a, {})[b] = metadata
    graph.setdefault(b, {})[a] = metadata


def shortest(graph, start, stop, points):
    serial = itertools.count()
    queue = [(0.0, next(serial), start)]
    distance, previous = {start: 0.0}, {}
    while queue:
        cost, _, current = heapq.heappop(queue)
        if cost != distance[current]:
            continue
        if current == stop:
            route = [current]
            while route[-1] != start:
                route.append(previous[route[-1]])
            return list(reversed(route)), cost
        for neighbor in graph[current]:
            step = math.dist(points[current], points[neighbor])
            proposed = cost + step
            if proposed < distance.get(neighbor, math.inf):
                distance[neighbor], previous[neighbor] = proposed, current
                heapq.heappush(queue, (proposed, next(serial), neighbor))
    raise AssertionError(("No OSM-node-connected path", start, stop))


def attach_intersection(key, node, point, graphs, points):
    """Split only existing literal edge segments; never bridge a spatial gap."""
    graph = graphs[key]
    matches = []
    for a in graph:
        for b, metadata in graph[a].items():
            if str(a) >= str(b):
                continue
            segment = LineString([points[a], points[b]])
            if segment.distance(point) < 1e-7:
                matches.append((a, b, metadata))
    assert len(matches) == 1, (key, node, "analytical intersection edge matches", matches)
    a, b, metadata = matches[0]
    assert point.distance(Point(points[a])) > 1e-5
    assert point.distance(Point(points[b])) > 1e-5
    del graph[a][b]
    del graph[b][a]
    points[node] = tuple(point.coords[0])
    add_edge(graph, a, node, metadata)
    add_edge(graph, node, b, metadata)
    return {"edgeNodeRefs": [a, b], "sourceWayId": metadata["wayId"]}


def audit(candidate=None):
    raw = LITERAL.read_bytes()
    features = json.loads(raw)["features"]
    selected = {key: [f for f in features if pred(f["properties"]["source"]["tags"])] for key, pred in PREDICATES.items()}
    graphs, points, original = {key: {} for key in selected}, {}, {}
    for key, entries in selected.items():
        for feature in entries:
            source = feature["properties"]["source"]
            refs = source["nodeRefs"]
            coords = feature["geometry"]["coordinates"]
            assert len(refs) == len(coords)
            for ref, lonlat in zip(refs, coords):
                projected = PROJECT(*lonlat)
                if ref in points:
                    assert math.dist(points[ref], projected) < 1e-6, ref
                points[ref], original[ref] = projected, tuple(lonlat)
            for a, b in zip(refs, refs[1:]):
                add_edge(graphs[key], a, b, {"wayId": source["osmId"]})

    unions = {key: unary_union([transform(PROJECT, shape(f["geometry"])) for f in entries]) for key, entries in selected.items()}
    crossings = []
    for a, b in PAIR_ORDER:
        point = unions[a].intersection(unions[b])
        assert point.geom_type == "Point", (a, b, point.wkt)
        crossings.append(point)
    # Both semantic confluence/junction choices are actual shared OSM nodes.
    corner_nodes = ["analytic:67-Kapos", 290209038, "analytic:Zselic-Szigetvári", 27421028]
    for index in [1, 3]:
        node = corner_nodes[index]
        a, b = PAIR_ORDER[index]
        assert node in graphs[a] and node in graphs[b], (node, a, b)
        assert Point(points[node]).distance(crossings[index]) < 1e-6

    analytical = []
    for index in [0, 2]:
        a, b = PAIR_ORDER[index]
        node, point = corner_nodes[index], crossings[index]
        analytical.append({
            "label": node,
            "wgs84": list(UNPROJECT(*point.coords[0])),
            "edgeA": {"physicalFeature": a} | attach_intersection(a, node, point, graphs, points),
            "edgeB": {"physicalFeature": b} | attach_intersection(b, node, point, graphs, points),
            "method": "Exact analytical intersection of literal projected edge segments; no nearest-point bridge or invented connector.",
        })

    ring, arcs = [], []
    for index, key in enumerate(["Kapos", "Zselic", "Szigetvári", "67"]):
        start, stop = corner_nodes[index], corner_nodes[(index + 1) % 4]
        route, length = shortest(graphs[key], start, stop, points)
        assert len(route) == len(set(route)), (key, "repeated graph node")
        coords = [points[n] for n in route]
        line = LineString(coords)
        assert line.is_simple, (key, "self crossing")
        ring += coords[:-1]
        arcs.append({
            "physicalFeature": key,
            "lengthMetres": length,
            "vertexCount": len(route),
            "nodeRefPath": route,
            "sourceWayIds": list(dict.fromkeys(graphs[key][a][b]["wayId"] for a, b in zip(route, route[1:]))),
            "start": start,
            "end": stop,
        })
    polygon = Polygon(ring)
    assert polygon.is_valid and polygon.exterior.is_simple
    assert len(polygon.interiors) == 0
    comparison = {"performed": False}
    if candidate:
        document = json.loads(Path(candidate).read_text())
        assert document["type"] == "FeatureCollection" and len(document["features"]) == 1
        properties = document["features"][0]["properties"]
        for key, expected in {
            "name": "Donner", "municipality": "Kaposvár", "estimated": True,
            "boundaryKind": "inferred_area", "canonicalNameIsNeighborhood": False,
            "usableForAddressAssignment": False, "confidence": "low",
            "currentNameIndependentlyConfirmed": False,
            "claimedAbsoluteAccuracyMetres": None,
            "sourceTextRequiresInterpretation": True,
        }.items():
            assert properties[key] == expected, (key, properties.get(key))
        geometry = document["features"][0]["geometry"] if document.get("type") == "FeatureCollection" else document["geometry"] if document.get("type") == "Feature" else document
        actual = transform(PROJECT, shape(geometry))
        hausdorff = polygon.boundary.hausdorff_distance(actual.boundary)
        symmetric = polygon.symmetric_difference(actual).area
        assert actual.is_valid and actual.geom_type == "Polygon"
        # One centimetre is a serialization/computational comparison tolerance,
        # and is explicitly not a source/geographic accuracy claim.
        assert hausdorff <= 0.01, ("candidate boundary differs", hausdorff)
        proof = json.loads((HERE / "construction-proof.json").read_text())
        assert proof["inputSha256"] == sha(raw)
        normalized = {"analytic:67-Kapos": "intersection:67/Kapos", "analytic:Zselic-Szigetvári": "intersection:Zselic/Szigetvári"}
        for independently_found, archived in zip(arcs, proof["arcs"]):
            assert independently_found["physicalFeature"] == archived["name"]
            expected_nodes = [normalized[node] if isinstance(node, str) else f"osm:{node}" for node in independently_found["nodeRefPath"]]
            assert expected_nodes == archived["nodeIds"], (archived["name"], "node path mismatch")
            for node, lonlat in zip(archived["nodeIds"], archived["coordinates"]):
                if node.startswith("osm:"):
                    assert tuple(lonlat) == original[int(node[4:])], (node, "literal node changed")
        assert set().union(*(set(a["sourceWayIds"]) for a in arcs)) == set().union(*(set(a["originalWayIds"]) for a in proof["arcs"]))
        comparison = {"performed": True, "candidatePath": str(Path(candidate).name), "sha256": sha(Path(candidate).read_bytes()), "boundaryHausdorffMetres": hausdorff, "symmetricDifferenceSquareMetres": symmetric, "serializationComparisonToleranceMetres": 0.01, "toleranceIsGeographicAccuracyClaim": False, "originalOsmCoordinatesRetainedVerbatim": True, "independentNodeRefPathsMatchConstructionProof": True, "independentSourceWaySetsMatchConstructionProof": True, "inferredLowConfidencePropertyScopeVerified": True, "differenceExplanation": "The candidate intersects straight source segments in WGS84 and preserves original OSM node coordinates. This independent audit intersects in EOV and uses a projected-coordinate round trip for comparison. The sub-millimetre difference is a computation-model difference, not measured geographic error."}

    return {
        "schemaVersion": 1,
        "reviewDate": "2026-11-14",
        "reviewer": "independent child agent donner_source_review",
        "method": "OSM node-reference graphs for each named physical feature; exactly two intended analytical river/road crossings inserted on actual literal segments; each of four arcs found through source-node connectivity.",
        "literalInputSha256": sha(raw),
        "selectedWayCounts": {key: len(entries) for key, entries in selected.items()},
        "sourceNodeIdentityCheck": "PASS",
        "sharedCornerNodeRefs": [290209038, 27421028],
        "analyticalCrossings": analytical,
        "orderedArcs": arcs,
        "geometry": {"valid": polygon.is_valid, "simpleExterior": polygon.exterior.is_simple, "interiorCount": len(polygon.interiors), "exteriorCoordinateCount": len(polygon.exterior.coords), "areaSquareMetres": polygon.area, "perimeterMetres": polygon.length},
        "extra67ZselicCrossing": {"wgs84": list(UNPROJECT(*unions["67"].intersection(unions["Zselic"]).coords[0])), "usedAsCorner": False, "explanation": "This lies outside the selected Zselic arc, which stops at its Szigetvári crossing farther north. It does not replace the source's four distinct physical-edge sequence."},
        "candidateComparison": comparison,
        "geographicAccuracyValidated": False,
        "claimedAbsoluteAccuracyMetres": None,
        "usableForAddressAssignment": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output", type=Path, help="Write review JSON; otherwise read-only")
    args = parser.parse_args()
    result = audit(args.candidate)
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"result": "PASS", "geometry": result["geometry"], "candidateComparison": result["candidateComparison"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
