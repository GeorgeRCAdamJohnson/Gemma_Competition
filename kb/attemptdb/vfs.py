"""Virtual file system over the repo AND tar archives, so archived runs (e.g. the 31B ca5 results.tar.gz files) are
ingested like normal directories. A virtual path (vpath) is a repo-relative posix path; archive members are
'<archive relpath>!/<member path>'."""
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP = re.compile(r"[\\/](\.git|node_modules|venv|\.venv|site-packages|__pycache__|upstream)[\\/]")
RESULT_ARCHIVE = re.compile(r"(results|smoke_results)\.tar(\.gz)?$|ab_logs\.tar\.gz$")


class VFS:
    def __init__(self, roots=("Outputs",), archives=True):
        self.files = {}  # vpath -> (kind, ref)  kind 'fs' (Path) or 'tar' (archive Path, member name)
        for r in roots:
            base = ROOT / r
            for p in base.rglob("*") if base.is_dir() else []:
                if p.is_file() and not SKIP.search(str(p)):
                    self.files[p.relative_to(ROOT).as_posix()] = ("fs", p)
        self.tars = {}
        if archives:
            for vp, (_, p) in list(self.files.items()):
                if RESULT_ARCHIVE.search(p.name):
                    try:
                        t = tarfile.open(p)
                        self.tars[vp] = t
                        for m in t.getmembers():
                            if m.isfile():
                                self.files[f"{vp}!/{m.name.lstrip('./')}"] = ("tar", (vp, m))
                    except (tarfile.TarError, OSError):
                        pass

    def exists(self, vp):
        return vp in self.files

    def read(self, vp, limit=None):
        kind, ref = self.files[vp]
        if kind == "fs":
            with open(ref, "rb") as f:
                return f.read(limit) if limit else f.read()
        tar_vp, m = ref
        f = self.tars[tar_vp].extractfile(m)
        return f.read(limit) if limit else f.read()

    def text(self, vp, limit=None):
        return self.read(vp, limit).decode("utf-8", errors="replace")

    def size(self, vp):
        kind, ref = self.files[vp]
        return ref.stat().st_size if kind == "fs" else ref[1].size

    def glob_name(self, name):
        return sorted(vp for vp in self.files if vp.rsplit("/", 1)[-1] == name)

    def match(self, regex):
        rx = re.compile(regex)
        return sorted(vp for vp in self.files if rx.search(vp))


def parent(vp):
    return vp.rsplit("/", 1)[0]


def parts_after_outputs(vp):
    """path components after 'Outputs/', with an archive's member path appended after the archive's own dir."""
    outer, _, member = vp.partition("!/")
    o = outer.split("/")
    o = o[1:] if o and o[0] == "Outputs" else o
    if member:
        o = o[:-1] + [p for p in member.split("/") if p]  # archive file name replaced by its member path
    return o
