# Final correction status: PASS

Both original material defects below were resolved by the separate `shard-4/corrections/features.geojson` replacement packet, SHA-256 `938e48f26e42a9825621bbc640e7a8fbecc0147ab5a24537b3380ae2ad216bdf`. Independent checks retained all 2,764 green-X source pixels with zero neighboring unit fill, verified the final geographic shape against that registered source mask, excluded all nine urban/Eresztvény checkpoints from the rural estimate, and retained four listed rural localities. Use these two corrections instead of the frozen originals. No further exclusion is recommended. Detailed results: `corrections-validation.json`.

Intake also resolved the spelling identity as canonical **Borbás belterület**, with Bordás aliases; broad Borbás remains separate. No northern industrial/logistics alias was applied.

# Independent shard 4 QA

Reviewed frozen `shard-4/features.geojson`, SHA-256 `ac81dd61f69f96deb3599b0f594bf615f04f04f7fc39446c709889e2ae85ab78`. No frozen/global files were changed. Review applies the requested coarse-boundary standard and identifies two material defects requiring a separate correction or exclusion.

1. **Kecskemét, Budaihegy–Vacshegy:** the stored source-pixel trace includes substantial parts of differently named source units. Direct overlay on figure 71 shows its western diagonal in cyan IX (Széchenyiváros–Máriahegy) and southern tail in pink I (Belváros). Inside the stored trace, exact source fill counts are 2,654 green-X pixels, 1,371 cyan-IX pixels, 261 pink-I pixels and 115 neighboring green-II pixels. Cyan and pink alone represent at least approximately 1.33 km² under the shared affine transform. This is a source-footprint error, not a registration or minor boundary caveat. Correct by isolating the green-X source enclosure; retain the shared registration unless independent source evidence warrants changing it. Evidence: `kecskemet-source-traces-overlay.png`.
2. **Salgótarján, Külterület (Eresztvény nélkül):** the output is 90.15 km² of the archived municipality's 92.63 km², or 97.3%. The build's available area input has only two residential surfaces meeting its threshold, and the subtraction leaves the source Belváros point, Vásártér and essentially all major urban estates inside the alleged rural remainder. Tested urban labels include Belváros, Beszterce-lakótelep, Kemerovó-lakótelep, Gorkij-lakótelep, Zagyvapálfalva and Baglyasalja. This is nearly the whole municipality with a few land-use holes, rather than a meaningful rural outline. Use archived complete residential relations and/or urban ITS unit extents before subtracting Eresztvény, or exclude this feature. The primary source does identify a rural unit, so the identity is valid; incomplete physical inputs invalidate the current geometry proxy.

The other five Kecskemét source traces show no material location/identity mismatch at the accepted rough scale. Bödögsor's partial municipal clipping is already explicit and is not by itself an exclusion recommendation. All 63 frozen features are valid nonempty polygons/multipolygons, with no identical geometry duplicates.

Alias review:

- **Bordás → Borbás:** support the spelling alias. Figure 71's small orange satellite is labeled Bordás belterület, while the following primary-source page twice calls the satellite Borbás and lists no separate Bordás. However, the already collected canonical Borbás geometry is the broad approximately 21.7 km² rural district; the new approximately 0.213 km² trace represents its satellite settlement. A name alias is supported; the two geometries are not equivalent.
- **Északi ipari övezet → Északi logisztikai övezet:** do not automatically accept. The available evidence supports a probable planning-edition label alignment, with no explicit equivalence statement. Retaining the requested historical/inventory name with uncertainty is acceptable at this task's scope.
- **Bödögsor / Bódogsor:** Bódogsor is the verified map spelling. The existing inventory identity can be retained with that source spelling as an alias; this is not a separate place.

Both material findings were sent to root, intake and the source worker. Root requested separate correction files; those corrections are outside this frozen-original review.
