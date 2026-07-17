"""Recovery coordinator v3 battery (GPT recovery re-review #2: B1 containment probes, B3 ledger
transitions, B4 contract-gate negatives, non-finite throttle minor). Everything network-free; test
runs live under pytest tmp_path (override: QUANT_RECOVERY_TEST_ROOT). E: must never be written by
the coordinator."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("rrc", ROOT / "scripts" / "raw_recovery_coordinator.py")
rrc = importlib.util.module_from_spec(_spec)
sys.modules["rrc"] = rrc  # dataclass annotation resolution needs the module in sys.modules pre-exec
_spec.loader.exec_module(rrc)


def _recovery_test_root(sub: str) -> Path:
    """A writable NON-E: root for the recovery batteries.

    NOT pytest tmp_path and NOT tempfile.mkdtemp(): this repo points tmp_path *and* TEMP at
    E:\\量化系统\\workspace\\outputs\\pytest_runtime_tmp, and the coordinator REFUSES every E: write by
    design — that refusal is the invariant under test, so running these there would test nothing.
    Default is the sanctioned C:\\quant_recovery area; set QUANT_RECOVERY_TEST_ROOT to any writable
    non-E: path if that drive is unavailable (GPT re-review #8: a sandboxed reviewer could not write it,
    so the full battery could not serve as passing evidence)."""
    base = Path(os.environ.get("QUANT_RECOVERY_TEST_ROOT") or r"C:\quant_recovery")
    try:
        base.mkdir(parents=True, exist_ok=True)
        probe = base / f".writeprobe_{uuid.uuid4().hex}"
        probe.write_bytes(b"x")
        probe.unlink()
    except OSError as exc:
        pytest.skip(f"recovery test root {base} is not writable ({exc}); set QUANT_RECOVERY_TEST_ROOT to "
                    f"a writable NON-E: path (E: is refused by the coordinator by design)")
    return base / sub / uuid.uuid4().hex


@pytest.fixture()
def crun(monkeypatch):
    """Isolated RECOVERY_ROOT, cleaned up after."""
    base = _recovery_test_root("runs_test")
    monkeypatch.setattr(rrc, "RECOVERY_ROOT", base)
    yield base
    shutil.rmtree(base, ignore_errors=True)


# ── B1: run-id + containment probes (GPT's exact escapes) ────────────────────────────────────────
def test_run_id_traversal_and_special_forms_refused(crun):
    for bad in (r"..\escape", r"..\..\Users\henry\recovery_escape", "..", "a/b", "a\\b",
                "C:abs", r"\\server\share", "con:stream", ".hidden", "a" * 65, ""):
        with pytest.raises(SystemExit, match="REFUSED"):
            rrc.RecoveryPaths(bad)


def test_assert_write_lexical_containment(crun):
    rp = rrc.RecoveryPaths("okrun")
    rp.create_root()
    # inside: ok
    p = rp.assert_write(rp.reports / "x.json")
    assert str(p).startswith(str(rp.root))
    # lexical .. escape refused BEFORE any resolve
    with pytest.raises(RuntimeError, match="outside run root"):
        rp.assert_write(rp.root / ".." / "sibling" / "f.txt")
    # sibling-prefix dir (quant_recovery_evil-style) refused
    with pytest.raises(RuntimeError, match="outside run root"):
        rp.assert_write(Path(str(rp.root) + "_evil") / "f.txt")
    # E: and UNC refused
    with pytest.raises(RuntimeError):
        rp.assert_write(Path(r"E:\量化系统\data\x.parquet"))
    with pytest.raises(RuntimeError, match="outside run root"):
        rp.assert_write(Path(r"\\srv\share\f"))


def test_reparse_point_in_ancestry_refused(crun):
    import _winapi
    rp = rrc.RecoveryPaths("jrun")
    rp.create_root()
    target = rp.root / "realdir"
    target.mkdir()
    junc = rp.root / "junc"
    _winapi.CreateJunction(str(target), str(junc))  # junction INSIDE the run root
    with pytest.raises(RuntimeError, match="reparse point"):
        rp.assert_write(junc / "f.txt")


def test_broken_junction_refused(crun):
    # GPT re-review #3 B3: a BROKEN junction (target missing) — Path.exists() returns False and would
    # SKIP it; os.lstat sees the reparse point and refuses.
    import _winapi
    rp = rrc.RecoveryPaths("brokjunc")
    rp.create_root()
    tgt = rp.root / "tmp_target"
    tgt.mkdir()
    junc = rp.root / "bjunc"
    _winapi.CreateJunction(str(tgt), str(junc))
    tgt.rmdir()  # now the junction is BROKEN (target gone)
    assert junc.exists() is False  # broken -> exists() lies (would SKIP the reparse scan)
    with pytest.raises(RuntimeError, match="reparse point"):
        rp.assert_write(junc / "escaped.txt")


def test_resume_clean_ok_and_tamper_refused(crun):
    rp, led = rrc.open_run("resumerun", new=True)
    # a clean resume re-opens the same run
    rp2, led2 = rrc.open_run("resumerun", new=False)
    assert rp2.run_id == "resumerun"
    # tampering ANY committed row now breaks the hash chain -> resume refuses (stronger than the old
    # run_created-field check; the chain head is anchored outside the jsonl)
    lines = rp.ledger_path.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0]); row["baseline_manifest_sha256"] = "0" * 64
    lines[0] = json.dumps(row)
    rp.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="integrity failed|run_created"):
        rrc.open_run("resumerun", new=False)


def _good_contract(tmp_doc: Path) -> dict:
    return {"doc_path": str(tmp_doc.relative_to(rrc.E_ROOT)), "doc_sha256": rrc.sha256_file(tmp_doc),
            "required_fields": ["ts_code", "trade_date", "close"], "natural_key": ["ts_code", "trade_date"],
            "pagination": "single page per trade_date",
            "pagination_spec": {"mode": "single_page", "page_limit": 0},
            "request_population": _open_sessions_pop("20260702", "20260703"),
            "rate_limit": "500/min@15000pts",
            "cadence": "daily ~16:00 CST", "pit_anchors": "trade_date session-open-knowable",
            "empty_policy": "dense_refuse", "reviewed_by": "henry",
            "reviewed_at": datetime.now(timezone.utc).isoformat()}


def test_contract_gate_rejects_placeholders_and_bad_docs(tmp_path, monkeypatch):
    # run entirely under tmp_path (no writes into the live E: mirror — GPT re-review #3 minor)
    fake_root = tmp_path
    fake_mirror = fake_root / "Tushare数据接口" / "content"
    fake_mirror.mkdir(parents=True)
    monkeypatch.setattr(rrc, "E_ROOT", fake_root)
    monkeypatch.setattr(rrc, "DOC_MIRROR", fake_mirror)

    def _good(doc):
        return {"doc_path": str(doc.relative_to(fake_root)), "doc_sha256": rrc.sha256_file(doc),
                "doc_id": rrc.parse_doc_identity(doc)["doc_id"],
                "required_fields": ["ts_code", "trade_date", "close"], "natural_key": ["ts_code", "trade_date"],
                "pagination": "single page per trade_date",
                "pagination_spec": {"mode": "single_page", "page_limit": 0},
                "request_population": _open_sessions_pop("20260702", "20260703"),
                "rate_limit": "500/min@15000pts",
                "cadence": "daily ~16:00 CST", "pit_anchors": "trade_date session-open-knowable",
                "empty_policy": "dense_refuse", "reviewed_by": "henry",
                "reviewed_at": datetime.now(timezone.utc).isoformat()}

    # a doc WITH a real Tushare-style field table (输出参数 | 名称 | ...) AND its own 接口 declaration
    # (F4: without the 接口 binding the gate cannot prove the doc documents this endpoint)
    _FIELD_DOC = ("# (doc_id=27)  daily interface doc\n接口：daily\n输出参数\n"
                  "| 名称 | 类型 | 默认显示 | 描述 |\n| --- | --- | --- | --- |\n"
                  "| ts_code | str | Y | code |\n| trade_date | str | Y | date |\n| close | float | Y | close |\n")

    # (a) "x"-stuffed contract (GPT's exact probe) — scalar AND list-element placeholders — refuses
    xstuffed = {k: "x" for k in rrc.CONTRACT_REQUIRED}
    xstuffed["required_fields"] = ["x", "x"]
    xstuffed["natural_key"] = ["x"]
    errs = rrc.contract_errors("daily", xstuffed)
    assert errs and any("placeholder" in e for e in errs)
    # (b) a real doc under the mirror whose declared fields cover required_fields/natural_key passes
    doc = fake_mirror / "27_股票日线行情.md"
    doc.write_text(_FIELD_DOC, encoding="utf-8")
    assert rrc.contract_errors("daily", _good(doc)) == []
    # (c) wrong hash / path-escape / future timestamp all refuse
    assert any("mismatch" in e for e in rrc.contract_errors("daily", dict(_good(doc), doc_sha256="0" * 64)))
    assert any("escapes" in e for e in rrc.contract_errors("daily", dict(_good(doc), doc_path="CLAUDE.md")))
    fut = dict(_good(doc), reviewed_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat())
    assert any("future" in e for e in rrc.contract_errors("daily", fut))
    # (d) M2: a FABRICATED required field (not in the doc) refuses — closes GPT re-review #4 M2
    fab = dict(_good(doc), required_fields=["ts_code", "trade_date", "not_a_real_field"])
    assert any("not in doc field list" in e and "not_a_real_field" in e for e in rrc.contract_errors("daily", fab))
    # (e) M2: a natural_key column that is neither a doc field nor derived refuses
    badnk = dict(_good(doc), natural_key=["ts_code", "invented_key"])
    assert any("declared derived fields" in e for e in rrc.contract_errors("daily", badnk))
    # (f) M2/F4: a UNIVERSAL derived stamp is allowed in natural_key...
    okderived = dict(_good(doc), natural_key=["ts_code", "trade_date", "raw_fetch_ts"])
    assert rrc.contract_errors("daily", okderived) == []
    # ...but another endpoint's derived field is NOT (F4: derived fields are endpoint-scoped)
    borrowed = dict(_good(doc), natural_key=["ts_code", "trade_date", "report_rc_payload_digest"])
    assert any("declared derived fields" in e for e in rrc.contract_errors("daily", borrowed))
    # (g) M2: a doc with NO field table (wrong doc cited) refuses — it carries a valid identity header
    # and 接口 binding so it reaches the field-table check rather than failing earlier on doc_id
    emptydoc = fake_mirror / "999_no_table.md"
    emptydoc.write_text("# (doc_id=999)\n接口：daily\njust prose, no field table\n", encoding="utf-8")
    assert any("no field table parsed" in e for e in rrc.contract_errors("daily", _good(emptydoc)))


def test_parse_doc_field_vocabulary_on_real_docs():
    # M2: the parser extracts real vendor fields from the pinned mirror docs (network-free).
    rc = rrc.parse_doc_field_vocabulary(rrc.DOC_MIRROR / "292_券商盈利预测数据.md")
    assert {"ts_code", "report_date", "org_name", "author_name", "quarter"} <= rc
    assert "report_rc_payload_digest" not in rc  # a DERIVED key is never a doc field
    ti = rrc.parse_doc_field_vocabulary(rrc.DOC_MIRROR / "107_龙虎榜机构交易单.md")
    assert {"exalter", "side", "reason", "buy", "sell"} <= ti  # top_inst vendor_record_key columns
    susp = rrc.parse_doc_field_vocabulary(rrc.DOC_MIRROR / "214_每日停复牌信息.md")
    assert {"ts_code", "trade_date", "suspend_type"} <= susp


def test_endpoint_matrix_unique_owner_per_output():
    # M1: every physical output_family is owned by exactly ONE row (no two requests claim one path).
    rrc.assert_unique_output_owner()
    fams = [r.output_family for r in rrc.ENDPOINT_MATRIX]
    assert len(fams) == len(set(fams)), "duplicate output_family"
    # indicators has exactly ONE owner (GPT B2) and it OWNS fundamentals/indicators
    ind = [r for r in rrc.ENDPOINT_MATRIX if r.source_endpoints == ("fina_indicator_vip",)]
    assert len(ind) == 1 and ind[0].owner == "A07" and ind[0].output_family == "fundamentals/indicators"
    # suspend_d feeds TWO DISTINCT output families (yearly suspension + per-date store) — GPT M1 split
    susp = sorted(r.output_family for r in rrc.ENDPOINT_MATRIX if r.source_endpoints == ("suspend_d",))
    assert susp == ["market/suspend_d", "market/suspension"]
    # A01 market/daily draws THREE source endpoints
    a01 = [r for r in rrc.ENDPOINT_MATRIX if r.owner == "A01"][0]
    assert a01.source_endpoints == ("daily", "daily_basic", "adj_factor")
    # event families expect profile-key dups; dense per-date families do not
    ti = [r for r in rrc.ENDPOINT_MATRIX if r.owner == "A11b"][0]
    assert ti.profile_key_dups_expected and "exalter" in ti.vendor_record_key
    a01d = a01
    assert not a01d.profile_key_dups_expected
    # statements carry a PIT version key (a restatement is a NEW row, not a dup)
    inc = [r for r in rrc.ENDPOINT_MATRIX if r.owner == "A03a"][0]
    assert inc.pit_version_key == ("ann_date", "f_ann_date", "update_flag")
    # stk_holdertrade's key INCLUDES change_vol (canonical PIT key) — GPT M1
    hld = [r for r in rrc.ENDPOINT_MATRIX if r.owner == "A12"][0]
    assert "change_vol" in hld.vendor_record_key
    # report_rc identity uses the payload digest, NEVER author_name alone
    rc = [r for r in rrc.ENDPOINT_MATRIX if r.owner == "A14"][0]
    assert "report_rc_payload_digest" in rc.content_dedup_key


def test_matrix_source_endpoints_equal_contract_yaml():
    # M2 reconciliation: the matrix's source-endpoint union MUST equal the contract-YAML key set.
    import yaml
    contracts = yaml.safe_load(rrc.CONTRACTS_YAML.read_text(encoding="utf-8")) or {}
    assert rrc.matrix_source_endpoints() == set(contracts.keys()), (
        "matrix<->contract endpoint drift: "
        f"gap={sorted(rrc.matrix_source_endpoints() - set(contracts))} "
        f"orphan={sorted(set(contracts) - rrc.matrix_source_endpoints())}")


def test_a15_rows_are_wholly_unbound():
    # A15 bucket-A siblings hard-block: UNBOUND callable + UNBOUND query_mode + UNBOUND keys.
    a15 = [r for r in rrc.ENDPOINT_MATRIX if r.owner.startswith("A15_")]
    assert len(a15) == 7
    for r in a15:
        assert r.callable.startswith("UNBOUND") and r.query_mode == "UNBOUND"
        assert r.vendor_record_key == ("UNBOUND",) and r.output_family.startswith("UNBOUND/")


# ── minor: non-finite throttle input ─────────────────────────────────────────────────────────────
def test_spaced_call_rejects_non_finite_base_sleep(tmp_path, monkeypatch):
    import time as _time
    from data_infra import tushare_lock
    lockdir = tmp_path / "locks"
    lockdir.mkdir()
    monkeypatch.setattr(tushare_lock, "_api_lock_dir", lambda: lockdir)
    for bad in (float("nan"), float("inf"), float("-inf"), -5, 0, None):
        t0 = _time.time()
        tushare_lock.spaced_call(lambda: "ok", bad)
        nxt = float(tushare_lock._next_allowed_path().read_text())
        assert nxt - t0 >= tushare_lock.MIN_BASE_SLEEP - 0.05, f"cooldown not floored for {bad!r}"
        tushare_lock._next_allowed_path().unlink()  # isolate iterations (no cross-wait)


def test_spaced_call_rate_limit_backoff_finite(tmp_path, monkeypatch):
    # GPT re-review #3 minor: an inf rate_limit_backoff must NOT persist inf as next-allowed. Drive a
    # rate-limit exception with a non-finite backoff and assert a FINITE cooldown lands.
    from data_infra import tushare_lock
    lockdir = tmp_path / "locks"
    lockdir.mkdir()
    monkeypatch.setattr(tushare_lock, "_api_lock_dir", lambda: lockdir)

    def _boom():
        raise RuntimeError("每分钟最多访问该接口 limit reached")  # matches _is_rate_limit

    for bad in (float("inf"), float("nan"), None):
        with pytest.raises(RuntimeError):
            tushare_lock.spaced_call(_boom, 1.5, rate_limit_backoff=bad)
        import math
        v = float(tushare_lock._next_allowed_path().read_text())
        assert math.isfinite(v), f"rate-limit backoff {bad!r} persisted non-finite next-allowed"
        tushare_lock._next_allowed_path().unlink()


# ── GPT re-review #5 F3: matrix keys BOUND to the production PIT logic ────────────────────────────
# The matrix must never drift from src/data_infra/pit_backend.py DATASET_SPECS (the production
# natural keys the live PIT ledger is built on). GPT found dividends omitting record_date/ex_date/
# pay_date (would COLLAPSE legally distinct dividend records) and the statement content keys omitting
# ann_date. This test is the anti-drift guard, not a one-time fix.
_MATRIX_TO_SPEC = {
    "market/daily": "daily", "market/index": "index_daily", "market/moneyflow": "moneyflow",
    "market/stk_limit": "stk_limit", "market/margin": "margin", "market/northbound": "northbound",
    "market/top_list": "top_list", "market/top_inst": "top_inst", "market/block_trade": "block_trade",
    "market/cyq_perf": "cyq_perf", "fundamentals/income": "income",
    "fundamentals/balancesheet": "balancesheet", "fundamentals/cashflow": "cashflow",
    "fundamentals/income_quarterly": "income_quarterly",
    "fundamentals/cashflow_quarterly": "cashflow_quarterly", "fundamentals/forecast": "forecast",
    "fundamentals/indicators": "indicators", "corporate/dividends": "dividends",
    "corporate/holder_number": "holder_number", "corporate/stk_holdertrade": "stk_holdertrade",
    "analyst/report_rc": "report_rc",
}


def test_matrix_vendor_keys_cover_production_natural_keys():
    """Every matrix vendor_record_key must COVER its production DATASET_SPEC natural_keys (a superset
    is fine — extra columns only make identity finer; a MISSING column collapses real records)."""
    from data_infra.pit_backend import DATASET_SPECS
    rows = {r.output_family: r for r in rrc.ENDPOINT_MATRIX}
    checked = 0
    for fam, spec_name in _MATRIX_TO_SPEC.items():
        row = rows[fam]
        spec = DATASET_SPECS[spec_name]
        prod = set(getattr(spec, "natural_keys", ()) or ())
        assert prod, f"{spec_name} has no production natural_keys"
        missing = prod - set(row.vendor_record_key)
        assert not missing, (f"{fam}: vendor_record_key {row.vendor_record_key} MISSES production "
                             f"natural key column(s) {sorted(missing)} — would collapse distinct records")
        checked += 1
    assert checked == len(_MATRIX_TO_SPEC)


def test_dividends_key_carries_the_settlement_dates():
    """GPT F3 (verified vs pit_backend): dividends identity needs record_date/ex_date/pay_date."""
    row = [r for r in rrc.ENDPOINT_MATRIX if r.output_family == "corporate/dividends"][0]
    for col in ("record_date", "ex_date", "pay_date", "div_proc"):
        assert col in row.vendor_record_key and col in row.content_dedup_key, f"dividends key lost {col}"


def test_statement_content_keys_retain_ann_date():
    """GPT F3: ann_date is visibility-relevant in production statement handling; dropping it from the
    content-dedup key can collapse rows that differ in when they became visible."""
    for fam in ("fundamentals/income", "fundamentals/balancesheet", "fundamentals/cashflow"):
        row = [r for r in rrc.ENDPOINT_MATRIX if r.output_family == fam][0]
        assert "ann_date" in row.content_dedup_key, f"{fam}: content_dedup_key dropped ann_date"


def test_event_families_use_a_lossless_payload_digest():
    """GPT F3: the docs establish no transaction id for top_list/top_inst/block_trade and the
    production key (ts_code,trade_date) is NOT unique, so any hand-picked column set is an unproven
    guess. A lossless row digest makes collapse of a genuinely distinct row impossible."""
    for fam in ("market/top_list", "market/top_inst", "market/block_trade"):
        row = [r for r in rrc.ENDPOINT_MATRIX if r.output_family == fam][0]
        assert "row_payload_digest" in row.vendor_record_key, f"{fam}: no lossless digest in the key"
        assert "row_payload_digest" in row.content_dedup_key
        assert "row_payload_digest" in rrc.derived_fields_for("top_inst")


def test_declared_dup_budgets_are_explicit_ints():
    """The ledger enforces max_content_dups; the matrix must DECLARE it (no boolean free pass)."""
    for r in rrc.ENDPOINT_MATRIX:
        assert isinstance(r.max_content_dups, int) and r.max_content_dups >= 0
        assert isinstance(r.profile_key_dups_expected, bool)


# ── GPT re-review #5 F4: doc<->endpoint binding + endpoint-scoped derived fields ──────────────────
def test_parse_doc_identity_on_real_docs():
    """Every mirrored doc declares its own doc_id + 接口 name; that is what binds it to an endpoint."""
    ident = rrc.parse_doc_identity(rrc.DOC_MIRROR / "107_龙虎榜机构交易单.md")
    assert ident["doc_id"] == "107" and ident["api_name"] == "top_inst"
    ident = rrc.parse_doc_identity(rrc.DOC_MIRROR / "292_券商盈利预测数据.md")
    assert ident["doc_id"] == "292" and ident["api_name"] == "report_rc"
    ident = rrc.parse_doc_identity(rrc.DOC_MIRROR / "103_分红送股数据.md")
    assert ident["api_name"] == "dividend"


def test_every_matrix_source_endpoint_has_a_resolvable_doc():
    """Each of the 32 source endpoints must have exactly one mirror doc that DECLARES it — otherwise
    its contract can never be proven to cite the right document."""
    docs = {}
    for f in rrc.DOC_MIRROR.glob("*.md"):
        api = rrc.parse_doc_identity(f)["api_name"]
        if api:
            docs.setdefault(api, []).append(f.name)
    unresolved = [ep for ep in rrc.matrix_source_endpoints()
                  if not any(rrc.doc_declares_endpoint(a, ep) for a in docs)]
    assert not unresolved, f"no doc declares these endpoints: {sorted(unresolved)}"


def test_wrong_doc_for_endpoint_refused(tmp_path, monkeypatch):
    """GPT F4 (reproduced): a REAL, correctly-hashed doc with a valid field table — but for ANOTHER
    API — used to approve the contract. The 接口 binding now refuses it."""
    fake_root = tmp_path
    fake_mirror = fake_root / "Tushare数据接口" / "content"
    fake_mirror.mkdir(parents=True)
    monkeypatch.setattr(rrc, "E_ROOT", fake_root)
    monkeypatch.setattr(rrc, "DOC_MIRROR", fake_mirror)
    # a genuine-looking doc for top_inst (valid table, declares 接口：top_inst)
    doc = fake_mirror / "107_龙虎榜机构交易单.md"
    doc.write_text("# (doc_id=107)\n接口：top_inst\n输出参数\n| 名称 | 类型 | 默认显示 | 描述 |\n"
                   "| --- | --- | --- | --- |\n| ts_code | str | Y | code |\n"
                   "| trade_date | str | Y | date |\n| exalter | str | Y | branch |\n", encoding="utf-8")
    base = {"doc_path": str(doc.relative_to(fake_root)), "doc_sha256": rrc.sha256_file(doc),
            "doc_id": "107",
            "required_fields": ["ts_code", "trade_date", "exalter"], "natural_key": ["ts_code", "trade_date"],
            "pagination": "single page per trade_date",
            "pagination_spec": {"mode": "single_page", "page_limit": 0},
            "request_population": _open_sessions_pop("20260702", "20260703"),
            "rate_limit": "500/min@15000pts",
            "cadence": "daily ~16:00 CST", "pit_anchors": "trade_date session-open-knowable",
            "empty_policy": "sparse_canary", "reviewed_by": "henry",
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    # cited for the endpoint it actually documents -> passes
    assert rrc.contract_errors("top_inst", base) == []
    # the SAME valid doc cited for a DIFFERENT endpoint -> refused
    errs = rrc.contract_errors("moneyflow", base)
    assert any("WRONG doc cited" in e and "top_inst" in e for e in errs), errs


def test_omitted_doc_id_refused(tmp_path, monkeypatch):
    """GPT re-review #6 F4 (reproduced): doc_id was OPTIONAL, so a valid contract that simply OMITTED it
    skipped the binding check and produced no errors. It is REQUIRED now."""
    fake_root = tmp_path
    fake_mirror = fake_root / "Tushare\u6570\u636e\u63a5\u53e3" / "content"
    fake_mirror.mkdir(parents=True)
    monkeypatch.setattr(rrc, "E_ROOT", fake_root)
    monkeypatch.setattr(rrc, "DOC_MIRROR", fake_mirror)
    doc = fake_mirror / "107_x.md"
    doc.write_text("# (doc_id=107)\n\u63a5\u53e3\uff1atop_inst\n| \u540d\u79f0 | \u7c7b\u578b |\n| --- | --- |\n"
                   "| ts_code | str |\n| trade_date | str |\n", encoding="utf-8")
    c = {"doc_path": str(doc.relative_to(fake_root)), "doc_sha256": rrc.sha256_file(doc),
         "required_fields": ["ts_code", "trade_date"], "natural_key": ["ts_code", "trade_date"],
         "pagination": "single",
         "pagination_spec": {"mode": "single_page", "page_limit": 0},
         "request_population": _open_sessions_pop("20260702", "20260703"),
         "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
         "empty_policy": "sparse_canary", "reviewed_by": "henry",
         "reviewed_at": datetime.now(timezone.utc).isoformat()}   # NO doc_id
    assert "doc_id" in rrc.CONTRACT_REQUIRED
    assert any("doc_id missing" in e for e in rrc.contract_errors("top_inst", c))


def test_doc_id_mismatch_refused(tmp_path, monkeypatch):
    fake_root = tmp_path
    fake_mirror = fake_root / "Tushare数据接口" / "content"
    fake_mirror.mkdir(parents=True)
    monkeypatch.setattr(rrc, "E_ROOT", fake_root)
    monkeypatch.setattr(rrc, "DOC_MIRROR", fake_mirror)
    doc = fake_mirror / "107_x.md"
    doc.write_text("# (doc_id=107)\n接口：top_inst\n| 名称 | 类型 |\n| --- | --- |\n"
                   "| ts_code | str |\n| trade_date | str |\n", encoding="utf-8")
    c = {"doc_path": str(doc.relative_to(fake_root)), "doc_sha256": rrc.sha256_file(doc), "doc_id": "999",
         "required_fields": ["ts_code", "trade_date"], "natural_key": ["ts_code", "trade_date"],
         "pagination": "single",
         "pagination_spec": {"mode": "single_page", "page_limit": 0},
         "request_population": _open_sessions_pop("20260702", "20260703"),
         "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
         "empty_policy": "sparse_canary", "reviewed_by": "henry",
         "reviewed_at": datetime.now(timezone.utc).isoformat()}
    assert any("doc_id 999" in e for e in rrc.contract_errors("top_inst", c))


def test_derived_fields_are_endpoint_scoped(tmp_path, monkeypatch):
    """GPT F4: the global allowlist let ANY endpoint key on ANY derived field. report_rc's payload
    digest must not be keyable on `daily`."""
    assert "report_rc_payload_digest" in rrc.derived_fields_for("report_rc")
    assert "report_rc_payload_digest" not in rrc.derived_fields_for("daily")
    assert "row_payload_digest" in rrc.derived_fields_for("top_inst")
    assert "row_payload_digest" not in rrc.derived_fields_for("income")
    # universal ingest stamps stay available everywhere, with declared provenance
    for ep in ("daily", "report_rc", "income"):
        assert "raw_fetch_ts" in rrc.derived_fields_for(ep)
    for m in (rrc._DERIVED_UNIVERSAL, *rrc._DERIVED_BY_ENDPOINT.values()):
        for fld, prov in m.items():
            assert isinstance(prov, str) and len(prov) > 20, f"{fld} lacks a provenance statement"


def test_borrowed_derived_field_in_natural_key_refused(tmp_path, monkeypatch):
    fake_root = tmp_path
    fake_mirror = fake_root / "Tushare数据接口" / "content"
    fake_mirror.mkdir(parents=True)
    monkeypatch.setattr(rrc, "E_ROOT", fake_root)
    monkeypatch.setattr(rrc, "DOC_MIRROR", fake_mirror)
    doc = fake_mirror / "27_daily.md"
    doc.write_text("# (doc_id=27)\n接口：daily\n输出参数\n| 名称 | 类型 |\n| --- | --- |\n"
                   "| ts_code | str |\n| trade_date | str |\n| close | float |\n", encoding="utf-8")
    c = {"doc_path": str(doc.relative_to(fake_root)), "doc_sha256": rrc.sha256_file(doc),
         "doc_id": "27",
         "required_fields": ["ts_code", "trade_date", "close"],
         "natural_key": ["ts_code", "trade_date", "report_rc_payload_digest"],  # borrowed from report_rc
         "pagination": "single",
         "pagination_spec": {"mode": "single_page", "page_limit": 0},
         "request_population": _open_sessions_pop("20260702", "20260703"),
         "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
         "empty_policy": "dense_refuse", "reviewed_by": "henry",
         "reviewed_at": datetime.now(timezone.utc).isoformat()}
    errs = rrc.contract_errors("daily", c)
    assert any("report_rc_payload_digest" in e and "declared derived fields" in e for e in errs), errs


# ── GPT re-review #7 B7 + minors: output-only fields, explicit aliases, real signatures ────────────
def _mk_doc(mirror, name, body):
    d = mirror / name
    d.write_text(body, encoding="utf-8")
    return d


def _io_doc(api, doc_id):
    """A doc whose INPUT table declares trade_date and whose OUTPUT table does NOT."""
    return (f"# (doc_id={doc_id})\n\u63a5\u53e3\uff1a{api}\n"
            "\u8f93\u5165\u53c2\u6570\n| \u540d\u79f0 | \u7c7b\u578b | \u5fc5\u9009 |\n| --- | --- | --- |\n"
            "| trade_date | str | Y |\n\n"
            "\u8f93\u51fa\u53c2\u6570\n| \u540d\u79f0 | \u7c7b\u578b | \u9ed8\u8ba4\u663e\u793a |\n| --- | --- | --- |\n"
            "| ts_code | str | Y |\n| exalter | str | Y |\n")


def test_input_only_field_cannot_be_a_natural_key(tmp_path, monkeypatch):
    """GPT re-review #7 B7 (reproduced): the parser UNIONED input and output tables, so a column that
    is only a QUERY PARAMETER passed as a natural_key. A row-identity key must name a column the
    RESPONSE actually contains."""
    fake_root = tmp_path
    mirror = fake_root / "Tushare\u6570\u636e\u63a5\u53e3" / "content"
    mirror.mkdir(parents=True)
    monkeypatch.setattr(rrc, "E_ROOT", fake_root)
    monkeypatch.setattr(rrc, "DOC_MIRROR", mirror)
    doc = _mk_doc(mirror, "107_x.md", _io_doc("top_inst", 107))
    fields = rrc.parse_doc_fields(doc)
    assert fields["output"] == {"ts_code", "exalter"} and "trade_date" in fields["input"]
    assert "trade_date" not in fields["output"], "input parameter leaked into the output vocabulary"
    base = {"doc_path": str(doc.relative_to(fake_root)), "doc_id": "107", "doc_sha256": rrc.sha256_file(doc),
            "required_fields": ["ts_code", "exalter"], "natural_key": ["ts_code", "trade_date"],
            "pagination": "single",
         "pagination_spec": {"mode": "single_page", "page_limit": 0},
         "request_population": _open_sessions_pop("20260702", "20260703"),
         "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
            "empty_policy": "sparse_canary", "reviewed_by": "henry",
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    assert any("trade_date" in e for e in rrc.contract_errors("top_inst", base))
    assert rrc.contract_errors("top_inst", dict(base, natural_key=["ts_code", "exalter"])) == []


def test_required_fields_cannot_vouch_for_a_natural_key(tmp_path, monkeypatch):
    """A fabricated required field must not authorize the same fabricated natural-key column."""
    fake_root = tmp_path
    mirror = fake_root / "Tushare\u6570\u636e\u63a5\u53e3" / "content"
    mirror.mkdir(parents=True)
    monkeypatch.setattr(rrc, "E_ROOT", fake_root)
    monkeypatch.setattr(rrc, "DOC_MIRROR", mirror)
    doc = _mk_doc(mirror, "107_x.md", _io_doc("top_inst", 107))
    c = {"doc_path": str(doc.relative_to(fake_root)), "doc_id": "107", "doc_sha256": rrc.sha256_file(doc),
         "required_fields": ["ts_code", "made_up"], "natural_key": ["ts_code", "made_up"],
         "pagination": "single",
         "pagination_spec": {"mode": "single_page", "page_limit": 0},
         "request_population": _open_sessions_pop("20260702", "20260703"),
         "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
         "empty_policy": "sparse_canary", "reviewed_by": "henry",
         "reviewed_at": datetime.now(timezone.utc).isoformat()}
    errs = rrc.contract_errors("top_inst", c)
    assert any("required_fields not in doc field list" in e for e in errs)
    assert any("natural_key columns not in doc field list" in e for e in errs), \
        "a fabricated required field vouched for the natural key"


def test_vip_aliases_are_explicit_not_a_suffix_strip():
    """GPT re-review #7 B7: a generic `_vip` strip let ANY <x>_vip claim <x>'s doc. Aliases must be an
    explicit reviewed map."""
    assert rrc.doc_declares_endpoint("income", "income_vip") is True      # declared alias
    assert rrc.doc_declares_endpoint("income", "income") is True
    assert rrc.doc_declares_endpoint("daily", "daily_vip") is False       # never reviewed -> refuse
    assert rrc.doc_declares_endpoint("moneyflow", "top_inst") is False
    for ep, base in rrc._DOC_ALIASES.items():
        assert ep.endswith("_vip") and base == ep[:-4]


def test_reviewed_at_must_be_timezone_aware_and_signer_recognized(tmp_path, monkeypatch):
    """GPT re-review #7 minors: a NAIVE reviewed_at was silently assumed UTC; reviewed_by accepted
    'xxx' because it merely checked length >= 3."""
    fake_root = tmp_path
    mirror = fake_root / "Tushare\u6570\u636e\u63a5\u53e3" / "content"
    mirror.mkdir(parents=True)
    monkeypatch.setattr(rrc, "E_ROOT", fake_root)
    monkeypatch.setattr(rrc, "DOC_MIRROR", mirror)
    doc = _mk_doc(mirror, "107_x.md", _io_doc("top_inst", 107))
    good = {"doc_path": str(doc.relative_to(fake_root)), "doc_id": "107", "doc_sha256": rrc.sha256_file(doc),
            "required_fields": ["ts_code", "exalter"], "natural_key": ["ts_code", "exalter"],
            "pagination": "single",
         "pagination_spec": {"mode": "single_page", "page_limit": 0},
         "request_population": _open_sessions_pop("20260702", "20260703"),
         "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
            "empty_policy": "sparse_canary", "reviewed_by": "henry",
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
    assert rrc.contract_errors("top_inst", good) == []
    naive = dict(good, reviewed_at=datetime.now().replace(tzinfo=None).isoformat())
    assert any("timezone-AWARE" in e for e in rrc.contract_errors("top_inst", naive))
    # "xxx" is refused as a placeholder (caught earlier); either refusal is correct, but it MUST refuse
    xxx_errs = rrc.contract_errors("top_inst", dict(good, reviewed_by="xxx"))
    assert any("reviewed_by" in e for e in xxx_errs), xxx_errs
    # an unrecognized but non-placeholder name must still refuse — a signature names a REAL reviewer
    assert any("not a recognized signer" in e for e in rrc.contract_errors("top_inst",
                                                                           dict(good, reviewed_by="somebody")))


# ── GPT re-review #7 F3: typed pagination/population + plan<->contract binding ────────────────────
def _signed(doc, fake_root, **over):
    c = {"doc_path": str(doc.relative_to(fake_root)), "doc_id": "107", "doc_sha256": rrc.sha256_file(doc),
         "required_fields": ["ts_code", "exalter"], "natural_key": ["ts_code", "exalter"],
         "pagination": "one page per trade_date",
         "pagination_spec": {"mode": "single_page", "page_limit": 0},
         "request_population": _open_sessions_pop("20260702", "20260703"),
         "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
         "empty_policy": "sparse_canary", "reviewed_by": "henry",
         "reviewed_at": datetime.now(timezone.utc).isoformat()}
    c.update(over)
    return c


def test_pagination_must_be_a_typed_spec_not_prose(tmp_path, monkeypatch):
    """GPT re-review #7 F3: `pagination` was free-form prose while the ledger independently received
    pagination_mode/page_limit — nothing proved execution matched what the human signed."""
    fake_root = tmp_path
    mirror = fake_root / "Tushare\u6570\u636e\u63a5\u53e3" / "content"
    mirror.mkdir(parents=True)
    monkeypatch.setattr(rrc, "E_ROOT", fake_root)
    monkeypatch.setattr(rrc, "DOC_MIRROR", mirror)
    doc = _mk_doc(mirror, "107_x.md", _io_doc("top_inst", 107))
    assert "pagination_spec" in rrc.CONTRACT_REQUIRED and "request_population" in rrc.CONTRACT_REQUIRED
    assert rrc.contract_errors("top_inst", _signed(doc, fake_root)) == []
    # prose where a typed spec belongs
    bad = _signed(doc, fake_root, pagination_spec="offset to cap=3000")
    assert any("typed mapping" in e for e in rrc.contract_errors("top_inst", bad))
    # internally inconsistent typed specs
    assert any("single_page requires page_limit == 0" in e for e in rrc.contract_errors(
        "top_inst", _signed(doc, fake_root, pagination_spec={"mode": "single_page", "page_limit": 3000})))
    assert any("POSITIVE page_limit" in e for e in rrc.contract_errors(
        "top_inst", _signed(doc, fake_root,
                            pagination_spec={"mode": "offset_paged", "page_limit": 0,
                                             "offset_param": "offset"})))
    assert any("offset_param" in e for e in rrc.contract_errors(
        "top_inst", _signed(doc, fake_root, pagination_spec={"mode": "offset_paged", "page_limit": 3000})))
    # population must be typed AND executable AND set-pinned (GPT re-review #10: `source` was prose)
    assert any("typed mapping" in e for e in rrc.contract_errors(
        "top_inst", _signed(doc, fake_root, request_population="every trading day")))
    errs = rrc.contract_errors("top_inst", _signed(doc, fake_root,
                                                   request_population={"resolver": "trade_cal_open_sessions"}))
    assert any("bounds must state the selection rule" in e for e in errs), errs
    assert any("expected_set_sha256 must pin the COMPLETE REQUEST SET" in e for e in errs), errs


def test_frozen_plan_pagination_must_match_the_signature(signed):
    """The ledger receives pagination_mode/page_limit independently; they MUST equal what was signed.
    (Rewritten for GPT re-review #8: the original drove the comparator with a synthetic contract that
    carried ONLY the two compared fields — which is exactly the hole #8 found, so it now refuses as an
    invalid signature. A drift probe must start from a genuinely VALID signed contract.)"""
    fake_root, mirror, cs, hashes = signed
    rrc.assert_plan_matches_contracts(_a01_plan(hashes, cs_map=cs), cs)      # baseline: clean
    drift_mode = _a01_plan(hashes, cs_map=cs)
    drift_mode[0] = dict(drift_mode[0], pagination_mode="offset_paged")
    with pytest.raises(RuntimeError, match="pagination_mode .* != signed"):
        rrc.assert_plan_matches_contracts(drift_mode, cs)
    drift_limit = _a01_plan(hashes, cs_map=cs)
    drift_limit[0] = dict(drift_limit[0], page_limit=3000)
    with pytest.raises(RuntimeError, match="page_limit .* != signed"):
        rrc.assert_plan_matches_contracts(drift_limit, cs)
    with pytest.raises(RuntimeError, match="NOT a valid signature"):
        rrc.assert_plan_matches_contracts(_a01_plan(hashes, cs_map=cs), {})   # unsigned cannot back a plan


def test_plan_population_resolver_must_match_the_matrix_query_mode(signed):
    """A contract resolving MONTHS while the matrix enumerates trading days is a coverage lie."""
    fake_root, mirror, cs, hashes = signed
    months = {"resolver": "calendar_months", "bounds": {"start": "202607", "end": "202607"}}
    months["expected_set_sha256"] = rrc.request_set_sha256(rrc.resolve_population(months))
    wrong = {ep: (dict(c, request_population=months) if ep == "daily" else c) for ep, c in cs.items()}
    h = {ep: rrc.canonical_contract_sha256(c) for ep, c in wrong.items()}
    with pytest.raises(RuntimeError, match="resolves via|DIFFERENT request_population"):
        rrc.assert_plan_matches_contracts(_a01_plan(h, cs_map=wrong), wrong)


def test_every_matrix_query_mode_has_a_population_unit():
    """A query_mode with no declared unit could never be matched by any signed contract."""
    modes = {r.query_mode for r in rrc.ENDPOINT_MATRIX if r.query_mode != "UNBOUND"}
    missing = [q for q in modes if q not in rrc._QUERY_MODE_TO_UNIT]
    assert not missing, f"query_modes with no population unit: {missing}"
    assert set(rrc._QUERY_MODE_TO_UNIT.values()) <= rrc._POPULATION_UNITS


# ── GPT re-review #8 BLOCKER-1: the plan must be bound to a VALID, SIGNED contract ─────────────────
def _cal_sha() -> str:
    """The reference bytes a population is PINNED to (GPT: resolving against LIVE reference data would
    force re-signing on every calendar refresh)."""
    return rrc.sha256_file(rrc.E_DATA / "reference" / "trade_cal.parquet")


def _open_sessions_pop(start: str, end: str) -> dict:
    """A SIGNED population: an executable resolver + bounds (incl. the pinned reference sha) + the
    sha256 of the COMPLETE REQUESTS that resolve — not a member list (GPT sign-off HOLD)."""
    spec = {"resolver": "trade_cal_open_sessions",
            "bounds": {"start": start, "end": end, "exchange": "SSE", "reference_sha256": _cal_sha()}}
    spec["expected_set_sha256"] = rrc.request_set_sha256(rrc.resolve_population(spec))
    return spec


def _valid_contract(mirror, fake_root, api="daily", doc_id="27", pop=None):
    body = (f"# (doc_id={doc_id})\n\u63a5\u53e3\uff1a{api}\n"
            "\u8f93\u51fa\u53c2\u6570\n| \u540d\u79f0 | \u7c7b\u578b |\n| --- | --- |\n"
            "| ts_code | str |\n| trade_date | str |\n| close | float |\n")
    doc = mirror / f"{doc_id}_{api}.md"
    doc.write_text(body, encoding="utf-8")
    return {"doc_path": str(doc.relative_to(fake_root)), "doc_id": doc_id,
            "doc_sha256": rrc.sha256_file(doc),
            "required_fields": ["ts_code", "trade_date", "close"],
            "natural_key": ["ts_code", "trade_date"], "pagination": "one page per trade_date",
            "pagination_spec": {"mode": "single_page", "page_limit": 0},
            "request_population": pop or _open_sessions_pop("20260702", "20260703"),
            "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
            "empty_policy": "dense_refuse", "reviewed_by": "henry",
            "reviewed_at": datetime.now(timezone.utc).isoformat()}


def _prow(rid, ep, part, chash, dataset="market/daily", c=None, params=None):
    row = [r for r in rrc.ENDPOINT_MATRIX if r.output_family == dataset][0]
    return {"request_id": rid, "endpoint": ep, "dataset": dataset, "partition": part,
            "params": params if params is not None else {"trade_date": part},
            "pagination_mode": "single_page", "page_limit": 0, "contract_sha256": chash,
            "empty_policy": (c or {}).get("empty_policy", "dense_refuse"),
            "doc_sha256": (c or {}).get("doc_sha256", ""),
            "natural_key": list((c or {}).get("natural_key", [])),
            "content_dedup_key": list(row.content_dedup_key),
            "max_content_dups": row.max_content_dups}


@pytest.fixture()
def signed(tmp_path, monkeypatch):
    fake_root = tmp_path
    mirror = fake_root / "Tushare\u6570\u636e\u63a5\u53e3" / "content"
    mirror.mkdir(parents=True)
    monkeypatch.setattr(rrc, "E_ROOT", fake_root)
    monkeypatch.setattr(rrc, "DOC_MIRROR", mirror)
    cs = {ep: _valid_contract(mirror, fake_root, api=ep, doc_id=str(27 + i))
          for i, ep in enumerate(("daily", "daily_basic", "adj_factor"))}
    hashes = {ep: rrc.canonical_contract_sha256(c) for ep, c in cs.items()}
    return fake_root, mirror, cs, hashes


def _a01_plan(hashes, parts=("20260702", "20260703"), per_ep=None, cs_map=None):
    rows = []
    for ep in ("daily", "daily_basic", "adj_factor"):
        for pt in (per_ep or {}).get(ep, parts):
            rows.append(_prow(f"{ep}:{pt}", ep, pt, hashes[ep], c=cs_map[ep] if cs_map else None))
    return rows


def test_plan_backed_by_an_unsigned_contract_refused(signed):
    """GPT re-review #8 BLOCKER-1 (reproduced): assert_plan_matches_contracts compared only the
    pagination axis and the population unit — it never called contract_errors, so a plan backed by a
    contract with NO doc / NO signer / NO field constraints was ACCEPTED. Checking two fields of a
    contract is not checking the contract."""
    fake_root, mirror, cs, hashes = signed
    rrc.assert_plan_matches_contracts(_a01_plan(hashes, cs_map=cs), cs)      # fully signed -> clean
    # a contract that merely carries the two compared fields, and nothing else
    naked = {"pagination_spec": {"mode": "single_page", "page_limit": 0},
             "request_population": _open_sessions_pop("20260702", "20260702")}
    bad = dict(cs, daily=naked)
    with pytest.raises(RuntimeError, match="NOT a valid signature"):
        rrc.assert_plan_matches_contracts(_a01_plan(hashes, cs_map=cs), bad)
    # an unsigned reviewer / stale doc hash must also refuse
    with pytest.raises(RuntimeError, match="NOT a valid signature"):
        rrc.assert_plan_matches_contracts(_a01_plan(hashes, cs_map=cs),
                                          dict(cs, daily=dict(cs["daily"], reviewed_by="somebody")))


def test_plan_contract_sha256_must_match_the_signed_contract(signed):
    """The plan carries a contract_sha256 that NOTHING checked — a plan could be bound to a contract
    that is not the one on disk."""
    fake_root, mirror, cs, hashes = signed
    tampered = _a01_plan(hashes, cs_map=cs)
    tampered[0] = dict(tampered[0], contract_sha256="0" * 64)
    with pytest.raises(RuntimeError, match="contract_sha256 .* != the canonical hash"):
        rrc.assert_plan_matches_contracts(tampered, cs)
    # editing the signed contract after the plan froze changes its identity -> every bound row refuses
    edited = dict(cs, daily=dict(cs["daily"], cadence="hourly"))
    with pytest.raises(RuntimeError, match="contract_sha256 .* != the canonical hash"):
        rrc.assert_plan_matches_contracts(_a01_plan(hashes, cs_map=cs), edited)


def test_a01_legs_on_different_trade_dates_refused(signed):
    """GPT re-review #8 BLOCKER-1 (reproduced): 'A01 三来源分别使用不同交易日的计划' was ACCEPTED.
    _QUERY_MODE_TO_UNIT proves CATEGORY consistency, never COVERAGE or MERGE consistency."""
    fake_root, mirror, cs, hashes = signed
    skewed = _a01_plan(hashes, cs_map=cs, per_ep={"daily": ("20260702", "20260703"),
                                       "daily_basic": ("20260702",),           # missing a session
                                       "adj_factor": ("20260702", "20260703")})
    with pytest.raises(RuntimeError, match="signed REQUESTS|missing"):
        rrc.assert_plan_matches_contracts(skewed, cs)
    # a leg on an entirely different session
    disjoint = _a01_plan(hashes, cs_map=cs, per_ep={"daily": ("20260702",), "daily_basic": ("20260703",),
                                         "adj_factor": ("20260702",)})
    with pytest.raises(RuntimeError, match="signed REQUESTS|missing"):
        rrc.assert_plan_matches_contracts(disjoint, cs)


def test_a01_missing_source_leg_refused(signed):
    fake_root, mirror, cs, hashes = signed
    rows = [r for r in _a01_plan(hashes, cs_map=cs) if r["endpoint"] != "adj_factor"]   # a whole leg omitted
    with pytest.raises(RuntimeError, match="omits source leg"):
        rrc.assert_plan_matches_contracts(rows, cs)


def test_a01_legs_must_share_one_population_snapshot(signed):
    """The legs of a merged output must be fetched over ONE population snapshot — a leg signing
    different bounds is a different snapshot even though the resolver matches."""
    fake_root, mirror, cs, hashes = signed
    cs2 = dict(cs, adj_factor=_valid_contract(mirror, fake_root, api="adj_factor", doc_id="29",
                                              pop=_open_sessions_pop("20260702", "20260706")))
    h2 = {ep: rrc.canonical_contract_sha256(c) for ep, c in cs2.items()}
    with pytest.raises(RuntimeError, match="DIFFERENT request_population|signed REQUESTS"):
        rrc.assert_plan_matches_contracts(_a01_plan(h2, cs_map=cs2), cs2)


def test_multi_source_rows_declare_an_explicit_merge_rule():
    """A merged output must state HOW it joins — implied is not machine-checkable."""
    multi = [r for r in rrc.ENDPOINT_MATRIX if len(r.source_endpoints) > 1]
    assert multi, "expected at least A01"
    for r in multi:
        assert isinstance(r.merge_spec, dict) and r.merge_spec.get("join_on"), \
            f"{r.output_family} draws {len(r.source_endpoints)} sources with no merge_spec.join_on"
        assert r.merge_spec.get("base") in r.source_endpoints


def test_freeze_request_plan_is_the_single_door(signed):
    """Validate-then-freeze in ONE call: contract validity, canonical hash, population and merge
    coverage cannot be skipped by calling the ledger's freeze_plan directly from recovery code."""
    fake_root, mirror, cs, hashes = signed
    calls = {"n": 0}

    class _FakeLedger:
        contract_loader = None

        def _freeze_plan_unvalidated(self, rows):
            calls["n"] += 1
            return "planhash"

    assert rrc.freeze_request_plan(_FakeLedger(), _a01_plan(hashes, cs_map=cs), cs) == "planhash"
    assert calls["n"] == 1
    naked = {"pagination_spec": {"mode": "single_page", "page_limit": 0},
             "request_population": _open_sessions_pop("20260702", "20260702")}
    with pytest.raises(RuntimeError, match="NOT a valid signature"):
        rrc.freeze_request_plan(_FakeLedger(), _a01_plan(hashes, cs_map=cs), dict(cs, daily=naked))
    assert calls["n"] == 1, "an invalid plan reached the ledger's freeze_plan"


