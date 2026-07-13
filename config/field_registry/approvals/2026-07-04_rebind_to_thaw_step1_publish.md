# Re-bind to the calendar-thaw publish (thaw_step1_20260703c / frozen_20260701_thaw_step1)

The 2026-02-27 calendar freeze ended: staged build `thaw_step1_20260703c` (calendar 4,410 -> 4,493
days, end 2026-07-01) published 2026-07-04 via the safe staged-first swap under the NEW policy
`frozen_20260701_thaw_step1` (spent_oos_end=2026-02-27 born-sealed window). All 25 approval YAMLs
re-bound on BOTH ids (provider depth9_20260630_sharecap_reanchor_20260701 -> thaw_step1_20260703c;
policy frozen_20260227_system_build -> frozen_20260701_thaw_step1).

Evidence the frozen prefix is unchanged (AUDIT3, workspace/outputs/calendar_unfreeze/
frozen_prefix_audit.json): 38,051,814 bins 0 missing / 0 shrunk; 760,267 sampled bins frozen-prefix
SHA byte-identical with 0 unexplained mismatches (81 approved exceptions = the contracted report_rc
202602 overlap-refetch completion, diff dates 2026-02-12/13); sidecar day-by-day membership identical
except 57 strictly-additive suspension-healing cells x2 (12 diagnosed codes). Dry-run report:
workspace/research/calendar_unfreeze/DRYRUN_REPORT.md (user-approved 2026-07-04).
`evaluate_approval_evidence_bindings()` -> 0 drift after rebind. Prior live retained as
`data/qlib_data.bak_thaw_step1_20260703c` (one rename from restore).
