#!/bin/bash
set -e
UV=$HOME/.local/bin/uv
echo "=== install managed 3.13 ==="
$UV python install 3.13
$UV python find 3.13
echo "=== headers check ==="
$UV run --python 3.13 python -c "import sysconfig,os; p=sysconfig.get_paths()['include']; print(p); assert os.path.exists(os.path.join(p,'Python.h')), 'NO HEADERS'"
echo PYTHON_H_OK
echo "=== rebuild venv on 3.13 ==="
$UV venv --clear ~/vllmenv --python 3.13
echo "=== install vllm cp313 ==="
$UV pip install -q --python ~/vllmenv/bin/python vllm
echo "=== verify ==="
~/vllmenv/bin/python -c "import sysconfig,os,vllm; p=sysconfig.get_paths()['include']; print('include:',p,'hdr:',os.path.exists(os.path.join(p,'Python.h')),'vllm:',vllm.__version__)"
echo VLLM_REINSTALL_DONE