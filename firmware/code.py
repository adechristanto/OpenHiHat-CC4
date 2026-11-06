import time

from console import SerialConsole
from midi_output import CC4Sender
from pedal import Calibration, PedalProcessor
from settings import Settings, SettingsStore


FIRMWARE_VERSION = "1.0.0"
SAMPLE_RATE_HZ = 1000
SAMPLE_INTERVAL_NS = 1_000_000


class FirmwareRuntime:
    def __init__(self, adc=None, writer=None, nvm=None, settings=None, store=None):
        self.adc = adc
        self.writer = writer
        self.store = store if store is not None else (SettingsStore(nvm) if nvm is not None else None)
        if settings is None and self.store is not None:
            self.settings, self.persistence_source, self.persistence_error = self.store.load()
        else:
            self.settings = settings if settings is not None else Settings()
            self.persistence_source = "injected" if settings is not None else "defaults"
            self.persistence_error = None
        self.settings.validate()
        self.processor = PedalProcessor(self.settings)
        self.calibration = Calibration(self.settings)
        self.sender = CC4Sender(self.settings.channel, self.settings.max_midi_rate_hz)
        self.console = SerialConsole(self)
        self.state = "running" if self.settings.open_raw is not None else "uncalibrated"
        self.sample_count = 0
        self.missed_deadlines = 0
        self.sensor_errors = 0
        self.last_cc = None
        self.usb_connected = False
        self._last_usb_connected = False
        self._next_sample_ns = None

    def set_setting(self, name, value):
        if name in ("open_raw", "closed_raw"):
            raise ValueError("calibration endpoints are set only by calibration")
        try:
            candidate = self.settings.copy(**{name: value})
        except TypeError:
            raise ValueError("unknown setting")
        self.settings = candidate
        self.processor.update_settings(candidate)
        self.calibration.cancel()
        self.calibration = Calibration(candidate)
        self.sender.configure(candidate.channel, candidate.max_midi_rate_hz)
        self.last_cc = None
        self.state = "running" if candidate.open_raw is not None else "uncalibrated"

    def save_settings(self, candidate=None):
        settings = self.settings if candidate is None else candidate
        if self.store is None:
            ok, error = False, "NVM is unavailable"
        else:
            ok, error = self.store.save(settings)
        if not ok:
            self.persistence_error = error
            self.state = "persistence_error"
            self.sender.disconnect()
            self.last_cc = None
            return False, error
        if candidate is not None:
            self.settings = candidate
            self.processor.update_settings(candidate)
            self.sender.configure(candidate.channel, candidate.max_midi_rate_hz)
            self.calibration = Calibration(candidate)
            self.state = "running"
        elif self.state == "persistence_error":
            self.state = "running" if self.settings.open_raw is not None else "uncalibrated"
        self.persistence_source = "NVM"
        self.persistence_error = None
        return True, None

    def begin_calibration(self, endpoint):
        now_ns = self._clock_ns()
        if endpoint == "open":
            self.calibration.begin_open(now_ns)
            self.state = "calibrating_open"
            self.processor.reset()
            self.sender.disconnect()
            self.last_cc = None
            return "release pedal fully; capturing open endpoint"
        if endpoint == "closed" and self.calibration.begin_closed(now_ns):
            self.state = "calibrating_closed"
            self.processor.reset()
            self.sender.disconnect()
            self.last_cc = None
            return "press pedal fully; capturing closed endpoint"
        return "error: calibrate open must succeed before calibrate closed"

    def cancel_calibration(self):
        self.calibration.cancel()
        self.state = "running" if self.settings.open_raw is not None else "uncalibrated"
        self.processor.reset()
        self.sender.disconnect()
        self.last_cc = None

    def process_raw(self, raw, now_ns):
        self.sample_count += 1
        cc = self.processor.process(raw)
        if self.processor.last_raw is None:
            self.sensor_error()
            return None
        if self.calibration.state in (Calibration.OPEN, Calibration.CLOSED):
            outcome = self.calibration.feed(raw, now_ns)
            if outcome is not None:
                kind, average = outcome
                if kind == "open_captured":
                    self.state = "awaiting_closed"
                elif kind == "ready":
                    candidate = self.calibration.candidate_settings()
                    self.state = "saving_calibration"
                    ok, error = self.save_settings(candidate)
                    if not ok:
                        self.calibration.cancel()
                        self.state = "calibration_error"
                        self.persistence_error = error
                    self.last_cc = None
                    return None
                elif kind == "timeout" or kind == "unstable" or kind == "span_too_small":
                    if self.calibration.state == Calibration.WAIT_CLOSED:
                        self.state = "awaiting_closed"
                    else:
                        self.state = "running" if self.settings.open_raw is not None else "uncalibrated"
        elif self.calibration.state == Calibration.WAIT_CLOSED:
            self.state = "awaiting_closed"
        if self.state != "running":
            self.last_cc = None
            return None
        self.last_cc = cc
        if cc is not None:
            self.sender.offer(cc)
        return cc

    def sensor_error(self):
        self.sensor_errors += 1
        self.processor.reset()
        self.last_cc = None
        self.sender.disconnect()

    def send_pending(self, writer=None, connected=None, now_ns=None):
        if writer is None:
            writer = self.writer
        if connected is None:
            connected = self.usb_connected
        if now_ns is None:
            now_ns = self._clock_ns()
        self.usb_connected = bool(connected)
        if self.usb_connected and not self._last_usb_connected:
            self.sender.disconnect()
            if self.last_cc is not None:
                self.sender.offer(self.last_cc)
        self._last_usb_connected = self.usb_connected
        self.sender.poll(writer, self.usb_connected, now_ns)

    def sample_if_due(self, now_ns):
        if self._next_sample_ns is None:
            self._next_sample_ns = now_ns
        if now_ns < self._next_sample_ns:
            return False
        late = now_ns - self._next_sample_ns
        missed = late // SAMPLE_INTERVAL_NS
        self.missed_deadlines += missed
        self._next_sample_ns += (missed + 1) * SAMPLE_INTERVAL_NS
        try:
            raw = self.adc.value
        except Exception:
            self.sensor_error()
            return True
        self.process_raw(raw, now_ns)
        return True

    def status_text(self):
        calibration = "not captured"
        if self.settings.open_raw is not None:
            calibration = "open=%d closed=%d" % (self.settings.open_raw, self.settings.closed_raw)
        return (
            "version=%s state=%s calibration=%s settings={channel:%d cc:4 curve:%s alpha:%.3f invert:%s rate:%d} "
            "raw=%s filtered=%s cc=%s samples=%d missed=%d sensor_errors=%d midi_sent=%d midi_partial=%d "
            "midi_backpressure=%d usb=%s persistence=%s persistence_error=%s"
            % (
                FIRMWARE_VERSION, self.state, calibration, self.settings.channel,
                self.settings.curve, self.settings.filter_alpha, self.settings.invert,
                self.settings.max_midi_rate_hz, self.processor.last_raw,
                self.processor.last_filtered, self.last_cc, self.sample_count,
                self.missed_deadlines, self.sensor_errors, self.sender.sent_count,
                self.sender.partial_write_count, self.sender.backpressure_count,
                self.usb_connected, self.persistence_source, self.persistence_error,
            )
        )

    @staticmethod
    def _clock_ns():
        if hasattr(time, "monotonic_ns"):
            return time.monotonic_ns()
        return int(time.monotonic() * 1_000_000_000)


def run():
    import analogio
    import board
    import microcontroller
    import supervisor
    import sys
    import time
    import usb_midi

    adc = analogio.AnalogIn(board.GP26)
    writer = usb_midi.ports[1]
    runtime = FirmwareRuntime(adc=adc, writer=writer, nvm=microcontroller.nvm)
    while True:
        now_ns = runtime._clock_ns()
        runtime.sample_if_due(now_ns)
        runtime.send_pending(writer, supervisor.runtime.usb_connected, now_ns)
        runtime.console.poll(
            supervisor.runtime.serial_bytes_available,
            sys.stdin.read,
            lambda line: print(line),
        )
        remaining_ns = runtime._next_sample_ns - runtime._clock_ns()
        if remaining_ns > 0:
            time.sleep(remaining_ns / 1_000_000_000)
        else:
            time.sleep(0)


if __name__ == "__main__":
    run()
