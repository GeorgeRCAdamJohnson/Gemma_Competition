"""Claims engine cl-4 tests (design §12.4 / §12.7 + REVISION 5 R5.7).

Real-log tests are CONTENT-ANCHORED: each locates its line by a content
substring, never by an absolute line number (the log is append-mostly and the
READ-THIS-FIRST block is edited in place). Synthetic tests cover the F1
classifier, ref binding, run checks and the three supersession rules.
"""
import json
import pathlib

import pytest

from kblib import claims

KB = pathlib.Path(__file__).resolve().parent.parent
G = KB.parent
LOG = G / "GEMMA_EXPERIMENT_LOG.md"


# ----------------------------------------------------------------- real log

@pytest.fixture(scope="module")
def real():
    if not LOG.is_file():
        pytest.skip("real log not present")
    from kblib import io, baseline as bl
    text, _ = io.read_text_bomaware(LOG)
    rows = []
    rp = KB / "runs.jsonl"
    if rp.is_file():
        rows = [json.loads(l) for l in rp.read_text(encoding="utf-8").splitlines() if l.strip()]
    src = bl.lb_source(KB)
    rl_p = KB / "curated" / "run_labels.json"
    rl = json.loads(rl_p.read_text(encoding="utf-8")) if rl_p.is_file() else {}
    cl = claims.extract(text, src["rows"], KB / "curated" / "claims.jsonl", rl.get("baseline", {}),
                        rows, lb_source_path=src["path"], run_labels=rl)
    lines = text.split("\n")
    return {"cl": cl, "lines": lines, "lb": src["rows"], "text": text}


def _line_of(real, needle, start=None):
    """1-based number of the first log line containing `needle` (and starting with `start`)."""
    for i, ln in enumerate(real["lines"], 1):
        if needle in ln and (start is None or ln.startswith(start)):
            return i
    pytest.fail(f"anchor not found in the log: {needle!r}")


def _claims_at(real, line):
    return [c for c in real["cl"]["claims"] if c["line"] == line]


def _facts_at(real, line, field=None):
    out = []
    for c in real["cl"]["claims"]:
        for f in c["facts"]:
            if f["line"] == line and (field is None or f["field"] == field):
                out.append(f)
    return out


def test_rtf4_live_best_line(real):
    ln = _line_of(real, "LIVE-BEST = v6 @ 0.12")
    cs = [c for c in _claims_at(real, ln) if c["kind"] == "standing-truth"]
    assert cs, "RTF #4 is a standing-truth claim"
    fs = cs[0]["facts"]
    f5 = [f for f in fs if f["field"] == "F5" and f["value"] == "0.12"]
    assert f5 and f5[0]["version"] == "v6" and f5[0]["binding"] == "idiom-@"
    f10 = [f for f in fs if f["field"] == "F10"]
    assert f10 and f10[0]["version"] == "v6" and f10[0]["value"] == "live-best"
    f1 = [f for f in fs if f["field"] == "F1"]
    assert [f["value"] for f in f1] == ["2/6"] and f1[0]["version"] == "v6"
    f2b = [f for f in fs if f["field"] == "F2b"]
    assert f2b and f2b[0]["value"] == ["rich_4077", "rich_4079"] and f2b[0]["version"] == "v6"


def test_first_lb_anchor_leaderboard_case_insensitive(real):
    ln = _line_of(real, "LEADERBOARD SCORE: 0.10", start="## SUBMISSION v2")
    f5 = _facts_at(real, ln, "F5")
    assert any(f["value"] == "0.10" and f["version"] == "v2" for f in f5)


def test_v6w_block_heading_idiom_table_and_live_best(real):
    ln = _line_of(real, "v6w SCORED **0.15**", start="## ")
    fs = _facts_at(real, ln)
    assert any(f["field"] == "F5" and f["value"] == "0.15" and f["version"] == "v6w" for f in fs)
    assert any(f["field"] == "F10" and f["version"] == "v6w" for f in fs)
    ln2 = _line_of(real, "Beats v6 @ 0.12")
    assert any(f["value"] == "0.12" and f["version"] == "v6" and f["binding"] == "idiom-@"
               for f in _facts_at(real, ln2, "F5"))
    # type-C table rows: score column only; the 0.18 budget label is never a score
    ln3 = _line_of(real, '"beat...beat" (v6)', start="|")
    assert [(f["value"], f["version"]) for f in _facts_at(real, ln3, "F5")] == [("0.12", "v6")]
    ln4 = _line_of(real, "v6w: 0.18 budget 28/8/80/240", start="|")
    assert [(f["value"], f["version"]) for f in _facts_at(real, ln4, "F5")] == [("0.15", "v6w")]
    assert any(h["text"] == "beat...beat" and h["version"] == "v6" for h in real["cl"]["hints"])
    ln5 = _line_of(real, "v6w @ 0.15 is now the live-best")
    f10 = _facts_at(real, ln5, "F10")
    assert any(f["version"] == "v6w" and f["value"] == "live-best"
               and f["check"]["status"] == "SUPPORTED" for f in f10)
    assert any(f["version"] == "v6" and f["value"] == "not-live-best" for f in f10)


