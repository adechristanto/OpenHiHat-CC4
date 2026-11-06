import sys
import unittest

sys.path.insert(0, "firmware")

from midi_output import CC4Sender
from pedal import Calibration, PedalProcessor, apply_curve, normalize
from settings import (
    RECORD_SIZE,
    Settings,
    SettingsError,
    SettingsStore,
    decode_settings,
    encode_settings,
)


class FakeWriter:
    def __init__(self, limit=None, responses=()):
        self.limit = limit
        self.responses = list(responses)
        self.data = bytearray()

    def write(self, data):
        if self.responses:
            result = self.responses.pop(0)
            if result in (None, 0):
                return result
        else:
            result = len(data)
        if self.limit is not None:
            result = min(result, self.limit)
        self.data.extend(data[:result])
        return result


class FakeNVM(bytearray):
    def __init__(self, size=4096, fail=False):
        super().__init__([255] * size)
        self.fail = fail
        self.writes = 0

    def __setitem__(self, key, value):
        if self.fail:
            raise OSError("write blocked")
        self.writes += 1
        return super().__setitem__(key, value)


class SettingsTests(unittest.TestCase):
    def test_record_round_trip_includes_maximum_stability_window(self):
        settings = Settings(
            channel=16, max_midi_rate_hz=125, open_raw=62000, closed_raw=9000,
            curve="hard", filter_alpha=0.2, invert=True, stability_samples=512,
        )
        restored = decode_settings(encode_settings(settings))
        self.assertEqual(restored.channel, 16)
        self.assertEqual(restored.open_raw, 62000)
        self.assertEqual(restored.closed_raw, 9000)
        self.assertEqual(restored.stability_samples, 512)
        self.assertEqual(restored.filter_alpha, 0.2)
        self.assertLessEqual(RECORD_SIZE, 32)

    def test_checksum_and_unknown_schema_are_rejected(self):
        record = bytearray(encode_settings(Settings()))
        record[10] ^= 1
        with self.assertRaises(SettingsError):
            decode_settings(record)
        record = bytearray(encode_settings(Settings()))
        record[4] = 99
        with self.assertRaisesRegex(SettingsError, "unknown schema"):
            decode_settings(record)

    def test_filter_alpha_cannot_round_to_zero_in_storage(self):
        with self.assertRaisesRegex(SettingsError, "filter_alpha"):
            Settings(filter_alpha=0.0001)
        settings = Settings(filter_alpha=0.001)
        self.assertEqual(decode_settings(encode_settings(settings)).filter_alpha, 0.001)

    def test_settings_reject_bool_as_integer_and_invalid_span(self):
        with self.assertRaises(SettingsError):
            Settings(channel=True)
        with self.assertRaises(SettingsError):
            Settings(open_raw=100, closed_raw=100)
        with self.assertRaises(SettingsError):
            Settings(open_raw=1000, closed_raw=500)

    def test_blank_foreign_corrupt_and_save_failure_are_safe(self):
        nvm = FakeNVM()
        store = SettingsStore(nvm)
        settings, source, error = store.load()
        self.assertIsNone(settings.open_raw)
        self.assertEqual(source, "defaults")
        self.assertEqual(error, "blank NVM")
        self.assertTrue(store.save(Settings(open_raw=50000, closed_raw=5000))[0])
        self.assertIsNotNone(store.load()[0].open_raw)
        nvm[0] = 17
        self.assertEqual(store.load()[2], "foreign NVM data")
        failed = SettingsStore(FakeNVM(fail=True)).save(Settings())
        self.assertFalse(failed[0])
        self.assertIn("write failed", failed[1])


class PedalTests(unittest.TestCase):
    def test_normalization_handles_both_polarities_and_clamps(self):
        self.assertEqual(normalize(100, 100, 1100), 0.0)
        self.assertEqual(normalize(600, 100, 1100), 0.5)
        self.assertEqual(normalize(1200, 100, 1100), 1.0)
        self.assertEqual(normalize(100, 1100, 100), 1.0)
        self.assertEqual(normalize(600, 1100, 100), 0.5)
        self.assertEqual(normalize(1200, 1100, 100), 0.0)
        with self.assertRaises(ValueError):
            normalize(1, 10, 10)

    def test_curves_are_monotonic_and_preserve_endpoints(self):
        for curve in ("linear", "soft", "hard"):
            values = [apply_curve(index / 100.0, curve) for index in range(101)]
            self.assertEqual(values[0], 0)
            self.assertEqual(values[-1], 1)
            self.assertEqual(values, sorted(values))

    def test_median_rejects_single_sample_spike_and_hysteresis_suppresses_noise(self):
        settings = Settings(
            open_raw=65535, closed_raw=0, filter_alpha=1.0, hysteresis=0.15,
        )
        processor = PedalProcessor(settings)
        self.assertEqual(processor.process(32768), 64)
        self.assertEqual(processor.process(65535), 64)
        self.assertEqual(processor.process(32768), 64)
        near_boundary_low = int(64.4 / 127 * 65535)
        near_boundary_high = int(64.6 / 127 * 65535)
        result = [processor.process(value) for value in [near_boundary_low, near_boundary_high] * 8]
        self.assertEqual(set(result), {64})

    def test_invalid_raw_resets_history_and_valid_sample_recovers(self):
        processor = PedalProcessor(Settings(open_raw=65535, closed_raw=0))
        processor.process(30000)
        self.assertIsNone(processor.process(65536))
        self.assertIsNone(processor.process(True))
        self.assertIsNone(processor.last_filtered)
        self.assertIsNotNone(processor.process(40000))

    def test_calibration_requires_distinct_stable_open_then_closed_commands(self):
        settings = Settings(stability_samples=8, stability_tolerance=10)
        calibration = Calibration(settings)
        self.assertFalse(calibration.begin_closed(0))
        calibration.begin_open(0)
        self.assertEqual(calibration.feed(10000, 1), None)
        outcome = None
        for index in range(7):
            outcome = calibration.feed(10000 + (index % 2), index + 2)
        self.assertEqual(outcome[0], "open_captured")
        self.assertEqual(calibration.state, Calibration.WAIT_CLOSED)
        self.assertTrue(calibration.begin_closed(20))
        outcome = None
        for index in range(8):
            outcome = calibration.feed(40000, 21 + index)
        self.assertEqual(outcome[0], "ready")
        candidate = calibration.candidate_settings()
        self.assertEqual(candidate.open_raw, 10000)
        self.assertEqual(candidate.closed_raw, 40000)

    def test_unstable_capture_is_rejected(self):
        settings = Settings(stability_samples=8, stability_tolerance=4)
        calibration = Calibration(settings)
        calibration.begin_open(0)
        outcome = None
        for index in range(8):
            outcome = calibration.feed(index * 10, index + 1)
        self.assertEqual(outcome[0], "unstable")
        self.assertEqual(calibration.state, Calibration.IDLE)


