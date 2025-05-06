from config import *
import time

# I2C init on GP0 (SDA), GP1 (SCL)
#i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400_000)

EEPROM_ADDR = 0x50  # 7-bit I2C address of 24LC32AT

def data_write(start_address: int, data: bytes):
    if not isinstance(data, (bytes, bytearray)):
        data = bytes(data)

    if len(data) > 32:
        raise ValueError("Max 32 bytes per write due to EEPROM page size.")

    high_addr = (start_address >> 8) & 0xFF
    low_addr = start_address & 0xFF
    to_send = bytes([high_addr, low_addr]) + data

    i2c.writeto(EEPROM_ADDR, to_send)
    time.sleep_ms(10)  # EEPROM write cycle time (5ms typical, 10ms safe)

def data_read(start_address: int, num_bytes: int) -> bytes:
    high_addr = (start_address >> 8) & 0xFF
    low_addr = start_address & 0xFF

    # Set the address pointer
    i2c.writeto(EEPROM_ADDR, bytes([high_addr, low_addr]), False)
    return i2c.readfrom(EEPROM_ADDR, num_bytes)
