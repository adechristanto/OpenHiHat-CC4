def normalize(raw, closed_raw, open_raw, invert=False):
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0 or raw > 65535:
        raise ValueError("raw ADC value must be an integer from 0 to 65535")
    if isinstance(closed_raw, bool) or not isinstance(closed_raw, int):
        raise ValueError("invalid closed endpoint")
    if isinstance(open_raw, bool) or not isinstance(open_raw, int):
        raise ValueError("invalid open endpoint")
    if closed_raw < 0 or closed_raw > 65535 or open_raw < 0 or open_raw > 65535:
        raise ValueError("invalid calibration endpoint")
    span = open_raw - closed_raw
    if span == 0:
        raise ValueError("calibration endpoints must differ")
    position = (raw - closed_raw) / span
    if position < 0:
        position = 0.0
    elif position > 1:
        position = 1.0
    if invert:
        position = 1.0 - position
    return position


def apply_curve(position, curve):
    if curve == "linear":
        return position
    if curve == "soft":
        return position * position
    if curve == "hard":
        return 1.0 - (1.0 - position) * (1.0 - position)
    raise ValueError("unsupported response curve")


class PedalProcessor:
    def __init__(self, settings):
        settings.validate()
        self.settings = settings
        self._samples = [0, 0, 0]
        self._sample_count = 0
        self._sample_index = 0
        self._ema = None
        self.last_raw = None
        self.last_filtered = None
        self.last_position = None
        self.last_cc = None

    def reset(self):
        self._sample_count = 0
        self._sample_index = 0
        self._ema = None
        self.last_filtered = None
        self.last_position = None
        self.last_cc = None

    def update_settings(self, settings):
        settings.validate()
        self.settings = settings
        self.reset()

    def _median(self, raw):
        self._samples[self._sample_index] = raw
        self._sample_index = (self._sample_index + 1) % 3
        if self._sample_count < 3:
            self._sample_count += 1
        if self._sample_count == 1:
            return raw
        if self._sample_count == 2:
            first = self._samples[(self._sample_index - 1) % 3]
            second = self._samples[(self._sample_index - 2) % 3]
            return second if first != second else first
        a, b, c = self._samples
        if a > b:
            a, b = b, a
        if b > c:
            b, c = c, b
        if a > b:
            a, b = b, a
        return b

    def process(self, raw):
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0 or raw > 65535:
            self.reset()
            self.last_raw = None
            return None
        filtered = self._median(raw)
        self.last_raw = raw
        if self._ema is None:
            self._ema = float(filtered)
        else:
            alpha = self.settings.filter_alpha
            self._ema += alpha * (filtered - self._ema)
        self.last_filtered = int(self._ema + 0.5)
        if self.settings.open_raw is None:
            return None
        position = normalize(
            self.last_filtered, self.settings.closed_raw, self.settings.open_raw,
            self.settings.invert,
        )
        self.last_position = apply_curve(position, self.settings.curve)
        scaled = self.last_position * 127.0
        if scaled <= 0:
            self.last_cc = 0
        elif scaled >= 127:
            self.last_cc = 127
        else:
            if self.last_cc is None:
                self.last_cc = int(scaled + 0.5)
            elif scaled > self.last_cc + 0.5 + self.settings.hysteresis:
                self.last_cc = int(scaled + 0.5 - self.settings.hysteresis)
            elif scaled < self.last_cc - 0.5 - self.settings.hysteresis:
                self.last_cc = int(scaled + 0.5 + self.settings.hysteresis)
            if self.last_cc < 0:
                self.last_cc = 0
            elif self.last_cc > 127:
                self.last_cc = 127
        return self.last_cc


class Calibration:
    IDLE = "idle"
    OPEN = "capture_open"
    WAIT_CLOSED = "await_closed"
    CLOSED = "capture_closed"
    READY = "ready"

    def __init__(self, settings, timeout_ns=5_000_000_000):
        self.settings = settings
        self.timeout_ns = timeout_ns
        self.state = self.IDLE
        self._started_ns = 0
        self._values = []
        self.open_raw = None
        self.closed_raw = None

    def begin_open(self, now_ns):
        self._begin(self.OPEN, now_ns)

    def begin_closed(self, now_ns):
        if self.state != self.WAIT_CLOSED:
            return False
        self._begin(self.CLOSED, now_ns)
        return True

    def cancel(self):
        self.state = self.IDLE
        self._values = []
        self.open_raw = None
        self.closed_raw = None

    def _begin(self, state, now_ns):
        self.state = state
        self._started_ns = now_ns
        self._values = []

    def feed(self, raw, now_ns):
        if self.state not in (self.OPEN, self.CLOSED):
            return None
        if now_ns - self._started_ns >= self.timeout_ns:
            self.state = self.IDLE if self.state == self.OPEN else self.WAIT_CLOSED
            self._values = []
            return "timeout", None
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0 or raw > 65535:
            return "invalid_sample", None
        self._values.append(raw)
        if len(self._values) < self.settings.stability_samples:
            return None
        low = min(self._values)
        high = max(self._values)
        if high - low > self.settings.stability_tolerance:
            self.state = self.IDLE if self.state == self.OPEN else self.WAIT_CLOSED
            self._values = []
            return "unstable", None
        average = sum(self._values) // len(self._values)
        self._values = []
        if self.state == self.OPEN:
            self.open_raw = average
            self.state = self.WAIT_CLOSED
            return "open_captured", average
        self.closed_raw = average
        if abs(self.open_raw - self.closed_raw) < self.settings.min_calibration_span:
            self.state = self.WAIT_CLOSED
            self.closed_raw = None
            return "span_too_small", average
        self.state = self.READY
        return "ready", average

    def candidate_settings(self):
        if self.state != self.READY:
            return None
        return self.settings.copy(open_raw=self.open_raw, closed_raw=self.closed_raw)
