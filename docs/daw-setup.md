# Use OpenHiHat with Logic Pro and Addictive Drums 2

Complete electrical qualification and pedal calibration before these steps. A USB MIDI fixture test does not verify real pedal movement or sound.

1. Connect the Pico and your MIDI pad controller to the Mac.
2. Open **Audio MIDI Setup** and show **MIDI Studio**. Find the Pico MIDI device. CircuitPython 7.3.3 uses the name `Pico`.
3. In Logic Pro, load Addictive Drums 2 on a software instrument track and enable recording for that track.
4. Route both the Pico's CC data and the pad controller's note data to that instrument. Check that Logic has not filtered controller messages.
5. Open Addictive Drums 2's **MIDI Mapping** window. Select **Hihat**.
6. Use **Learn** beside **CC Hihat Tip**, then strike the pad that represents the hi-hat. Use the appropriate CC edge articulation for an additional strike zone.
7. In the advanced CC hi-hat settings, use controller number 4. Start with reverse disabled. The firmware's convention is closed 0 and open 127.
8. Move the pedal and watch the incoming CC value. Confirm closed, intermediate, and open positions while striking the pad.
9. Tune **Foot Close** and **Foot Splash** sensitivity. Leave separate foot-close and foot-splash note assignments unmapped when using AD2's CC detection.
10. Save the map preset. Verify the setup again with both pad controllers connected if you use two.

XLN's [hi-hat setup guide](https://support.xlnaudio.com/hc/en-us/articles/11720576066973-E-drum-hihat-setup-for-Addictive-Drums-2) explains CC hi-hat mapping. Its [MIDI Mapping reference](https://support.xlnaudio.com/hc/en-us/articles/16593408783389-MIDI-Mapping-Window) describes controller number 4 and the built-in foot-close and foot-splash detection.

The firmware sends no drum notes. A pad strike supplies the note event. Addictive Drums 2 combines that event with the latest CC4 position to choose an articulation.

This delivery does not claim a tested Logic Pro or Addictive Drums session. Record physical pedal response, sound behavior, duplicate-event checks, and audible latency during acceptance.
