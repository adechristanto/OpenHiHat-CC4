#!/usr/bin/env python3
"""Back up and install OpenHiHat files on an identified CIRCUITPY volume."""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path("/Volumes/CIRCUITPY"))
    parser.add_argument("--apply", action="store_true", help="Write files after backing up existing versions")
    args = parser.parse_args()
    target = args.target.resolve()
    boot_info = (target / "boot_out.txt").read_text()
    if "Board ID:raspberry_pi_pico" not in [line.strip() for line in boot_info.splitlines()]:
        parser.error("Target is not the identified Raspberry Pi Pico CircuitPython volume")
    sources = sorted((ROOT / "firmware").glob("*.py"), key=lambda p: (p.name == "code.py", p.name))
    if not sources or not any(path.name == "code.py" for path in sources):
        parser.error("Firmware source must contain code.py")
    manifest = {path.name: digest(path) for path in sources}
    for source in sources:
        compile(source.read_text(), str(source), "exec")
    print("Target " + str(target))
    print("Firmware files " + ", ".join(manifest))
    if not args.apply:
        print("Dry run. Stop the running app and disable autoreload before using --apply.")
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup = ROOT / "backups" / ("install-" + stamp)
    backup.mkdir(parents=True)
    for source in sources:
        destination = target / source.name
        if destination.exists():
            shutil.copy2(destination, backup / source.name)
    shutil.copy2(target / "boot_out.txt", backup / "boot_out.txt")
    for source in sources:
        with (target / source.name).open("wb") as handle:
            handle.write(source.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        if digest(target / source.name) != manifest[source.name]:
            raise RuntimeError("Installed file hash mismatch: " + source.name)
    report = {"target": str(target), "backup": str(backup), "sha256": manifest}
    report_path = ROOT / "artifacts" / "installed-manifest.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print("Verified every installed file against its SHA256.")
    print("Backup " + str(backup))
    print("Hard-reset the Pico to apply boot.py USB configuration.")


if __name__ == "__main__":
    main()
