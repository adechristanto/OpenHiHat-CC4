# Contributing

Contributions and reproducible bug reports are welcome. Describe the board, CircuitPython version, pedal model, circuit, and steps to reproduce hardware issues. Do not include USB serial numbers, private backups, or device configuration dumps in public issues.

Run `python3 -m unittest discover -s tests -v` after firmware changes. Run `node --check web/app.js` after changing the browser interface. Describe which checks used physical hardware and which used simulated inputs.

Do not assume a pedal's wiring or electrical behavior from its model name alone. Document circuit measurements, component ratings, and unverified assumptions. Preserve safe behavior when calibration is missing or invalid.

By submitting a contribution, you agree to license your contribution under the MIT license in this project.
