<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

# Architecture rules

- Cloud supplier importing is disabled: `/api/public/sync` returns 410 without database access and `arm_sync_cron()` is a no-op, so stale schedules cannot restart imports during the static-catalog migration.
- Product photos are stored in the private `products` bucket and served via `/api/public/img/*` with immutable cache — public buckets are blocked.
- Storefront and admin read the same GitHub Pages snapshot; admin writes only GitHub Contents API with a device-local owner token so both remain independent of Cloud.
- Public catalog imports run in GitHub Actions using secret-held source configuration and publish only sanitized catalog/state JSON plus numeric-named WebP covers; direct Pages artifact deployment keeps weekly publication independent of Cloud.
- Catalog normalization uses explicit club aliases and league identities in scripts/catalog_rules.py; substring similarity alone must not merge different clubs.
- Footwear import rules live in a pure Python module, with a single category and explicit subtype; public catalog filters subtype before brand to avoid mixing footwear groups.
- Section classification is shared through public catalog metadata; storefront navigation reveals leagues, teams and garment filters one level at a time so special sports never enter club football.
- Weekly imports persist opaque per-source batch offsets, cap network waits and process bounded album batches; source addresses are never stored in public progress files.
- Privacy audits validate public product fields and source-host references separately from translation/denylist dictionaries, preventing legitimate safety rules from failing their own audit.
- Static-catalog photo privacy uses the pure scripts/photo_policy.py rules and confidence-bearing English/Chinese OCR confirmed across two segmentations: uncertain/error results cannot hide products, avoiding fabric/crest false positives.
- Album covers come from the seller-selected album header or exact listing card, resolving matching thumbnails to original images and excluding noscript duplicates; missing or privacy-rejected covers use whole-frame smooth perimeter and centered contrast scoring, with pixel deduplication and eight-photo cap to keep galleries bounded.
- Historical gallery recovery matches full original export metadata one-to-one and reads the matched private album in DOM order; old stored sort order and positional IDs cannot establish album order, and ambiguous matches remain unchanged.
- Extra galleries transfer as numeric-only public release packages to a separate Pages repository, keeping cross-repository automation free of shared credentials and provider metadata.
- Gallery recovery requires the previous photo package before proceeding and requeues missing gallery files, preventing transient download failures from silently losing earlier batches.
- Gallery pilots write only sanitized visual artifacts, never catalog/state/photo changes, so visual approval precedes mass recovery.

- Gallery recovery writes only to the catalog and photo repositories; the storefront repository is never a workflow write target.
- Gallery failures are handled by a catalog-only workflow_run supervisor: three failed-job retries, then a fresh main dispatch resuming committed progress; active runs, pilots and cancellations are never modified.
- Automatic cover picks live in auto-covers.json (product id -> gallery file). The auto-covers workflow swaps that gallery photo with the current cover (old cover stays in the gallery, nothing is deleted) and records it in auto-covers-applied.json; gallery recovery treats applied ids like manual covers and never reprocesses them. portadas.json (owner choices) always wins.
