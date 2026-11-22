"""Stage `catalog`: what has already been tried, so new experiments are not re-runs.
  bundle_diffs        every bundle vs pack 1 (colab_fasteval/arms/C_pack1): added / removed / modified files + diff
  arm_bundles         experiment arm -> bundle (registration file hashes, else an unambiguous arm-name match)
  experiment_catalog  per experiment: dates, platform, model(s), adapters, context, task cohort hash, arms, totals,
                      and a signature over (cohort, models, adapters, changed files) to detect repeats
  arm_catalog         per (experiment, arm): attempts, resolved/verified rates, bundle, changed files vs pack 1
"""
import difflib
import hashlib
import json
import time

SCHEMA = """
CREATE TABLE bundle_diffs (bundle_id INTEGER, relpath TEXT, change TEXT, bytes_pack1 INTEGER, bytes_bundle INTEGER,
  diff TEXT, PRIMARY KEY (bundle_id, relpath));
CREATE TABLE arm_bundles (exp TEXT, arm TEXT, bundle_id INTEGER, basis TEXT, PRIMARY KEY (exp, arm));
CREATE TABLE experiment_catalog (exp TEXT PRIMARY KEY, platform TEXT, first_utc TEXT, last_utc TEXT, n_attempts INTEGER,
  n_unique_tasks INTEGER, cohort_sha12 TEXT, arms TEXT, models TEXT, adapters TEXT, max_model_len INTEGER,
  resolved INTEGER, verified INTEGER, verified_known INTEGER, overflow INTEGER, slug TEXT, signature TEXT,
  log_sections INTEGER);
CREATE TABLE arm_catalog (exp TEXT, arm TEXT, n INTEGER, rounds INTEGER, resolved INTEGER, verified INTEGER,
  verified_known INTEGER, resolve_rate REAL, verified_rate REAL, overflow INTEGER, mean_s REAL, bundle_sha12 TEXT,
  changed_vs_pack1 TEXT, PRIMARY KEY (exp, arm));
CREATE VIEW repeated_experiments AS
  SELECT signature, COUNT(*) AS n_exps, GROUP_CONCAT(exp, ' | ') AS exps, MIN(first_utc) AS first, MAX(last_utc) AS last
  FROM experiment_catalog WHERE signature IS NOT NULL GROUP BY signature HAVING COUNT(*) > 1;
"""
PACK1 = "colab_fasteval/arms/C_pack1"


