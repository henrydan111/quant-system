# Field Approval Workflow

This directory holds per-promotion YAML evidence files for dataset status
transitions (typically `quarantine` → `pending_review` → `approved`). Every
write to `../field_approval_log.jsonl` is paired with a YAML here describing
the evidence reviewed and the reviewer.

The text format is intentional: every transition must be diffable in Git and
visible to future auditors. Do not store approvals only in a binary parquet
log.

## File naming

```
YYYY-MM-DD_{dataset_id}_{from_status}_to_{to_status}.yaml
```

Example: `2026-06-15_moneyflow_quarantine_to_approved.yaml`.

## Required fields

Every approval that promotes a dataset to (or toward) **formal use** MUST
carry both `provider_build_id` and `calendar_policy_id` so the
approval-evidence drift check (`src/data_infra/approval_evidence.py`, wired
into `scripts/run_daily_qa.py`) can verify the on-disk evidence was gathered
against the currently-published provider build. A future provider rebuild
whose `provider_build_id` / `calendar_policy_id` differs from any approval's
binding fails daily QA until the evidence is re-verified.

```yaml
date: 2026-06-15
dataset_id: moneyflow
from_status: quarantine
to_status: approved
reviewer: henrydan111
# REQUIRED binding (PR 10 / 10a / 10b / 10c): pin the provider build +
# calendar policy under which the on-disk evidence was verified. Both must
# be non-empty strings. A blank value or a missing key FAILS daily QA.
provider_build_id: prod_full_20260421_namespace_v1
calendar_policy_id: frozen_20260227_system_build
evidence:
  - "Manually ran scripts/audit_moneyflow_anomalies.py over 2014-01-01 to 2026-02-27"
  - "Cross-checked sample 50 stock-days against JoinQuant valuation values"
  - "Findings: 0 anomalies > 1% deviation; null rate 0.3% on suspended days only"
notes: "Promoted after anomaly review; replaces the 2026-05-26 seed quarantine."
related_findings_id: null
```

After approving, update `config/field_registry/field_status.yaml` to reflect
the new status AND append a JSON line to `field_approval_log.jsonl` with the
transition.

## Non-provider-bound administrative records (binding_exempt)

Some YAMLs in this directory are NOT formal-use promotions — e.g. a
coverage/diagnostic fix that re-shapes how `field_status.yaml` matches
existing fields, or a status registration that keeps a dataset in
`quarantine` / `pending_review`. These records have no provider-bound
formal-use evidence to pin, so they MUST declare an explicit exemption
instead of omitting the binding keys:

```yaml
date: 2026-05-27
dataset_id: moneyflow, hk_hold, margin_detail
reviewer: henrydan111
binding_exempt: true
binding_exempt_reason: >-
  Coverage/diagnostic fix only — no dataset is promoted to formal use,
  so there is no provider-bound evidence to bind to a provider_build_id.
notes: "..."
```

The marker must be a strict boolean `true` with a non-empty
`binding_exempt_reason`. Pre-PR-10c the drift scanner silently skipped any
YAML missing both binding keys, which could not distinguish a true unbound
record from a new approval that accidentally omitted the binding. The
explicit `binding_exempt` marker makes the exemption visible and auditable.
Setting `binding_exempt: true` AND providing binding keys is a
contradiction and fails daily QA.