# ── GPT re-review #9 BLOCKER-1/2: the plan must IMPLEMENT its contract; coverage reads PARAMS ─────
def test_plan_must_implement_the_contract_not_merely_cite_it(signed):
    """GPT re-review #9 BLOCKER-1 (reproduced): the hash proved the contract was UNCHANGED, never that
    the PLAN IMPLEMENTS IT — a fully valid contract was accepted beside a plan that changed
    empty_policy, natural_key and doc_sha256."""
    fake_root, mirror, cs, hashes = signed
    rrc.assert_plan_matches_contracts(_a01_plan(hashes, cs_map=cs), cs)      # baseline clean
    for field, bad in (("empty_policy", "sparse_canary"), ("doc_sha256", "0" * 64)):
        rows = _a01_plan(hashes, cs_map=cs)
        rows[0] = dict(rows[0], **{field: bad})
        with pytest.raises(RuntimeError, match=f"{field}.*!= signed|does not implement its contract"):
            rrc.assert_plan_matches_contracts(rows, cs)
    rows = _a01_plan(hashes, cs_map=cs)
    rows[0] = dict(rows[0], natural_key=["ts_code"])          # narrower than signed
    with pytest.raises(RuntimeError, match="natural_key .* != signed"):
        rrc.assert_plan_matches_contracts(rows, cs)


