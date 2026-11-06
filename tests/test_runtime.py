import sys
import unittest

sys.path.insert(0, "firmware")

from code import FirmwareRuntime
from settings import Settings
from test_core import FakeNVM, FakeWriter


class RuntimeTests(unittest.TestCase):
    def test_uncalibrated_runtime_keeps_adc_console_and_midi_safe(self):
        nvm = FakeNVM()
        runtime = FirmwareRuntime(nvm=nvm)
        for index in range(20):
            self.assertIsNone(runtime.process_raw(30000 + index, index * 1_000_000))
        writer = FakeWriter()
        runtime.send_pending(writer, True, 0)
        self.assertEqual(bytes(writer.data), b"")
        self.assertEqual(nvm.writes, 0)
        self.assertIn("state=uncalibrated", runtime.status_text())

    def test_runtime_calibration_persists_only_after_open_then_closed(self):
        nvm = FakeNVM()
        settings = Settings(stability_samples=8, stability_tolerance=4)
        runtime = FirmwareRuntime(nvm=nvm, settings=settings)
        self.assertIn("capturing open", runtime.begin_calibration("open"))
        now = runtime._clock_ns()
        for index in range(8):
            runtime.process_raw(10000 + index % 2, now + index * 1_000_000)
        self.assertEqual(runtime.state, "awaiting_closed")
        self.assertIn("capturing closed", runtime.begin_calibration("closed"))
        now = runtime._clock_ns()
        for index in range(8):
            runtime.process_raw(40000, now + index * 1_000_000)
        self.assertEqual(runtime.state, "running")
        self.assertEqual(runtime.settings.open_raw, 10000)
        self.assertEqual(runtime.settings.closed_raw, 40000)
        self.assertEqual(nvm.writes, 1)
        self.assertEqual(runtime.persistence_source, "NVM")

    def test_calibration_save_failure_suppresses_candidate_and_midi(self):
        nvm = FakeNVM(fail=True)
        settings = Settings(stability_samples=8, stability_tolerance=4)
        runtime = FirmwareRuntime(nvm=nvm, settings=settings)
        runtime.begin_calibration("open")
        now = runtime._clock_ns()
        for index in range(8):
            runtime.process_raw(10000, now + index * 1_000_000)
        runtime.begin_calibration("closed")
        now = runtime._clock_ns()
        for index in range(8):
            runtime.process_raw(40000, now + index * 1_000_000)
        self.assertEqual(runtime.state, "calibration_error")
        self.assertIsNone(runtime.settings.open_raw)
        self.assertIsNone(runtime.last_cc)
        writer = FakeWriter()
        runtime.send_pending(writer, True, 10_000_000)
        self.assertEqual(bytes(writer.data), b"")

    def test_sensor_error_requires_new_valid_sample_and_reconnect_resyncs(self):
        settings = Settings(open_raw=65535, closed_raw=0, filter_alpha=1)
        runtime = FirmwareRuntime(settings=settings)
        writer = FakeWriter()
        runtime.process_raw(30000, 0)
        runtime.send_pending(writer, True, 0)
        first = bytes(writer.data)
        self.assertEqual(len(first), 3)
        runtime.sensor_error()
        runtime.send_pending(writer, True, 4_000_000)
        self.assertEqual(bytes(writer.data), first)
        runtime.process_raw(40000, 5_000_000)
        runtime.send_pending(writer, True, 5_000_000)
        self.assertEqual(len(writer.data), 6)
        runtime.send_pending(writer, False, 6_000_000)
        runtime.send_pending(writer, True, 7_000_000)
        self.assertEqual(len(writer.data), 9)

    def test_sample_scheduler_samples_once_and_counts_missed_deadlines(self):
        class ADC:
            value = 1234

        runtime = FirmwareRuntime(adc=ADC())
        self.assertTrue(runtime.sample_if_due(0))
        self.assertFalse(runtime.sample_if_due(500_000))
        self.assertTrue(runtime.sample_if_due(3_500_000))
        self.assertEqual(runtime.sample_count, 2)
        self.assertEqual(runtime.missed_deadlines, 2)

    def test_invalid_sample_discards_queued_and_partial_midi_until_fresh_sample(self):
        for limit in (None, 1):
            with self.subTest(write_limit=limit):
                runtime = FirmwareRuntime(settings=Settings(open_raw=65535, closed_raw=0, filter_alpha=1))
                writer = FakeWriter(limit=limit)
                runtime.send_pending(writer, True, 0)
                runtime.process_raw(5000, 1)
                if limit is not None:
                    runtime.send_pending(writer, True, 2)
                before = bytes(writer.data)
                runtime.process_raw(None, 3)
                runtime.send_pending(writer, True, 4)
                self.assertEqual(bytes(writer.data), before)
                self.assertEqual(runtime.sensor_errors, 1)
                self.assertIsNone(runtime.last_cc)
                runtime.process_raw(65535, 5)
                for now in (6, 7, 8):
                    runtime.send_pending(writer, True, now)
                self.assertEqual(bytes(writer.data[len(before):]), b"\xB0\x04\x7F")

    def test_successful_save_retry_recovers_operational_state(self):
        for calibrated in (False, True):
            with self.subTest(calibrated=calibrated):
                nvm = FakeNVM(fail=True)
                settings = Settings(open_raw=65535, closed_raw=0) if calibrated else Settings()
                runtime = FirmwareRuntime(settings=settings, nvm=nvm)
                self.assertFalse(runtime.save_settings()[0])
                self.assertEqual(runtime.state, "persistence_error")
                nvm.fail = False
                self.assertTrue(runtime.save_settings()[0])
                self.assertIsNone(runtime.persistence_error)
                expected_state = "running" if calibrated else "uncalibrated"
                self.assertEqual(runtime.state, expected_state)
                runtime.process_raw(65535, 0)
                writer = FakeWriter()
                runtime.send_pending(writer, True, 0)
                self.assertEqual(bytes(writer.data), b"\xB0\x04\x7F" if calibrated else b"")

    def test_save_without_storage_suspends_output(self):
        runtime = FirmwareRuntime(settings=Settings(open_raw=65535, closed_raw=0))
        runtime.process_raw(65535, 0)
        self.assertFalse(runtime.save_settings()[0])
        self.assertEqual(runtime.state, "persistence_error")
        writer = FakeWriter()
        runtime.send_pending(writer, True, 1)
        self.assertEqual(bytes(writer.data), b"")

    def test_console_reads_only_when_available_and_validates_fields(self):
        runtime = FirmwareRuntime(settings=Settings())
        output = []
        reads = []
        command_text = "set channel 4\nset open_raw 123\n"
        chars = iter(command_text)

        def read_char(size):
            reads.append(size)
            return next(chars)

        runtime.console.poll(False, read_char, output.append)
        self.assertEqual(reads, [])
        for _ in range(len(command_text)):
            runtime.console.poll(True, read_char, output.append)
        self.assertEqual(runtime.settings.channel, 4)
        self.assertEqual(reads, [1] * len(reads))
        self.assertTrue(any("not configurable" in item for item in output))


if __name__ == "__main__":
    unittest.main()
