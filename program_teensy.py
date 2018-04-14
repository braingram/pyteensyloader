#!/usr/bin/env python

import sys
import time

import usb.core


fn = 'teensy_reboot_test.ino.TEENSY31.hex'

"""
{"at90usb162",   15872,   128},
{"atmega32u4",   32256,   128},
{"at90usb646",   64512,   256},
{"at90usb1286", 130048,   256},
#if defined(USE_LIBUSB) || defined(USE_APPLE_IOKIT) || defined(USE_WIN32)
{"mkl26z64",     63488,   512},
{"mk20dx128",   131072,  1024},
{"mk20dx256",   262144,  1024},
{"mk66fx1m0",  1048576,  1024},
{"mk64fx512",   524288,  1024},

// Add duplicates that match friendly Teensy Names
// Match board names in boards.txt
{"TEENSY2",   32256,   128},
{"TEENSY2PP", 130048,   256},
{"TEENSYLC",     63488,   512},
{"TEENSY30",   131072,  1024},
{"TEENSY31",   262144,  1024},
{"TEENSY35",   524288,  1024},
{"TEENSY36",  1048576,  1024},
"""

# Teensy 3.2
code_size = 262144
block_size = 1024
write_size = block_size + 64
max_memory = 0x100000


def read_intel_hex(fn, code_size):
    data = [0xff] * code_size
    mask = [False] * code_size
    n = 0
    with open(fn, 'rb') as f:
        for l in f:
            l = l.strip()
            if l[0] != ':':
                return data, mask, n
            # bc[2], addr[4], rtype[2], data[bc * 2], cs[2]
            bc = int(l[1:3], 16)
            addr = int(l[3:7], 16)  # used?
            rtype = int(l[7:9], 16)
            if rtype == 0:  # data
                ei = 9 + bc * 2
                ld = l[9:ei]
                cs = int(l[ei:ei+2], 16)
                ld = [int(i + j, 16) for (i, j) in zip(ld[::2], ld[1::2])]
                s = sum(ld) + bc + rtype + (addr & 0xFF) + (addr >> 8)
                s = (((~(s & 0xFF) & 0xFF)) + 1) & 0xFF
                if cs != s:
                    raise Exception("Checksum error: %s != %s" % (s, cs))
                data[addr:addr+len(ld)] = ld
                mask[addr:addr+len(ld)] = [True] * len(ld)
                n = max(n, addr+len(ld))
            elif rtype == 1:  # eof
                return data, mask, n
            #elif rtype == 2:  # extended segment address
            #elif rtype == 3:  # start segment address
            #elif rtype == 4:  # extended linear address
            #elif rtype == 5:  # start linear address
            else:
                raise NotImplementedError(
                    "Unsupported record type: %s" % rtype)
    return data, mask, n


devs = list(usb.core.find(find_all=True, idVendor=0x16C0, idProduct=0x0483))
if len(devs):
    print("Found %s attached teensies" % len(devs))
    for d in devs:
        print("\t%s" % d.serial_number)
    if len(devs) == 0:
        sys.exit(1)

    # TODO select teensy
    dev = devs[0]

    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
    dev.set_configuration()

    # soft reboot
    print("Soft reboot...")
    dev.ctrl_transfer(0x21, 0x20, 0, 0, chr(134), 10000)

    time.sleep(1.0)

# find HalfKay HID teensy
t = 5
while t > 0:
    dev = usb.core.find(idVendor=0x16C0, idProduct=0x0478)
    if dev is not None:
        break
    time.sleep(0.1)
    t -= 0.1
if dev is None:
    print("No bootloader found")
    sys.exit(1)
if dev.is_kernel_driver_active(0):
    dev.detach_kernel_driver(0)
time.sleep(0.1)
dev.set_configuration()

# read hex
data, mask, n = read_intel_hex(fn, code_size)
print("%0.2f%% used" % (n / float(code_size) * 100.))

# write hex
i = 0
t = 5000
while i < n:
    d = data[i:i+block_size]
    m = mask[i:i+block_size]
    if len(d) < block_size:  # pad block
        d += [0xFF] * (block_size - len(d))
        m += [False] * (block_size - len(d))
    if any(m) or (i != 0):
        # write
        addr = [i & 0xFF, (i >> 8) & 0xFF, (i >> 16) & 0xFF]
        d = addr + ([0] * 61) + d
        # s = str(bytearray(d))
        c = 0
        while t > 0:
            try:
                r = dev.ctrl_transfer(0x21, 9, 0x0200, 0, d, t)
            except usb.core.USBError:
                r = 0
            c += r
            if (c == len(d)):
                break
            time.sleep(0.01)
            t -= 10
        if c != len(d):
            raise Exception("Failed to write firmware")
    t = 500  # only use long timeout on first block
    i += block_size

# boot
print("Booting...")
block = '\x00' * (block_size + 64)
block = '\xff\xff\xff' + block[3:]
t = 5000
while t > 0:
    try:
        dev.ctrl_transfer(0x21, 9, 0x0200, 0, block, t)
        break
    except usb.core.USBError:
        time.sleep(0.01)
        t -= 10
