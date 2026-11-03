#!/usr/bin/env python3
"""Inspect X11 pressed keys; release once only when explicitly requested."""
import argparse
import ctypes as C
import json
import os
import sys
import time


def observe(pressed, initial, seconds, clock=time.monotonic, sleep=time.sleep):
    """Observe without injecting events; preserve even transient pressed states."""
    started = clock()
    after = initial
    seen = {key['keycode']: key for key in initial}
    changes = []
    while clock() - started < seconds:
        sleep(min(0.2, max(0, seconds - (clock() - started))))
        current = pressed()
        seen.update((key['keycode'], key) for key in current)
        if current != after:
            changes.append({'elapsed_seconds': round(clock() - started, 3), 'pressed': current})
        after = current
    return after, list(seen.values()), changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', action='store_true')
    parser.add_argument('--watch-seconds', type=float, default=5.0,
                        help='Observation after a release attempt (0–30 seconds; default: 5). Keep all keys released.')
    args = parser.parse_args()
    if not 0 <= args.watch_seconds <= 30:
        parser.error('--watch-seconds must be between 0 and 30')
    if sys.platform != 'linux' or os.environ.get('XDG_SESSION_TYPE', '').lower() != 'x11':
        raise RuntimeError('Requires a confirmed native Linux X11 session (XDG_SESSION_TYPE=x11).')
    if not os.environ.get('DISPLAY'):
        raise RuntimeError('DISPLAY is unset; run inside the affected graphical session.')
    x = C.CDLL('libX11.so.6')
    x.XOpenDisplay.argtypes = [C.c_char_p]
    x.XOpenDisplay.restype = C.c_void_p
    x.XCloseDisplay.argtypes = [C.c_void_p]
    x.XQueryKeymap.argtypes = [C.c_void_p, C.c_void_p]
    x.XKeycodeToKeysym.argtypes = [C.c_void_p, C.c_ubyte, C.c_int]
    x.XKeycodeToKeysym.restype = C.c_ulong
    x.XKeysymToString.argtypes = [C.c_ulong]
    x.XKeysymToString.restype = C.c_char_p
    x.XSync.argtypes = [C.c_void_p, C.c_int]
    display = x.XOpenDisplay(None)
    if not display:
        raise RuntimeError('Cannot open DISPLAY with current session credentials.')

    def pressed():
        buf = C.create_string_buffer(32)
        x.XQueryKeymap(display, buf)
        result = []
        for code in range(8, 256):
            if buf.raw[code // 8] & (1 << (code % 8)):
                name = x.XKeysymToString(x.XKeycodeToKeysym(display, code, 0))
                result.append({'keycode': code, 'name': name.decode(errors='replace') if name else 'unknown'})
        return result

    try:
        before = pressed()
        report = {'display': os.environ['DISPLAY'], 'before': before, 'released': []}
        if args.release and before:
            xt = C.CDLL('libXtst.so.6')
            xt.XTestQueryExtension.argtypes = [C.c_void_p] + [C.POINTER(C.c_int)] * 4
            values = [C.c_int() for _ in range(4)]
            if not xt.XTestQueryExtension(display, *(C.byref(v) for v in values)):
                raise RuntimeError('XTEST extension unavailable; no releases sent.')
            xt.XTestFakeKeyEvent.argtypes = [C.c_void_p, C.c_uint, C.c_int, C.c_ulong]
            for key in before:
                if not xt.XTestFakeKeyEvent(display, key['keycode'], 0, 0):
                    raise RuntimeError(f"Release request failed for keycode {key['keycode']}")
                report['released'].append(key)
            x.XSync(display, 0)
            time.sleep(0.2)
        report['after'] = pressed()
        if args.release:
            report['immediate_after'] = report['after']
            after, seen, changes = observe(pressed, report['after'], args.watch_seconds)
            report.update(after=after, observed_pressed=seen, changes=changes,
                          watch_seconds=args.watch_seconds)
            if seen:
                report['status'] = 'pressed_during_observation'
                report['next_step'] = ('If all keys were released, manually Stop → Start Deskflow on the controller; '
                                       'then query and, if needed, release once. Do not loop releases. '
                                       'If this already followed a reconnect, stop releasing and inspect input sources/logs.')
            else:
                report['status'] = 'clear_during_observation' if before else 'no_pressed_keys_detected'
                report['next_step'] = 'Try typing and confirm recovery; a clear observation window does not guarantee no later recurrence.'
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if args.release and report['observed_pressed'] else 0
    finally:
        x.XCloseDisplay(display)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
