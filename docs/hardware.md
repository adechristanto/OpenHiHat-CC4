# Hardware reference

## Identified hardware

The tested board identifies itself as `Raspberry Pi Pico with rp2040`. Its board ID is `raspberry_pi_pico`. It ran Adafruit CircuitPython 7.3.3.

The user identifies the pedal as an Alesis RealHat continuous pedal. The photographed plug is a two-contact TS plug. The user measured resistance across tip and sleeve with the pedal disconnected from power. The readings indicate a variable resistance; its internal construction has not been independently inspected.

The software input is GP26, ADC0, physical pin 31. This identifies the firmware input only. It does not specify a pedal connection.

One RealHat pedal was tested with the preliminary divider below. Component ratings, transient protection, long-term operation, and other pedal models remain unverified. This is a prototype, not an approved production circuit.

```text
Pico 3V3 (pin 36) ── 8.08 kΩ measured resistor ──┬── GP26 / ADC0 (pin 31)
                                                  └── pedal tip
Pico AGND (pin 33) ───────────────────────────────── pedal sleeve
```

The pedal must be isolated from any drum module or other power source. Verify the pedal type and resistance before connecting it. Never apply an external voltage to an unpowered Pico. Confirm the pinout and input voltage with a meter before use.

## Electrical limits

The RP2040 ADC accepts a signal within the board's ADC supply range. On the standard Pico, design for 0 to 3.3 V relative to analog ground. Do not connect a drum module output or an unknown pedal voltage to GP26. Do not apply a signal to an unpowered Pico.

The future input circuit needs current limiting, appropriate protection, filtering, and strain relief. Its component values depend on the measured pedal topology. An active voltage source needs a different design from a passive resistance sensor.

GP26 floats when nothing is connected. Changing raw values in that condition do not prove pedal response or a disconnected-pedal detector. ADC rail readings alone do not distinguish valid endpoints from faults.

## Discovery record

Complete this record with the pedal disconnected and unpowered before approving an input circuit.

| Item | Observation |
|---|---|
| Exact pedal model and label | User reports Alesis RealHat continuous |
| Connector type and contact names | Photographed TS plug, tip and sleeve |
| Passive or active output | User's unpowered resistance measurements suggest passive; internal construction not independently inspected |
| Resistance between each contact pair, fully open | Tip to sleeve: 70 kΩ |
| Resistance between each contact pair, 25% closed | Tip to sleeve: approximately 60 kΩ |
| Resistance between each contact pair, 50% closed | Tip to sleeve: approximately 40 kΩ |
| Resistance between each contact pair, 75% closed | Tip to sleeve: approximately 20 kΩ |
| Resistance between each contact pair, fully closed | Tip to sleeve: approximately 1–5 kΩ depending on pressure |
| Continuous, stepped, or switch behavior | User reports smooth change |
| Excitation requirement | Divider needed to obtain a voltage; independently powered sources excluded from preliminary test |
| Approved protected circuit and jack pinout | Pending |
| Voltage at GP26 | User reported a range within 0–3.26 V; exact endpoint voltages not recorded |

## Sources

The [Raspberry Pi Pico datasheet](https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf) describes board pins and ADC connections. The [RP2040 datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf) specifies ADC electrical characteristics.
