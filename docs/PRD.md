# PRD — OpenHiHat CC4 Converter

> Historical specification. The implementation and current verification status are documented in the README and verification guide.

**Version:** 1.0<br>
**Project type:** DIY Hardware + Embedded Firmware<br>
**Target platform:** Raspberry Pi Pico (RP2040)<br>
**Primary integration:** macOS, Logic Pro, Addictive Drums 2<br>
**Project status:** Specification — pending pedal identification<br>
**Language:** Firmware and technical documentation in English

## 1. Product Overview

OpenHiHat is a low-cost, open-source USB-MIDI controller that converts the physical position of an electronic hi-hat pedal into continuous MIDI CC4 messages.

The product must operate independently from any drum module, sampler, or MIDI pad controller.

### Problem

The user's current Alesis hi-hat setup does not provide the required continuous MIDI CC4 behavior for Addictive Drums 2.

The user intends to use one or two Millenium NonaPads as MIDI note controllers and wants an independent USB-MIDI device for hi-hat position control.

### Proposed Solution

Build a dedicated microcontroller-based USB-MIDI device using a Raspberry Pi Pico.

The converter will:

1. Measure the hi-hat pedal's electrical position.
2. Normalize and calibrate the sensor values.
3. Smooth electrical noise without sacrificing responsiveness.
4. Convert the position into MIDI CC4, values 0–127.
5. Send MIDI data through USB to the host computer.
6. Support configurable pedal polarity and response curves.
7. Operate without proprietary drivers or a companion app.

## 2. Goals and Non-Goals

### Primary Goals

- Continuous hi-hat position control
- Plug-and-play USB-MIDI operation on macOS
- Compatibility with Addictive Drums 2 CC HiHat mode
- Low-latency response suitable for live drumming
- Stable output without MIDI jitter
- Reusable pedal calibration
- Easy firmware updates
- Low-cost, beginner-friendly construction

### Non-Goals (MVP)

- Generating drum sounds
- Acting as a USB host for other MIDI devices
- Reading velocity from drum pads
- MIDI DIN connectivity
- Wireless MIDI
- Modifying the firmware of an Alesis or Millenium drum pad
- Supporting multiple pedal inputs in the first version

## 3. Critical Hardware Discovery

Before implementing a final schematic, identify the exact Alesis pedal model and electrical behavior.

The developer must not assume that every Alesis pedal is an ordinary potentiometer or that every jack has the same pinout.

Required discovery:

- Record pedal model and connector type (TS, TRS, TRRS, or proprietary).
- Measure resistance between every applicable contact pair while the pedal is disconnected and unpowered.
- Record resistance at fully open, 25%, 50%, 75%, and fully closed.
- Check whether the resistance changes continuously, in discrete steps, or only as an on/off contact.
- Identify whether the pedal is passive or requires excitation power.
- Determine its electrical output topology.
- Document the correct jack wiring before connecting the microcontroller.

**Hardware gate:** No final input circuit shall be approved until these measurements are complete.

If the pedal is an active voltage-output device, a passive resistive-sensor circuit must not be used without redesign.

## 4. System Architecture

Signal pipeline:

Alesis Pedal<br>
→ 6.35 mm Input Jack<br>
→ Protected Analog Interface<br>
→ RP2040 ADC<br>
→ Signal Processing<br>
→ Calibration / Response Mapping<br>
→ MIDI CC4 Encoder<br>
→ USB-MIDI Device<br>
→ macOS / Logic Pro<br>
→ Addictive Drums 2

The device shall not require the Alesis Strike Multipad to function.

## 5. Hardware Requirements

### HW-001 — Microcontroller

Use Raspberry Pi Pico (RP2040) for the MVP.

Required interfaces:

- One ADC input
- Native USB device interface
- Nonvolatile configuration storage
- One optional status LED

### HW-002 — Pedal Interface

Provide a 6.35 mm jack compatible with the identified pedal.

The interface must:

- Detect the measured pedal resistance or voltage
- Avoid exceeding RP2040 ADC voltage limits
- Include appropriate current limiting and input filtering
- Avoid applying external voltage to an unpowered microcontroller
- Provide physical strain relief for cables

### HW-003 — Analog Measurements

The firmware shall acquire the pedal sensor at a target rate of 1,000 samples per second.

ADC readings must be converted into a normalized position.

Electrical noise must be filtered.

### HW-004 — USB

Use the microcontroller's native USB port for both power and MIDI communication.

The device must enumerate as a USB-MIDI class-compliant device.

Proposed device name:

`OpenHiHat CC4`

### HW-005 — Power

USB bus-powered operation only.

No external power supply is required for the confirmed passive-sensor design.

### HW-006 — Enclosure

