import {createHash} from 'node:crypto';

const digest = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');

/** Per-object, source-bound semantic corrections. Coordinates and source facts stay intact. */
export function applySemanticAudit(collected, canonicalSettlements, audit = null) {
  if (!audit) return collected;
  if (audit.schemaVersion !== 1 || !Array.isArray(audit.records)) throw new Error('Invalid semantic audit');
  const canonical = new Set(canonicalSettlements), records = new Map();
  for (const row of audit.records) {
    if (!/^osm:(?:way|relation):[1-9]\d*$/.test(row.id ?? '') || records.has(row.id) ||
        !canonical.has(row.municipality) || typeof row.sourceName !== 'string' || !row.sourceName ||
        !/^[a-f0-9]{64}$/.test(row.sourceSha256 ?? '') || !/^[a-f0-9]{64}$/.test(row.geometrySha256 ?? '') ||
        row.action !== 'retain_as_local_area' || !['accommodation_area','cemetery_subarea'].includes(row.semanticType) ||
        typeof row.reason !== 'string' || !row.reason || !Array.isArray(row.evidenceUrls) ||
        !row.evidenceUrls.length || row.evidenceUrls.some(url => typeof url !== 'string' || !url.startsWith('https://'))) {
      throw new Error('Invalid source-bound semantic audit record');
    }
    records.set(row.id, row);
  }
  const applied = new Set();
  const features = collected.features.map(feature => {
    const row = records.get(feature.id);
    if (!row) return feature;
    const p = feature.properties;
    if (p.source?.provider !== 'openstreetmap' || p.source.sha256 !== row.sourceSha256 ||
        p.municipality !== row.municipality || p.name !== row.sourceName || digest(feature.geometry) !== row.geometrySha256) {
      throw new Error(`Semantic audit source changed; review required: ${feature.id}`);
    }
    applied.add(feature.id);
    return {...feature, properties: {...p, boundaryKind: 'local_area', semanticType: row.semanticType,
      canonicalNameIsNeighborhood: false, canonicalNameSupported: false,
      nameVerificationStatus: 'quarter_name_not_corroborated', semanticReview: row,
      usableForAddressAssignment: false}};
  });
  if (applied.size !== records.size) throw new Error('Semantic audit contains a missing source object; review required');
  return {...collected, features};
}
