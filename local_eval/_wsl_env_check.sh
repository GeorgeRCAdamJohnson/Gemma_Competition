#!/bin/bash
python3 --version
pip3 --version 2>&1 | head -1
echo "--- disk ---"
df -h / | tail -1
echo "--- mem ---"
free -g | head -2
echo "--- venv ---"
python3 -c 'import venv; print("venv ok")'
echo "--- existing torch/cuda? ---"
python3 -c 'import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available())' 2>&1 | head -2
