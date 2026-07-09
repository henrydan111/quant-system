ROLE
You are the same senior reviewer who issued review #1 (REVISE: 0 Blocker / Major-1,2,3 / Minor-1..5 / Q2,Q4,Q5,Q6,Q8 findings) on the 虚拟AI投研部 design. This is re-review #2: verify each fix, close residual R6, and issue SHIP or REVISE.

REPO
https://github.com/henrydan111/quant-system  (branch: calendar-unfreeze)
Raw: https://raw.githubusercontent.com/henrydan111/quant-system/calendar-unfreeze/<path>
The six documents (fetch to verify fixes in place; README §2b is the applied-findings ledger):
workspace/research/ai_research_dept/{README,VIRTUAL_RESEARCH_DEPT_DESIGN_v1,INTEL_CENTER_DATA_LAYER_v1,RESEARCH_REPORT_FULLTEXT_PIPELINE_v1,SYNTHESIS_LAYER_AMENDMENT_v1,PRICE_VOLUME_INTELLIGENCE_v1}.md

FIX MAP (finding → applied change → location)
1. Major-1 retrieval governance → new cross-cutting rule #8: any change to recall universe / channel
   priority / importance thresholds / relevance formula / decay / LLM borderline routing =
   RetrievalConfigCandidateID; if its output is consumed by any score/composite/ranking/selection →
   full C16b (golden-set calibration, effective-trial count, one-winner throttle, forward-only).
   Explicitly names "relation-channel stocks did better → raise weight" as retrieval alpha tuning.
   [INTEL_CENTER §3 #8]
2. Major-2 synthesis validation → three-level check: L1 source_id exists+as-of legal; L2 claim maps to
   source category; L3 claim_strength(fact|interpretation|hypothesis) ≤ evidence_strength(direct_quote|
   multi_source|inference); over-level statements demoted to hypothesis or quarantined; no numbers
   outside the anchor set. [SYNTHESIS_LAYER_AMENDMENT 修补⑤ table]
3. Major-3 composite fence → evidence_class="research_summary"; barred from ranking universe /
   candidate generation / portfolio overlay unless C16-registered. [VIRTUAL §6.2]
4. Minor-1 → retrieval_profile_snapshot_id = hash{taxonomy_version, tag_version, relation_graph_version,
   focus_word_version, retrieval_config_id} persisted per dossier. [INTEL_CENTER §2A.3]
5. Minor-2 → relation_graph_snapshot (daily); all graph queries graph_version ≤ decision_time; circular
   evidence detection (A→B & B→A same-source same-window → circular, excluded from propagation).
   [SYNTHESIS_LAYER_AMENDMENT 修补①]
6. Minor-3 → focus-word lifecycle candidate→approved→deprecated; LLM mints candidate only; candidate
   words tag-only (no heat board, no retrieval channel). [INTEL_CENTER §2A.2]
7. Minor-4 → golden set extended with retrieval-relevance labels (stock,date,event → relevant/irrelevant
   + proper channel). [VIRTUAL §8.1]
8. Minor-5 → platform hard boundary: pages cannot trigger re-tagging/config change/LLM regeneration;
   platform process must not import scoring/orchestration modules (architecture test). [INTEL_CENTER §6]
9. Q2 → explicit C16 candidate-surface list (Pass-C fields, story_arc/credibility, consensus_core/
   herding/blind_spots, situation_type, retrieval borderline judge, chief synthesizer, regime labels,
   RetrievalConfig) — all default evidence_class=research_summary, human-read only.
   [SYNTHESIS_LAYER_AMENDMENT new section]
10. Q4 → independent_source_count with report-family clustering (same broker × relation × 90d = 1
    confirmation). [SYNTHESIS_LAYER_AMENDMENT 修补①]
11. Q5 → any artifact lacking evidence_class is refused by every evaluator (fail-closed).
    [INTEL_CENTER §3 #9]
12. Q6 → chief synthesizer moved v1.5 → v2 (hardest-to-verify module last). [AMENDMENT + README §4]
13. Q8-C2 → clarified: ALL v1 outputs exclude Pass-C (digest cards start v1.5). [README §4]

R6 CLOSURE — consolidated LLM call budget (monthly, 149-name pool; doubao lite=quick / pro=deep)
| Stage | v1 | v1.5 adds |
|---|---|---|
| Text event typing (anns_d/irm_qa after deterministic kill) | 2-3k quick | — |
| Research reports Pass-A/B (300-800 PDFs) | 1.5-3k quick + 0.3-0.8k deep | Pass-C +0.3-0.8k deep; cross-report brief +0.15k deep |
| Analyst seats (3 seats × cadence) | monthly decision: ~0.5k deep; if daily scoring: ~6-7k deep (50% cache) | narrative memory +0.15k/quarter; regime card +30/mo deep |
| Retrieval borderline judging (5-10% of items) | 1-2k quick | — |
| Narrative assembly (市场日评/线索报告) | 0.5-1k deep | — |
| **Total** | **~5-8k quick + 1.3-9k deep ≈ 低数十至数百元 RMB/月** (cadence is the dominant swing; scoring cadence will be pre-registered before build) | +~1-2k deep |

RE-REVIEW QUESTIONS
1. Does each fix, as worded at its location, actually close the finding? Quote any wording that leaves a loophole and give exact replacement.
2. Major-2 L3: is the 3×3 strength lattice (fact/interpretation/hypothesis × direct_quote/multi_source/inference) operationally checkable by code+LLM-critic, or does it need a worked rubric per pair? If the latter, specify the minimum rubric.
3. Major-1: is RetrievalConfigCandidateID + one-winner sufficient, or does retrieval ALSO need a frozen default config pinned before any forward run (analogous to FORWARD_PREREG)? State yes/no and why.
4. Any NEW issue introduced by the fixes (e.g., snapshot storage growth, candidate-lifecycle for focus words starving the hot-word channel, evidence_class fail-closed breaking legitimate v1 replay flows)?
5. Final: SHIP / REVISE, plus the single most important residual risk.

OUTPUT FORMAT
Findings ranked Blocker/Major/Minor with quoted line + exact replacement; final line SHIP or REVISE + residual risk.
