#!/usr/bin/env python
"""
MCU auto-detection
HEX auto-detection

bDeviceClass: 2: serial, 0: (use interface, which is HID)
"""

import time

import usb.core


LONG_TIMEOUT = 5000
SHORT_TIMEOUT = 500
POLL_TIME = 10

# code_size, block_size
mcus = {
    "at90usb162": (15872, 128),
    "atmega32u4": (32256, 128),
    "at90usb646": (64512, 256),
    "at90usb1286": (130048, 256),
    "mkl26z64": (63488, 512),
    "mk20dx128": (131072, 1024),
    "mk20dx256": (262144, 1024),
    "mk66fx1m0": (1048576, 1024),
    "mk64fx512": (524288, 1024),
}
mcus["TEENSY2"] = mcus["atmega32u4"]
mcus["TEENSY2PP"] = mcus["at90usb1286"]
mcus["TEENSYLC"] = mcus["mkl26z64"]
mcus["TEENSY30"] = mcus["mk20dx128"]
mcus["TEENSY31"] = mcus["mk20dx256"]
mcus["TEENSY32"] = mcus["mk20dx256"]
mcus["TEENSY35"] = mcus["mk64fx512"]
mcus["TEENSY36"] = mcus["mk66fx1m0"]

DEFAULT_MCU = "TEENSY32"


def get_mcu(mcu):
    if mcu is None:
        mcu = DEFAULT_MCU
    if mcu not in mcus:
        raise ValueError("Unknown mcu: %s" % mcu)
    return mcus[mcu]


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


def organize_by_serial(devs, serial=None):
    r = {}
    for d in devs:
        # TODO check for duplicates
        if hasattr(d, 'serial_number'):
            r[d.serial_number] = d
        #elif hasattr(d, 'iSerialNumber'):
        #    r[d.iSerialNumber] = d
    if serial is None:
        return r
    if isinstance(serial, (str, unicode)):
        if serial in r:
            return r[serial]
        raise IOError("Teensy %s not found" % serial)
    serial = list(serial)
    return {k: r[k] for k in r if k in serial}


def find_serial_teensies(serial=None):
    devs = list(usb.core.find(
        find_all=True, idVendor=0x16C0, idProduct=0x0483))
    return organize_by_serial(devs, serial)


def find_hid_teensies(serial=None):
    devs = list(usb.core.find(
        find_all=True, idVendor=0x16C0, idProduct=0x0478))
    return organize_by_serial(devs, serial)


def wait_for_device(
        serial, poll_function=find_hid_teensies, timeout=LONG_TIMEOUT,
        poll_time=POLL_TIME):
    if timeout <= 0:
        raise ValueError("Timeout[%s] must be > 0" % timeout)
    while timeout > 0:
        try:
            dev = poll_function(serial)
            return dev
        except IOError:
            time.sleep(poll_time / 1000.)
            timeout -= poll_time


def get_single_teensy(find_function=None, serial_number=False):
    if find_function == 'serial':
        find_function = find_serial_teensies
    elif find_function == 'hid':
        find_function = find_hid_teensies
    elif find_function is None:
        def find_function():
            a = find_serial_teensies()
            a.update(find_hid_teensies())
            return a
    devs = find_function()
    if len(devs) == 0:
        raise IOError("Failed to find teensy")
    elif len(devs) > 1:
        raise IOError("Found %i[>1] teensies" % len(devs))
    if serial_number:
        return devs.keys()[0]
    return devs.values()[0]


def soft_reboot_serial(dev=None, find=True):
    if dev is None:
        dev = get_single_teensy(find_serial_teensies)
    if isinstance(dev, (str, unicode)):
        dev = find_serial_teensies(dev)
    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
        time.sleep(0.1)
        dev.set_configuration()

    if find:
        old_devs = find_hid_teensies()
    dev.ctrl_transfer(0x21, 0x20, 0, 0, chr(134), 10000)
    if not find:
        return

    # look for new hid device
    t = LONG_TIMEOUT
    dev = None
    while t > 0 and dev is None:
        devs = find_hid_teensies()
        for d in devs:
            if d not in old_devs:
                dev = d
                break
        time.sleep(POLL_TIME / 1000.)
        t -= POLL_TIME
    if dev is None:
        raise IOError("Device %s did not re-appear after reboot" % dev)
    return dev


def program_hid_device(filename, mcu=None, dev=None, autoboot=True):
    code_size, block_size = get_mcu(mcu)

    if dev is None:
        dev = get_single_teensy(find_hid_teensies)
    if isinstance(dev, (str, unicode)):
        dev = find_hid_teensies(dev)
    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
        dev.set_configuration()

    data, mask, n = read_intel_hex(filename, code_size)

    i = 0
    t = LONG_TIMEOUT

    while i < n:
        d = data[i:i+block_size]
        m = mask[i:i+block_size]
        if len(d) < block_size:  # pad block
            d += [0xFF] * (block_size - len(d))
            m += [False] * (block_size - len(d))
        if any(m) or (i != 0):
            # write
            if block_size <= 256 and code_size < 0x10000:
                raise NotImplementedError("only 512/1024 block size supported")
            elif block_size == 256:
                raise NotImplementedError("only 512/1024 block size supported")
            elif block_size in (512, 1024):
                addr = [i & 0xFF, (i >> 8) & 0xFF, (i >> 16) & 0xFF]
                d = addr + ([0] * 61) + d
            else:
                raise ValueError("Unknown block_size: %s" % block_size)
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
                time.sleep(POLL_TIME / 1000.)
                t -= POLL_TIME
            if c != len(d):
                raise Exception("Failed to write firmware")
        t = SHORT_TIMEOUT  # only use long timeout on first block
        i += block_size

    if autoboot:
        boot(mcu, dev)


def boot(mcu=None, dev=None):
    # TODO wait for device to reappear, do HID teensies disappear?
    code_size, block_size = get_mcu(mcu)

    if dev is None:
        dev = get_single_teensy(find_hid_teensies)
    if isinstance(dev, (str, unicode)):
        dev = find_hid_teensies(dev)
    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
        time.sleep(0.1)
        dev.set_configuration()

    if block_size in (512, 1024):
        block = '\x00' * (block_size + 64)
    else:
        block = '\x00' * (block_size + 2)
    block = '\xff\xff\xff' + block[3:]
    t = LONG_TIMEOUT
    while t > 0:
        try:
            dev.ctrl_transfer(0x21, 9, 0x0200, 0, block, t)
            return True
        except usb.core.USBError:
            time.sleep(POLL_TIME / 1000.)
            t -= POLL_TIME
    return False


def reset_teensy(dev=None, mcu=None):
    # find serial device, reboot it
    boot(mcu, soft_reboot_serial(dev))
    # TODO wait for it to re-appear?


def program_teensy(fn, mcu=None, dev=None, autoboot=True):
    # find device
    if dev is None:
        try:
            dev = get_single_teensy(find_hid_teensies)
        except IOError:
            dev = get_single_teensy(find_serial_teensies)
            dev = soft_reboot_serial(dev)
            time.sleep(1.0)
    if isinstance(dev, (str, unicode)):
        try:
            dev = find_hid_teensies(dev)
        except IOError:
            dev = find_serial_teensies(dev)
            dev = soft_reboot_serial(dev)
            time.sleep(1.0)

    program_hid_device(fn, mcu, dev, autoboot=autoboot)
