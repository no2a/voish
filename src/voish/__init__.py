#!/usr/bin/env python3

# ref: https://github.com/alphacep/vosk-api/blob/v0.3.45/python/example/test_microphone.py

# prerequisites: as described in https://alphacephei.com/vosk/install and also python module `sounddevice` (simply run command `pip install sounddevice`)
# Example usage using Dutch (nl) recognition model: `python test_microphone.py -m nl`
# For more help run: `python test_microphone.py -h`

import argparse
import json
import queue
import subprocess
import sys

import sounddevice as sd
from vosk import Model, KaldiRecognizer
import yaml


q = queue.Queue()

def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text

def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "-l", "--list-devices", action="store_true",
        help="show list of audio devices and exit")
    args, remaining = parser.parse_known_args()
    if args.list_devices:
        print(sd.query_devices())
        sys.exit(0)
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parser])
    parser.add_argument(
        "-d", "--device",
        type=int_or_str,
        help="input device (numeric ID or substring)",
        default=0,
        )
    parser.add_argument('config')
    return parser.parse_args(remaining)


def run(cmd) -> int:
    p = subprocess.run(cmd['args'])
    return p.returncode


def _submain(config, samplerate):
    model = Model(lang=config['model'])
    words = json.dumps(list(config['commands'].keys()))
    print('available commands:', list(config['commands'].keys()))
    if config.get('grammar'):
        rec = KaldiRecognizer(model, samplerate, words)
    else:
        rec = KaldiRecognizer(model, samplerate)
    last_command = None
    prompt = True
    with sd.InputStream(dtype="int16", channels=1, callback=callback):
        while True:
            if prompt:
                print('\n> ', end='')
                prompt = False
            data = q.get()
            if rec.AcceptWaveform(data):
                r = rec.Result()
            else:
                r = rec.PartialResult()
            j = json.loads(r)
            text = j.get('text')
            if not text:
                continue
            print()
            prompt = True
            command = text.replace(' ', '')
            print('recognized `%s` as command `%s`' % (text, command), end='')
            c = config["commands"].get(command)
            if not c:
                print(' -> not found')
                continue
            print(' -> found %s' % (c, ))
            if c.get('again'):
                if last_command:
                    print('ok, run the last command again', '`%s`' % last_command)
                    c = config["commands"][last_command]
                    command = last_command
                else:
                    print('command does not run yet')
                    c = None
            if c:
                print('running command:', c['args'])
                rc = run(c)
                print('rc: %s' % rc)
                last_command = command


def main():
    args = parse_args()
    with open(args.config) as f:
        config = yaml.safe_load(f)
    d = sd.query_devices(args.device, "input")
    _submain(config, d["default_samplerate"])


if __name__ == '__main__':
    main()
