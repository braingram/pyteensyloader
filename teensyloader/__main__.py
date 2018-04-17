#!/usr/bin/env python
"""
reset device
program device

list device(s) hid + serial


firmware filename

python -m teensyloader reset 

commands:
   list
   reset
   program

arguments:
    -d device [serial number(s)]
    -f firmware [filename]
"""

from __future__ import print_function

import argparse
import sys

from . import core


parser = argparse.ArgumentParser(
    description="python utility for programming/resetting/finding teensies")

parser.add_argument("command", type=str, choices=["list", "reset", "program"])
parser.add_argument("firmware", type=str, nargs="?")
parser.add_argument("-d", "--device", type=str, default=None)
parser.add_argument(
    "-m", "--mcu", type=str, default=core.DEFAULT_MCU)

args = parser.parse_args(sys.argv[1:])

if args.command == "list":
    for (l, q) in [
            ('serial', core.find_serial_teensies),
            ('hid', core.find_hid_teensies)]:
        devs = q()
        print("Found %i %s teensies:" % (len(devs), l))
        for d in devs:
            print("\t%s" % d)
elif args.command == "reset":
    if args.device is None:
        dev = [core.get_single_teensy('serial', serial_number=True), ]
    else:
        if ',' in args.device:
            dev = [s.strip() for s in args.device.strip().split(",")]
        elif args.device.lower() == 'all':
            dev = core.find_serial_teensies().keys()
        else:
            dev = [args.device, ]
    for d in dev:
        print("Resetting %s... " % d, end="")
        core.reset_teensy(d, args.mcu)
        print("done")
elif args.command == "program":
    if args.firmware is None:
        raise ValueError("firmware filename is required to program")
    if args.device is None:
        dev = [core.get_single_teensy(serial_number=True), ]
    else:
        if ',' in args.device:
            dev = [s.strip() for s in args.device.strip().split(",")]
        elif args.device.lower() == 'all':
            dev = (
                core.find_serial_teensies().keys() +
                core.find_hid_teensies().keys())
        else:
            dev = [args.device, ]
    for d in dev:
        print("Programming %s... " % d, end="")
        core.program_teensy(args.firmware, args.mcu, dev=d)
        print("done")
