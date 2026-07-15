# SCRIPT_STATUS: ACTIVE — 2026-07-13 incident recovery: page-receipt ledger (GPT re-review #4 B2)
"""Restoration-proof ledger: coordinator-OWNED page receipts + a hash chain anchored outside the JSONL.

Why counts-and-a-boolean are not proof (GPT re-review #2..#4 B2): an adapter can claim `last_page` for a
lone page 3, hand back arbitrary bytes, or replay one empty receipt twice. This ledger removes every
one of those:

- The COORDINATOR persists each page it is handed (a DataFrame) as an immutable receipt parquet and
  computes its row count + sha256 ITSELF — the adapter's claims are never trusted.
- A frozen, hashed request plan binds each request to its endpoint/params/partition, its OWN receipt
  output path (distinct from any consolidated file — two requests can't "verify" one shared output),
  its natural (null-check) key, its content-dedup key, its page limit, and the signed contract + doc
  hashes; the plan freeze also binds the coordinator commit + the adapter-bundle hash.
- `verify_request` proves CONTIGUOUS page coverage (retries supersede), an endpoint-correct TERMINAL
  (an exact-limit last page demands a following empty page unless the contract defines another proof),
  reconciles pre-dedup / post-dedup / excess-duplicate / null-key counts against the concatenated
  receipts, REJECTS null semantic keys and unexpected duplicates, and binds the per-request output to
  the ordered page hashes.
- Every appended row carries `prev_record_hash`/`record_hash`; the chain HEAD lives in a separate file,
  so a truncated or edited JSONL tail is detected on load (fail closed).

All writes go through the no-follow broker (recovery_write_broker). No network.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path


class LedgerError(RuntimeError):
    pass


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _h(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def request_id(endpoint: str, params: dict, partition: str) -> str:
    return _h(_canon({"e": endpoint, "p": params, "part": partition}))[:24]


def _df_sha256(df) -> tuple[str, int]:
    """Deterministic content hash + row count of a DataFrame (column-sorted, index-dropped)."""
    import pandas as pd  # noqa: F401
    d = df.reindex(sorted(df.columns), axis=1).reset_index(drop=True)
    payload = d.to_json(orient="split", date_format="iso").encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), int(len(d))


# request states; failed is never terminal-valid
_TERMINAL = {"verified", "confirmed_empty"}
_PLAN_REQUIRED = {"request_id", "endpoint", "dataset", "params", "partition", "empty_policy",
                  "receipt_output", "natural_key", "content_dedup_key", "page_limit",
                  "baseline_dups", "contract_sha256", "doc_sha256"}
# a valid terminal claim on the LAST page:
_TERMINALS = {"last_partial",     # rows < page_limit  -> genuine last page
              "empty_terminal",   # a trailing empty page confirmed the end
              "contract_terminal"}  # the signed contract defines another terminal proof (named in the plan)


class PageReceiptLedger:
    def __init__(self, rp, *, coordinator_commit: str, adapter_bundle_hash: str):
        # rp is the coordinator's RecoveryPaths (provides .broker() + run-root paths).
        self.rp = rp
        self.ledger_path = rp.root / "ledger" / "recovery_ledger.jsonl"
        self.plan_path = rp.root / "ledger" / "request_plan.json"
        self.head_path = rp.root / "ledger" / "ledger_chain_head.json"
        self.receipts_dir = rp.root / "ledger" / "page_receipts"
        self.coordinator_commit = coordinator_commit
        self.adapter_bundle_hash = adapter_bundle_hash

    # ── hash chain (head anchored OUTSIDE the editable jsonl) ────────────────────────────────────
    def _genesis(self) -> str:
        return _h(_canon({"run": self.rp.run_id, "commit": self.coordinator_commit,
                          "adapters": self.adapter_bundle_hash}))

    def _read_head(self) -> dict:
        if not self.head_path.exists():
            return {"n": 0, "record_hash": self._genesis()}
        return json.loads(self.head_path.read_text(encoding="utf-8"))

    def _append(self, row: dict) -> None:
        """Under the caller's lock. Chains record_hash off the external head, appends, then advances
        the head file — so a later JSONL edit/truncation breaks the replay."""
        head = self._read_head()
        prev = head["record_hash"]
        rec = {"seq": head["n"] + 1, "at": datetime.now().isoformat(timespec="seconds"),
               "prev_record_hash": prev, **row}
        rec["record_hash"] = _h(prev + _canon({k: v for k, v in rec.items() if k != "record_hash"}))
        p = self.rp.assert_write(self.ledger_path)
        with self.rp.broker().open_for_write(p, "a") as fh:
            fh.write(_canon(rec) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.rp.write_json(self.head_path, {"n": rec["seq"], "record_hash": rec["record_hash"]})

    def _load(self) -> list:
        """Replay + verify the chain from genesis; the recomputed tail MUST equal the head file. Any
        torn line / broken link / head mismatch = fail closed."""
        if not self.ledger_path.exists():
            return []
        rows, prev = [], self._genesis()
        for i, line in enumerate(self.ledger_path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                raise LedgerError(f"ledger torn/malformed at line {i + 1}")
            body = {k: v for k, v in rec.items() if k != "record_hash"}
            if rec.get("prev_record_hash") != prev or rec.get("record_hash") != _h(prev + _canon(body)):
                raise LedgerError(f"ledger hash-chain break at line {i + 1} (tamper/truncation)")
            prev = rec["record_hash"]
            rows.append(rec)
        if self._read_head().get("record_hash") != prev:
            raise LedgerError("ledger head does not match the chain tail (truncated/rewound)")
        return rows

    # ── plan ─────────────────────────────────────────────────────────────────────────────────────
    def freeze_plan(self, plan_rows: list) -> str:
        with self.rp._lock():
            if self.plan_path.exists():
                raise LedgerError("request plan already frozen")
            seen = set()
            outs = {}
            for r in plan_rows:
                if not _PLAN_REQUIRED <= set(r):
                    raise LedgerError(f"plan row missing {_PLAN_REQUIRED - set(r)}")
                if r["request_id"] != request_id(r["endpoint"], r["params"], r["partition"]):
                    raise LedgerError(f"request_id mismatch for {r['request_id']}")
                if r["request_id"] in seen:
                    raise LedgerError(f"duplicate request_id {r['request_id']}")
                if r["empty_policy"] not in ("dense_refuse", "sparse_canary"):
                    raise LedgerError(f"bad empty_policy {r['empty_policy']}")
                # per-request receipt outputs must be UNIQUE (no shared-output cross-verify)
                if r["receipt_output"] in outs:
                    raise LedgerError(f"two requests share receipt_output {r['receipt_output']}")
                outs[r["receipt_output"]] = r["request_id"]
                seen.add(r["request_id"])
            blob = _canon(plan_rows)
            sha = _h(blob)
            self.rp.write_json(self.plan_path, {"sha256": sha, "coordinator_commit": self.coordinator_commit,
                                                "adapter_bundle_hash": self.adapter_bundle_hash, "rows": plan_rows})
            self._append({"kind": "lifecycle", "event": "plan_frozen", "plan_sha256": sha,
                          "coordinator_commit": self.coordinator_commit,
                          "adapter_bundle_hash": self.adapter_bundle_hash, "request_count": len(plan_rows)})
            return sha

    def _plan(self) -> dict:
        if not self.plan_path.exists():
            raise LedgerError("no frozen request plan")
        plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        if _h(_canon(plan["rows"])) != plan["sha256"]:
            raise LedgerError("request plan hash mismatch (tampered)")
        return {r["request_id"]: r for r in plan["rows"]}

    def event(self, name: str, **kw) -> None:
        with self.rp._lock():
            self._load()
            self._append({"kind": "lifecycle", "event": name, **kw})

    # ── page receipts (coordinator-owned) ────────────────────────────────────────────────────────
    def record_page(self, rid: str, page: int, df, *, terminal_claim: str = "") -> None:
        """Persist a fetched page (a DataFrame) as an immutable receipt; the COORDINATOR computes its
        row count + sha256. A retry of the same page supersedes the earlier attempt."""
        with self.rp._lock():
            rows = self._load()
            plan = self._plan()
            if rid not in plan:
                raise LedgerError(f"request {rid} not in the frozen plan")
            if self._state_of(rows, rid) in _TERMINAL:
                raise LedgerError(f"request {rid} already terminal")
            receipt = self.rp.assert_write(self.receipts_dir / rid / f"page_{int(page)}.parquet")
            self.rp.broker().mkdirs(receipt.parent)
            df.reset_index(drop=True).to_parquet(receipt, index=False)
            page_sha, n = _df_sha256(df)
            self._append({"kind": "attempt", "request_id": rid, "endpoint": plan[rid]["endpoint"],
                          "params": plan[rid]["params"], "page": int(page), "row_count": n,
                          "page_sha256": page_sha, "receipt": str(receipt.relative_to(self.rp.root)).replace("\\", "/"),
                          "terminal_claim": terminal_claim})

    def _attempts(self, rows, rid):
        return [r for r in rows if r.get("kind") == "attempt" and r.get("request_id") == rid]

    def _latest_pages(self, rows, rid) -> dict:
        """page -> latest attempt (retry supersession)."""
        out = {}
        for a in self._attempts(rows, rid):
            out[a["page"]] = a  # ledger is ordered, so last wins
        return out

    def _state_of(self, rows, rid):
        st = "planned" if rid in self._plan() else None
        for r in rows:
            if r.get("request_id") != rid:
                continue
            st = r["state"] if r["kind"] == "verdict" else "fetched"
        return st

    # ── verification ─────────────────────────────────────────────────────────────────────────────
    def verify_request(self, rid: str) -> dict:
        """Prove contiguous coverage + terminal + key integrity + output binding; write the per-request
        receipt output; return the evidence. Raises LedgerError on any gap."""
        import pandas as pd
        with self.rp._lock():
            rows = self._load()
            plan = self._plan()
            if rid not in plan:
                raise LedgerError(f"request {rid} not in the frozen plan")
            row = plan[rid]
            pages = self._latest_pages(rows, rid)
            if not pages:
                raise LedgerError(f"{rid}: no page receipts")
            nums = sorted(pages)
            if nums != list(range(1, len(nums) + 1)):
                raise LedgerError(f"{rid}: pages not contiguous 1..N: {nums}")
            limit = int(row["page_limit"]) if row["page_limit"] else 0
            # every page except the last must be FULL (== limit) when a limit applies; the last proves termination
            if limit:
                for p in nums[:-1]:
                    if pages[p]["row_count"] != limit:
                        raise LedgerError(f"{rid}: short page {p} before the end (gap/truncation)")
            last = pages[nums[-1]]
            tc = last.get("terminal_claim")
            if tc not in _TERMINALS:
                raise LedgerError(f"{rid}: last page lacks a valid terminal_claim ({tc})")
            if limit and last["row_count"] == limit and tc == "last_partial":
                raise LedgerError(f"{rid}: exact-limit last page needs a trailing empty page (empty_terminal)")
            # concatenate the receipts, bind ordered page hashes
            ordered_hashes = [pages[p]["page_sha256"] for p in nums]
            frames = [pd.read_parquet(self.rp.root / pages[p]["receipt"]) for p in nums]
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            nk = list(row["natural_key"])
            miss = [k for k in nk if k not in df.columns]
            if miss:
                raise LedgerError(f"{rid}: output missing natural-key columns {miss}")
            null_keys = int(df[nk].isna().any(axis=1).sum()) if nk else 0
            if null_keys:
                raise LedgerError(f"{rid}: {null_keys} rows with a null natural key")
            dk = list(row["content_dedup_key"]) or nk
            pre = int(len(df))
            deduped = df.drop_duplicates(subset=dk)
            post = int(len(deduped))
            excess = pre - post
            if excess and not row["baseline_dups"]:
                raise LedgerError(f"{rid}: {excess} unexpected duplicate rows under {dk} (baseline_dups=False)")
            if pre == 0 and row["empty_policy"] == "dense_refuse":
                raise LedgerError(f"{rid}: dense dataset verified with 0 rows")
            # write the per-request receipt output + hash
            out = self.rp.assert_write(self.rp.staging_data / row["receipt_output"])
            self.rp.broker().mkdirs(out.parent)
            deduped.reset_index(drop=True).to_parquet(out, index=False)
            out_sha, _ = _df_sha256(deduped)
            ev = {"pre_dedup_rows": pre, "post_dedup_rows": post, "excess_dup_rows": excess,
                  "null_key_rows": 0, "ordered_page_hashes": ordered_hashes, "output_sha256": out_sha,
                  "contract_sha256": row["contract_sha256"], "doc_sha256": row["doc_sha256"]}
            self._append({"kind": "verdict", "request_id": rid, "state": "verified", "evidence": ev})
            return ev

    def confirm_empty(self, rid: str, *, canary_request_id: str) -> None:
        with self.rp._lock():
            rows = self._load()
            plan = self._plan()
            if rid not in plan:
                raise LedgerError(f"{rid} not in the frozen plan")
            row = plan[rid]
            if row["empty_policy"] != "sparse_canary":
                raise LedgerError(f"{rid}: dense dataset — an empty result can NEVER be accepted")
            empt = [a for a in self._attempts(rows, rid) if a["row_count"] == 0]
            if len({a["page_sha256"] for a in empt}) < 2:  # DISTINCT empty receipts, not one replayed twice
                raise LedgerError(f"{rid}: confirmed_empty needs >=2 DISTINCT empty page receipts")
            can = plan.get(canary_request_id)
            if not can or can["endpoint"] != row["endpoint"]:
                raise LedgerError(f"{rid}: canary must be a planned SAME-endpoint request")
            if self._state_of(rows, canary_request_id) != "verified" \
                    or not any(a["row_count"] > 0 for a in self._attempts(rows, canary_request_id)):
                raise LedgerError(f"{rid}: canary {canary_request_id} must be verified AND nonempty")
            self._append({"kind": "verdict", "request_id": rid, "state": "confirmed_empty",
                          "canary_request_id": canary_request_id})

    def consolidation_allowed(self, dataset: str):
        rows = self._load()
        plan = self._plan()
        pend = [rid for rid, r in plan.items() if r["dataset"] == dataset
                and self._state_of(rows, rid) not in _TERMINAL]
        return (len(pend) == 0, pend)
