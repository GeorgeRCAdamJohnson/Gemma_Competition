cd "$1"
echo "== python3 -> $(which python3)"
python3 -c "import sys; print(sys.executable, sys.version.split()[0])"
python3 -c "import rich.console; print('python3 import rich.console OK', rich.__file__)" 2>&1 | tail -3
python3 -c "import pygments; print('pygments OK')" 2>&1 | tail -1
python3 -c "import markdown_it; print('markdown_it OK')" 2>&1 | tail -1
python3 -c "import pytest; print('pytest OK', pytest.__version__)" 2>&1 | tail -1
echo "== python -> $(which python)"
python -c "import sys; print(sys.executable, sys.version.split()[0])"
python -c "import rich.console; print('python import rich.console OK')" 2>&1 | tail -3
python -m pytest --version 2>&1 | tail -2
