"""Wait until the daily submission allowance resets (00:00 UTC + 3 min), then submit one kernel. Retries on the
'daily allowance' error for up to 2 h in case the reset lags. usage: python _submit_at_reset.py <owner/slug> <msg>"""
import datetime as dt
import sys
import time

import requests
from kaggle.api.kaggle_api_extended import KaggleApi

kernel, msg = sys.argv[1], sys.argv[2]
now = dt.datetime.now(dt.timezone.utc)
reset = (now + dt.timedelta(days=1)).replace(hour=0, minute=3, second=0, microsecond=0)
print(f"now {now:%Y-%m-%d %H:%M} UTC, waiting until {reset:%Y-%m-%d %H:%M} UTC ({(reset-now).total_seconds()/3600:.1f} h)", flush=True)
time.sleep(max(0, (reset - now).total_seconds()))
api = KaggleApi()
api.authenticate()
deadline = time.time() + 2 * 3600
while True:
    try:
        r = api.competition_submit_code(file_name="submission.zip", message=msg, competition="gemma-4-developer-agent",
                                        kernel=kernel, kernel_version=1)
        print(f"{dt.datetime.now(dt.timezone.utc):%H:%M} UTC SUBMITTED {kernel}: {r}", flush=True)
        break
    except requests.HTTPError as e:
        body = e.response.text[:400]
        print(f"{dt.datetime.now(dt.timezone.utc):%H:%M} UTC HTTP {e.response.status_code}: {body}", flush=True)
        if "daily Submission allowance" not in body or time.time() > deadline:
            break
        time.sleep(300)
