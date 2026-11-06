import gc
import time
import microcontroller
import analogio
import board
import supervisor
import usb_midi
from code import FirmwareRuntime
from pedal import PedalProcessor
from settings import Settings


gc.collect()
print("cpu_hz", microcontroller.cpu.frequency, "free_bytes", gc.mem_free())
adc = analogio.AnalogIn(board.GP26)
runtime = FirmwareRuntime(adc=adc, writer=usb_midi.ports[1], settings=Settings())
clock = time.monotonic_ns

def measure(name, count, action):
    gc.collect()
    start = clock()
    for index in range(count):
        action(index)
    elapsed = clock() - start
    print(name, "calls", count, "elapsed_ns", elapsed, "us_per_call", elapsed // count // 1000)

measure("clock", 100, lambda i: clock())
measure("runtime_clock", 100, lambda i: runtime._clock_ns())
measure("adc", 100, lambda i: adc.value)
measure("uncalibrated_process", 100, lambda i: runtime.process_raw(30000, i * 1000000))
processor = PedalProcessor(Settings(open_raw=60000, closed_raw=5000))
measure("calibrated_process", 100, lambda i: processor.process(30000))
measure("sender_idle", 100, lambda i: runtime.send_pending(usb_midi.ports[1], True, clock()))
measure("console_idle", 100, lambda i: runtime.console.poll(False, None, None))
measure("sleep_zero", 100, lambda i: time.sleep(0))
measure("sleep_100us", 100, lambda i: time.sleep(0.0001))
measure("sleep_1ms", 100, lambda i: time.sleep(0.001))
adc.deinit()
print("PROFILE_COMPLETE sensor_errors", runtime.sensor_errors, "samples", runtime.sample_count)
