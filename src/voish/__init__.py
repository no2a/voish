#!/usr/bin/env python3

# ref: https://github.com/alphacep/vosk-api/blob/v0.3.45/python/example/test_microphone.py

# prerequisites: as described in https://alphacephei.com/vosk/install and also python module `sounddevice` (simply run command `pip install sounddevice`)
# Example usage using Dutch (nl) recognition model: `python test_microphone.py -m nl`
# For more help run: `python test_microphone.py -h`

import argparse
import json
import os
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


def find_keywords(keywords, text):
    text = text.replace(' ', '')
    for i in keywords:
        if i in text:
            return i
    return None


def load_model(c):
    if 'path' in c:
        model = Model(model_path=os.path.expanduser(c['path']))
    else:
        model = Model(lang=c['lang'])
    return model


def _submain(config, samplerate):
    recs = []
    for cm in config['models']:
        model = load_model(cm)
        words = json.dumps(list(config['commands'].keys()))
        if config.get('grammar'):
            recs.append(KaldiRecognizer(model, samplerate, words))
        else:
            recs.append(KaldiRecognizer(model, samplerate))
    print('available commands:', list(config['commands'].keys()))
    last_command = None
    prompt = True
    with sd.InputStream(dtype="int16", channels=1, callback=callback):
        while True:
            prompt, last_command = _in_loop(prompt, last_command, recs, config)


def put_data_get_text(rec, data):
    if rec.AcceptWaveform(data):
        r = rec.Result()
    else:
        r = rec.PartialResult()
    j = json.loads(r)
    text = j.get('text')
    return text


def find_command_in_text(text_list, commands):
    for text in text_list:
        command = find_keywords(commands.keys(), text)
        if command:
            break
    if not command:
        return None, None
    return command, commands[command]


def _in_loop(prompt, last_command, recs, config):
    if prompt:
        print('> ', end='')
        prompt = False
    data = q.get()
    text_list = []
    for rec in recs:
        if text := put_data_get_text(rec, data):
            text_list.append(text)
    if not text_list:
        return prompt, last_command
    print('recognized %s' % (text_list, ), end='')
    prompt = True
    command, c = find_command_in_text(text_list, config['commands'])
    if not command:
        print(' -> no command matched')
        return prompt, last_command
    print(' -> command matched: %s %s' % (command, c))
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
    return prompt, last_command


def main():
    args = parse_args()
    with open(args.config) as f:
        config = yaml.safe_load(f)
    d = sd.query_devices(args.device, "input")
    try:
        _submain(config, d["default_samplerate"])
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
