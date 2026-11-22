"""Launch one registered private experiment, or resume its version-pinned collection."""
import argparse
import ast
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import time


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATTERN = re.compile(r"\.(json|jsonl|log|patch|diff)$")
TERMINAL = {"COMPLETE", "ERROR", "CANCEL_ACKNOWLEDGED"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def cell_sources(notebook):
    return [(cell["cell_type"], "".join(cell["source"])) for cell in notebook["cells"]]


def preflight(package, *, for_launch=False):
    metadata = read_json(package / "kernel-metadata.json")
    registration = read_json(package / "registration.json")
    if for_launch and registration.get("inspect_only"):
        raise ValueError("This is an inspect-only template; prepare a new package before launch")
    code = metadata["code_file"]
    if Path(code).name != code or not code.endswith(".ipynb"):
        raise ValueError("code_file must be a notebook filename within the package")
    if (metadata.get("is_private") is not True or metadata.get("kernel_type") != "notebook"
            or metadata.get("language") != "python"):
        raise ValueError("Only explicitly private Python notebook experiments are supported")
    if not re.fullmatch(r"[\w-]+/[\w-]+", registration["slug"]):
        raise ValueError("Invalid registered kernel slug")
    if metadata["id"] != registration["slug"]:
        raise ValueError("Metadata slug differs from registration")
    if not registration.get("comparison") or not registration.get("criteria"):
        raise ValueError("Register the hypothesis/comparison and decision criteria first")
    seconds = registration.get("notebook_seconds")
    if type(seconds) is not int or seconds <= 0:
        raise ValueError("Register a positive notebook_seconds platform limit")
    raw = (package / code).read_bytes()
    if digest(raw) != registration["notebook_sha256"]:
        raise ValueError("Notebook hash differs from registration")
    notebook = json.loads(raw)
    trees = [ast.parse(source) for kind, source in cell_sources(notebook) if kind == "code"]
    if "bundle_sha256" in registration:
        bundles = [
            node.value.args[0].value
            for tree in trees for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "bundle" for target in node.targets)
            and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == "base64"
            and node.value.func.attr == "b64decode" and len(node.value.args) == 1
            and isinstance(node.value.args[0], ast.Constant)
            and isinstance(node.value.args[0].value, (str, bytes))
        ]
        if len(bundles) != 1:
            raise ValueError("Expected one literal base64 input bundle")
        bundle = base64.b64decode(bundles[0], validate=True)
        if digest(bundle) != registration["bundle_sha256"]:
            raise ValueError("Embedded input bundle differs from registration")
        with tarfile.open(fileobj=io.BytesIO(bundle)) as archive:
            files = {}
            for member in archive.getmembers():
                if member.isfile():
                    if member.name in files:
                        raise ValueError("Duplicate input bundle member")
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ValueError(f"Unreadable bundle member: {member.name}")
                    files[member.name] = stream.read()
        if registration.get("task_content") == "mounted":
            if "tasks.jsonl" in files or not re.fullmatch(r"[a-f0-9]{64}", registration["tasks_sha256"]):
                raise ValueError("Mounted task definitions must have a pinned hash and not be embedded")
        elif digest(files["tasks.jsonl"]) != registration["tasks_sha256"]:
            raise ValueError("Embedded task definitions differ from registration")
        if json.loads(files["ab_tasks.json"]) != registration["task_ids"]:
            raise ValueError("Embedded task IDs differ from registration")
        for arm, expected in registration["arm_hashes"].items():
            prefix = f"arms/{arm}/"
            hashes = {name[len(prefix):]: digest(data) for name, data in sorted(files.items())
                      if name.startswith(prefix)}
            if not hashes or digest(json.dumps(hashes, sort_keys=True).encode()) != expected:
                raise ValueError(f"Embedded arm differs from registration: {arm}")
    return metadata, registration


