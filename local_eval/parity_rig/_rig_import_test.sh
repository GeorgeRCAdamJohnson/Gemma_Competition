#!/bin/bash
# Does the rig's verification actually import the workspace, or site-packages?
set -u
mkdir -p /tmp/w && tar xzf /snaps/rich_3006.tgz -C /tmp/w
cd /tmp/w || exit 1

echo "=== A. harness editable-install line ==="
pip install --no-index --find-links=/wheels --no-build-isolation --no-deps -e /workspace >/dev/null 2>&1
echo "pip rc=$?  (/wheels exists: $([ -d /wheels ] && echo yes || echo no))"

echo "=== B. where does rich come from under the harness command? ==="
PYTHONSAFEPATH=1 PYTHONNOUSERSITE=1 python -s -c "import rich; print('rich ->', rich.__file__)"

echo "=== C. sabotage the workspace rich, then run the harness pytest ==="
printf '\nraise RuntimeError("WORKSPACE_RICH_IMPORTED")\n' >> rich/__init__.py
PYTHONSAFEPATH=1 PYTHONNOUSERSITE=1 python -s -m pytest tests/test_console.py -q 2>&1 | tail -3

echo "=== D. same but without PYTHONSAFEPATH (workspace on path) ==="
python -m pytest tests/test_console.py -q 2>&1 | tail -3