def test_total_row_one_f1_per_version_column(real):
    ln = _line_of(real, "| **TOTAL** | **4/6** | 2/6 | 2/6 | 3/6 | **3/6** |")
    f1 = _facts_at(real, ln, "F1")
    assert [f["value"] for f in f1] == ["4/6", "2/6", "2/6", "3/6", "3/6"]
    assert all("task" not in f for f in f1)
    assert f1[-1]["version"] == "v6z-on-v6w-armb"
    assert _facts_at(real, ln, "F2") == [] and _facts_at(real, ln, "F3") == []


def test_armB_f1v_fact_line(real):
    ln = _line_of(real, "armB = 3/6")
    cs = _claims_at(real, ln)
    assert cs and cs[0]["kind"] == "fact-line"
    f1v = [f for f in cs[0]["facts"] if f["field"] == "F1v"]
    assert f1v and f1v[0]["value"] == "3/6" and f1v[0]["version"] == "v6z-on-v6w-armb"


def test_v3_patches_vs_resolves_only_keyed(real):
    ln = _line_of(real, "v3 patches 3/6 but resolves 1/6", start="## ")
    f1 = _facts_at(real, ln, "F1")
    assert [(f["value"], f["version"]) for f in f1] == [("1/6", "v3")]


def test_ca5_31b_scored_020_bound_to_ca5(real):
    ln = _line_of(real, "ca5-31B scored 0.20")
    f5 = [f for f in _facts_at(real, ln, "F5") if f["value"] == "0.20"]
    assert f5 and f5[0]["version"] == "ca5" and f5[0].get("model") == "31b"
    from kblib import attribution
    lb_has = any((r.get("status") or "").endswith("COMPLETE") and r.get("publicScore")
                 and round(float(r["publicScore"]), 2) == 0.20
                 and attribution.description_track(r.get("description", "")) == "main"
                 and (r.get("description") or "").lower().startswith("ca5")
                 for r in real["lb"])
    assert (f5[0]["check"]["status"] == "SUPPORTED") == lb_has


def test_b_temp1_ref_binding(real):
    ln = _line_of(real, "ref 57201051 (v6w + temperature 1.0 / top_k 64, only change) = 0.13 public")
    f5 = [f for f in _facts_at(real, ln, "F5") if f["value"] == "0.13"]
    assert f5 and f5[0]["ref"] == "57201051"
    lb_has = any(str(r.get("ref")) == "57201051" and r.get("publicScore")
                 and round(float(r["publicScore"]), 2) == 0.13 for r in real["lb"])
    assert (f5[0]["check"]["status"] == "SUPPORTED") == lb_has


def test_bar_for_v4_is_bar_not_outcome(real):
    ln = _line_of(real, "Bar for v4: >=2/6")
    tok = claims.Tokenizer()
    fs, _ = claims.line_facts(real["lines"][ln - 1], ln, tok)
    assert any(f["field"] == "bar" and f["value"] == "2/6" for f in fs)
    assert not any(f["field"] == "F1" and f["value"] == "2/6" for f in fs)
    assert not any(f["field"] == "F1" and f["value"] == "2/6" for f in _facts_at(real, ln))


def test_resolved_but_banked_only_keyed(real):
    ln = _line_of(real, "0/6 resolved but 6/6 BANKED", start="## ")
    fs, _ = claims.line_facts(real["lines"][ln - 1][3:], ln, claims.Tokenizer())
    assert [f["value"] for f in fs if f["field"] == "F1"] == ["0/6"]