def test_a01_coverage_reads_request_params_not_the_partition_label(signed):
    """GPT re-review #9 BLOCKER-2 (reproduced): coverage compared only the `partition` LABEL, so a plan
    where every leg CLAIMED 20260702 while daily_basic actually requested 20260703 was accepted."""
    fake_root, mirror, cs, hashes = signed
    rows = _a01_plan(hashes, cs_map=cs, parts=("20260702",))
    # the label still says 20260702; the REQUEST asks for 20260703
    for i, r in enumerate(rows):
        if r["endpoint"] == "daily_basic":
            rows[i] = dict(r, params={"trade_date": "20260703"})
    with pytest.raises(RuntimeError, match="partition label .* but the request asks for"):
        rrc.assert_plan_matches_contracts(rows, cs)


def test_legs_requesting_different_sessions_refused_even_with_honest_labels(signed):
    fake_root, mirror, cs, hashes = signed
    rows = [r for r in _a01_plan(hashes, cs_map=cs, parts=("20260702",)) if r["endpoint"] != "daily_basic"]
    rows.append(_prow("daily_basic:20260703", "daily_basic", "20260703", hashes["daily_basic"],
                      c=cs["daily_basic"]))
    with pytest.raises(RuntimeError, match="signed REQUESTS|missing"):
        rrc.assert_plan_matches_contracts(rows, cs)


