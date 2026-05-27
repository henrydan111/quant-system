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

```yaml
date: 2026-06-15
dataset_id: moneyflow
from_status: quarantine
to_status: approved
reviewer: henrydan111
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
