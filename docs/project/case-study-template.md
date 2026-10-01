# External case-study template

Use this template only after a real external project or user has evaluated SchemaRouter. Do not
pre-fill a project name as if adoption already exists.

## Permission

- Public project/user name:
- Public evaluation/integration URL:
- Permission to name the project: yes / no
- Permission to quote: yes / no
- Permission to use logo: yes / no / not requested
- Date permission was confirmed:
- Public source for permission, if any:

Private contact details do not belong in this file.

## Context

- What application/agent stack was being built?
- How many tools/capabilities/providers were involved?
- Which problem motivated the evaluation?
- What was the existing tool discovery/filtering approach?

## Environment

- downstream project version/commit:
- SchemaRouter version/commit:
- Python/runtime:
- model/provider, if relevant:
- hardware, if relevant:
- relevant integration packages and versions:

## Integration surface

Describe the smallest actual boundary used:

```text
existing agent/runtime
    -> <SchemaRouter retrieval / execution boundary>
    -> existing tool/MCP/provider surface
```

State clearly which system owns:

- agent orchestration;
- tool retrieval;
- execution approval/policy;
- transport lifecycle;
- schema validation;
- output projection.

## Workload

Describe the evaluation requests/tasks.

Include:

- number of requests/tasks;
- whether they were created before or after seeing results;
- at least one unsupported/no-route request;
- any adversarial or ambiguous requests;
- exact data needed to reproduce the workload when it is public.

## Before / after

| Metric | Before | With SchemaRouter | Measurement notes |
| --- | ---: | ---: | --- |
| model-visible tools |  |  |  |
| serialized schema bytes or actual model tokens |  |  | label the unit correctly |
| required-tool recall |  |  |  |
| task completion |  |  |  |
| unsupported false-route rate |  |  |  |
| added routing latency p50/p95 |  |  |  |
| execution/validation failures |  |  |  |

Add domain-specific metrics only when they are actually measured.

## Result

Summarize what changed in concrete terms. Separate:

- measured effect;
- maintainer/user qualitative feedback;
- interpretation.

Do not convert a subjective comment into a quantitative claim.

## Limitations

Every case study must include limitations. Examples:

- one downstream application only;
- small or non-random workload;
- framework-native filtering was not tuned;
- byte counts rather than model tokens;
- no production traffic;
- latency measured on one machine;
- provider/version may change;
- integration used SchemaRouter only for retrieval, not execution.

## Artifacts

- downstream PR/commit:
- runnable example:
- benchmark/evaluation output:
- SchemaRouter issue/PR created from feedback:
- independent reproduction, if any:

## Evidence level

Choose one:

- E1 — public external evaluation;
- E2 — downstream reproducible branch/PR/test;
- E3 — downstream released/default use;
- E4 — independent benchmark/reliability reproduction.

## Quote

Only include a quote if explicit permission exists.

> _Optional public quote_

Attribution:
