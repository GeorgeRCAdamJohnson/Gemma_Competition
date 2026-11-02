"""swegemma CLI with the SCORER's context management turned on (compaction-faithful local runs).

The stock `python -m swegemma eval` builds EvalConfig with events_compaction_config=None and context_cache_config=None
(swegemma/cli.py:245-266). The scorer configures both (comp_official/HARNESS_README.md 7.2 and the official
getting-started notebook): EventsCompactionConfig(compaction_interval=15, overlap_size=2, token_threshold=14336,
event_retention_size=5) and ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10).
This wrapper injects exactly those values and then runs the normal CLI. Usage (inside the rig image):
    python /rig/_compact_main.py eval --tasks ... (same args as `python -m swegemma eval`)
"""
import sys

import swegemma.cli as cli
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig

_orig = cli.EvalConfig


def _patched(**kw):
    kw.setdefault("events_compaction_config", EventsCompactionConfig(
        compaction_interval=15, overlap_size=2, token_threshold=14336, event_retention_size=5))
    kw.setdefault("context_cache_config", ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10))
    return _orig(**kw)


cli.EvalConfig = _patched
print("[compact_main] scorer compaction ON: interval=15 overlap=2 token_threshold=14336 retention=5", flush=True)
sys.exit(cli.main(sys.argv[1:]))
