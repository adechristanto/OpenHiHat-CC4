# Verification evidence

The firmware was installed on the attached Raspberry Pi Pico running CircuitPython 7.3.3. The installer verified the SHA256 hash of each copied file. The original application, libraries, and initial NVM contents were backed up under `backups/`.

`python3 -m unittest discover -s tests -v` passed 27 tests. These cover settings validation, calibration, filtering, MIDI encoding and suppression, incomplete writes, sensor faults, and persistence recovery.

The Pico-side synthetic fixture sent all 128 CC4 values and three reverse-polarity values through the actual USB MIDI port. macOS CoreMIDI received the expected 131 messages, including channel 2, without extra bytes. The fixture did not write NVM. See `artifacts/usb-midi-capture.txt` and `artifacts/pico-fixture.txt`.

An uncalibrated setting persisted across a hard reset. The final saved curve is linear. The final status reported `state=uncalibrated`, no calibration endpoints, `midi_sent=0`, and no persistence error. See `artifacts/persistence-after-reset.txt` and `artifacts/final-status.txt`.

The user subsequently measured a RealHat pedal and reported that the preliminary breadboard circuit, continuous pedal response, and foot-splash operation worked in Addictive Drums 2. This is user-reported evidence from one setup. A Logic Pro session, simultaneous physical pads, idle jitter, and physical latency remain unverified.

The running firmware reports missed 1 ms sampling deadlines even after removing repeated imports from its clock path. The 1 kHz target and under-10 ms position-to-USB target are not verified. Bench results and local artifacts are not included in a source release.