def test_plan_row_without_params_refused(signed):
    fake_root, mirror, cs, hashes = signed
    rows = _a01_plan(hashes, cs_map=cs, parts=("20260702",))
    rows[0] = dict(rows[0], params={})
    with pytest.raises(RuntimeError, match="no params"):
        rrc.assert_plan_matches_contracts(rows, cs)


def test_freeze_door_installs_a_LIVE_contract_loader(signed):
    """The loader must read the LIVE contracts, never a snapshot taken at freeze — a snapshot would be
    compared against my own frozen copy and could never detect the edit it exists to catch."""
    fake_root, mirror, cs, hashes = signed
    class _FakeLedger:
        contract_loader = None
        def _freeze_plan_unvalidated(self, rows):
            return "ph"

    L = _FakeLedger()
    rrc.freeze_request_plan(L, _a01_plan(hashes, cs_map=cs), cs)
    assert L.contract_loader is rrc.load_signed_contracts


# ── GPT re-review #10 BLOCKER-1: the population must be CORRECT, not merely agreed ────────────────
def test_a_sunday_is_refused_against_the_real_trade_calendar(signed):
    """GPT re-review #10 (reproduced): ALL A01 legs using a Sunday passed while the contract claimed
    'trade_cal open sessions'. Coverage proved the legs agreed with EACH OTHER — never that they
    covered the correct set. `source` was unenforced prose; no calendar check existed."""
    fake_root, mirror, cs, hashes = signed
    # 20260704/05 are a real weekend and are genuinely absent from the resolved population
    sessions = {dict(r)["trade_date"] for r in rrc.resolve_population(cs["daily"]["request_population"])}
    assert "20260705" not in sessions and {"20260702", "20260703"} <= sessions
    sunday = _a01_plan(hashes, cs_map=cs, parts=("20260702", "20260705"))   # every leg agrees...
    with pytest.raises(RuntimeError, match="NOT signed|signed REQUESTS"):
        rrc.assert_plan_matches_contracts(sunday, cs)                       # ...and is still wrong


