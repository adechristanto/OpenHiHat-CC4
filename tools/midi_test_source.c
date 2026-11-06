#include <CoreFoundation/CoreFoundation.h>
#include <CoreMIDI/CoreMIDI.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(void) {
    MIDIClientRef client = 0;
    MIDIEndpointRef source = 0;
    if (MIDIClientCreate(CFSTR("OpenHiHat Test"), NULL, NULL, &client) != noErr ||
        MIDISourceCreate(client, CFSTR("OpenHiHat Test"), &source) != noErr) {
        fprintf(stderr, "Could not create CoreMIDI source\n");
        return 1;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    puts("READY");
    int value, velocity;
    char line[80];
    while (fgets(line, sizeof(line), stdin)) {
        if (sscanf(line, "note %d %d", &value, &velocity) == 2) {
            if (value < 0 || value > 127 || velocity < 1 || velocity > 127) { puts("ERROR"); continue; }
            Byte buffer[128];
            MIDIPacketList *list = (MIDIPacketList *)buffer;
            MIDIPacket *packet = MIDIPacketListInit(list);
            Byte on[] = {0x90, (Byte)value, (Byte)velocity};
            if (!MIDIPacketListAdd(list, sizeof(buffer), packet, 0, sizeof(on), on) || MIDIReceived(source, list) != noErr) { puts("ERROR"); continue; }
            usleep(50000);
            packet = MIDIPacketListInit(list);
            Byte off[] = {0x80, (Byte)value, 0};
            if (!MIDIPacketListAdd(list, sizeof(buffer), packet, 0, sizeof(off), off) || MIDIReceived(source, list) != noErr) puts("ERROR");
            else puts("OK");
            continue;
        }
        if (sscanf(line, "%d", &value) != 1) { puts("ERROR"); continue; }
        if (value < 0 || value > 127) { puts("ERROR"); continue; }
        Byte buffer[128];
        MIDIPacketList *list = (MIDIPacketList *)buffer;
        MIDIPacket *packet = MIDIPacketListInit(list);
        Byte message[] = {0xB0, 4, (Byte)value};
        if (!MIDIPacketListAdd(list, sizeof(buffer), packet, 0, sizeof(message), message) ||
            MIDIReceived(source, list) != noErr) puts("ERROR");
        else puts("OK");
    }
    MIDIClientDispose(client);
    return 0;
}
