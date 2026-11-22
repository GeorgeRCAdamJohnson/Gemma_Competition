# Check prior work in the intel DB before proposing or judging a lever

The project has run hundreds of experiments; most "new" ideas have been tried. The intel DB (`kb/attempts.sqlite`,
built by `python kb/attemptdb/build.py`) indexes every section of `GEMMA_EXPERIMENT_LOG.md` and every crawled
document (READMEs, audits, receipts, configs, notebooks).

## Rules
1. **Before calling any idea "untested", "new" or "never tried", or recommending it, search for it:**
   `python kb/attemptdb/q.py --prior "<terms>"` (FTS5 syntax: `max_output_tokens 16384`, `"40 calls"`,
   `verify AND reserve`). Try two or three phrasings (the parameter name, the value, the plain-English idea).
2. **Cite what you find** by log line (`line_start`) or document path, with its result. If nothing matches, say
   "not found in the DB" and list the searches you ran; do not write "untested".
3. **For arm-level effects, check the measured tables too:** `arm_catalog` (what each arm changed),
   `Outputs/DIRECTION_REGISTER.md` (arm vs its own control) and `Outputs/ARM_MECHANISMS.md` (task-adjusted).
4. **When comparing against outside notebooks or papers,** run the lookup for each difference before listing it as
   something we could try.
5. If the DB is stale (built before the relevant runs), rebuild it or say the check is incomplete.
