from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
UTILS = ROOT / "utils"
if str(UTILS) not in sys.path:
    sys.path.append(str(UTILS))
