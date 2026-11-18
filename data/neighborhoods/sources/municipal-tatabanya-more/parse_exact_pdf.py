"""Read this PDF's actual decimal path operands/CTMs without float snapping.

The original CAD page uses exact decimal graphics transforms. MuPDF exposes
float32 positions, which can differ at shared source vertices by ~0.00003 pt.
This small, source-specific PDF content interpreter retains original Decimal
arithmetic and verifies paint-order mapping against MuPDF independently.
It does not reconstruct missing paths or automatically close stroked outlines.
"""
from decimal import Decimal, getcontext, Inexact
from pathlib import Path
import fitz

getcontext().prec = 50
getcontext().traps[Inexact] = True
D = Decimal
IDENTITY = (D(1), D(0), D(0), D(1), D(0), D(0))


def tokens(data):
    index, length = 0, len(data)
    whitespace = b'\x00\t\n\x0c\r '
    delimiters = whitespace + b'()<>[]{}/%'
    while index < length:
        char = data[index]
        if char in whitespace:
            index += 1
            continue
        if char == 37:
            while index < length and data[index] not in b'\r\n':
                index += 1
            continue
        if char == 40:
            depth, start = 1, index
            index += 1
            while depth:
                if index >= length:
                    raise ValueError('Unterminated PDF literal string')
                if data[index] == 92:
                    index += 2
                    continue
                depth += (data[index] == 40) - (data[index] == 41)
                index += 1
            yield ('string', data[start:index])
            continue
        if char == 60:
            if data[index:index + 2] == b'<<':
                yield ('delimiter', b'<<')
                index += 2
            else:
                end = data.index(b'>', index + 1)
                yield ('string', data[index:end + 1])
                index = end + 1
            continue
        if char in b'[]>':
            yield ('delimiter', bytes([char]))
            index += 1
            continue
        start = index
        if char == 47:
            index += 1
            while index < length and data[index] not in delimiters:
                index += 1
            yield ('name', data[start:index])
            continue
        while index < length and data[index] not in delimiters:
            index += 1
        if index == start:
            raise ValueError('Unsupported content token near ' + repr(data[index:index + 30]))
        value = data[start:index]
        try:
            yield ('number', D(value.decode('ascii')))
        except Exception:
            yield ('operator', value.decode('ascii'))


def concatenate(first, second):
    a, b, c, d, e, f = first
    g, h, i, j, k, l = second
    return (a*g+c*h, b*g+d*h, a*i+c*j, b*i+d*j,
            a*k+c*l+e, b*k+d*l+f)


