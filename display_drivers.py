# Display Driver Definitions for Tildagon Badge Display Mirroring & Screen Drivers
# No hardcoded display drivers in firmware - all drivers are data-driven structures defined here.

# GC9A01 Round LCD Controller Driver
# Used by the Tildagon Round Screen Hexpansion
GC9A01_DRIVER = {
    "init": [
        (0xef, None, 0),
        (0xeb, b"\x14", 0),
        (0xfe, None, 0),
        (0xef, None, 0),
        (0xeb, b"\x14", 0),
        (0x84, b"\x40", 0),
        (0x85, b"\xff", 0),
        (0x86, b"\xff", 0),
        (0x87, b"\xff", 0),
        (0x88, b"\x0a", 0),
        (0x89, b"\x21", 0),
        (0x8a, b"\x00", 0),
        (0x8b, b"\x80", 0),
        (0x8c, b"\x01", 0),
        (0x8d, b"\x01", 0),
        (0x8e, b"\xff", 0),
        (0x8f, b"\xff", 0),
        (0xb6, b"\x00\x20", 0),
        (0x90, b"\x08\x08\x08\x08", 0),
        (0xbd, b"\x06", 0),
        (0xbc, b"\x00", 0),
        (0xff, b"\x60\x01\x04", 0),
        (0xc3, b"\x13", 0),
        (0xc4, b"\x13", 0),
        (0xc9, b"\x22", 0),
        (0xbe, b"\x11", 0),
        (0xe1, b"\x10\x0e", 0),
        (0xdf, b"\x21\x0c\x02", 0),
        (0xf0, b"\x45\x09\x08\x08\x26\x2a", 0),
        (0xf1, b"\x43\x70\x72\x36\x37\x6f", 0),
        (0xf2, b"\x45\x09\x08\x08\x26\x2a", 0),
        (0xf3, b"\x43\x70\x72\x36\x37\x6f", 0),
        (0xed, b"\x1b\x0b", 0),
        (0xae, b"\x77", 0),
        (0xcd, b"\x63", 0),
        (0x70, b"\x07\x07\x04\x0e\x0f\x09\x07\x08\x03", 0),
        (0xe8, b"\x34", 0),
        (0x62, b"\x18\x0d\x71\xed\x70\x70\x18\x0f\x71\xef\x70\x70", 0),
        (0x63, b"\x18\x11\x71\xf1\x70\x70\x18\x13\x71\xf3\x70\x70", 0),
        (0x64, b"\x28\x29\xf1\x01\xf1\x00\x07", 0),
        (0x66, b"\x3c\x00\xcd\x67\x45\x45\x10\x00\x00\x00", 0),
        (0x67, b"\x00\x3c\x00\x00\x00\x01\x54\x10\x32\x98", 0),
        (0x74, b"\x10\x85\x80\x00\x00\x4e\x00", 0),
        (0x98, b"\x3e\x07", 0),
        (0x35, None, 0),       # TEON
        (0x21, None, 0),       # INVON
        (0x11, None, 150),     # SLPOUT, wait 150ms
        (0x36, b"\xc8", 0),    # MADCTL: BGR + MX + MY (matches badge native rotation)
        (0x3a, b"\x05", 0),    # COLMOD: 16-bit RGB565
        (0x29, None, 150),     # DISPON, wait 150ms
        (0x2a, b"\x00\x00\x00\xef", 0), # CASET: 0..239
        (0x2b, b"\x00\x00\x00\xef", 0), # PASET: 0..239
        (0x2c, None, 0),       # RAMWR
    ],
    "prefix": [
        (0x2a, b"\x00\x00\x00\xef", 0), # CASET
        (0x2b, b"\x00\x00\x00\xef", 0), # PASET
        (0x2c, None, 0),                 # RAMWR
    ],
    "baudrate": 40_000_000,
}

# HDMI Driver
# Transmits 4-byte framing magic header 'TDHD' before pixel payload
HDMI_DRIVER = {
    "header": b"TDHD",
    "baudrate": 20_000_000,
}
