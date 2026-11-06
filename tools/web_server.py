#!/usr/bin/env python3
"""Run the local OpenHiHat test interface."""
import glob
import json
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from pico_console import Console

ROOT = Path(__file__).resolve().parents[1]
LOCK = threading.Lock()
MIDI_LOCK = threading.Lock()
SOURCE = None
ALLOWED = {"status", "raw", "calibrate open", "calibrate closed", "cancel", "save"}

def command(text):
    if text not in ALLOWED:
        raise ValueError("Unsupported command")
    with LOCK:
        ports = glob.glob('/dev/cu.usbmodem*')
        if len(ports) != 1:
            raise RuntimeError('Connect one Pico USB serial device')
        console = Console(ports[0])
        try:
            console.write(text.encode('ascii') + b'\n')
            response = console.read(1.5, until=b'\n').decode('utf-8', 'replace').strip()
        finally:
            console.close()
        if not response:
            raise RuntimeError('No response from Pico. Close other serial monitors and try again.')
        return response

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'web'), **kwargs)

    def respond(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != '/api/status':
            return super().do_GET()
        try:
            self.respond({'connected': True, 'status': command('status'), 'error': None})
        except (OSError, RuntimeError, ValueError) as error:
            self.respond({'connected': False, 'status': None, 'error': str(error)})

    def do_POST(self):
        origin = self.headers.get('Origin', '')
        if origin != 'http://127.0.0.1:8765' or self.headers.get('Host') != '127.0.0.1:8765':
            return self.respond({'error': 'Invalid origin'}, 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 1024:
                raise ValueError('Invalid request size')
            payload = json.loads(self.rfile.read(length))
            if self.path == '/api/command':
                response = command(payload.get('command'))
            elif self.path == '/api/test-midi':
                value = payload.get('value')
                if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 127:
                    raise ValueError('MIDI value must be from 0 to 127')
                with MIDI_LOCK:
                    if SOURCE is None or SOURCE.poll() is not None:
                        raise RuntimeError('Virtual MIDI source is unavailable')
                    SOURCE.stdin.write(str(value) + '\n')
                    SOURCE.stdin.flush()
                    if SOURCE.stdout.readline().strip() != 'OK':
                        raise RuntimeError('MIDI send failed')
                response = 'Sent synthetic CC4 value %d on channel 1' % value
            elif self.path == '/api/pad':
                note, velocity = payload.get('note'), payload.get('velocity')
                if any(isinstance(v, bool) or not isinstance(v, int) for v in (note, velocity)) or not 0 <= note <= 127 or not 1 <= velocity <= 127:
                    raise ValueError('Invalid note or velocity')
                with MIDI_LOCK:
                    if SOURCE is None or SOURCE.poll() is not None:
                        raise RuntimeError('Virtual MIDI source is unavailable')
                    SOURCE.stdin.write('note %d %d\n' % (note, velocity))
                    SOURCE.stdin.flush()
                    if SOURCE.stdout.readline().strip() != 'OK':
                        raise RuntimeError('MIDI send failed')
                response = 'Sent note %d with velocity %d' % (note, velocity)
            else:
                return self.respond({'error': 'Not found'}, 404)
            self.respond({'response': response})
        except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError) as error:
            self.respond({'error': str(error)}, 400)

if __name__ == '__main__':
    binary = ROOT / 'artifacts' / 'midi_test_source'
    binary.parent.mkdir(exist_ok=True)
    subprocess.run(['clang', str(ROOT / 'tools' / 'midi_test_source.c'), '-framework', 'CoreMIDI', '-framework', 'CoreFoundation', '-o', str(binary)], check=True)
    SOURCE = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    if SOURCE.stdout.readline().strip() != 'READY':
        raise SystemExit('Could not create virtual MIDI source')
    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    print('Open http://127.0.0.1:8765 in your browser', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        SOURCE.terminate()
        SOURCE.wait()
