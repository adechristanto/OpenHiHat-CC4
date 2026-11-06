# Calibrate and configure the pedal

Complete the [electrical measurement record](hardware.md) and use an approved protected circuit first. Do not calibrate the floating GP26 input as if it were a pedal.

Run commands from the project root. These commands communicate with the running firmware. They do not enter the Python REPL.

1. Inspect the raw input while moving the pedal. Confirm a usable continuous range.

   ```sh
   python3 tools/pico_console.py --command raw
   ```

2. Hold the pedal fully open, then start open capture.

   ```sh
   python3 tools/pico_console.py --command 'calibrate open'
   python3 tools/pico_console.py --command status
   ```

   Wait for `state=awaiting_closed`. The firmware averages a stable window. If capture is unstable or times out, hold the endpoint and repeat open capture.

3. Hold the pedal fully closed, then start closed capture.

   ```sh
   python3 tools/pico_console.py --command 'calibrate closed'
   python3 tools/pico_console.py --command status
   ```

   A successful capture validates the endpoint span, saves the calibration, and enters `state=running`. Confirm the stored endpoint values in status. A failed save must leave output disabled.

4. Move the pedal through its range. Confirm closed 0, open 127, and useful intermediate values using a MIDI monitor.
5. Restart the Pico and confirm the endpoints load from NVM. Repeat the closed and open checks.

Open and closed raw values may increase or decrease with pedal movement. Calibration handles either polarity. Use inversion only for an intentional change of MIDI convention.

To stop an unfinished capture, send `cancel`. To see the command list, send `help`.

## Change settings

`set` validates a setting and applies it in RAM. Use `save` to retain it across restarts. Successful endpoint calibration saves automatically. Never change settings or calibrate during a performance.

```sh
python3 tools/pico_console.py --command 'set channel 1'
python3 tools/pico_console.py --command 'set curve linear'
python3 tools/pico_console.py --command 'set filter_alpha 0.2'
python3 tools/pico_console.py --command 'set invert off'
python3 tools/pico_console.py --command save
```

| Field | Default | Allowed values |
|---|---|---|
| `channel` | 1 | Integers 1 through 16 |
| `max_midi_rate_hz` | 250 | Integers 1 through 250 |
| `curve` | `linear` | `linear`, `soft`, `hard` |
| `filter_alpha` | 0.2 | 0.001 through 1.0, stored at 0.001 precision |
| `invert` | false | `on`, `off`, `true`, `false` |
| `hysteresis` | 0.15 | 0 through 0.49 in CC-value units |
| `min_calibration_span` | 1024 | Integers 1 through 65535 in CircuitPython ADC units |
| `stability_tolerance` | 256 | Integers 1 through 65535 in CircuitPython ADC units |
| `stability_samples` | 128 | Integers 8 through 512 |

The raw ADC representation is 0 through 65535. That scale does not imply a 16-bit physical ADC. Lower `filter_alpha` smooths more and responds more slowly. `soft` squares normalized position. `hard` uses `1 - (1 - position)^2`. Both curves preserve calibrated endpoints.

The controller number stays fixed at 4. Sampling targets 1,000 Hz. Note generation is absent. Calibration endpoints cannot be assigned through `set`.

Settings occupy a bounded record in `microcontroller.nvm`. They do not require writes to the mounted CIRCUITPY filesystem. A version or checksum failure disables output and requires diagnosis or recalibration. Power loss during a save can corrupt that record.
