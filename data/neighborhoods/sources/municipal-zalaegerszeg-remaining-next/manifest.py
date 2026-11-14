"""Freeze/check all package artifacts except this manifest itself. Offline only."""
import argparse,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
D=P/'artifact-manifest.json'
def role(n):
 if n.startswith('zalaegerszeg-'):return 'frozen_copied_source_or_historical_reference_input'
 if n.startswith('current-name') or n=='extract-current-name-evidence.py':return 'independent_current_name_evidence_not_fit_controls'
 if n.startswith('independent-'):return 'independent_audit'
 if n=='remaining-inferred-import.geojson':return 'six_estimated_candidate_export'
 if 'registry-entry' in n:return 'proposed_inferred_registry_entry_not_applied_here'
 if 'literal' in n:return 'literal_source_unit6_and_expected_raw_quarantine_evidence'
 if 'iparterulet-one-pixel' in n:return 'explicit_estimated_one_pixel_interpretation'
 if 'manual' in n:return 'manual_reconstruction_source_caps_alternatives_and_proof'
 if n.endswith('.png') or n.endswith('.npz'):return 'source_pixel_inspection_or_cache'
 return 'reproducibility_documentation_or_check'
rows=[{'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'role':role(p.name)} for p in sorted(P.iterdir()) if p.is_file() and p!=D]
entry=json.loads((P/'remaining-registry-entry.json').read_text())
x={'schemaVersion':1,'status':'frozen_six_estimated_candidates_unregistered_by_this_batch','candidateFeatureCount':6,'candidateExport':'remaining-inferred-import.geojson','candidateExportSha256':entry['sha256'],'sourceUrl':'https://zalaegerszeg.hu/wp-content/uploads/2023/05/Zalaegerszeg_ITS.pdf','originalPdfSha256':'4534775c49466eba0460e583aa45a12127f0a46cd8c0e768ed689b830e4eb035','sourceImageSha256':'cf259e0c7c54c3b58a0cf1e624ef178432ae734336cd3b676a9c7f2675aa8e37','pinnedOsmPbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','independentInteriorControlCount':0,'absoluteAccuracyMetres':None,'globalRegistriesModifiedByThisBatch':False,'frozenExistingFiveModified':False,'artifacts':rows}
s=json.dumps(x,ensure_ascii=False,indent=2)+'\n';arg=argparse.ArgumentParser();arg.add_argument('--check',action='store_true');a=arg.parse_args()
if a.check:
 assert D.read_text()==s,'Package manifest changed'
else:D.write_text(s)
print(json.dumps({'artifacts':len(rows),'candidateExportSha256':entry['sha256'],'check':a.check}))
