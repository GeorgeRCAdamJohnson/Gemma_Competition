#!/bin/bash
mkdir -p ~/.local/bin
printf '#!/bin/bash\nexec /usr/bin/gcc "$@" -lstdc++\n' > ~/.local/bin/g++
chmod +x ~/.local/bin/g++
~/.local/bin/uv pip install -q ninja 2>/dev/null || true
if [ -x ~/vllmenv/bin/ninja ]; then ln -sf ~/vllmenv/bin/ninja ~/.local/bin/ninja; fi
echo "--- verify ---"
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.local/bin
command -v g++ ninja gcc
nvcc_test=$(
  PATH="$HOME/.local/bin:/usr/bin" nvcc --version 2>&1 | head -1
)
echo "g++ runs: $(g++ --version 2>&1 | head -1)"
echo "ninja runs: $(ninja --version 2>&1)"