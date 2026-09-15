import os
import sys
import time
from pathlib import Path

log_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "KidProductionz Sales OS" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
with (log_dir / "pyinstaller-smoke.log").open("w", encoding="utf-8") as fh:
    fh.write("SMOKE_TEST_STARTED\n")
    fh.write(f"sys.executable={sys.executable}\n")
    fh.write(f"sys.frozen={getattr(sys, 'frozen', False)}\n")
    fh.write(f"cwd={os.getcwd()}\n")
time.sleep(30)
