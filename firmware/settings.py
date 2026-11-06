import struct


MAGIC = b"OHH4"
SCHEMA_VERSION = 1
RECORD_FORMAT = "<4sBBHBBHHHBHHHHH"
RECORD_SIZE = struct.calcsize(RECORD_FORMAT)
SLOT_SIZE = 32
CURVES = ("linear", "soft", "hard")


class SettingsError(ValueError):
    pass


class Settings:
    __slots__ = (
        "channel", "max_midi_rate_hz", "open_raw", "closed_raw", "curve",
        "filter_alpha", "invert", "hysteresis", "min_calibration_span",
        "stability_tolerance", "stability_samples",
    )

    def __init__(
        self, channel=1, max_midi_rate_hz=250, open_raw=None, closed_raw=None,
        curve="linear", filter_alpha=0.2, invert=False, hysteresis=0.15,
        min_calibration_span=1024, stability_tolerance=256, stability_samples=128,
    ):
        self.channel = channel
        self.max_midi_rate_hz = max_midi_rate_hz
        self.open_raw = open_raw
        self.closed_raw = closed_raw
        self.curve = curve
        self.filter_alpha = filter_alpha
        self.invert = invert
        self.hysteresis = hysteresis
        self.min_calibration_span = min_calibration_span
        self.stability_tolerance = stability_tolerance
        self.stability_samples = stability_samples
        self.validate()

    @staticmethod
    def _integer(value, field, low, high):
        if isinstance(value, bool) or not isinstance(value, int) or value < low or value > high:
            raise SettingsError("invalid " + field)

    @staticmethod
    def _number(value, field, low, high, include_low=True):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SettingsError("invalid " + field)
        value = float(value)
        if value != value or value == float("inf") or value == float("-inf"):
            raise SettingsError("invalid " + field)
        if (value < low if include_low else value <= low) or value > high:
            raise SettingsError("invalid " + field)

    def validate(self):
        self._integer(self.channel, "channel", 1, 16)
        self._integer(self.max_midi_rate_hz, "max_midi_rate_hz", 1, 250)
        self._integer(self.min_calibration_span, "min_calibration_span", 1, 65535)
        self._integer(self.stability_tolerance, "stability_tolerance", 1, 65535)
        self._integer(self.stability_samples, "stability_samples", 8, 512)
        if self.curve not in CURVES:
            raise SettingsError("invalid curve")
        if not isinstance(self.invert, bool):
            raise SettingsError("invalid invert")
        self._number(self.filter_alpha, "filter_alpha", 0.001, 1)
        self._number(self.hysteresis, "hysteresis", 0, 0.49)
        self.filter_alpha = int(float(self.filter_alpha) * 1000 + 0.5) / 1000.0
        self.hysteresis = int(float(self.hysteresis) * 1000 + 0.5) / 1000.0
        if (self.open_raw is None) != (self.closed_raw is None):
            raise SettingsError("both calibration endpoints are required")
        if self.open_raw is not None:
            self._integer(self.open_raw, "open_raw", 0, 65535)
            self._integer(self.closed_raw, "closed_raw", 0, 65535)
            if abs(self.open_raw - self.closed_raw) < self.min_calibration_span:
                raise SettingsError("calibration span is too small")

    def copy(self, **changes):
        values = {
            "channel": self.channel,
            "max_midi_rate_hz": self.max_midi_rate_hz,
            "open_raw": self.open_raw,
            "closed_raw": self.closed_raw,
            "curve": self.curve,
            "filter_alpha": self.filter_alpha,
            "invert": self.invert,
            "hysteresis": self.hysteresis,
            "min_calibration_span": self.min_calibration_span,
            "stability_tolerance": self.stability_tolerance,
            "stability_samples": self.stability_samples,
        }
        values.update(changes)
        return Settings(**values)


def _checksum(record):
    crc = 0xFFFF
    for index in range(len(record)):
        if index in (6, 7):
            continue
        crc ^= record[index] << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def encode_settings(settings):
    settings.validate()
    flags = (1 if settings.open_raw is not None else 0) | (2 if settings.invert else 0)
    open_raw = settings.open_raw if settings.open_raw is not None else 0
    closed_raw = settings.closed_raw if settings.closed_raw is not None else 0
    values = (
        MAGIC, SCHEMA_VERSION, RECORD_SIZE, 0, flags, settings.channel,
        settings.max_midi_rate_hz, open_raw, closed_raw, CURVES.index(settings.curve),
        int(settings.filter_alpha * 1000 + 0.5),
        int(settings.hysteresis * 1000 + 0.5), settings.min_calibration_span,
        settings.stability_tolerance, settings.stability_samples,
    )
    record = bytearray(struct.pack(RECORD_FORMAT, *values))
    checksum = _checksum(record)
    record[6] = checksum & 255
    record[7] = checksum >> 8
    return bytes(record)


def decode_settings(record):
    if len(record) < 7 or record[:4] != MAGIC:
        raise SettingsError("foreign data")
    if record[4] != SCHEMA_VERSION:
        raise SettingsError("unknown schema")
    if record[5] != RECORD_SIZE or len(record) < RECORD_SIZE:
        raise SettingsError("invalid record length")
    record = record[:RECORD_SIZE]
    if record[6] | (record[7] << 8) != _checksum(record):
        raise SettingsError("checksum mismatch")
    values = struct.unpack(RECORD_FORMAT, record)
    flags = values[4]
    if flags & ~3:
        raise SettingsError("invalid flags")
    calibrated = flags & 1
    curve_index = values[9]
    if curve_index >= len(CURVES):
        raise SettingsError("invalid curve")
    try:
        return Settings(
            channel=values[5], max_midi_rate_hz=values[6],
            open_raw=values[7] if calibrated else None,
            closed_raw=values[8] if calibrated else None,
            curve=CURVES[curve_index], filter_alpha=values[10] / 1000.0,
            invert=bool(flags & 2), hysteresis=values[11] / 1000.0,
            min_calibration_span=values[12], stability_tolerance=values[13],
            stability_samples=values[14],
        )
    except (IndexError, SettingsError):
        raise SettingsError("invalid settings")


class SettingsStore:
    def __init__(self, nvm, slot_size=SLOT_SIZE):
        if slot_size < RECORD_SIZE:
            raise ValueError("NVM slot is too small")
        self.nvm = nvm
        self.slot_size = slot_size

    def load(self):
        try:
            data = bytes(self.nvm[:self.slot_size])
        except Exception as error:
            return Settings(), "defaults", "NVM read failed: " + str(error)
        if not data or all(byte == 255 for byte in data) or all(byte == 0 for byte in data):
            return Settings(), "defaults", "blank NVM"
        if data[:4] != MAGIC:
            return Settings(), "defaults", "foreign NVM data"
        try:
            return decode_settings(data), "NVM", None
        except SettingsError as error:
            return Settings(), "defaults", str(error)

    def save(self, settings):
        record = encode_settings(settings)
        padded = record + bytes(self.slot_size - len(record))
        try:
            self.nvm[:self.slot_size] = padded
            if bytes(self.nvm[:len(record)]) != record:
                return False, "NVM verification failed"
        except Exception as error:
            return False, "NVM write failed: " + str(error)
        return True, None
