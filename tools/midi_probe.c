#include <CoreFoundation/CoreFoundation.h>
#include <CoreMIDI/CoreMIDI.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned long messages = 0;
static unsigned long notes = 0;

static void receive(const MIDIPacketList *list, void *context, void *source) {
    (void)context;
    (void)source;
    const MIDIPacket *packet = &list->packet[0];
    for (UInt32 i = 0; i < list->numPackets; i++) {
        printf("MIDI");
        for (UInt16 j = 0; j < packet->length; j++) {
            printf(" %02X", packet->data[j]);
            if ((packet->data[j] & 0xF0) == 0x90) notes++;
        }
        printf("\n");
        messages++;
        packet = MIDIPacketNext(packet);
    }
}

static void name_of(MIDIObjectRef object, char *text, size_t capacity) {
    CFStringRef name = NULL;
    text[0] = 0;
    if (MIDIObjectGetStringProperty(object, kMIDIPropertyDisplayName, &name) == noErr && name) {
        CFStringGetCString(name, text, capacity, kCFStringEncodingUTF8);
        CFRelease(name);
    }
}

int main(int argc, char **argv) {
    const char *match = argc > 1 ? argv[1] : "Pico";
    double seconds = argc > 2 ? atof(argv[2]) : 0;
    MIDIClientRef client = 0;
    MIDIPortRef input = 0;
    setvbuf(stdout, NULL, _IOLBF, 0);
    OSStatus status = MIDIClientCreate(CFSTR("OpenHiHat verification"), NULL, NULL, &client);
    if (status != noErr) {
        fprintf(stderr, "MIDIClientCreate failed %d\n", (int)status);
        return 1;
    }
    status = MIDIInputPortCreate(client, CFSTR("CC4 capture"), receive, NULL, &input);
    if (status != noErr) return 2;
    unsigned int connected = 0;
    for (ItemCount i = 0; i < MIDIGetNumberOfSources(); i++) {
        MIDIEndpointRef endpoint = MIDIGetSource(i);
        char name[512];
        name_of(endpoint, name, sizeof(name));
        printf("SOURCE %s\n", name);
        if (strstr(name, match)) {
            status = MIDIPortConnectSource(input, endpoint, NULL);
            if (status != noErr) return 3;
            printf("CONNECTED %s\n", name);
            connected++;
        }
    }
    if (!connected) {
        fprintf(stderr, "No MIDI source matched %s\n", match);
        MIDIClientDispose(client);
        return 4;
    }
    if (seconds > 0) CFRunLoopRunInMode(kCFRunLoopDefaultMode, seconds, false);
    printf("SUMMARY packets=%lu note_status_bytes=%lu\n", messages, notes);
    MIDIClientDispose(client);
    return 0;
}
