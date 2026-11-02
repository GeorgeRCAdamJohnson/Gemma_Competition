import io, json, sys, urllib.error
sys.path.insert(0, r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval")
import run_local as R

R.TRACE_FILE = None
calls = {"n": 0}


def parse_fail(messages, model):
    calls["n"] += 1
    body = json.dumps({"error": {"code": 500, "message": "Failed to parse tool call arguments as JSON: boom"}}).encode()
    raise urllib.error.HTTPError("http://x", 500, "err", {}, io.BytesIO(body))


def other_500(messages, model):
    calls["n"] += 1
    raise urllib.error.HTTPError("http://x", 500, "err", {}, io.BytesIO(b'{"error":{"message":"kv cache full"}}'))


R.chat = parse_fail
stats = {"turns": 3}
r = R.chat_retry([], "m", stats, "t")
assert calls["n"] == 1, calls
assert r["choices"][0]["finish_reason"] == "length"
assert r["choices"][0]["message"]["content"] == "<|tool_call>"
assert stats["unclosed_calls"] == 1 and "chat_retries" not in stats, stats

R.time.sleep = lambda s: None
R.chat = other_500
calls["n"] = 0
try:
    R.chat_retry([], "m", {"turns": 0}, "t")
    raise SystemExit("expected the non-parse 500 to be retried and re-raised")
except urllib.error.HTTPError:
    pass
assert calls["n"] == R.CHAT_RETRIES + 1, calls
print("OK: parse-failure 500 -> synthetic unclosed turn (no retries); other 500s still retried", R.CHAT_RETRIES, "times")