class MidiTests(unittest.TestCase):
    def test_channel_encoding_duplicates_and_rate_limit(self):
        sender = CC4Sender(channel=16)
        writer = FakeWriter()
        sender.offer(64)
        sender.poll(writer, True, 0)
        self.assertEqual(bytes(writer.data), b"\xBF\x04\x40")
        sender.offer(64)
        sender.poll(writer, True, 20_000_000)
        self.assertEqual(bytes(writer.data), b"\xBF\x04\x40")
        sender.offer(127)
        sender.poll(writer, True, 3_999_999)
        self.assertEqual(len(writer.data), 3)
        sender.poll(writer, True, 4_000_000)
        self.assertEqual(bytes(writer.data[-3:]), b"\xBF\x04\x7F")

    def test_none_zero_short_writes_and_stale_coalescing(self):
        sender = CC4Sender()
        writer = FakeWriter(responses=[None, 0, 1, 1, 1, 3])
        sender.offer(10)
        sender.poll(writer, True, 0)
        sender.poll(writer, True, 0)
        sender.poll(writer, True, 0)
        sender.offer(20)
        sender.offer(30)
        sender.poll(writer, True, 0)
        self.assertEqual(bytes(writer.data), b"\xB0\x04")
        sender.poll(writer, True, 0)
        self.assertEqual(bytes(writer.data), b"\xB0\x04\x0A")
        sender.poll(writer, True, 4_000_000)
        self.assertEqual(bytes(writer.data[-3:]), b"\xB0\x04\x1E")
        self.assertEqual(sender.partial_write_count, 2)
        self.assertEqual(sender.backpressure_count, 2)

    def test_disconnect_discards_partial_and_reconnect_resends_current(self):
        sender = CC4Sender()
        writer = FakeWriter(limit=1)
        sender.offer(55)
        sender.poll(writer, True, 0)
        self.assertEqual(bytes(writer.data), b"\xB0")
        sender.poll(writer, False, 1)
        sender.offer(55)
        sender.poll(writer, True, 2)
        sender.poll(writer, True, 3)
        sender.poll(writer, True, 4)
        self.assertEqual(bytes(writer.data), b"\xB0\xB0\x04\x37")

    def test_newest_value_replaces_stale_value_after_partial_packet(self):
        sender = CC4Sender()
        writer = FakeWriter(limit=1)
        sender.offer(10)
        sender.poll(writer, True, 0)
        sender.offer(90)
        sender.poll(writer, True, 1)
        sender.poll(writer, True, 2)
        sender.offer(80)
        sender.poll(writer, True, 4_000_002)
        sender.poll(writer, True, 8_000_000)
        sender.poll(writer, True, 12_000_000)
        sender.poll(writer, True, 16_000_000)
        self.assertEqual(bytes(writer.data), b"\xB0\x04\x0A\xB0\x04\x50")

    def test_channel_change_resends_and_finishes_started_message_first(self):
        sender = CC4Sender(channel=1)
        writer = FakeWriter(limit=1)
        sender.offer(20)
        sender.poll(writer, True, 0)
        sender.configure(channel=2, max_rate_hz=250)
        sender.offer(20)
        sender.poll(writer, True, 1)
        sender.offer(20)
        sender.poll(writer, True, 2)
        sender.offer(20)
        sender.poll(writer, True, 4_000_002)
        sender.offer(20)
        sender.poll(writer, True, 4_000_003)
        sender.offer(20)
        sender.poll(writer, True, 4_000_004)
        self.assertEqual(bytes(writer.data), b"\xB0\x04\x14\xB1\x04\x14")

    def test_unstarted_value_that_returns_to_last_sent_value_is_suppressed(self):
        sender = CC4Sender()
        writer = FakeWriter()
        sender.offer(0)
        sender.poll(writer, True, 0)
        sender.offer(10)
        sender.offer(0)
        sender.poll(writer, True, 4_000_000)
        self.assertEqual(bytes(writer.data), b"\xB0\x04\x00")

    def test_channel_change_keeps_forced_value_when_same_sample_arrives(self):
        sender = CC4Sender()
        writer = FakeWriter()
        sender.offer(20)
        sender.poll(writer, True, 0)
        sender.configure(channel=2, max_rate_hz=250)
        sender.offer(20)
        sender.poll(writer, True, 4_000_000)
        self.assertEqual(bytes(writer.data), b"\xB0\x04\x14\xB1\x04\x14")


if __name__ == "__main__":
    unittest.main()
