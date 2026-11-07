"""Rate-limit-safe pull of specific files from a kernel's output.

The kaggle client's kernels_output() recurses through pages with no delay, which trips 429 on kernels with
thousands of output files. This pages at page_size 100 with a pause, backs off on 429, and downloads only files
whose path matches PATTERN. Stops early once every name in WANT (if given) has been found.

usage: python kaggle_pkg/_pull_slow.py <owner/slug> <dest_dir> <regex> [exact_name ...]
"""
import os
import re
import sys
import time

import requests
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest

kernel, dest, pattern = sys.argv[1], sys.argv[2], re.compile(sys.argv[3])
want = set(sys.argv[4:])
owner, slug = kernel.split("/")
api = KaggleApi()
api.authenticate()
token, page, got = None, 0, []
while True:
    page += 1
    req = ApiListKernelSessionOutputRequest()
    req.user_name, req.kernel_slug, req.page_size = owner, slug, 100
    if token:
        req.page_token = token
    for attempt in range(8):
        try:
            with api.build_kaggle_client() as k:
                resp = k.kernels.kernels_api_client.list_kernel_session_output(req)
            break
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"page {page}: 429, sleeping {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise
    else:
        sys.exit("gave up after repeated 429s")
    files = resp.files or []
    for f in files:
        if pattern.search(f.file_name):
            out = os.path.join(dest, f.file_name)
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            r = requests.get(f.url, timeout=120)
            r.raise_for_status()
            open(out, "wb").write(r.content)
            got.append(f.file_name)
            print(f"downloaded {f.file_name} ({len(r.content)} B)", flush=True)
    print(f"page {page}: {len(files)} files listed, {len(got)} downloaded so far", flush=True)
    token = resp.next_page_token
    if not token or (want and want <= {os.path.basename(g) for g in got} | set(got)):
        break
    time.sleep(4)
print("DONE", got)