After successful prototyping, install all components in a nonconductive enclosure with accessible USB and pedal connectors.

## 6. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Read pedal position | P0 |
| FR-002 | Send MIDI CC4 | P0 |
| FR-003 | Support USB-MIDI class | P0 |
| FR-004 | Calibrate open/closed endpoints | P0 |
| FR-005 | Invert pedal direction | P0 |
| FR-006 | Filter ADC noise | P0 |
| FR-007 | Suppress redundant CC messages | P0 |
| FR-008 | Persist calibration settings | P1 |
| FR-009 | Configurable response curve | P1 |
| FR-010 | Serial diagnostic mode | P1 |
| FR-011 | Detect disconnected pedal where electrically possible | P1 |
| FR-012 | Configurable MIDI channel | P1 |
| FR-013 | Optional foot-chick MIDI event | P2 |
| FR-014 | Optional hardware calibration button | P2 |

P0 = required for MVP, P1 = recommended for V1, P2 = future enhancement.

## 7. MIDI Specification

### MIDI Format

- Protocol: USB-MIDI 1.0
- Message: Control Change
- Default MIDI channel: 1
- Controller: 4
- Valid data values: 0–127

### Position Convention

| Pedal State | MIDI CC4 |
|---|---|
| Fully closed | 0 |
| 25% open | ~32 |
| Half open | ~64 |
| 75% open | ~95 |
| Fully open | 127 |

Intermediate values are illustrative targets after calibration, not guaranteed sensor readings.

Example channel-1 MIDI messages:

- Closed: `B0 04 00`
- Half open: `B0 04 40`
- Fully open: `B0 04 7F`

### Message Transmission

- Transmit a value immediately after USB initialization and a valid sensor reading.
- Send CC4 when the quantized value changes.
- Do not continuously repeat unchanged CC values.
- Support a configurable maximum update rate, initially 250 updates per second.
- Avoid batching that increases latency.
- Preserve message ordering.
- Do not send arbitrary Note On messages during initialization.

## 8. Calibration Requirements

Calibration is mandatory because different pedals may have different electrical ranges.

### Calibration Procedure

1. Enter calibration mode.
2. Release the pedal fully.
3. Record multiple raw ADC measurements.
4. Average the stable readings as `open_raw`.
5. Press the pedal fully.
6. Record and average the stable readings as `closed_raw`.
7. Validate that the measured range exceeds the minimum usable ADC span.
8. Save both endpoints.
9. Determine polarity automatically or allow manual override.
10. Return to operational mode.

Calibration shall also be accessible via a USB serial console or configuration file.

### Data Processing

Normalize:

`position = clamp((raw - closed_raw) / (open_raw - closed_raw), 0, 1)`

The formula must handle increasing and decreasing ADC values without division by zero.

Output:

`cc4 = round(position * 127)`

Apply a user-configurable response curve after normalization.

### Curves

Implement:

- Linear (default)
- Soft
- Hard
- Custom lookup table (future)

The response must be monotonic, and both calibrated endpoints must remain reachable.

## 9. Noise Filtering and Responsiveness

The controller shall:

- Sample ADC data at 1 kHz.
- Apply lightweight filtering (initially a small median filter and an adjustable low-pass filter).
- Prevent single-sample spikes.
- Suppress repetitive CC messages caused by electrical noise.
- Allow rapid pedal movements without sluggish response.

Avoid excessive smoothing that delays closing and reopening events.

### Performance Targets

These are design targets requiring measurement, not guaranteed hardware specifications.

| Metric | Target |
|---|---|
| ADC sampling | 1,000 Hz |
| CC range | 0–127 |
| Position-to-USB submission | Under 10 ms |
| Maximum CC rate | 250 messages/s |
| Stable idle output | No repeated CC jitter |
| USB reconnection | Automatic |
| Unintended Note On events | Zero |

Track physical-to-DAW behavior separately, because operating-system scheduling and audio buffer size affect total audible latency.

## 10. Fault Handling

The firmware must handle:

- Missing calibration
- Short circuit or out-of-range sensor
- Disconnected pedal, where detectable
- USB unplug/replug
- Corrupted configuration
- Invalid calibration range
- Unsupported or unrecognized sensor behavior

On configuration failure, enter a safe calibration/diagnostic mode.

Do not assume every ADC endpoint value indicates a disconnected pedal.

## 11. Firmware Architecture

Suggested modules:

`main.py` — initialization and main loop<br>
`pedal.py` — ADC acquisition<br>
`calibration.py` — endpoint calibration<br>
`filter.py` — signal conditioning<br>
`mapping.py` — normalized position and response curve<br>
`midi_output.py` — USB-MIDI messages<br>
`settings.py` — persistent configuration<br>
`diagnostics.py` — serial logging and troubleshooting

