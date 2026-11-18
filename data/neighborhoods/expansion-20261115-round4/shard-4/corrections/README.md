# Shard 4 — two independently reviewed replacements

Import only `corrections/features.geojson` from this folder. Its two quality 30 / priority 25 candidates replace the selected shapes for Kecskemét **Budaihegy-Vacshegy** and Salgótarján **Külterület (Eresztvény nélkül)** from the frozen63-name packet. Preserve those original candidates as historical alternatives, but select these corrected candidates for address matching. The other 61 frozen features are unchanged.

The former Budaihegy-Vacshegy hand trace crossed neighboring cyan IX, pink I and green II source units. The correction digitally extracts the whole actual green X enclosure from municipal figure71/PDFp138. It retains all 2,764 exact green fill pixels and no exact fill pixels from those neighboring units. Closing bridges internal black strokes and filling removes the numeral/stroke holes; the outer boundary remains a coarse pixel-level source trace. The original nine-label affine remains, with 162 m fit RMS and no claimed modern absolute accuracy. Corrected area 2.431498 km².

The former Salgótarján subtraction used an incomplete way-only context and retained central urban places. This correction subtracts full archived assembled residentialrelations and complete earlier municipal ITS urban unit estimates, with Eresztvény explicitly excluded. Corrected rural area 73.731441 km² out of a 92.630307 km² municipality. All nine urban/Eresztvény checkpoints are outside; the checked Kotyháza, Ponyipuszta, Pécskőpuszta and Csókáspuszta rural places remain inside. Named rural settlements are not excluded merely because they have mapped dwellings. This is still a low-confidence planning/physical-source proxy, not exact current cadastral belterület classification.

Independent QA by shard5 passed both material corrections. The complete receipt is `independent-qa.json`, copied from `round4/review/shard4-by-shard5/corrections-validation.json`. Source overlays and before/after urban/rural previews are included.

Offline rebuild from any working directory:

`PYTHONPATH=/workspace/ingatlan/.local/geodata python /absolute/path/to/corrections/build.py`

Requires Python, NumPy, SciPy, Pillow, Shapely and pyproj. Every geometry input is archived in this folder. No PBF scan, download or network is needed. `source-paths.json` records unchanged frozen-source origins. The source pixel GeoJSON and excluded urban proxy are diagnostics, not extra WGS84 neighborhood outputs.

All frozen originals and their manifests were preserved. Global registry, ID, alias and Git integration belongs to the root intake agent.
