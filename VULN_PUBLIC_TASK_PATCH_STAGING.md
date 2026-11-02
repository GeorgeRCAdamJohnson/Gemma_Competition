# Vulnerability Disclosure — Public-Split Gold-Patch Staging in the Gemma 4 Developer Agent Harness

**Author:** comfyops
**Date:** 2026-10-11
**Status:** DRAFT for responsible disclosure to the competition organizers. NOT exploited on the live leaderboard.
**Scope:** Public-leaderboard integrity only. This document analyzes a mechanism; it does not accuse any specific
competitor and does not include a working exploit submission.

---

## 1. Summary

The public portion of the leaderboard can be inflated **without the agent solving anything**, by pre-staging the
publicly-available gold patches for the exposed open-source repositories (rich / fastapi / requests / httpx) inside
the submission and emitting the matching diff when the agent recognizes a task from its problem statement.

The harness hands the agent the **repository name and the full problem-statement text** of each task, and scores a
task **solely** on whether the produced `git diff` applies cleanly and makes the hidden tests pass. There is **no
check** that the patch was derived by the agent's reasoning rather than copied from a known answer. For the public
repos, the gold patches are open-source-derivable, so a problem-statement -> gold-diff map is sufficient to resolve
those tasks mechanically.

This is a **public-leaderboard integrity** issue. It does not necessarily affect the private split (see §6), which is
exactly why a high *public* score may not predict hidden/private performance — a point the organizers' own data
description already makes.

---

## 2. What the agent receives per task (the exposure)

Per `HARNESS_README.md` §5.2 (`build_agent_prompt`), the initial user message to the agent contains, verbatim:

```
You are evaluating a software engineering task for repository {task.repo}.

Problem Statement:
{task.problem_statement}
```

plus (if present) `## Hints: {task.hints_text}`, the task budget, environment rules, and a `find . -maxdepth 3`
workspace listing (§5.2 item 7). Session state (§5.1) exposes `problem_description = task.problem_statement` and
`hints = task.hints_text`, both interpolatable into the agent instruction via `{problem_description}`.

**Key point:** `task.repo` and the full `task.problem_statement` are given to the agent. The `instance_id` is NOT in
the prompt (it appears only in output artifact filenames, §9). Therefore the usable match key is the **problem-statement
text itself** (optionally combined with the repo name and the file tree) — all of which are reproducible for the public
open-source repositories from their public issue trackers and git history.

---

## 3. How scoring works (why a staged patch resolves)

Per `HARNESS_README.md` §8:

- `submit_patch()` (or the automatic fallback) simply captures `git diff --binary` of `/workspace` (§8.1). It records
  whatever is in the working tree. There is no provenance check.
- Phase 2 verification (§8.2) applies the captured `agent_patch` with a 4-pass resilient apply, resets **test files**
  to baseline, applies the hidden `task.test_patch`, and runs pytest. A task is `resolved = True` iff pytest exits 0
  with the required test nodes passing.
- The anti-tampering reset (§8.2 step 3) protects only **test/config files** (`test_*.py`, `conftest.py`, `pytest.ini`,
  etc.). It does **not** inspect or penalize the agent's edits to **source** files, and it has **no check** that the
  source diff was reasoned rather than memorized/pre-staged.

**Consequence:** if the agent emits the correct source-level gold diff for a public task, it applies and passes — and
is scored `resolved`. The harness cannot distinguish a legitimately-derived fix from a verbatim copy of a known answer.

---

## 4. The mechanism (feasibility, not a working exploit)

For the exposed public repos, gold patches are derivable from public git history. A submission could, in principle:

1. Ship a static map `fingerprint(problem_statement) -> gold_source_diff` for public tasks (bundled as data in the
   submission; the submission is declarative YAML + files, but the agent's own tool calls can read bundled files).
2. On each task, the agent compares the received `problem_statement` to the map; on a hit, it writes the staged diff
   to the correct source path(s) via its normal editing tools and calls `submit_patch`.
3. The hidden tests then pass because the staged diff IS the gold fix.

This requires no reasoning and no actual repair capability. It is bounded to the public split (see §6).

> This document deliberately does NOT include the map, the fingerprints, or a runnable staging agent. The feasibility
> is established by the harness mechanics above; a weaponized artifact is unnecessary for disclosure and is withheld.

---

## 5. Why a live exploit submission is NOT part of this report

A gamed public submission would (a) violate competition rules on leaderboard manipulation, (b) pollute the public
board other competitors use as a reference, and (c) prove only that the author can inflate their own score — it would
NOT demonstrate that any other high-scoring entry used this method. The vulnerability is proven by the harness
mechanics (§2-§4), not by a leaderboard row. Per responsible-disclosure practice, any proof-of-concept is run in a
**local, self-owned sandbox only** (see §7), never against the live scoring system.

---

## 6. Blast radius and the public/private distinction

- **Public split (~58 public-scored tasks, rich/fastapi/requests/httpx):** fully exposed. Gold patches derivable.
  Staging resolves these mechanically.
- **Private split (~remaining of ~120 total, private repos):** per the organizers' data description, private tasks
  come from private repositories and do NOT share the public repos. Their problem statements and gold patches are not
  public, so the staging map cannot cover them.
- **Therefore:** this attack inflates the **public** leaderboard but should collapse on the **private** rescoring. A
  competitor relying on it would show an anomalously high public score and a much lower private score. This is both
  the limit of the attack and a **detection signal** for the organizers (see §8).

This is consistent with the organizers' own stated caveat that public tasks had prior exposure and that public scores
do not predict hidden performance.

---

## 7. Responsible proof-of-concept (local only, optional)

If a demonstration is required, it is run entirely on a self-owned machine against a **known public task** whose gold
patch is public, showing that emitting the gold source diff yields `resolved = True` under the local `swegemma eval`
harness. This touches no Kaggle leaderboard and no private data. It is a controlled PoC against our own instance, the
standard for responsible disclosure. (Not performed as part of this draft; available on request.)

---

## 8. Recommended remediations (for the organizers)

1. **Do not use public tasks for ranking.** Score public tasks for feedback only; rank on the private split. (If
   already the case, state it, since it neutralizes most of the incentive.)
2. **Detect verbatim gold-patch emission.** Flag submissions whose source diff matches the known gold patch at
   byte/AST level on public tasks, or whose public-vs-private resolution gap exceeds a threshold.
3. **Withhold or paraphrase the problem statement / repo identity** so public tasks cannot be fingerprinted, or
   draw public evaluation tasks from issues without public gold patches.
4. **Weight or gate on private resolution** so a public-only inflation cannot climb the ranked board.

---

## 9. Evidence basis

All harness claims above are sourced from the competition's own `HARNESS_README.md`:
- §5.1 / §5.2 — session state and `build_agent_prompt` (repo + problem_statement exposed; no instance_id).
- §8.1 — `submit_patch` captures `git diff` with no provenance check.
- §8.2 — verification applies the agent's source diff, resets only test/config files, scores on pytest pass.
- §9 — `instance_id` appears only in output artifact filenames, not the agent prompt.

No private task content, no gold-patch map, and no runnable staging agent are included in this disclosure.