def retry_read(operation):
    import requests

    for attempt in range(3):
        try:
            return operation()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as error:
            response = getattr(error, "response", None)
            status = response.status_code if response is not None else None
            if (status is not None and status != 429 and status < 500) or attempt == 2:
                raise
            print(f"Read failed ({type(error).__name__}, HTTP {status}); retry {attempt + 1}/2",
                  flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("Read retries exhausted")


class KaggleBackend:
    def __init__(self):
        from kaggle.api.kaggle_api_extended import KaggleApi

        self.api = KaggleApi()
        self.api.authenticate()

    def owned_kernel_exists(self, slug):
        page = 1
        while True:
            kernels = self.api.kernels_list(
                mine=True, search=slug.split("/")[-1], page=page, page_size=100,
            )
            if kernels is None:
                raise RuntimeError("Kaggle returned no owned-kernel listing")
            if any(kernel.ref == slug for kernel in kernels):
                return True
            if len(kernels) < 100:
                return False
            page += 1

    def source(self, slug, version=None):
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest

        request = ApiGetKernelRequest()
        request.user_name, request.kernel_slug = slug.split("/")
        if version is not None:
            request.version_label = f"v{version}"
        with self.api.build_kaggle_client() as client:
            return client.kernels.kernels_api_client.get_kernel(request)

    def status(self, slug, version):
        result = self.api.kernels_status(f"{slug}/{version}")
        return result.status.name, result.failure_message

    def push(self, package, seconds, accelerator):
        import requests

        try:
            result = self.api.kernels_push(str(package), timeout=str(seconds), acc=accelerator)
        except requests.HTTPError as error:
            if error.response is None:
                raise
            raise RuntimeError(
                f"Kaggle push rejected: HTTP {error.response.status_code}: "
                f"{error.response.text}"
            ) from error
        invalid = {name: getattr(result, name) for name in (
            "invalid_tags", "invalid_dataset_sources", "invalid_kernel_sources",
            "invalid_competition_sources", "invalid_model_sources",
        ) if getattr(result, name)}
        if result.error or invalid:
            raise RuntimeError(f"Kaggle push rejected or changed inputs: {result.error}; {invalid}")
        if result.version_number < 1:
            raise RuntimeError("Push returned no version; inspect Kaggle before recovery")
        return result.version_number

    def page(self, slug, version, token):
        from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest

        request = ApiListKernelSessionOutputRequest()
        request.user_name, request.kernel_slug = slug.split("/")
        request.version_label = f"v{version}"
        request.page_size = 100
        if token:
            request.page_token = token
        with self.api.build_kaggle_client() as client:
            return client.kernels.kernels_api_client.list_kernel_session_output(request)


def verify_remote(backend, state, output):
    result = retry_read(lambda: backend.source(state["slug"], state["version"]))
    expected = read_json(output / "package" / state["code_file"])
    remote = json.loads(result.blob.source)
    if result.metadata.is_private is not True or cell_sources(remote) != cell_sources(expected):
        raise RuntimeError("Remote privacy/source mismatch; stop and inspect this version, do not repush")
    write_json(output / "remote_notebook.json", remote)


def launch(backend, package, output, expected_version, accelerator, log):
    metadata, registration = preflight(package, for_launch=True)
    if expected_version < 1:
        raise ValueError("Expected version must be positive")
    if expected_version == 1:
        if retry_read(lambda: backend.owned_kernel_exists(registration["slug"])):
            raise RuntimeError("Expected a new kernel, but this owned slug already exists")
    else:
        head = retry_read(lambda: backend.source(registration["slug"]))
        current = head.metadata.current_version_number
        if current != expected_version - 1:
            raise RuntimeError(f"Expected previous version {expected_version - 1}, found {current}")
        status, _ = retry_read(lambda: backend.status(registration["slug"], current))
        if status not in TERMINAL:
            raise RuntimeError(f"Previous version is {status}; no new launch")
    if output.resolve().is_relative_to(package.resolve()):
        raise ValueError("Output must be outside the frozen package")
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "package"
    frozen.mkdir()
    for name in (metadata["code_file"], "kernel-metadata.json", "registration.json"):
        (frozen / name).write_bytes((package / name).read_bytes())
    frozen_metadata, frozen_registration = preflight(frozen, for_launch=True)
    if frozen_metadata != metadata or frozen_registration != registration:
        raise ValueError("Package metadata/registration changed during preflight; no push")
    state = {
        "slug": registration["slug"], "expected_version": expected_version,
        "version": None, "code_file": metadata["code_file"],
        "accelerator": accelerator, "notebook_seconds": registration["notebook_seconds"],
        "notebook_sha256": registration["notebook_sha256"],
        "metadata_sha256": digest((frozen / "kernel-metadata.json").read_bytes()),
        "registration_sha256": digest((frozen / "registration.json").read_bytes()),
        "log": str(log.resolve()),
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "phase": "registered",
    }
    write_json(output / "receipt.json", state)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(
            f"\n\n### {state['registered_at']} - private experiment launch registration\n\n"
            f"Package receipt: `{output.resolve()}`; slug `{state['slug']}`; "
            f"expected version {expected_version}; accelerator `{accelerator}`; "
            f"requested platform cap {state['notebook_seconds']}s.\n"
            f"Notebook SHA256 `{state['notebook_sha256']}`; "
            f"metadata SHA256 `{state['metadata_sha256']}`; "
            f"registration SHA256 `{state['registration_sha256']}`.\n"
            f"Comparison: {registration['comparison']}\n\n"
            f"Decision criteria: `{json.dumps(registration['criteria'], sort_keys=True)}`.\n"
            "No leaderboard submission or automatic relaunch. Runtime/quota/cost not independently "
            "verified by this local launcher; inspect the saved hardware/runtime log.\n"
        )
    state["phase"] = "push_attempted_do_not_retry"
    write_json(output / "receipt.json", state)
    version = backend.push(frozen, state["notebook_seconds"], accelerator)
    state.update(version=version, phase="pushed")
    write_json(output / "receipt.json", state)
    if version != expected_version:
        raise RuntimeError(f"Concurrent push: got version {version}, expected {expected_version}; inspect receipt")
    return state


def download(url, target):
    import requests

    temporary = target.with_suffix(target.suffix + ".part")
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with temporary.open("wb") as stream:
            for chunk in response.iter_content(1024 * 1024):
                stream.write(chunk)
        length = response.headers.get("Content-Length")
        if not response.headers.get("Content-Encoding") and length is not None:
            if temporary.stat().st_size != int(length):
                raise RuntimeError(f"Incomplete output download: {target.name}")
    temporary.replace(target)


def collect(backend, state, output):
    destination = output / "results"
    destination.mkdir(exist_ok=True)
    token = None
    seen = set()
    count = 0
    while True:
        page = retry_read(lambda: backend.page(state["slug"], state["version"], token))
        if page.log:
            (destination / "kernel.log").write_text(page.log, encoding="utf-8")
        for item in page.files or []:
            name = PurePosixPath(item.file_name)
            if name.is_absolute() or ".." in name.parts or "\\" in item.file_name or ":" in item.file_name:
                raise ValueError(f"Unsafe remote output name: {item.file_name}")
            if not OUTPUT_PATTERN.search(item.file_name):
                continue
            target = destination.joinpath(*name.parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Output path escapes destination")
            target.parent.mkdir(parents=True, exist_ok=True)
            retry_read(lambda: download(item.url, target))
            count += 1
        token = page.next_page_token
        print(f"Collected {count} result/trace/log files", flush=True)
        if not token:
            break
        if token in seen:
            raise RuntimeError("Kaggle repeated an output page token")
        seen.add(token)
        time.sleep(4)
    return count


def monitor(backend, state, output, wait_seconds, poll_seconds):
    verify_remote(backend, state, output)
    state["phase"] = "source_verified"
    write_json(output / "receipt.json", state)
    deadline = time.monotonic() + wait_seconds
    while True:
        status, failure = retry_read(lambda: backend.status(state["slug"], state["version"]))
        state.update(status=status, failure_message=failure, phase="monitoring")
        write_json(output / "receipt.json", state)
        print(f"{state['slug']} v{state['version']}: {status} {failure}", flush=True)
        if status in TERMINAL:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            state["phase"] = "monitor_deadline_remote_may_still_run"
            write_json(output / "receipt.json", state)
            print("Local monitoring deadline; remote may still run. Resume this receipt, never relaunch.")
            return 4
        time.sleep(min(poll_seconds, remaining))
    state["downloaded_files"] = collect(backend, state, output)
    summaries = list((output / "results").rglob("memory_summary.json"))
    if len(summaries) > 1:
        raise RuntimeError("Ambiguous experiment summaries; inspect downloaded results")
    summary = read_json(summaries[0]) if summaries else None
    report = {
        "slug": state["slug"], "version": state["version"], "platform_status": status,
        "experiment_summary": summary,
        "warning": "Missing/unstarted grades are not failures. Partial cohorts are not paired comparisons. "
                   "Local scores are not leaderboard predictions.",
    }
    write_json(output / "result_report.json", report)
    table = ""
    try:  # per-task results table; never blocks collection
        from kaggle_pkg.results_table import build as build_table
        table = build_table(output)
        print(table, flush=True)
    except Exception as error:  # noqa: BLE001
        print(f"Results table not built: {error!r}", flush=True)
    report_hash = digest((output / "result_report.json").read_bytes())
    if state.get("logged_report_sha256") != report_hash:
        with Path(state["log"]).open("a", encoding="utf-8") as stream:
            stream.write(
                f"\n\n### {datetime.now(timezone.utc).isoformat()} - private experiment collected\n\n"
                f"`{state['slug']}` version {state['version']}; platform `{status}`.\n"
                f"Result receipt: `{(output / 'result_report.json').resolve()}`; "
                f"SHA256 `{report_hash}`.\n\n"
                f"Saved summary: `{json.dumps(summary, sort_keys=True)}`.\n\n"
                f"{report['warning']}\n"
                + (f"\nResults table (`{(output / 'RESULTS_TABLE.md').resolve()}`):\n\n"
                   + table.split("\n\n", 2)[-1] + "\n" if table else "")
            )
        state["logged_report_sha256"] = report_hash
    state["phase"] = "collected"
    write_json(output / "receipt.json", state)
    print(json.dumps(report, indent=2), flush=True)
    if status != "COMPLETE":
        return 3
    return 0 if summary is not None and summary.get("complete") is True else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Offline validation only; no auth, upload or GPU")
    check.add_argument("--package", required=True, type=Path)
    start = commands.add_parser("launch", help="Preregister, push once, monitor and collect")
    start.add_argument("--package", required=True, type=Path)
    start.add_argument("--expected-version", required=True, type=int)
    start.add_argument("--accelerator", required=True, choices=["NvidiaL4"])
    start.add_argument("--log", type=Path, default=ROOT / "GEMMA_EXPERIMENT_LOG.md")
    resume = commands.add_parser("resume", help="Read-only Kaggle operations; NEVER pushes")
    resume.add_argument("--recover-version", type=int,
                        help="After ambiguous push only: explicit expected version, source-verified before use")
    for command in (start, resume):
        command.add_argument("--output", required=True, type=Path)
        command.add_argument("--wait-seconds", type=int, default=7200)
        command.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()
    if args.command == "check":
        _, registration = preflight(args.package)
        print(f"OFFLINE_PREFLIGHT_OK {registration['slug']} {registration['notebook_sha256']}")
        return 0
    if args.wait_seconds <= 0 or args.poll_seconds <= 0:
        parser.error("Monitoring intervals must be positive")
    if args.command == "launch":
        preflight(args.package, for_launch=True)
        if args.output.exists():
            parser.error("Output already exists; use resume, never relaunch")
        backend = KaggleBackend()
        state = launch(backend, args.package, args.output, args.expected_version, args.accelerator, args.log)
    else:
        state = read_json(args.output / "receipt.json")
        frozen = args.output / "package"
        preflight(frozen)
        for key, name in (("notebook_sha256", state["code_file"]),
                          ("metadata_sha256", "kernel-metadata.json"),
                          ("registration_sha256", "registration.json")):
            if digest((frozen / name).read_bytes()) != state[key]:
                raise ValueError(f"Receipt/package mismatch: {name}")
        if args.recover_version is not None:
            if state["version"] is not None or args.recover_version != state["expected_version"]:
                parser.error("Recovery requires an ambiguous push and the preregistered expected version")
            state["version"] = args.recover_version
        if not state["version"]:
            parser.error("Push outcome unknown; inspect Kaggle, then resume with --recover-version N")
        backend = KaggleBackend()
    return monitor(backend, state, args.output, args.wait_seconds, args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
