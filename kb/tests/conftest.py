import pathlib
import sys

KB = pathlib.Path(__file__).resolve().parent.parent
if str(KB) not in sys.path:
    sys.path.insert(0, str(KB))
