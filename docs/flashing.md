# Install or restore OpenHiHat

## Install on this Pico

This project targets the original Raspberry Pi Pico with RP2040. Install CircuitPython and connect the `CIRCUITPY` drive first. The prototype used CircuitPython 7.3.3. The firmware uses only CircuitPython built-ins. The host tools use Python 3 and macOS system frameworks. No pip package is required.

Back up the complete existing CIRCUITPY drive and any important device-specific NVM before installation. The installer backs up only files that it overwrites; it does not make a complete device or NVM backup.

Run commands from the project root.

1. Run the desktop tests.

   ```sh
   python3 -m unittest discover -s tests -v
   ```

2. Check the target and source files without writing the board.

   ```sh
   python3 tools/install.py
   ```

3. Stop the running application and suspend autoreload while copying files.

   ```sh
   python3 tools/pico_console.py --repl 'import supervisor; supervisor.disable_autoreload(); print("ready for install")'
   ```

4. Install the files. The installer backs up existing versions of files it overwrites and verifies each installed SHA256 hash. It copies `code.py` last.

   ```sh
   python3 tools/install.py --apply
   ```

5. Hard-reset from the REPL left by step 3. A hard reset applies `boot.py` USB configuration.

   ```sh
   python3 tools/pico_console.py --reset
   ```

6. Read the running firmware's status after the serial port returns.

   ```sh
   python3 tools/pico_console.py --command status
   ```

The firmware must report an uncalibrated or configuration-error state when no valid calibration exists. It must emit no CC data in that state. Use `--port /dev/cu.usbmodem...` if more than one USB serial device is present.

`code.py` takes precedence over an existing `main.py`. OpenHiHat does not overwrite `main.py` or the existing library directory, but you should still keep a complete backup before installation.

## Restore the old application

1. Stop OpenHiHat with the REPL command used above.
2. Rename the installed `code.py` on `CIRCUITPY` to `code.py.disabled`. Preserve a copy of the installed `boot.py`, then rename it to `boot.py.disabled` if the previous application needs the original USB setup.
3. Restore your original `main.py` from your own backup if it has changed.
4. Hard-reset the board. The original application runs from `main.py` again.

The installer does not back up NVM. OpenHiHat stores configuration in a leading NVM record. Restoring a separately captured NVM backup is a distinct maintenance action. Do not overwrite NVM during a routine firmware update.

## Recover an unusable CircuitPython installation

Use the official [Raspberry Pi Pico CircuitPython download page](https://circuitpython.org/board/raspberry_pi_pico/). Hold BOOTSEL while connecting USB to expose the RP2040 boot drive, then copy the correct Pico UF2. Back up the mounted filesystem and NVM first when they are accessible. A runtime upgrade can change USB names or library compatibility. Repeat serial and MIDI verification after any upgrade.
