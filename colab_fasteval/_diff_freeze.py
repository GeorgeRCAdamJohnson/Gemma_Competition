"""Summarize the Kaggle task environment (freeze_after_wheelhouse.txt): GPU stack versions, test tooling, and the
packages most likely imported by fastapi/rich/requests task tests."""
import re
from pathlib import Path

lines = Path("Outputs/env_freeze/freeze_after_wheelhouse.txt").read_text(encoding="utf-8").splitlines()
pk = {}
for l in lines:
    m = re.match(r"^([A-Za-z0-9_.\-]+)==(.+)$", l.strip())
    if m:
        pk[m.group(1).lower().replace("_", "-")] = m.group(2)
    elif " @ " in l:
        n = l.split(" @ ")[0].strip().lower().replace("_", "-")
        pk[n] = "@url"
print("packages:", len(pk))
show = ["torch", "vllm", "transformers", "tensorflow", "jax", "numpy", "pytest", "pytest-timeout", "pytest-asyncio",
        "pytest-cov", "pytest-xdist", "anyio", "trio", "pydantic", "pydantic-core", "starlette", "fastapi", "httpx",
        "sqlalchemy", "sqlmodel", "databases", "orjson", "ujson", "email-validator", "python-multipart", "jinja2",
        "pyyaml", "dirty-equals", "inline-snapshot", "typer", "flask", "rich", "pygments", "markdown-it-py",
        "attrs", "requests", "urllib3", "idna", "charset-normalizer", "pysocks", "trustme", "werkzeug",
        "typing-extensions", "coverage", "mypy", "passlib", "python-jose", "pyjwt", "aiosqlite", "peewee"]
for s in show:
    print(f"  {s:22s} {pk.get(s, '-')}")
Path("Outputs/env_freeze/kaggle_pins.txt").write_text("\n".join(f"{k}=={v}" for k, v in sorted(pk.items()) if v != "@url") + "\n")