def test_missing_session_is_refused(signed):
    """A plan that skips a signed session is an INCOMPLETE recovery, not a smaller job."""
    fake_root, mirror, cs, hashes = signed
    short = _a01_plan(hashes, cs_map=cs, parts=("20260702",))   # 20260703 signed but unplanned
    with pytest.raises(RuntimeError, match="missing"):
        rrc.assert_plan_matches_contracts(short, cs)


def test_population_must_resolve_to_the_signed_hash(signed):
    """expected_set_sha256 pins the set the human signed: if the reference data or the bounds move,
    the contract no longer describes the population and must be re-signed."""
    fake_root, mirror, cs, hashes = signed
    drifted = dict(cs["daily"])
    drifted["request_population"] = dict(drifted["request_population"], expected_set_sha256="0" * 64)
    errs = rrc.contract_errors("daily", drifted)
    assert any("sign the request set that resolves" in e for e in errs), errs
    # widening the bounds without re-signing also refuses
    wider = dict(cs["daily"])
    wider["request_population"] = dict(wider["request_population"],
                                       bounds={"start": "20260701", "end": "20260710", "exchange": "SSE",
                                               "reference_sha256": _cal_sha()})
    assert any("sign the request set that resolves" in e for e in rrc.contract_errors("daily", wider))


