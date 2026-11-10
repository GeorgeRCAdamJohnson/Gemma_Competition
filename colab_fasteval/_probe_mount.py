# Runs ON the Colab VM (separate kernel): is Drive mounted, and is the kaggle pin list present?
import os
from pathlib import Path

print("hostname", os.uname().nodename)
print("drive mounted:", os.path.ismount("/content/drive"), "| MyDrive:", Path("/content/drive/MyDrive").exists())
print("pins:", Path("/content/kaggle_pins.txt").exists())
