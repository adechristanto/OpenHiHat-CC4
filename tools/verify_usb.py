#!/usr/bin/env python3
"""Capture real Pico USB MIDI from an in-memory fixture and check the byte stream."""

import argparse
from pathlib import Path
import select
import subprocess
import time
from pico_console import Console


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--match", default="Pico")
    args = parser.parse_args()
    binary = ROOT / "artifacts" / "midi_probe"
    subprocess.run([
        "clang", "-Wall", "-Wextra", "-Werror", str(ROOT / "tools" / "midi_probe.c"),
        "-framework", "CoreMIDI", "-framework", "CoreFoundation", "-o", str(binary),
    ], check=True)
    capture = subprocess.Popen([str(binary), args.match, "5"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = bytearray()
    try:
        deadline = time.monotonic() + 4
        while b"CONNECTED " not in output:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("MIDI source did not connect: " + output.decode())
            ready, _, _ = select.select([capture.stdout], [], [], remaining)
            if ready:
                chunk = capture.stdout.read1(8192)
                if not chunk:
                    raise RuntimeError("MIDI capture exited: " + capture.stderr.read().decode())
                output.extend(chunk)
        console = Console(args.port)
        try:
            fixture_result = console.repl((ROOT / "tools" / "pico_usb_fixture.py").read_text(), seconds=4)
        finally:
            console.close()
        remaining, errors = capture.communicate(timeout=7)
        output.extend(remaining)
        if capture.returncode:
            raise RuntimeError(errors.decode())
        capture_text = output.decode()
        (ROOT / "artifacts" / "usb-midi-capture.txt").write_text(capture_text)
        (ROOT / "artifacts" / "pico-fixture.txt").write_text(fixture_result)
        stream = []
        for line in capture_text.splitlines():
            if line.startswith("MIDI "):
                stream.extend(int(byte, 16) for byte in line.split()[1:])
        expected = [byte for value in range(128) for byte in (0xB0, 4, value)]
        expected.extend(byte for value in (0, 64, 127) for byte in (0xB1, 4, value))
        if stream != expected:
            raise AssertionError("USB MIDI byte stream differed from all 131 expected CC4 messages. See artifacts/usb-midi-capture.txt")
        if "FIXTURE_OK" not in fixture_result:
            raise AssertionError("Pico fixture did not finish")
        print("PASS. Received exactly 131 expected CC4 messages through macOS CoreMIDI, with no extra bytes or notes.")
        print("PASS. Both raw polarities, every CC value, channel 2, and duplicate suppression matched the fixture.")
        print("PASS. Pico NVM was unchanged. The fixture used synthetic input, not a physical pedal.")
        print("The application is stopped at the REPL. Hard-reset the Pico and verify its safe startup state.")
    finally:
        if capture.poll() is None:
            capture.terminate()
            capture.communicate(timeout=2)


if __name__ == "__main__":
    main()