The modules must be independently testable.

Use CircuitPython for the initial implementation, with an optional migration to the Pico SDK / TinyUSB in a later version if latency measurements justify it.

Avoid unnecessary allocations and file writes in the high-frequency sampling loop.

## 12. Configuration

Suggested configuration fields:

```json
{
  "device_name": "OpenHiHat CC4",
  "midi_channel": 1,
  "cc_number": 4,
  "sample_rate_hz": 1000,
  "max_midi_rate_hz": 250,
  "open_raw": null,
  "closed_raw": null,
  "curve": "linear",
  "filter_strength": 0.2,
  "debug": false,
  "generate_foot_chick_note": false
}
```

Null endpoint values mean calibration has not yet been completed.

Configuration validation is mandatory.

## 13. Addictive Drums 2 Integration

The converter must work alongside one or more independent USB-MIDI drum pad controllers.

Proposed setup:

- NonaPad 1: drum MIDI notes
- NonaPad 2: additional drum MIDI notes
- OpenHiHat: MIDI CC4
- Addictive Drums 2: final audio rendering

Use AD2's CC HiHat mode.

Map the hi-hat strike pad to `CC Hihat Tip` or another appropriate CC hi-hat articulation.

Map the converter's CC4 as the pedal position source.

Avoid separate note mappings that generate duplicate pedal-chick events.

Initially rely on Addictive Drums 2's built-in Foot Close and Foot Splash detection.

## 14. Testing and Acceptance Criteria

### Unit Tests

- ADC normalization
- Calibration with increasing sensor values
- Calibration with decreasing sensor values
- Invalid calibration range
- Monotonic curve output
- MIDI message encoding
- Redundant-message suppression
- Configuration validation
- Fault handling

### Hardware Tests

- Confirm correct pedal wiring
- Confirm no ADC input overvoltage
- Confirm stable USB recognition
- Confirm actual raw ADC readings change with pedal position
- Confirm closed = 0 and open = 127
- Confirm usable intermediate values
- Confirm stable output at rest
- Confirm rapid movements are tracked reliably

### Integration Tests

- Device appears in macOS MIDI Studio
- Logic Pro receives CC4
- Addictive Drums 2 responds to continuous pedal position
- Closed, partially open, and open articulations are distinguishable
- Foot Chick and Foot Splash work after AD2 sensitivity tuning
- Two additional MIDI pad controllers operate simultaneously
- No stuck or duplicated hi-hat events

### Acceptance Criteria

MVP is considered complete only when:

1. The actual Alesis pedal is electrically identified.
2. The circuit operates without exceeding component ratings.
3. The converter functions without the Strike Multipad.
4. macOS identifies it as a USB-MIDI device.
5. CC4 responds correctly to measured pedal movement.
6. Intermediate hi-hat positions are usable in Addictive Drums 2.
7. Idle jitter is absent.
8. Measured controller processing latency meets the target.
9. Firmware and wiring instructions are documented.
10. All P0 tests pass.

## 15. Deliverables

The developer must deliver:

1. Full firmware source code
2. Dependency and toolchain documentation
3. Exact supported hardware list
4. Confirmed pinout and electrical schematic
5. Breadboard wiring instructions
6. Calibration instructions
7. Flashing guide
8. USB-MIDI verification guide
9. Logic Pro / Addictive Drums 2 setup guide
10. Automated tests and test results
11. Troubleshooting guide
12. README and open-source project structure

## 16. Implementation Milestones

**M0 — Sensor Discovery:** Identify the pedal's electrical characteristics and prove that its position can be measured.

**M1 — Hardware Prototype:** Build a safe breadboard circuit and read stable sensor data.

**M2 — USB-MIDI MVP:** Send CC4 messages from the Pico to macOS.

**M3 — Calibration and Filtering:** Implement stable, responsive positioning and persistent settings.

**M4 — DAW Integration:** Verify the entire setup with Logic Pro, Addictive Drums 2, and external MIDI pads.

**M5 — Finished Device:** Produce a soldered or PCB-based build with enclosure and documentation.

## 17. Engineering Principles

- Prefer simple, maintainable hardware and firmware.
- Never assume an undocumented pedal pinout.
- Validate electrical compatibility before applying voltage.
- Keep input processing separate from MIDI output.
- Prioritize responsiveness and reliability over additional features.
- Preserve the ability to flash updated firmware.
- Do not replace a hardware measurement problem with speculative software compensation.
- Document actual measurements and test evidence instead of claiming unverified compatibility.

**Final product vision:** An inexpensive, dependable, open-source hi-hat controller that turns a compatible analog electronic drum pedal into a class-compliant MIDI CC4 device, independently of any commercial drum module.
