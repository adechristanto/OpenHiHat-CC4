# OpenHiHat contributor instructions

Firmware targets CircuitPython on Raspberry Pi Pico RP2040. Keep signal processing testable on desktop Python. Run `python3 -m unittest discover -s tests -v` after firmware changes.

No pedal circuit is approved until its unpowered measurements and exact model are recorded. Do not infer a jack pinout. Missing or invalid calibration must suppress MIDI. Do not generate MIDI notes.

## Agent skills

### Issue tracker

Track local work as Markdown under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Domain docs

Use a single context with `GLOSSARY.md` and `docs/adr/` when those files exist. See `docs/agents/domain.md`.
