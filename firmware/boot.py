import usb_midi


usb_midi.enable()

try:
    import usb_hid
    usb_hid.disable()
except (ImportError, AttributeError):
    pass

set_names = getattr(usb_midi, "set_names", None)
if set_names is not None:
    try:
        set_names(
            streaming_interface_name="OpenHiHat CC4",
            audio_control_interface_name="OpenHiHat CC4",
            in_jack_name="OpenHiHat MIDI In",
            out_jack_name="OpenHiHat CC4",
        )
    except TypeError:
        pass

try:
    import supervisor
except ImportError:
    supervisor = None
if supervisor is not None:
    set_identification = getattr(supervisor, "set_usb_identification", None)
    if set_identification is not None:
        try:
            set_identification(manufacturer="OpenHiHat", product="OpenHiHat CC4")
        except TypeError:
            pass
