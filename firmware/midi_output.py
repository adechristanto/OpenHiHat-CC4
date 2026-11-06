class CC4Sender:
    def __init__(self, channel=1, max_rate_hz=250):
        if isinstance(channel, bool) or not isinstance(channel, int) or not 1 <= channel <= 16:
            raise ValueError("channel must be from 1 to 16")
        if isinstance(max_rate_hz, bool) or not isinstance(max_rate_hz, int) or not 1 <= max_rate_hz <= 250:
            raise ValueError("max_rate_hz must be from 1 to 250")
        self.channel = channel
        self.max_rate_hz = max_rate_hz
        self._interval_ns = (1_000_000_000 + max_rate_hz - 1) // max_rate_hz
        self._message = bytearray(3)
        self._view = memoryview(self._message)
        self._pending = False
        self._offset = 0
        self._next_value = None
        self._force_next = False
        self._force_pending = False
        self._last_value = None
        self._last_complete_ns = None
        self._connected = False
        self.sent_count = 0
        self.partial_write_count = 0
        self.backpressure_count = 0

    def configure(self, channel, max_rate_hz):
        if isinstance(channel, bool) or not isinstance(channel, int) or not 1 <= channel <= 16:
            raise ValueError("channel must be from 1 to 16")
        if isinstance(max_rate_hz, bool) or not isinstance(max_rate_hz, int) or not 1 <= max_rate_hz <= 250:
            raise ValueError("max_rate_hz must be from 1 to 250")
        channel_changed = channel != self.channel
        self.max_rate_hz = max_rate_hz
        self._interval_ns = (1_000_000_000 + max_rate_hz - 1) // max_rate_hz
        if not channel_changed:
            return
        self.channel = channel
        if self._pending and self._offset > 0:
            self._next_value = self._message[2] if self._next_value is None else self._next_value
            self._force_next = True
        elif self._pending:
            self._message[0] = 0xB0 | (channel - 1)
            self._next_value = None
            self._force_next = False
            self._force_pending = True
        elif self._last_value is not None:
            value = self._last_value
            self._last_value = None
            self._set_message(value)

    def disconnect(self):
        self._connected = False
        self._pending = False
        self._offset = 0
        self._next_value = None
        self._force_next = False
        self._force_pending = False
        self._last_value = None

    def offer(self, value):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 127:
            raise ValueError("CC value must be from 0 to 127")
        if self._pending:
            current = self._message[2]
            if self._offset == 0:
                if value == self._last_value and not self._force_pending:
                    self._pending = False
                    self._next_value = None
                    return
                if value == current:
                    self._next_value = None
                else:
                    self._set_message(value)
                    self._next_value = None
                return
            if value == current:
                if self._force_next:
                    self._next_value = value
                else:
                    self._next_value = None
            elif self._next_value != value:
                self._next_value = value
            return
        if value == self._last_value:
            self._next_value = value if self._force_next else None
            return
        self._next_value = None
        self._set_message(value)

    def _set_message(self, value):
        self._message[0] = 0xB0 | (self.channel - 1)
        self._message[1] = 4
        self._message[2] = value
        self._pending = True
        self._offset = 0
        self._force_pending = False

    def poll(self, writer, connected, now_ns):
        if not connected:
            self.disconnect()
            return
        if not self._connected:
            self._connected = True
            self._last_value = None
            self._last_complete_ns = None
        if not self._pending:
            if self._next_value is not None:
                value = self._next_value
                self._next_value = None
                if value != self._last_value or self._force_next:
                    self._set_message(value)
                self._force_next = False
            if not self._pending:
                return
        if self._offset == 0 and self._last_complete_ns is not None:
            if now_ns - self._last_complete_ns < self._interval_ns:
                return
        view = self._view[self._offset:]
        try:
            written = writer.write(view)
        except Exception:
            self.backpressure_count += 1
            return
        if written is None or written == 0:
            self.backpressure_count += 1
            return
        if isinstance(written, bool) or not isinstance(written, int) or written < 0:
            self.backpressure_count += 1
            return
        remaining = 3 - self._offset
        if written > remaining:
            written = remaining
        if written < remaining:
            self.partial_write_count += 1
        self._offset += written
        if self._offset == 3:
            self._last_value = self._message[2]
            self._last_complete_ns = now_ns
            self.sent_count += 1
            self._pending = False
            self._offset = 0
            self._force_pending = False
            if self._next_value == self._last_value and not self._force_next:
                self._next_value = None