def test_d_arms_retracted_heading_chain(real):
    ln = _line_of(real, "[RETRACTED same day", start="## 2026-10-21 D-ARMS")
    corr = _line_of(real, "2026-10-21 CORRECTION: D-ARMS", start="## ")
    units = {u["start"]: u for u in real["cl"]["units"]}
    old, new = units[ln], units[corr]
    cs = [c for c in real["cl"]["claims"] if c["unit_id"] == old["id"]]
    assert cs and all(c["status"] == "SUPERSEDED" for c in cs)
    assert all(old["id"] in c["chain"] and new["id"] in c["chain"] for c in cs)
    ch = cs[0]["chain"]
    assert ch.index(old["id"]) < ch.index(new["id"])
    assert cs[0]["superseded_by"][0]["unit_id"] == new["id"]


def test_v6_1of6_is_superseded_by_the_logs_own_quoted_correction(real):
    """L6746 'v6 scored 1/6 on this sample' was corrected in the log itself
    (`CORRECTED: "... v6 scored 1/6 on the v6b sample." v6 scored **2/6**`): it is
    SUPERSEDED, never CONTRADICTED; the quote is not an assertion of the correction."""
    old = _line_of(real, "**Baseline:** v6 scored 1/6 on this sample")
    fix = _line_of(real, 'CORRECTED: "v6b was a lateral null; v6 scored 1/6 on the v6b sample."')
    oc = [c for c in real["cl"]["claims"] if c["line"] <= old <= int(c["lines"].split("-")[1])
          and any(f["field"] == "F1" and f["value"] == "1/6" for f in c["facts"])]
    assert oc and all(c["status"] == "SUPERSEDED" for c in oc)
    assert oc[0]["superseded_by"][0]["link_basis"] == "quoted-fact"
    q = [f for f in _facts_at(real, fix) if f["field"] == "F1" and f["value"] == "1/6"]
    assert q and all(f.get("quoted") for f in q)
    assert any(f["field"] == "F1" and f["value"] == "2/6" and f["version"] == "v6"
               and not f.get("quoted") for f in _facts_at(real, fix))


def test_corrected_block_not_superseded_by_entries_citing_it_as_source(real):
    blk = _line_of(real, "CORRECTED -- earlier log entries the raw data contradicts", start="### ")
    u = next(x for x in real["cl"]["units"] if x["start"] == blk)
    assert u["superseded"] is False
    src = _line_of(real, "That was already RETRACTED by the audit at L9287")
    assert any(x["line"] <= src and "SOURCE" in x["reason"]
               for x in real["cl"]["unresolved_citations"])


def test_v10_label_collision_detected(real):
    h = {x["token"]: x for x in real["cl"]["label_collisions"]}
    if not any("version10" in (k or "") for k in
               {r for x in h.values() for r in x["kernel_runs_tasks"]}) and "v10" not in h:
        pytest.skip("129-task version10 kernel run not on disk")
    v10 = h["v10"]
    assert "Outputs/v10" in v10["experiment_runs_tasks"]
    assert v10["kernel_label"].endswith("version10")
    assert list(v10["kernel_runs_tasks"].values())[0] == 129
    assert not any(f.get("version") == "v10" and (f.get("check") or {}).get("status") == "CONTRADICTED"
                   for c in real["cl"]["claims"] for f in c["facts"])


def test_version_history_rows(real):
    def row(ver):
        return _line_of(real, f"| {ver} ", start=f"| {ver} ")
    v6 = _facts_at(real, row("v6 "))
    assert ("F1", "2/6", "v6") in [(f["field"], f["value"], f.get("version")) for f in v6]
    assert ("F5", "0.12", "v6") in [(f["field"], f["value"], f.get("version")) for f in v6]
    assert any(f["field"] == "F2b" and f["value"] == ["rich_4077", "rich_4079"] for f in v6)
    v8 = _facts_at(real, row("v8 "))
    assert [f["value"] for f in v8 if f["field"] == "F1"] == ["1/6"]
    v10 = _facts_at(real, row("v10"))
    assert ("F1", "2/10", "v10") in [(f["field"], f["value"], f.get("version")) for f in v10]
    assert ("F1v", "0/10", "v9") in [(f["field"], f["value"], f.get("version")) for f in v10]


def test_real_statuses_and_supersession_fields(real):
    cl = real["cl"]
    assert len(cl["claims"]) > 78
    allowed = {"SUPPORTED", "CONTRADICTED", "UNVERIFIED", "SUPERSEDED"}
    assert all(c["status"] in allowed for c in cl["claims"])
    for c in cl["claims"]:
        assert "chain" in c and "superseded_by" in c
        if c["status"] == "SUPERSEDED":
            assert c["superseded_by"] and c["chain"]