def test_population_spec_must_be_executable_not_prose(signed):
    fake_root, mirror, cs, hashes = signed
    for bad in ({"unit": "open_trade_date", "source": "trade_cal open sessions"},   # the OLD schema
                {"resolver": "every trading day", "bounds": {"start": "1", "end": "2"},
                 "expected_set_sha256": "0" * 64},
                "all sessions"):
        errs = rrc.contract_errors("daily", dict(cs["daily"], request_population=bad))
        assert any("resolver must be one of" in e or "typed mapping" in e for e in errs), (bad, errs)


def test_empty_population_refused(signed):
    fake_root, mirror, cs, hashes = signed
    empty = {"resolver": "trade_cal_open_sessions",
             "bounds": {"start": "20260704", "end": "20260705", "exchange": "SSE",
                        "reference_sha256": _cal_sha()}}                              # a weekend only
    empty["expected_set_sha256"] = rrc.request_set_sha256(set())
    assert any("EMPTY set" in e for e in rrc.contract_errors("daily", dict(cs["daily"],
                                                                          request_population=empty)))


def test_every_unit_resolves_to_complete_requests():
    """GPT sign-off HOLD: the fix is not "declare more params" — it is that the RESOLVER emits the
    complete request and the comparison never projects. Every matrix query_mode must reach a resolver,
    and every resolver's output must be a full canonical request."""
    for r in rrc.ENDPOINT_MATRIX:
        if r.query_mode == "UNBOUND":
            continue
        unit = rrc._QUERY_MODE_TO_UNIT[r.query_mode]
        assert unit in rrc._UNIT_RESOLVERS, f"{unit} reaches no resolver"
        assert rrc._UNIT_RESOLVERS[unit] in rrc._POPULATION_RESOLVERS
        assert unit in rrc._UNIT_LABEL_PARAM, f"{unit} declares no label axis"
    # the multi-parameter units carry their full request shape
    rt = rrc.resolve_population({"resolver": "report_periods_x_types",
                                 "bounds": {"periods": ["20260331"], "report_types": ["2"]}})
    assert set(dict(next(iter(rt)))) == {"period", "report_type"}
    ix = rrc.resolve_population({"resolver": "index_code_ranges",
                                 "bounds": {"codes": ["000300.SH"], "start_date": "20260101",
                                            "end_date": "20260702"}})
    assert set(dict(next(iter(ix)))) == {"ts_code", "start_date", "end_date"}


