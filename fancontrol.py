#!/usr/bin/env python3
# -*- coding: utf8 -*-

import glob
import io
import itertools
import logging
import os
import shlex
import stat
import subprocess
import sys

log = logging.getLogger('fancontrol')
log.addHandler(logging.StreamHandler(sys.stdout))
log.setLevel(logging.DEBUG)

DEFAULT_DEVICE_PATTERNS = [
    '/dev/sg*',
    '/dev/ses*',
    '/dev/bsg/*',
]
# sg_ses uses a default of 65532, but not everything supports that
MAX_SES_RESULT_LEN = 32768
MAX_FANS = 6
FAN_SPEED_LEVELS = list(range(1, 8))

def sg_ses(*args, error_is_fatal=True, **kwargs):
    cmd = ['sg_ses', '--maxlen={:d}'.format(MAX_SES_RESULT_LEN)] + list(args)
    run_args = {
        'stdout': subprocess.PIPE,
        'stderr': subprocess.DEVNULL,
        'stdin': subprocess.DEVNULL,
        'check': True,
    }
    run_args.update(kwargs)

    log.debug('# %s', ' '.join(shlex.quote(t) for t in cmd))
    try:
        result = subprocess.run(cmd, **run_args)
    except subprocess.CalledProcessError as err:
        log.debug('Command returned non-zero exitcode: %s', err.returncode)
        log.debug('Command STDOUT: %s', err.stdout.decode('utf-8'))
        log.debug('Command STDERR: %s', err.stderr.decode('utf-8'))
        if error_is_fatal:
            raise err
        else:
            return None
    return result

def get_sa120_devices(device_patterns):
    invert_dict = lambda d: {v: k for k, v in d.items()}

    extant_devices = filter(lambda d: stat.S_ISCHR(os.stat(d).st_mode),
        itertools.chain(*[glob.glob(device_glob) for device_glob in device_patterns]))
    unique_devices = invert_dict(invert_dict({dev_path: get_device_id(dev_path) 
        for dev_path in extant_devices}))

    for dev_path, dev_id in unique_devices.items():
        log.info('Checking device: %s (%s)', dev_path, dev_id)
        try:
            out = sg_ses(dev_path, '--status').stdout.decode('utf-8')
        except subprocess.CalledProcessError as err:
            log.debug(err)
            continue

        if out.strip():
            enc_name = out.splitlines()[0].strip()
            log.debug('Found enclosure on %s: %s', dev_path, enc_name)
            if 'ThinkServerSA120' in enc_name:
                log.info('Found a SA120 at: %s', dev_path)
                yield dev_path

def get_device_id(device_path):
    dev_stat = os.stat(device_path)
    return '{},{}'.format(os.major(dev_stat.st_rdev), os.minor(dev_stat.st_rdev))

def get_fan_speed(device_path, fan_idx):
    return int(sg_ses(device_path, '--index=coo,{:d}'.format(fan_idx), '--get=1:2:11').stdout.decode('utf-8'))

def get_fan_speeds(device_path):
    return [get_fan_speed(device_path, i) for i in range(0, MAX_FANS)]

def set_fan_speeds(device_path, speed):
    if speed not in FAN_SPEED_LEVELS:
        raise ValueError('Invalid fan speed level: %d' % speed)

    fan_data = sg_ses(device_path, '-p', '0x2', '--raw').stdout.split()

    for fan_idx in range(MAX_FANS):
        offset = 88 + (fan_idx * 4)
        fan_data[offset + 0] = b'80'
        fan_data[offset + 1] = b'00'
        fan_data[offset + 2] = b'00'
        fan_data[offset + 3] = u'{:x}'.format(1 << 5 | speed & 7).encode('utf-8')

    cmd_input = io.BytesIO()
    for offset in range(len(fan_data)):
        cmd_input.write(fan_data[offset])
        if (offset + 1) % 16 == 0:
            cmd_input.write(b'\n')
        elif (offset + 1) % 8 == 0:
            cmd_input.write(b'  ')
        else:
            cmd_input.write(b' ')
    cmd_input.write(b'\n')

    proc = sg_ses(device_path, '-p', '0x2', '--control', '--data', '-',
        stdin=subprocess.PIPE)
    out = proc.communicate(input=cmd_input.getvalue())[0].decode('utf-8')
    log.debug('Fan control cmd output: %s', out)

def main(args):
    dev_patterns = DEFAULT_DEVICE_PATTERNS + args.devices

    for dev_path in get_sa120_devices(dev_patterns):
        for fan_idx, fan_speed in enumerate(get_fan_speeds(dev_path)):
            log.info('Fan #%d: %d RPM', fan_idx, fan_speed)

        if args.set_speed:
            log.info('Setting fan speed level: %d', args.set_speed)
            set_fan_speeds(dev_path, args.set_speed)
    else:
        log.warning('No enclosures found!')

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--set-speed',
        help='Set the fan speed level',
        type=int, default=None,
        choices=FAN_SPEED_LEVELS,
    )
    parser.add_argument('devices',
        help='Extra paths to search for enclosures',
        metavar='DEVICE', nargs='*',
    )
    parser.add_argument('-v', '--verbose',
        help='Log more messages',
        action='count', default=0,
    )
    parser.add_argument('-q', '--quiet',
        help='Log fewer messages',
        action='count', default=0,
    )
    args = parser.parse_args()

    log.setLevel(
        min(logging.CRITICAL, max(logging.DEBUG,
            logging.INFO + (args.quiet * 10) - (args.verbose * 10)
        ))
    )

    main(args)
