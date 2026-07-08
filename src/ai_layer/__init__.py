"""ai_layer — the LLM-adjacent layer of the MVP re-rank pipeline.

Owner module per CONTRACTS.md C14 for C12 (typed analyst output) and C16
(LLM-score containment). Everything in here that TOUCHES a decision must be
deterministic; LLMs only populate typed annotations upstream. This package is
outside all formal paths (NON-FORMAL research layer) until promoted through
the contract ladder.
"""
