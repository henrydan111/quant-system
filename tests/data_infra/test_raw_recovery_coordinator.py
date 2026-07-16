"""Recovery coordinator v3 battery (GPT recovery re-review #2: B1 containment probes, B3 ledger
transitions, B4 contract-gate negatives, non-finite throttle minor). Everything network-free; test
runs live under C:\\quant_recovery\\runs_test\\<uuid> (C: is the sanctioned recovery area; E: must
never be written by the coordinator)."""
from __future__ import annotations

import importlib.util
import json
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


@pytest.fixture()
def crun(monkeypatch):
    """Isolated RECOVERY_ROOT on C: (the sanctioned recovery drive), cleaned up after."""
    base = Path(r"C:\quant_recovery") / "runs_test" / uuid.uuid4().hex
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
            "pagination": "single page per trade_date", "rate_limit": "500/min@15000pts",
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
                "pagination": "single page per trade_date", "rate_limit": "500/min@15000pts",
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
            "pagination": "single page per trade_date", "rate_limit": "500/min@15000pts",
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
         "pagination": "single", "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
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
         "pagination": "single", "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
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
         "pagination": "single", "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
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
            "pagination": "single", "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
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
         "pagination": "single", "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
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
            "pagination": "single", "rate_limit": "500/min", "cadence": "daily", "pit_anchors": "trade_date",
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
