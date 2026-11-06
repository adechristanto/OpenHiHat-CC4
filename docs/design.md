# Firmware design

The controller converts a calibrated ADC position into MIDI CC4. Calibration owns the relationship between raw sensor endpoints and physical open or closed positions. USB transport owns message completion, rate limits, and duplicate suppression.

Two candidate designs were compared before implementation.

| Criterion | Domain controller | Event reducer |
|---|---|---|
| Calibration and output ownership | Explicit objects with bounded state | One state record and event transitions |
| Sampling allocations | Mutable preallocated filter state | Requires care to avoid event and state allocations |
| Hardware-independent tests | Pure processing and fake transport | Pure reducer and fake effects |
| Maintenance cost | Few domain modules and a thin runtime | More event cases and effect coordination |

The implementation follows the domain controller design. It takes the reducer candidate's small portable processing boundary. It avoids allocating event objects in the sampling loop.

Settings use a versioned, bounded record with a checksum in `microcontroller.nvm`. This avoids simultaneous macOS and firmware writes to the mounted FAT filesystem. Saves occur during explicit maintenance operations. A checksum detects corruption. It does not make a flash write atomic. Power loss during a save can require recalibration.

The Pico's NVM shares an erase region. Two logical slots in that region would not justify a claim that one survives every interrupted flash operation. This implementation makes no such claim.

The application writes three MIDI bytes to `usb_midi.PortOut`. TinyUSB adds USB-MIDI packet framing. The application never writes a four-byte USB packet to the MIDI stream API. The [CircuitPython USB MIDI API](https://docs.circuitpython.org/en/latest/shared-bindings/usb_midi/index.html) documents the port write contract. The [installed-version implementation](https://github.com/adafruit/circuitpython/blob/7.3.3/shared-module/usb_midi/PortOut.c) calls `tud_midi_stream_write` directly.

The application targets 1,000 ADC samples per second and at most 250 CC messages per second by default. CircuitPython and host scheduling can delay progress. These settings do not prove physical-to-USB or audible latency.

CircuitPython 7.3.3 on this board lacks both USB naming APIs. The host-visible source stays `Pico CircuitPython usb_midi.ports[0]`. Feature detection allows newer runtimes to use `OpenHiHat CC4`. The [supervisor API](https://docs.circuitpython.org/en/latest/shared-bindings/supervisor/index.html) documents product naming in `boot.py` on supporting versions.