# ----------------------------------------------------------------- synthetic

def _tok():
    return claims.Tokenizer(["v6z_on_v6w-armb"])


def test_classifier_bar_unit_keyed_unkeyed():
    tok = _tok()
    f = lambda s: [(x["field"], x["value"]) for x in claims.line_facts(s, 1, tok)[0]
                   if x["field"] in ("F1", "bar", "unkeyed", "F1v", "F2b")]
    assert f("Hard bar: >=2/6 resolved") == [("bar", "2/6")]
    assert f("v5 hit 7/22 calls before the edit") == []
    assert f("budget 28/8/80/240 eval") == []
    assert f("v5 resolved 1/6 (rich_1 + rich_2)") == [("F1", "1/6"), ("F2b", ["rich_1", "rich_2"])]
    assert f("v5 patches 3/6 overall") == [("unkeyed", "3/6")]
    assert f("armB = 3/6, same as before") == [("F1v", "3/6")]
    # a parenthetical restating a non-resolve metric is not a resolve count
    assert ("F1v", "0/5") not in f("never-edited 2/5 (v19=0/5, WORSE)")


def test_f5_patterns_and_bar_context():
    tok = _tok()
    fs = lambda s: [(x["value"], x.get("version"), x.get("ref")) for x in claims.line_facts(s, 1, tok)[0]
                    if x["field"] == "F5"]
    assert fs("v6 @ 0.12 was the bar") == [("0.12", "v6", None)]
    assert fs("ca5-31B scored 0.20 today") == [("0.20", "ca5", None)]
    assert fs("ref 57201051 (v6w + temp 1.0) = 0.13 public.") == [("0.13", "v6w", "57201051")]
    assert fs("A25 = 0.13 (8/58) on the board") == [("0.13", "a25", None)]
    assert fs("v6 should score >= 0.10 on the full set") == []
    assert fs("v6w: 0.18 budget 28/8/80/240") == []


def _lb(*rows):
    return [{"ref": r, "status": "SubmissionStatus.COMPLETE", "publicScore": s, "description": d,
             "date": "2026-10-20 00:00:00"} for r, s, d in rows]


def test_f5_check_ref_and_version_mapping(tmp_path):
    log = ("## 2026-10-20 RESULTS\n\n"
           "- ref 11112222 (v7 + temp 1.0) = 0.13 public.\n\n"
           "- v7 @ 0.15 per the board.\n\n"
           "- v8 @ 0.30 per the board.\n")
    lb = _lb(("11112222", "0.13", "v7 + temp 1.0"), ("33334444", "0.15", "v7 again"),
             ("55556666", "0.12", "v8 first"))
    cl = claims.extract(log, lb, tmp_path / "none.jsonl", {"label": "v7"}, [])
    st = {f["value"]: f["check"]["status"] for c in cl["claims"] for f in c["facts"] if f["field"] == "F5"}
    assert st == {"0.13": "SUPPORTED", "0.15": "SUPPORTED", "0.30": "CONTRADICTED"}


def _rows(run, label, resolved, platform="kaggle", track="main"):
    return [{"run_id": run, "task": t, "version_label": label, "arm": None, "track": track,
             "run_kind": "kaggle-kernel", "stack": {"platform": platform},
             "outcome": {"resolved": r, "tool_calls": 10}, "config": {"max_tool_calls": 28}}
            for t, r in resolved.items()]


def test_f1_check_against_bound_run_and_stack_guard(tmp_path):
    rows = _rows("submit_v5/out", "v5", {"rich_1": True, "rich_2": False, "rich_3": False})
    rows += _rows("local_eval/parity_rig/b/v9/r0", "v9", {"rich_1": True, "rich_2": True,
                                                          "rich_3": False}, platform="local-rig")
    rows += _rows("submit_v6/out", "v6", {"rich_1": True, "rich_2": False, "rich_3": False})
    log = ("## 2026-10-01 v5 RESULT\n\nv5 resolved 1/3 on the gate.\n\n"
           "## 2026-10-02 v6 again\n\nv6 resolved 2/3 on the gate.\n\n"
           "## 2026-10-03 v9 note\n\nv9 resolved 2/3 on the gate.\n\n"
           "## 2026-10-04 v9 rig RESULT\n\nOn the parity rig, v9 resolved 2/3.\n")
    cl = claims.extract(log, [], tmp_path / "none.jsonl", {}, rows)
    by_unit = {c["entry_heading"]: c for c in cl["claims"]}
    assert by_unit["2026-10-01 v5 RESULT"]["status"] == "SUPPORTED"
    # a single, uncorrected, same-line-bound claim that disagrees with the only run
    assert by_unit["2026-10-02 v6 again"]["status"] == "CONTRADICTED"
    # stacks are never pooled: an entry that names no local stack is not judged by a rig run
    assert by_unit["2026-10-03 v9 note"]["status"] == "UNVERIFIED"
    assert "never pooled" in by_unit["2026-10-03 v9 note"]["reason"]
    assert by_unit["2026-10-04 v9 rig RESULT"]["status"] == "SUPPORTED"


