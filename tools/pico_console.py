#!/usr/bin/env python3
"""Send a bounded command to a CircuitPython console using macOS serial APIs."""

import argparse
import glob
import os
from pathlib import Path
import select
import termios
import time


class Console:
    def __init__(self, port):
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.original = termios.tcgetattr(self.fd)
        attrs = termios.tcgetattr(self.fd)
        attrs[0] = 0
        attrs[1] = 0
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] = 0
        attrs[4] = termios.B115200
        attrs[5] = termios.B115200
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)

    def write(self, data):
        while data:
            _, ready, _ = select.select([], [self.fd], [], 2)
            if not ready:
                raise TimeoutError("Serial write timed out")
            count = os.write(self.fd, data)
            data = data[count:]

    def read(self, seconds=1, until=None):
        deadline = time.monotonic() + seconds
        data = bytearray()
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.fd], [], [], min(0.1, max(0, deadline - time.monotonic())))
            if ready:
                chunk = os.read(self.fd, 8192)
                if chunk:
                    data.extend(chunk)
            if until and until in data:
                break
        return bytes(data)

    def repl(self, source, seconds=5):
        self.write(b"\x03")
        self.read(0.2)
        self.write(b"\x03")
        self.read(0.2)
        self.write(b"\x01")
        banner = self.read(2, b"raw REPL; CTRL-B to exit\r\n>")
        if b"raw REPL" not in banner:
            raise RuntimeError("Could not enter raw REPL: " + repr(banner))
        self.write(source.encode("utf-8") + b"\x04")
        result = self.read(seconds, b"\x04>")
        self.write(b"\x02")
        if not result.startswith(b"OK") or b"\x04>" not in result:
            raise RuntimeError("Incomplete REPL response: " + repr(result))
        output, error = result[2:].split(b"\x04", 1)
        error = error.rsplit(b"\x04>", 1)[0]
        if error:
            raise RuntimeError(error.decode("utf-8", "replace"))
        return output.decode("utf-8", "replace")

    def close(self):
        try:
            termios.tcsetattr(self.fd, termios.TCSANOW, self.original)
        except (OSError, termios.error):
            pass
        os.close(self.fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--repl", help="Interrupt firmware and execute Python")
    mode.add_argument("--repl-file", type=Path, help="Interrupt firmware and execute a local Python file")
    mode.add_argument("--command", help="Send one line to the running firmware")
    mode.add_argument("--listen", action="store_true")
    mode.add_argument("--reset", action="store_true", help="Hard-reset from an existing friendly REPL prompt")
    parser.add_argument("--seconds", type=float, default=2)
    parser.add_argument("--output", help="Save the response to a local file")
    args = parser.parse_args()
    ports = glob.glob("/dev/cu.usbmodem*")
    deadline = time.monotonic() + 5
    while not args.port and not ports and time.monotonic() < deadline:
        time.sleep(0.1)
        ports = glob.glob("/dev/cu.usbmodem*")
    if not args.port and len(ports) != 1:
        parser.error("Specify --port when there is not exactly one USB serial device")
    console = Console(args.port or ports[0])
    try:
        if args.repl is not None or args.repl_file is not None:
            source = args.repl if args.repl is not None else args.repl_file.read_text()
            result = console.repl(source, args.seconds)
        else:
            if args.reset:
                console.write(b"import microcontroller; microcontroller.reset()\r\n")
            elif args.command is not None:
                console.write(args.command.encode("utf-8") + b"\n")
            try:
                result = console.read(args.seconds).decode("utf-8", "replace")
            except OSError:
                if not args.reset:
                    raise
                result = "Pico serial device disconnected during reset. Reopen the port to verify startup.\n"
        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(result)
            print("Saved console response to " + args.output)
        else:
            print(result, end="")
    finally:
        console.close()


if __name__ == "__main__":
    main()
