# Adoption metrics and growth scorecard

SchemaRouter measures growth as **qualified usage and adoption**, not stars alone. The project does
not add invasive product telemetry solely for marketing analytics.

## Baseline

The pre-campaign GitHub baseline was captured on **2026-10-01**:

| Metric | Baseline |
| --- | ---: |
| GitHub stars | 1 |
| Forks | 0 |
| Subscribers | 1 |
| Network count | 0 |
| Open issues + PRs | 26 |

The automated scorecard also queries PyPIStats for package downloads and attempts GitHub's rolling
14-day traffic endpoints. The first successful scorecard run is the canonical PyPI/traffic baseline,
because those values are time-windowed external data and should not be guessed into source control.

## Automated collection

The **Growth Scorecard** GitHub Actions workflow runs every Monday and can be dispatched manually.

It records:

- GitHub stars, forks, subscribers, open issues/PRs, network count, topics, and repository dates;
- PyPI downloads for the last day, week, and month;
- GitHub views and clones for the rolling 14-day traffic window when the token has sufficient
  traffic permission;
- collection timestamp and explicit metric limitations.

Each run writes JSON and Markdown artifacts retained for 180 days and renders the Markdown summary in
the workflow UI.

The collector is:

```bash
python scripts/capture_growth_scorecard.py \
  --json-out /tmp/growth-scorecard.json \
  --markdown-out /tmp/growth-scorecard.md
```

## Permission model

Public GitHub repository metadata and PyPIStats need no private telemetry. Repository traffic is a
different API surface: GitHub limits it to users/tokens with repository traffic access.

The workflow therefore treats traffic as optional evidence. If the default `GITHUB_TOKEN` cannot
read it, the artifact says `unavailable` instead of failing the entire snapshot.

Maintainers may optionally configure a `SCHEMAROUTER_GROWTH_GITHUB_TOKEN` secret with the minimum
read permission needed for traffic metrics. No write permission is required.

## Leading versus lagging indicators

**Leading indicators**

- PyPI downloads by day/week/month;
- repository views and unique visitors when available;
- repository clones and unique cloners when available;
- quickstart/example execution failures surfaced through issues;
- integration/package-extra usage evidence when a downstream project publishes it.

**Lagging indicators**

- stars;
- forks;
- subscribers;
- external contributors;
- verifiable downstream adopters and case studies.

A star increase without install/adopter evidence is not reported as product adoption.

## Metrics that remain evidence-driven/manual

Some useful signals do not have a reliable, privacy-preserving public API:

- external repositories depending on or referencing SchemaRouter;
- downstream CI use;
- install-to-first-success;
- framework/plugin integration adoption;
- case studies and independent reproductions.

These are added only when there is verifiable public evidence. They are not inferred from GitHub
search noise or fabricated from traffic counters.

## Snapshot cadence

- **Weekly:** automated workflow snapshot.
- **Monthly:** retain one representative workflow artifact and summarize material changes in #583.
- **Before/after a campaign:** record the exact run IDs used for comparison.
- **Release-specific:** compare downloads by version only when the data source can support the claim.

## Interpretation limitations

PyPI downloads include CI and repeated installs and are not unique users. GitHub traffic is a rolling
14-day window. Stars measure awareness more than usage. Open issue counts mix bug reports, research
trackers, and planned work.

For that reason, growth decisions should use several signals together and keep external-adopter
evidence separate from raw counters.
