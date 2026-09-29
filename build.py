from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REQUIRED_INPUTS = [
    ROOT / "L01-26_GML.zip",
    ROOT / "source-data" / "ne_10m_admin_1_states_provinces_data.zip",
]
missing = [path for path in REQUIRED_INPUTS if not path.is_file()]
if missing:
    print("再生成に必要な入力データがありません:", file=sys.stderr)
    for path in missing:
        print(f"  {path}", file=sys.stderr)
    print("地価データはREADMEの公式データページから取得してください。", file=sys.stderr)
    raise SystemExit(2)

subprocess.run([sys.executable, str(ROOT / "map.py")], cwd=ROOT, check=True)
subprocess.run(
    [sys.executable, str(ROOT / "tools" / "check_external_dependencies.py"), "--site", str(ROOT / "site")],
    cwd=ROOT,
    check=True,
)