def test_legacy_pulled_dir_is_a_rep_of_its_version(tmp_path):
    rows = _rows("Outputs/v10", "v10", {"rich_1": True, "rich_2": True, "rich_3": False})
    rows += _rows("_v10_kaggle_pull", "-v10-kaggle-pull", {"rich_1": False, "rich_2": False,
                                                           "rich_3": False})
    log = "## 2026-10-03 v10 committed\n\nv10's committed score is 0/3 resolved.\n"
    cl = claims.extract(log, [], tmp_path / "none.jsonl", {}, rows)
    f = next(f for c in cl["claims"] for f in c["facts"] if f["field"] == "F1")
    assert f["check"]["status"] == "UNVERIFIED"            # two v10 reps disagree: never forced
    assert f["check"]["runs_agree"] == ["_v10_kaggle_pull"]
    assert f["check"]["runs_disagree"] == ["Outputs/v10"]
    # binding rule (a) is scoped to the claim + its heading: a path cited elsewhere in
    # the entry does not pin the claim; a path in the heading does
    log2 = ("## 2026-10-03 v10 entry\n\nWe compared to the pasted Outputs/v10 run.\n\n"
            "### v10 committed\nv10's committed score is 0/3 resolved.\n\n"
            "## 2026-10-04 v10 RESULT -- 2/3. source: Outputs/v10\n\nv10 resolved 2/3.\n")
    cl2 = claims.extract(log2, [], tmp_path / "none.jsonl", {}, rows)
    f1 = {(c["unit_start_line"], f["value"]): f["check"] for c in cl2["claims"] for f in c["facts"]
          if f["field"] == "F1"}
    assert f1[(5, "0/3")]["status"] == "UNVERIFIED"
    assert f1[(8, "2/3")]["status"] == "SUPPORTED"
    assert "run path cited" in f1[(8, "2/3")]["binding_basis"]


def test_supersession_heading_tag_above_and_cited_line(tmp_path):
    log = "\n".join([
        "# log",
        "## 2026-10-01 A7 RESULT [RETRACTED same day: see CORRECTION below] A7 wins big",
        "A7 = 3/6 resolved.",
        "",
        "## 2026-10-01 unrelated entry",
        "nothing here.",
        "",
        "## 2026-10-02 CORRECTION: A7 wins big claim retracted",
        "it was noise.",
        "",
        "## 2026-10-03 v9 RESULT -- PASS",
        "v9 resolved 2/6 here.",
        "",
        "## 2026-10-04 CORRECTION -- v9 PASS ABOVE IS OVERSTATED",
        "re-read it.",
        "",
        "## 2026-10-05 v4 RESULT",
        "v4 resolved 1/6.",
        "",
        "## 2026-10-06 v4 follow-up",
        "The v4 claim at L18 is RETRACTED: wrong run.",
    ])
    cl = claims.extract(log, [], tmp_path / "none.jsonl", {}, [])
    units = {u["start"]: u for u in cl["units"]}
    st = {}
    for c in cl["claims"]:
        st.setdefault(c["unit_start_line"], set()).add(c["status"])
    assert st[2] == {"SUPERSEDED"} and units[2]["superseded"]
    c2 = next(c for c in cl["claims"] if c["unit_start_line"] == 2)
    assert c2["chain"] == [units[2]["id"], units[8]["id"]]
    assert st[11] == {"SUPERSEDED"}
    c11 = next(c for c in cl["claims"] if c["unit_start_line"] == 11)
    assert c11["superseded_by"][0]["link_basis"] == "correction-above"
    assert st[17] == {"SUPERSEDED"}
    c17 = next(c for c in cl["claims"] if c["unit_start_line"] == 17)
    assert c17["superseded_by"][0]["link_basis"].startswith("cited-line")
    assert "SUPERSEDED" not in st.get(5, set())


