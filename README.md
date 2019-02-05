# lenovo-sa120-fanspeed-utility

A rewrite of the original fanspeed utility from @AndrewX192.

## Requirements

Requires Python and the `sg_ses` utility, provided by [the `sg3_utils` package](http://sg.danny.cz/sg/sg3_utils.html).

Debian-based systems might use:

    # apt-get install sg3-utils

On RHEL/CentOS systems:

    # yum install sg3_utils

FreeBSD systems via `pkg`:

    # pkg install sysutils/sg3_utils

FreeNAS 9.10 includes `sg_ses` as part of the standard image.

## Usage

Finds the ThinkServer Enclosure automatically. Works when the devices are
either `/dev/sg*`, `/dev/ses*`, or `/dev/bsg/*`. You can optionally specify
additional paths to search in case the defaults do not cover your setup.

~~~~
# ./fancontrol.py -h
usage: fancontrol.py [-h] [-s {1,2,3,4,5,6,7}] [-v] [-q] [-j]
                     [DEVICE [DEVICE ...]]
        
positional arguments:
  DEVICE                Extra paths to search for enclosures

optional arguments:
  -h, --help            show this help message and exit
  -s {1,2,3,4,5,6,7}, --set-speed {1,2,3,4,5,6,7}
                        Set the fan speed level
  -v, --verbose         Log more messages
  -q, --quiet           Log fewer messages
  -j, --json            Write fan speeds as json to stdout
~~~~

**NOTE** Most output is sent to *stderr*, except for the JSON from `-j` which is
output on *stdout*.

## Examples

~~~~
# ./fancontrol.py
Checking device: /dev/ses0 (0,169)
Found a SA120 at: /dev/ses0
Fan #0: 830 RPM
Fan #1: 944 RPM
Fan #2: 937 RPM
Fan #3: 928 RPM
Fan #4: 939 RPM
Fan #5: 954 RPM
~~~~
~~~~
# ./fancontrol.py -s 2
Checking device: /dev/ses0 (0,169)
Found a SA120 at: /dev/ses0
Setting fan speed level: 2
~~~~
~~~~
# ./fancontrol.py -j
Checking device: /dev/ses0 (0,169)
Found a SA120 at: /dev/ses0
Checking device: /dev/ses1 (0,170)
{"ses0": {"fan_0": 830, "fan_1": 944, "fan_2": 939, "fan_3": 928, "fan_4": 939, "fan_5": 954}}
~~~~
