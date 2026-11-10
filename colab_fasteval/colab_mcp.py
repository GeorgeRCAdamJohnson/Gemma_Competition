"""Tiny CLI for Google's hosted Colab MCP server (https://colaboratory.googleapis.com/mcp).

Auth: a fresh ADC access token per call (see token()), so the hourly token expiry that breaks a static
Authorization header in mcp.json never bites. Optional quota project via COLAB_QUOTA_PROJECT.
Windows-friendly alternative to the official `colab` CLI (googlecolab/google-colab-cli: Linux/macOS only).

usage:
  python colab_mcp.py tools                         # list tool names
  python colab_mcp.py call <tool> '<json args>'     # call any tool, print the JSON result
  python colab_mcp.py specs | sub | runtimes        # shortcuts for read-only calls
"""
import json
import os
import shutil
import subprocess
import sys
import uuid

import requests

URL = "https://colaboratory.googleapis.com/mcp"


def token():
    """ADC token. The Colab scope is granted once by:
    gcloud auth application-default login --scopes=openid,https://www.googleapis.com/auth/cloud-platform,
        https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory
    (plain `gcloud auth print-access-token` lacks the colaboratory scope -> 403 insufficient scopes)."""
    gcloud = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    return subprocess.run([gcloud, "auth", "application-default", "print-access-token"], capture_output=True,
                          text=True, check=True, shell=os.name == "nt").stdout.strip()


def quota_project():
    """quota_project_id that `gcloud auth application-default login` writes into the ADC file."""
    base = os.environ.get("APPDATA") if os.name == "nt" else os.path.expanduser("~/.config")
    p = os.path.join(base or "", "gcloud", "application_default_credentials.json")
    try:
        return json.load(open(p, encoding="utf-8")).get("quota_project_id")
    except OSError:
        return None


def rpc(method, params=None, auth=True, timeout=660):
    h = {"content-type": "application/json", "accept": "application/json, text/event-stream"}
    if auth:
        h["authorization"] = f"Bearer {token()}"
        qp = os.environ.get("COLAB_QUOTA_PROJECT") or quota_project()
        if qp:
            h["x-goog-user-project"] = qp  # colaboratory.googleapis.com rejects user ADC without one
    body = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params or {}}
    r = requests.post(URL, json=body, headers=h, timeout=timeout, stream=True)
    if r.status_code != 200:
        return {"http_error": r.status_code, "body": r.text[:2000]}
    ctype = r.headers.get("content-type", "")
    if "event-stream" not in ctype:
        return r.json()
    final = None  # SSE: print progress notifications (streamed stdout), keep the final response
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        msg = json.loads(line[5:].strip())
        if msg.get("method", "").endswith("progress"):
            p = msg.get("params", {})
            print(p.get("message", ""), end="" if str(p.get("message", "")).endswith("\n") else "\n", flush=True)
        elif "result" in msg or "error" in msg:
            final = msg
    return final


def redact(s):
    """Hide runtime proxy tokens (short-lived credentials) from printed output."""
    import re
    return re.sub(r'(\\?"token\\?":\s*\\?")[^"\\]+', r"\1<redacted>", s)


def call(tool, args):
    return rpc("tools/call", {"name": tool, "arguments": args})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tools"
    if cmd == "tools":
        out = rpc("tools/list", auth=False)
        print("\n".join(t["name"] for t in out["result"]["tools"]))
        sys.exit()
    short = {"specs": "list_runtime_specs", "sub": "get_subscription", "runtimes": "list_runtimes"}
    if cmd in short:
        out = call(short[cmd], {})
    elif cmd == "call":
        out = call(sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {})
    elif cmd == "exec":
        # exec <runtimes/ID | runtimes/ID/sessions/SID> <local.py> [executionId]
        target, src = sys.argv[2], sys.argv[3]
        args = {("session" if "/sessions/" in target else "runtime"): target,
                "code": open(src, encoding="utf-8").read()}
        if len(sys.argv) > 4:
            args["executionId"] = sys.argv[4]
        out = call("execute_code", args)
        sc = (out or {}).get("result", {}).get("structuredContent")
        if sc is not None:  # print the useful parts, not the whole envelope
            for k in ("stdout", "stderr", "result", "error", "outputTruncated", "session"):
                if sc.get(k):
                    print(f"== {k}\n{sc[k]}")
            sys.exit()
    else:
        sys.exit(__doc__)
    print(redact(json.dumps(out, indent=1))[:20000])
