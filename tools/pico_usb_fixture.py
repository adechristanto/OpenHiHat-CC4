import microcontroller
import time
import usb_midi
from midi_output import CC4Sender
from pedal import PedalProcessor
from settings import Settings, decode_settings, encode_settings


before = microcontroller.nvm[:]
config = Settings(stability_samples=512, filter_alpha=0.001)
restored = decode_settings(encode_settings(config))
assert restored.stability_samples == 512
assert restored.filter_alpha > 0

writer = usb_midi.ports[1]
processor = PedalProcessor(Settings(open_raw=60000, closed_raw=5000, filter_alpha=1, hysteresis=0))
sender = CC4Sender()
for expected in range(128):
    raw = 5000 + int(55000 * expected / 127 + 0.5)
    for unused in range(3):
        value = processor.process(raw)
    assert value == expected
    sender.offer(value)
    sender.poll(writer, True, time.monotonic_ns())
    time.sleep(0.006)
    sender.offer(value)
    sender.poll(writer, True, time.monotonic_ns())
assert sender.sent_count == 128

processor = PedalProcessor(Settings(open_raw=5000, closed_raw=60000, filter_alpha=1, hysteresis=0))
sender = CC4Sender(channel=2)
for expected, raw in ((0, 60000), (64, 32500), (127, 5000)):
    for unused in range(3):
        value = processor.process(raw)
    assert value == expected
    sender.offer(value)
    sender.poll(writer, True, time.monotonic_ns())
    time.sleep(0.006)
assert sender.sent_count == 3
assert microcontroller.nvm[:] == before
print("FIXTURE_OK all_128_values reverse_polarity channel_2 duplicates_suppressed nvm_unchanged")
