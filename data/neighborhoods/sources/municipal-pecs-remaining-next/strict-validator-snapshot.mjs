// Unmodified strict geometry-validator source snapshot for offline audit.
import {createHash} from 'node:crypto';
const EPSILON = 1e-12;
export const TARGET_CITIES = Object.freeze(['Budapest', 'Baja', 'Békéscsaba', 'Debrecen', 'Dunaújváros',
  'Eger', 'Érd', 'Esztergom', 'Győr', 'Hódmezővásárhely', 'Kaposvár', 'Kecskemét', 'Miskolc',
  'Nagykanizsa', 'Nyíregyháza', 'Pécs', 'Salgótarján', 'Sopron', 'Szeged', 'Székesfehérvár',
  'Szekszárd', 'Szolnok', 'Szombathely', 'Tatabánya', 'Veszprém', 'Zalaegerszeg']);

const sorted = values => [...values].sort((a, b) => a < b ? -1 : a > b ? 1 : 0);
const sha256 = value => createHash('sha256').update(value).digest('hex');
const normalizedName = value => value.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().replace(/[\s\p{Punctuation}]/gu, '');
const samePoint = (a, b) => a[0] === b[0] && a[1] === b[1];
const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
const onSegment = (a, b, p) => Math.abs(cross(a, b, p)) <= EPSILON &&
  p[0] >= Math.min(a[0], b[0]) - EPSILON && p[0] <= Math.max(a[0], b[0]) + EPSILON &&
  p[1] >= Math.min(a[1], b[1]) - EPSILON && p[1] <= Math.max(a[1], b[1]) + EPSILON;

function intersects(a, b, c, d) {
  const abC = cross(a, b, c), abD = cross(a, b, d), cdA = cross(c, d, a), cdB = cross(c, d, b);
  if (((abC > EPSILON && abD < -EPSILON) || (abC < -EPSILON && abD > EPSILON)) &&
      ((cdA > EPSILON && cdB < -EPSILON) || (cdA < -EPSILON && cdB > EPSILON))) return true;
  return onSegment(a, b, c) || onSegment(a, b, d) || onSegment(c, d, a) || onSegment(c, d, b);
}

function ringArea(ring) {
  // Translating first avoids cancellation when small polygons have large absolute coordinates.
  const origin = ring[0];
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i++) sum += cross(origin, ring[i], ring[i + 1]);
  return sum / 2;
}

function pointInside(point, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 2; i < ring.length - 1; j = i++) {
    const a = ring[i], b = ring[j];
    if (onSegment(a, b, point)) return false;
    if ((a[1] > point[1]) !== (b[1] > point[1]) &&
        point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}

function ringsIntersect(a, b) {
  for (let i = 0; i < a.length - 1; i++) {
    for (let j = 0; j < b.length - 1; j++) if (intersects(a[i], a[i + 1], b[j], b[j + 1])) return true;
  }
  return false;
}

/** Validate source geometry; do not repair, simplify, invent, or mutate a boundary. */
export function validateGeometry(geometry, expectedBbox = undefined) {
  if (!geometry || !['Polygon', 'MultiPolygon'].includes(geometry.type)) {
    return {valid: false, reason: 'not_polygon'};
  }
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  if (!Array.isArray(polygons) || !polygons.length) return {valid: false, reason: 'empty_geometry'};
  const bbox = [Infinity, Infinity, -Infinity, -Infinity];
  let vertices = 0;
  for (const polygon of polygons) {
    if (!Array.isArray(polygon) || !polygon.length) return {valid: false, reason: 'empty_polygon'};
    const checkedRings = [];
    for (const original of polygon) {
      if (!Array.isArray(original) || original.length < 4) return {valid: false, reason: 'short_ring'};
      if (original.some(point => !Array.isArray(point) || point.length !== 2 ||
          !point.every(Number.isFinite) || Math.abs(point[0]) > 180 || Math.abs(point[1]) > 90)) {
        return {valid: false, reason: 'invalid_coordinate'};
      }
      if (!samePoint(original[0], original.at(-1))) return {valid: false, reason: 'open_ring'};
      // Consecutive duplicate vertices are harmless; ignore them only in the validation copy.
      const ring = original.filter((point, index) => index === 0 || !samePoint(point, original[index - 1]));
      if (ring.length < 4 || Math.abs(ringArea(ring)) <= EPSILON) return {valid: false, reason: 'degenerate_ring'};
      for (let i = 0; i < ring.length - 1; i++) {
        for (let j = i + 2; j < ring.length - 1; j++) {
          if (i === 0 && j === ring.length - 2) continue;
          if (intersects(ring[i], ring[i + 1], ring[j], ring[j + 1])) return {valid: false, reason: 'self_intersection'};
        }
      }
      checkedRings.push(ring);
      vertices += original.length;
      for (const [lon, lat] of original) {
        bbox[0] = Math.min(bbox[0], lon); bbox[1] = Math.min(bbox[1], lat);
        bbox[2] = Math.max(bbox[2], lon); bbox[3] = Math.max(bbox[3], lat);
      }
    }
    for (let i = 1; i < checkedRings.length; i++) {
      if (!pointInside(checkedRings[i][0], checkedRings[0]) || ringsIntersect(checkedRings[i], checkedRings[0])) {
        return {valid: false, reason: 'hole_outside_shell'};
      }
      for (let j = 1; j < i; j++) {
        if (ringsIntersect(checkedRings[i], checkedRings[j]) || pointInside(checkedRings[i][0], checkedRings[j]) ||
            pointInside(checkedRings[j][0], checkedRings[i])) return {valid: false, reason: 'overlapping_holes'};
      }
    }
  }
  if (expectedBbox !== undefined && (!Array.isArray(expectedBbox) || expectedBbox.length !== 4 ||
      !expectedBbox.every(Number.isFinite) || expectedBbox.some((value, index) => Math.abs(value - bbox[index]) > 1e-6))) {
    return {valid: false, reason: 'bbox_mismatch'};
  }
  return {valid: true, bbox, vertices};
}

