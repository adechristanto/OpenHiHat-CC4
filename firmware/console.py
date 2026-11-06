SET_FIELDS = {
    "channel": "int",
    "max_midi_rate_hz": "int",
    "curve": "curve",
    "filter_alpha": "float",
    "invert": "bool",
    "hysteresis": "float",
    "min_calibration_span": "int",
    "stability_tolerance": "int",
    "stability_samples": "int",
}


class SerialConsole:
    def __init__(self, runtime, max_line_length=96):
        self.runtime = runtime
        self.max_line_length = max_line_length
        self._line = ""
        self._discarding = False

    def poll(self, available, read_char, write_line):
        if not available:
            return
        try:
            char = read_char(1)
        except Exception:
            return
        if not char:
            return
        if isinstance(char, bytes):
            char = char.decode("utf-8", "ignore")
        for item in char:
            if item in ("\r", "\n"):
                if self._discarding:
                    write_line("error: command too long")
                elif self._line:
                    self._execute(self._line, write_line)
                self._line = ""
                self._discarding = False
            elif not self._discarding:
                if len(self._line) >= self.max_line_length:
                    self._line = ""
                    self._discarding = True
                else:
                    self._line += item

    def _execute(self, line, write_line):
        parts = line.strip().split()
        if not parts:
            return
        command = parts[0]
        if command == "help" and len(parts) == 1:
            write_line("help | status | raw | calibrate open | calibrate closed | cancel | set <field> <value> | save")
        elif command == "status" and len(parts) == 1:
            write_line(self.runtime.status_text())
        elif command == "raw" and len(parts) == 1:
            write_line("raw=" + str(self.runtime.processor.last_raw))
        elif command == "calibrate" and len(parts) == 2 and parts[1] in ("open", "closed"):
            result = self.runtime.begin_calibration(parts[1])
            write_line(result)
        elif command == "cancel" and len(parts) == 1:
            self.runtime.cancel_calibration()
            write_line("calibration cancelled")
        elif command == "set" and len(parts) == 3:
            self._set(parts[1], parts[2], write_line)
        elif command == "save" and len(parts) == 1:
            ok, error = self.runtime.save_settings()
            write_line("settings saved" if ok else "error: " + str(error))
        else:
            write_line("error: malformed command; use help")

    def _set(self, name, value, write_line):
        kind = SET_FIELDS.get(name)
        if kind is None:
            write_line("error: field is not configurable")
            return
        try:
            if kind == "int":
                parsed = int(value)
            elif kind == "float":
                parsed = float(value)
            elif kind == "bool":
                if value not in ("on", "off", "true", "false"):
                    raise ValueError("use on/off")
                parsed = value in ("on", "true")
            else:
                parsed = value
            self.runtime.set_setting(name, parsed)
        except (ValueError, TypeError) as error:
            write_line("error: " + str(error))
            return
        write_line(name + "=" + str(getattr(self.runtime.settings, name)))
