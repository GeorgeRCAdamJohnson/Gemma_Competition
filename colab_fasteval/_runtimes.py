"""Print exact Colab runtime names (API) with accelerator and host, one per line."""
import json
import sys

sys.path.insert(0, "colab_fasteval")
import colab_mcp as c

out = c.call("list_runtimes", {})
for r in (out.get("result", {}).get("structuredContent", {}) or {}).get("runtimes", []):
    host = r.get("connectionInfo", {}).get("url", "").split("//")[-1].split(".")[0]
    print(repr(r["name"]), r["runtimeSpec"].get("accelerator"), host)
