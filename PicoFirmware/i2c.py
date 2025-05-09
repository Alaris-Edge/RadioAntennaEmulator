from config import *
import time

# I2C init on GP0 (SDA), GP1 (SCL)
#i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400_000)

EEPROM_ADDR = 0x50  # 7-bit I2C address of 24LC32AT
EEPROM_SIZE = 4096  # Total capacity in bytes (4 KBytes)
PAGE_SIZE = 32     # EEPROM page size in bytes


def data_write(start_address: int, data: bytes):
    """
    Write bytes to the EEPROM starting at the given address.

    Uses EEPROM page size (32 bytes) and polls for write completion via ACK
    rather than a fixed delay, improving throughput.
    """
    if not isinstance(data, (bytes, bytearray)):
        data = bytes(data)

    if len(data) > PAGE_SIZE:
        raise ValueError(f"Max {PAGE_SIZE} bytes per write due to EEPROM page size.")

    if start_address < 0 or start_address + len(data) > EEPROM_SIZE:
        raise ValueError("Write range exceeds EEPROM capacity.")

    high_addr = (start_address >> 8) & 0xFF
    low_addr = start_address & 0xFF
    to_send = bytes([high_addr, low_addr]) + data

    # Initiate write cycle
    i2c.writeto(EEPROM_ADDR, to_send)
    # Poll device for ACK to signal write completion
    while True:
        try:
            # Attempt zero-length write; success means EEPROM is ready
            i2c.writeto(EEPROM_ADDR, b"")
            break
        except OSError:
            # EEPROM is busy, keep polling
            time.sleep_ms(1)


def data_read(start_address: int, num_bytes: int) -> bytes:
    """
    Read a sequence of bytes from the EEPROM starting at the given address.

    Uses a repeated-start write to set the address pointer without issuing a stop.
    """
    if num_bytes < 0 or start_address < 0 or start_address + num_bytes > EEPROM_SIZE:
        raise ValueError("Read range exceeds EEPROM capacity.")

    high_addr = (start_address >> 8) & 0xFF
    low_addr = start_address & 0xFF

    # Set the address pointer without a stop condition
    i2c.writeto(EEPROM_ADDR, bytes([high_addr, low_addr]), stop=False)
    return i2c.readfrom(EEPROM_ADDR, num_bytes)