def test_internal_consistency_rules_synthetic(tmp_path):
    rows = _rows("submit_v5/out", "v5", {"rich_1": True, "rich_2": True, "rich_3": False})
    # (1) quoted retraction supersedes the earlier claim, only that claim
    log = ("## 2026-10-01 v5 gate\n\nv5 resolved 1/3 on the gate.\n\nv5 is the base.\n\n"
           "## 2026-10-03 audit\n\n- CORRECTED: \"v5 resolved 1/3 on the gate.\" v5 resolved 2/3.\n")
    cl = claims.extract(log, [], tmp_path / "n.jsonl", {}, rows)
    st = {c["line"]: c["status"] for c in cl["claims"]}
    assert st[3] == "SUPERSEDED" and st[9] == "SUPPORTED"
    assert cl["stats"]["quoted_fact_links"] == 1
    # (4) self-disagreement without a correction -> not asserted, reported
    log2 = ("## 2026-10-01 v5 gate\n\nv5 resolved 1/3 on the gate.\n\n"
            "## 2026-10-02 v5 again\n\nv5 resolved 2/3 on the gate.\n")
    cl2 = claims.extract(log2, [], tmp_path / "n.jsonl", {}, rows)
    assert all(c["status"] != "CONTRADICTED" for c in cl2["claims"])
    assert cl2["self_disagreements"] and cl2["self_disagreements"][0]["line"] == 3
    # (2) a cited line that is the SOURCE of a retraction is not superseded
    log3 = ("## 2026-10-01 v5 result\n\nv5 resolved 2/3.\n\n"
            "## 2026-10-02 audit CORRECTION\n\nThe v3 claim was RETRACTED by the audit at L3.\n")
    cl3 = claims.extract(log3, [], tmp_path / "n.jsonl", {}, rows)
    assert not any(u["superseded"] for u in cl3["units"])
    # (3) label collision: experiment vN and kernel versionN
    rows4 = _rows("Outputs/v10", "v10", {"rich_1": True, "rich_2": False})
    rows4 += _rows("submit_k/out_v10", "kern-a-version10", {"rich_1": False, "rich_2": False,
                                                            "rich_3": False})
    log4 = ("## 2026-10-29 ca5\n\nRESULT: ca5 uses the v10 config.\n\n"
            "## 2026-10-30 note\n\nv10 resolved 0/2 on that pair.\n")
    cl4 = claims.extract(log4, [], tmp_path / "n.jsonl", {}, rows4)
    assert [h["token"] for h in cl4["label_collisions"]] == ["v10"]
    assert any("kern-a-version10" in c["versions"] for c in cl4["claims"] if c["line"] == 3)
    f = next(f for c in cl4["claims"] for f in c["facts"] if f["field"] == "F1")
    assert f["check"]["status"] == "UNVERIFIED" and "label collision" in f["check"]["reason"]


def test_curated_merge_reads_evidence(tmp_path):
    p = tmp_path / "Gemma" / "kb" / "curated" / "claims.jsonl"
    p.parent.mkdir(parents=True)
    (tmp_path / "Gemma" / "x.md").write_text("x", encoding="utf-8")
    p.write_text(json.dumps({"id": "J-a", "kind": "judgment", "status": "SUPPORTED", "text": "t",
                             "evidence": ["Gemma/x.md#L3 (note)", "Gemma/missing.md"]}) + "\n"
                 + "not json\n", encoding="utf-8")
    cl = claims.extract("## h\nbody\n", [], p, {}, [])
    cur = cl["curated"][0]
    assert cur["id"] == "J-a" and cur["status"] == "SUPPORTED"
    assert cur["evidence"][0]["path"] == "Gemma/x.md" and cur["evidence"][0]["line"] == 3
    assert cur["evidence_ok"] is False and cur["evidence_missing"] == ["Gemma/missing.md"]
    assert cl["curated_errors"] and cl["curated_errors"][0]["line"] == 2


def test_extract_deterministic(tmp_path):
    log = "## v5 RESULT\nv5 resolved 1/6 (rich_1)\n\n| task | v5 | v6 |\n|---|---|---|\n| rich_1 | T 3c | F 4c |\n"
    a = claims.extract(log, [], tmp_path / "n.jsonl", {}, [])
    b = claims.extract(log, [], tmp_path / "n.jsonl", {}, [])
    assert json.dumps(a["claims"], sort_keys=True) == json.dumps(b["claims"], sort_keys=True)
