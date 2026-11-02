"""Put a shortcut to PDF Text Extractor on the desktop: an application on a Mac, a shortcut (.lnk) on Windows.

    python -m pdftextextractor.shortcut [--if-missing]
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
NAME = "PDF Text Extractor"


def desktop() -> Path:
    if sys.platform == "win32":
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                                 capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if out.stdout.strip():
                return Path(out.stdout.strip())
        except Exception:  # noqa: BLE001
            pass
    return Path.home() / "Desktop"


def make_mac_app(where: Path) -> Path:
    """An application bundle that starts the app (or, before the first set-up, opens the set-up in Terminal)."""
    app = where / f"{NAME}.app"
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps({
        "CFBundleName": NAME, "CFBundleDisplayName": NAME, "CFBundleExecutable": NAME, "CFBundleIdentifier": "local.pdftextextractor",
        "CFBundlePackageType": "APPL", "CFBundleShortVersionString": "1.0", "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True}))
    exe = macos / NAME
    exe.write_text(f'''#!/bin/bash
APP="{APP_DIR}"
if [ -f "$APP/.venv/.ready" ] && "$APP/.venv/bin/python" -c "import PySide6, pymupdf" >/dev/null 2>&1; then
  cd "$APP" && exec "$APP/.venv/bin/python" -m pdftextextractor
else
  open -a Terminal "$APP/start_mac.command"
fi
''', encoding="utf-8")
    os.chmod(exe, 0o755)
    return app


def make_windows_lnk(where: Path) -> Path:
    lnk = where / f"{NAME}.lnk"
    target = APP_DIR / "start_windows.bat"
    q = lambda p: "'" + str(p).replace("'", "''") + "'"
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({q(lnk)});$s.TargetPath={q(target)};"
          f"$s.WorkingDirectory={q(APP_DIR)};$s.WindowStyle=7;$s.Description={q(NAME)};$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], check=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return lnk


def main() -> int:
    where = desktop()
    target = where / (f"{NAME}.app" if sys.platform == "darwin" else f"{NAME}.lnk")
    if "--if-missing" in sys.argv and target.exists():
        return 0
    made = make_mac_app(where) if sys.platform == "darwin" else make_windows_lnk(where) if sys.platform == "win32" else None
    print(f"shortcut: {made}" if made else "no desktop shortcut is made on this system")
    return 0


if __name__ == "__main__":
    sys.exit(main())