def test_request_key_is_the_complete_canonical_request():
    """`_request_population_key` returns EVERY parameter — the identity, not an axis. The partition
    label is checked for honesty but is never the key."""
    row = [r for r in rrc.ENDPOINT_MATRIX if r.query_mode == "per_period_report_type"][0]
    pr = {"request_id": "r", "endpoint": "income_vip", "dataset": row.output_family,
          "partition": "20260630", "params": {"period": "20260630", "report_type": "2"}}
    assert rrc._request_population_key(pr, row) == rrc._canon_request({"period": "20260630",
                                                                       "report_type": "2"})
    # an extra parameter CHANGES the request identity — it cannot ride along unseen
    pr_extra = dict(pr, params={"period": "20260630", "report_type": "2", "fields": "all"})
    assert rrc._request_population_key(pr_extra, row) != rrc._request_population_key(pr, row)
    # a label that misdescribes its own request refuses
    with pytest.raises(RuntimeError, match="label is not evidence"):
        rrc._request_population_key(dict(pr, partition="20260331"), row)


def test_index_range_request_key_carries_its_bounds():
    row = [r for r in rrc.ENDPOINT_MATRIX if r.query_mode == "per_index_range"][0]
    pr = {"request_id": "r", "endpoint": "index_daily", "dataset": row.output_family,
          "partition": "000300.SH",
          "params": {"ts_code": "000300.SH", "start_date": "20260101", "end_date": "20260702"}}
    key = rrc._request_population_key(pr, row)
    assert dict(key) == {"ts_code": "000300.SH", "start_date": "20260101", "end_date": "20260702"}
    # the SAME code over a different range is a DIFFERENT request (GPT: a 2099 range rode in free)
    other = rrc._request_population_key(
        dict(pr, params={"ts_code": "000300.SH", "start_date": "20990101", "end_date": "20990102"}), row)
    assert other != key