def read_paths(pdf_path):
    document = fitz.open(pdf_path)
    if len(document) != 1:
        raise ValueError('Expected the archived single-page Tatabánya source')
    page = document[0]
    streams = b'\n'.join(document.xref_stream(ref) for ref in page.get_contents())
    height = D(str(page.rect.height))
    ctm, stroke, fill = IDENTITY, (D(0),)*3, (D(0),)*3
    stack, operands, path, paths = [], [], [], []
    current = start = None
    raw_path = []

    def point(x, y):
        a, b, c, d, e, f = ctm
        return (a*x+c*y+e, height-(b*x+d*y+f))

    for kind, value in tokens(streams):
        if kind != 'operator':
            operands.append((kind, value))
            continue
        op = value
        args = [val for typ, val in operands if typ == 'number']
        if op == 'q':
            stack.append((ctm, stroke, fill))
        elif op == 'Q':
            ctm, stroke, fill = stack.pop()
        elif op == 'cm':
            if len(args) != 6:
                raise ValueError('Non-numeric matrix arguments')
            ctm = concatenate(ctm, tuple(args))
        elif op in ['RG', 'rg']:
            if len(args) != 3:
                raise ValueError('Invalid color operands')
            if op == 'RG':
                stroke = tuple(args)
            else:
                fill = tuple(args)
        elif op in ['G', 'g']:
            if op == 'G':
                stroke = tuple(args * 3)
            else:
                fill = tuple(args * 3)
        elif op == 'm':
            current = start = point(*args)
            raw_path.append({'operator': op, 'operands': [str(arg) for arg in args],
                             'ctm': [str(arg) for arg in ctm]})
        elif op == 'l':
            following = point(*args)
            path.append(('l', current, following))
            current = following
            raw_path.append({'operator': op, 'operands': [str(arg) for arg in args],
                             'ctm': [str(arg) for arg in ctm]})
        elif op == 'c':
            following = point(args[4], args[5])
            path.append(('c', current, point(args[0], args[1]), point(args[2], args[3]), following))
            current = following
            raw_path.append({'operator': op, 'operands': [str(arg) for arg in args],
                             'ctm': [str(arg) for arg in ctm]})
        elif op == 'h':
            if current != start:
                path.append(('l', current, start))
            current = start
            raw_path.append({'operator': op, 'explicitSourceCloseOperator': True})
        elif op in ['S', 'f', 'f*', 'B', 'B*', 's', 'b', 'b*']:
            if op in ['s', 'b', 'b*'] and current != start:
                path.append(('l', current, start))
            paths.append({'index': len(paths), 'paint': op,
                          'color': None if op.startswith('f') else stroke,
                          'fill': None if op in ['S', 's'] else fill,
                          'items': list(path), 'rawPath': raw_path,
                          'explicitClose': any(item['operator'] == 'h' for item in raw_path)
                                           or op in ['s', 'b', 'b*']})
            path, raw_path = [], []
            current = start = None
        elif op == 'n':
            path, raw_path = [], []
            current = start = None
        elif op in ['re', 'v', 'y', 'Do', 'BI', 'ID', 'EI']:
            raise ValueError('Unimplemented geometry operator in source: ' + op)
        operands = []
    if stack or path:
        raise ValueError('Unbalanced source graphics state or trailing unpainted path')

    drawings = page.get_drawings()
    if len(paths) != len(drawings):
        raise ValueError('Source paint-order mismatch: ' + str((len(paths), len(drawings))))
    worst = 0.0
    for exact, approximate in zip(paths, drawings):
        for key in ['color', 'fill']:
            if ((exact[key] is None) != (approximate[key] is None)
                    or exact[key] is not None and any(abs(float(a)-b) > 1e-6
                                                     for a, b in zip(exact[key], approximate[key]))):
                raise ValueError('Paint-order color mismatch at ' + str(exact['index']))
        exact_points = [point for item in exact['items'] for point in item[1:]]
        approximate_points = []
        for item in approximate['items']:
            if item[0] == 'qu':
                approximate_points.extend(tuple(point) for point in item[1])
            elif item[0] == 're':
                approximate_points.extend([tuple(item[1].tl), tuple(item[1].br)])
            else:
                approximate_points.extend(tuple(point) for point in item[1:])
        # MuPDF can expose a collapsed zero-size subpath differently. Compare
        # the full bounding boxes for all draws, and exact sequence for every
        # actual outline selected later by the converter.
        if exact_points and approximate_points:
            for axis in [0, 1]:
                for operator in [min, max]:
                    delta = abs(float(operator(point[axis] for point in exact_points))
                                - operator(point[axis] for point in approximate_points))
                    worst = max(worst, delta)
                    if delta > 0.0003:
                        raise ValueError('Exact source/MuPDF geometry mismatch at ' + str(exact['index']))
    return {'document': document, 'page': page, 'paths': paths,
            'rawStreams': streams, 'maximumMuPdfBoundingCoordinateDifferencePoints': worst,
            'pageSize': (D(str(page.rect.width)), height)}


if __name__ == '__main__':
    import json
    root = Path(__file__).resolve().parents[4]
    result = read_paths(root / 'data/neighborhoods/sources/municipal-west/tatabanya-map.source.pdf')
    print(json.dumps({'pathCount': len(result['paths']),
                      'maximumMuPdfDifferencePoints': result['maximumMuPdfBoundingCoordinateDifferencePoints']}))