def run(db, vfs):
    db.executescript(SCHEMA)
    p1 = db.execute("SELECT bundle_id FROM bundles WHERE path = ?", (PACK1,)).fetchone()
    base = {r: (s, b, c) for r, s, b, c in db.execute(
        "SELECT relpath, sha256, bytes, content FROM bundle_files WHERE bundle_id = ?", (p1[0],))} if p1 else {}
    changed = {}
    for (bid,) in db.execute("SELECT bundle_id FROM bundles").fetchall():
        files = {r: (s, b, c) for r, s, b, c in db.execute(
            "SELECT relpath, sha256, bytes, content FROM bundle_files WHERE bundle_id = ?", (bid,))}
        ch = []
        for r in sorted(set(files) | set(base)):
            if r not in base:
                ch.append((r, "added", None, files[r][1], (files[r][2] or "")[:20000]))
            elif r not in files:
                ch.append((r, "removed", base[r][1], None, None))
            elif files[r][0] != base[r][0]:
                d = "".join(difflib.unified_diff((base[r][2] or "").splitlines(True), (files[r][2] or "").splitlines(True),
                                                 "pack1/" + r, "bundle/" + r, n=1))[:20000]
                ch.append((r, "modified", base[r][1], files[r][1], d))
        db.executemany("INSERT INTO bundle_diffs VALUES (?,?,?,?,?,?)", [(bid, *c) for c in ch])
        changed[bid] = sorted(f"{c[1][0]}:{c[0]}" for c in ch)
    # arm -> bundle
    for exp, role, bid in db.execute("SELECT exp, role, bundle_id FROM exp_bundles").fetchall():
        for (arm,) in db.execute("SELECT DISTINCT arm FROM attempts WHERE exp = ? AND arm IS NOT NULL", (exp,)):
            want = "baseline" if arm in ("base", "control", "C_pack1") else "treatment"
            if role == want:
                db.execute("INSERT OR IGNORE INTO arm_bundles VALUES (?,?,?,?)", (exp, arm, bid, f"registration:{role}"))
    by_name = {}
    for bid, path, sha in db.execute("SELECT bundle_id, path, sha12 FROM bundles"):
        by_name.setdefault(path.rsplit("/", 1)[-1], {}).setdefault(sha, bid)
    for exp, arm in db.execute("SELECT DISTINCT exp, arm FROM attempts WHERE arm IS NOT NULL").fetchall():
        m = by_name.get(arm)
        if m and len(m) == 1:
            db.execute("INSERT OR IGNORE INTO arm_bundles VALUES (?,?,?,?)", (exp, arm, next(iter(m.values())), "arm-name (unique sha)"))
    # catalogs
    utc = lambda t: time.strftime("%Y-%m-%d %H:%M", time.gmtime(t)) if t else None
    for (exp,) in db.execute("SELECT DISTINCT exp FROM attempts").fetchall():
        a = db.execute("""SELECT COUNT(*), COUNT(DISTINCT task), GROUP_CONCAT(DISTINCT arm), GROUP_CONCAT(DISTINCT model),
            SUM(resolved), SUM(verified), SUM(verified IS NOT NULL), SUM(error_class = 'overflow')
            FROM attempts_unique WHERE exp = ?""", (exp,)).fetchone()
        tasks = sorted(t for (t,) in db.execute("SELECT DISTINCT task FROM attempts_unique WHERE exp = ? AND task IS NOT NULL", (exp,)))
        ts = db.execute("""SELECT MIN(t.first_ts), MAX(t.last_ts) FROM traces t JOIN attempts x ON x.id = t.attempt_id
                           WHERE x.exp = ? AND t.first_ts > 1.6e9""", (exp,)).fetchone()
        has_v = db.execute("SELECT name FROM sqlite_master WHERE name = 'vllm_servers'").fetchone()
        max_len = db.execute("SELECT MAX(max_model_len) FROM vllm_servers WHERE exp = ?", (exp,)).fetchone()[0] if has_v else None
        loras = set()
        for (lm,) in (db.execute("SELECT lora_modules FROM vllm_servers WHERE exp = ?", (exp,)) if has_v else []):
            loras |= {x for x in json.loads(lm or "[]") if x}
        e = db.execute("SELECT slug, adapter_sha256 FROM experiments WHERE exp = ?", (exp,)).fetchone() or (None, None)
        adapters = json.dumps(sorted(loras | ({f"sha256:{e[1][:12]}"} if e[1] else set())))
        sv = (max_len, None)
        arms = sorted(set((a[2] or "").split(","))) if a[2] else []
        ch = {arm: changed.get(b) for arm, b in db.execute("SELECT arm, bundle_id FROM arm_bundles WHERE exp = ?", (exp,))}
        cohort = hashlib.sha1(",".join(tasks).encode()).hexdigest()[:12] if tasks else None
        plat = "kaggle" if "kaggle" in exp or (e[0] or "").startswith("comfyops/") else "colab" if exp.startswith(("colab", "ab_logs")) else "local/other"
        sig_src = json.dumps([cohort, sorted(set((a[3] or "").split(","))), adapters, sorted((k, v) for k, v in ch.items() if v is not None)])
        sig = hashlib.sha1(sig_src.encode()).hexdigest()[:12] if ch else None
        nlog = db.execute("SELECT COUNT(DISTINCT sec_id) FROM log_mentions WHERE kind = 'exp' AND value = ?", (exp,)).fetchone()[0] \
            if db.execute("SELECT name FROM sqlite_master WHERE name = 'log_mentions'").fetchone() else None
        db.execute("INSERT OR REPLACE INTO experiment_catalog VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            exp, plat, utc(ts[0]), utc(ts[1]), a[0], a[1], cohort, json.dumps(arms), a[3], adapters, sv[0],
            a[4], a[5], a[6], a[7], e[0], sig, nlog))
    db.executescript("""
    INSERT OR REPLACE INTO arm_catalog
    SELECT u.exp, u.arm, COUNT(*), COUNT(DISTINCT u.round), SUM(u.resolved), SUM(u.verified), SUM(u.verified IS NOT NULL),
      ROUND(1.0 * SUM(u.resolved) / COUNT(*), 3),
      ROUND(1.0 * SUM(u.verified) / NULLIF(SUM(u.verified IS NOT NULL), 0), 3),
      SUM(u.error_class = 'overflow'), ROUND(AVG(u.duration_s), 1), b.sha12, NULL
    FROM attempts_unique u LEFT JOIN arm_bundles ab ON ab.exp = u.exp AND ab.arm = u.arm
    LEFT JOIN bundles b ON b.bundle_id = ab.bundle_id WHERE u.arm IS NOT NULL GROUP BY u.exp, u.arm;
    """)
    for exp, arm, bid in db.execute("SELECT exp, arm, bundle_id FROM arm_bundles").fetchall():
        db.execute("UPDATE arm_catalog SET changed_vs_pack1 = ? WHERE exp = ? AND arm = ?",
                   (json.dumps(changed.get(bid)), exp, arm))
    n = db.execute("SELECT COUNT(*), (SELECT COUNT(*) FROM arm_bundles), (SELECT COUNT(*) FROM repeated_experiments) FROM experiment_catalog").fetchone()
    print(f"    {n[0]} experiments catalogued, {n[1]} arms mapped to bundles, {n[2]} repeated signatures", flush=True)
