"""Wait until the daily submission allowance resets (00:00 UTC + 3 min), then submit one kernel.

usage: python _submit_at_reset.py <owner/slug> <msg>

Fixes vs the first version (which stalled):
- polls the WALL CLOCK every 30 s instead of one long time.sleep(); on Windows a sleeping/suspended machine
  does not advance time.sleep, so one long sleep overshoots by the suspend time.
- authenticates AFTER the wait (OAuth token may have refreshed while waiting).
- looks up the kernel's current version instead of hardcoding kernel_version=1.
- retries on the 'daily allowance' error every 2 min for up to 2 h in case the reset lags.
"""
import datetime as dt
import sys
import time

import requests
from kaggle.api.kaggle_api_extended import KaggleApi

kernel, msg = sys.argv[1], sys.argv[2]
owner, slug = kernel.split("/", 1)


def utc():
    return dt.datetime.now(dt.timezone.utc)


now = utc()
reset = now.replace(hour=0, minute=3, second=0, microsecond=0)
if reset <= now:
    reset += dt.timedelta(days=1)
print(f"now {now:%Y-%m-%d %H:%M} UTC, waiting until {reset:%Y-%m-%d %H:%M} UTC "
      f"({(reset - now).total_seconds() / 3600:.1f} h)", flush=True)
last_beat = 0.0
while utc() < reset:
    if time.time() - last_beat > 1800:  # heartbeat every 30 min so a stall is visible
        print(f"  {utc():%H:%M} UTC waiting ({(reset - utc()).total_seconds() / 3600:.2f} h left)", flush=True)
        last_beat = time.time()
    time.sleep(30)

api = KaggleApi()
api.authenticate()
version = 1
try:
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest

    req = ApiGetKernelRequest()
    req.user_name, req.kernel_slug = owner, slug
    with api.build_kaggle_client() as c:
        version = c.kernels.kernels_api_client.get_kernel(req).metadata.current_version_number or 1
except Exception as e:  # fall back to v1 rather than not submitting
    print(f"version lookup failed ({type(e).__name__}: {e}); using v1", flush=True)
print(f"{utc():%H:%M} UTC submitting {kernel} v{version}", flush=True)

def landed():
    """True if a submission of this kernel was created after the reset (a reset connection can still succeed)."""
    try:
        for s in api.competition_submissions("gemma-4-developer-agent")[:5]:
            when = dt.datetime.fromisoformat(str(s.date)).replace(tzinfo=dt.timezone.utc)
            if slug in str(getattr(s, "url", "")) and when >= reset - dt.timedelta(minutes=3):
                print(f"{utc():%H:%M} UTC already landed: ref {s.ref} at {when:%H:%M} UTC ({s.status})", flush=True)
                return True
    except Exception as e:
        print(f"{utc():%H:%M} UTC landed-check failed ({type(e).__name__}); retrying submit", flush=True)
    return False


deadline = time.time() + 2 * 3600
while True:
    if landed():
        break
    try:
        r = api.competition_submit_code(file_name="submission.zip", message=msg, competition="gemma-4-developer-agent",
                                        kernel=kernel, kernel_version=version)
        print(f"{utc():%H:%M} UTC SUBMITTED {kernel} v{version}: {r}", flush=True)
        break
    except requests.HTTPError as e:
        body = e.response.text[:400]
        print(f"{utc():%H:%M} UTC HTTP {e.response.status_code}: {body}", flush=True)
        if "daily Submission allowance" not in body or time.time() > deadline:
            break
        time.sleep(120)
    except Exception as e:  # network blip: retry, don't die
        print(f"{utc():%H:%M} UTC {type(e).__name__}: {str(e)[:300]}", flush=True)
        if time.time() > deadline:
            break
        time.sleep(120)