def test_resolvers_read_the_real_reference_data():
    """The resolver is the FACT: it reads the surviving trade_cal, so a weekend is simply not in it."""
    reqs = rrc.resolve_population({"resolver": "trade_cal_open_sessions",
                                   "bounds": {"start": "20260701", "end": "20260710",
                                              "exchange": "SSE", "reference_sha256": _cal_sha()}})
    sessions = {dict(r)["trade_date"] for r in reqs}
    assert "20260705" not in sessions          # Sunday
    assert "20260704" not in sessions          # Saturday
    assert {"20260701", "20260702", "20260703", "20260706"} <= sessions
    assert all(set(dict(r)) == {"trade_date"} for r in reqs)   # COMPLETE requests, not bare members
    with pytest.raises(RuntimeError, match="unknown population resolver"):
        rrc.resolve_population({"resolver": "vibes", "bounds": {}})


# ── GPT sign-off HOLD: the COMPLETE request is the identity — no first-axis projection ────────────
def test_unsigned_report_type_is_an_unsigned_request(signed):
    """GPT (reproduced through the fully signed gate): income_vip(period=20260331, report_type=999) was
    ACCEPTED because the tuple was projected to k[0]. The real direct-quarter recipe uses ('2','3')
    (scripts/fetch_quarterly_statements.py)."""
    row = [r for r in rrc.ENDPOINT_MATRIX if r.query_mode == "per_period_report_type"][0]
    spec = {"resolver": "report_periods_x_types",
            "bounds": {"start": "20260331", "end": "20260331", "report_types": ["2", "3"]}}
    spec["expected_set_sha256"] = rrc.request_set_sha256(rrc.resolve_population(spec))
    signed_reqs = rrc.resolve_population(spec)
    assert rrc._canon_request({"period": "20260331", "report_type": "2"}) in signed_reqs
    assert rrc._canon_request({"period": "20260331", "report_type": "999"}) not in signed_reqs, \
        "report_type=999 is inside the signed request set"


def test_unsigned_index_range_is_an_unsigned_request():
    """GPT (reproduced): signed index code 000300.SH accepted an UNSIGNED 20990101..20990102 range."""
    spec = {"resolver": "index_code_ranges",
            "bounds": {"codes": ["000300.SH"], "start_date": "20260101", "end_date": "20260702"}}
    reqs = rrc.resolve_population(spec)
    assert rrc._canon_request({"ts_code": "000300.SH", "start_date": "20260101",
                               "end_date": "20260702"}) in reqs
    assert rrc._canon_request({"ts_code": "000300.SH", "start_date": "20990101",
                               "end_date": "20990102"}) not in reqs, "a 2099 range rode in free"


def test_stock_repartition_binds_its_range():
    """GPT (reproduced): all 5,861 signed stocks accepted arbitrary 2099 cyq_perf ranges because
    stock_repartition bound only ts_code — the real call takes ts_code + start_date + end_date."""
    row = [r for r in rrc.ENDPOINT_MATRIX if r.query_mode == "per_stock_repartition"][0]
    assert rrc._UNIT_RESOLVERS[rrc._QUERY_MODE_TO_UNIT[row.query_mode]] == "stock_basic_ranges"
    sb_sha = rrc.sha256_file(rrc.E_DATA / "reference" / "stock_basic.parquet")
    reqs = rrc.resolve_population({"resolver": "stock_basic_ranges",
                                   "bounds": {"list_status": "L,D,P", "start_date": "20180101",
                                              "end_date": "20260702", "reference_sha256": sb_sha}})
    one = dict(sorted(reqs)[0])
    assert set(one) == {"ts_code", "start_date", "end_date"}
    assert one["start_date"] == "20180101" and one["end_date"] == "20260702"


def test_non_quarter_periods_can_be_signed_explicitly():
    """GPT: report_periods generated only standard quarter ends (73 for 20080331..20260331) while the
    baseline holds 98 indicator partitions — data_tracker records NON-quarter periods in legacy Tushare
    indicator history. A generated calendar cannot describe vendor-reported reality."""
    gen = rrc.resolve_population({"resolver": "report_periods",
                                  "bounds": {"start": "20080331", "end": "20260331"}})
    assert len(gen) == 73                       # exactly the generated quarter-ends GPT counted
    odd = rrc.resolve_population({"resolver": "report_periods",
                                  "bounds": {"periods": ["20260331", "20260415", "20260630"]}})
    assert rrc._canon_request({"period": "20260415"}) in odd     # a NON-quarter period, signed
    with pytest.raises(RuntimeError, match="non-empty signed list"):
        rrc.resolve_population({"resolver": "report_periods", "bounds": {"periods": []}})


def test_report_types_must_be_signed_explicitly():
    with pytest.raises(RuntimeError, match="explicit `report_types` list"):
        rrc.resolve_population({"resolver": "report_periods_x_types",
                                "bounds": {"start": "20260331", "end": "20260331"}})


def test_reference_derived_populations_are_pinned():
    """GPT answer 2: resolving from LIVE reference data forces re-signing whenever listings/statuses
    change. The contract pins the exact reference bytes instead, so a refresh is a deliberate re-sign."""
    with pytest.raises(RuntimeError, match="reference_sha256 must pin"):
        rrc.resolve_population({"resolver": "trade_cal_open_sessions",
                                "bounds": {"start": "20260701", "end": "20260702"}})
    with pytest.raises(RuntimeError, match="the contract pins"):
        rrc.resolve_population({"resolver": "trade_cal_open_sessions",
                                "bounds": {"start": "20260701", "end": "20260702",
                                           "reference_sha256": "0" * 64}})


def test_plan_with_an_unsigned_parameter_refused(signed):
    """The whole point: a request whose PRIMARY axis matches but which carries an unsigned parameter is
    an unsigned request. No projection can see this."""
    fake_root, mirror, cs, hashes = signed
    rows = _a01_plan(hashes, cs_map=cs)
    rows[0] = dict(rows[0], params=dict(rows[0]["params"], adj="qfq"))   # an extra, unsigned param
    with pytest.raises(RuntimeError, match="does not make the signed REQUESTS|NOT signed"):
        rrc.assert_plan_matches_contracts(rows, cs)
