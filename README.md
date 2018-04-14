A simple python module for:

- listing available teensies
- resetting connected (serial) teensies
- programming connected teensies

Examples
----

```bash

# list available (serial and hid) teensies by serial number
python -m teensyloader list

# reset a connected teensy 3.2
python -m teensyloader reset -m TEENSY32

# reset all connected teensy 3.2s
python -m teensyloader reset -d all -m TEENSY32

# reset a specific connected teensy 3.2
python -m teensyloader reset -d 1234567 -m TEENSY32

# program a specific connected teensy 3.1
python -m teensyloader program test_sketch.ino.TEENSY31.hex -d 1234567 -m TEENSY31
```

Requirements
----

Requires pyusb (python libusb module):

https://github.com/pyusb/pyusb

All the low-level usb messages were taken from here:

https://github.com/PaulStoffregen/teensy_loader_cli
