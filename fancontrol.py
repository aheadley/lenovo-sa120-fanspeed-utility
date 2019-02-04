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

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('fancontrol')

DEFAULT_DEVICE_PATTERNS = [
    '/dev/sg*',
    '/dev/ses*',
    '/dev/bsg/*',
]
# sg_ses uses a default of 65532, but not everything supports that
MAX_SES_RESULT_LEN = 32768
MAX_FANS = 6

def sg_ses(*args, **kwargs):
    cmd = ['sg_ses', '--maxlen={:d}'.format(MAX_SES_RESULT_LEN)] + args
    run_args = {
        'stdout': subprocess.PIPE,
        'stderr': subprocess.DEVNULL,
        'check': True,
    }
    run_args.update(kwargs)

    log.debug('Running command: %s', ' '.join(shlex.quote(t) for t in cmd))
    return subprocess.run(cmd, **run_args)

def get_sa120_devices(device_patterns):
    invert_dict = lambda d: {v: k for k, v in d.items()}

    extant_devices = filter(lambda d: stat.S_ISCHR(os.stat(d).st_mode),
        itertools.chain(*[glob.glob(device_glob) for device_glob in device_patterns]))
    unique_devices = invert_dict(invert_dict({dev_path: get_device_id(dev_path) 
        for dev_path in extant_devices}))

    log.debug('Found existing devices: %s', ', '.join(unique_devices.keys()))

    for dev_path, dev_id in unique_devices.items():
        log.info('Checking device: %s (%s)', dev_path, dev_id)
        try:
            out = sg_ses(dev_path, '--status').stdout.decode('utf-8')
        except subprocess.CalledProcessError as err:
            log.debug(err)
            continue

        if out.strip():
            enc_name = out.splitlines()[0].strip()
            log.info('Found enclosure on %s: %s', dev_path, enc_name)
            if 'ThinkServerSA120' in enc_name:
                yield dev_path

def get_device_id(device_path):
    dev_stat = os.stat(device_path)
    return '{},{}'.format(os.major(dev_stat.st_rdev), os.minor(dev_stat.st_rdev))

def get_fan_speed(device_path, fan_idx):
    return int(sg_ses(device_path, '--index=coo,{:d}'.format(fan_idx), '--get=1:2:11').stdout.decode('utf-8'))

def get_fan_speeds(device_path):
    return [get_fan_speed(device_path, i) for i in range(0, MAX_FANS)]

def set_fan_speeds(device_path, speed):
    fan_data = sg_ses(device_path, '-p', '0x2', '--raw').stdout.split()

    for fan_idx in range(0, MAX_FANS):
        idx = 88 + 4 * fan_idx
        fan_data[idx + 0] = b'80'
        fan_data[idx + 1] = b'00'
        fan_data[idx + 2] = b'00'
        fan_data[idx + 3] = u'{:x}'.format(1 << 5 | speed & 7).encode('utf-8')

    cmd_input = io.BytesIO()
    for offset in range(0, len(fan_data)):
        cmd_input.write(fan_data[offset])
        if offset > 0 and offset % 16 == 0:
            cmd_input.write(b'\n')
        elif offset > 0 and offset % 8 == 0:
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
            log.info('Setting fan speed to: %d RPM', args.set_speed)
            set_fan_speeds(device_path, args.set_speed)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--set-speed',
        help='Set the fan speed',
        type=int,
    )
    parser.add_argument('devices',
        help='Extra paths to search for enclosure',
        metavar='DEVICE', nargs='*',
    )
    args = parser.parse_args()

    main(args)
