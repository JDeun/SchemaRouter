# Research impact evidence register

This directory records independently checkable *mentions*, not a global citation count. The canonical record is `citations.json` and `external-adoption.json`. Each work has one ID regardless of revisions or repeated mentions. **Never** label a literature review as an independent reproduction.

## Evidence levels
- `verified-primary`: primary publisher/arXiv text independently inspected, with both bibliography and in-text context.
- `verified-mirror`: text inspected in a third-party copy; primary-source verification remains pending.
- `candidate`: metadata/search hit only, not counted.
- `retracted`: evidence withdrawn or invalidated.

Counts must distinguish verified primary, mirror-only and candidates. External documentation references are not necessarily software adoption. Evidence and assertions must include URLs, exact sections, observed date, method, and caveats. Do not publish private emails or correspondent identities without consent.

## Intake and workflow
1. Run `python scripts/check_research_impact.py` (stdlib only). The scheduled workflow publishes a candidate artifact, **not** a verified citation count.
2. Compare candidates to canonical IDs; open a review issue for substantive new evidence, not for each API hit.
3. Inspect the source's actual body and bibliography, confirm SchemaRouter/arXiv:2608.21375 and record quotation location. Independently reproduced benchmarks require separate experiment/method/data evidence.
4. Update JSON with a reviewed PR. Keep URLs and provenance; never overwrite historical uncertainty without documenting it.

The private TRACE correspondence is deliberately **not** copied into this public repository. Track correspondence privately, and link only publicly disclosed research outputs.

## Career-safe summary
A scoping review discussed SchemaRouter's field-F1 vs downstream-answer-accuracy trade-off. This is a *secondary discussion of a reported experiment*, not an independently reproduced result or endorsement. See `citations.json` for evidence limits.
