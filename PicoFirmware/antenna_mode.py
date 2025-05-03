"""
antenna_mode.py

Controls the 48-bit shift registers for antenna modes, reads antenna sense and mode inputs,
and manages fan speed. Supports multiple input formats for shift-register data.
"""

import time
from config import SR_SER, SR_SRCLK, SR_RCLK, SR_OE, SR_OUT, antenna_sense, mode_pins, fan_pwm


def update_shift_registers(data):
    """
    Update the 48-bit shift registers and read back their state.

    Args:
        data (list[int] | int | str): 48-bit pattern to write. Can be:
          - list or tuple of 48 bits (0 or 1)
          - integer (will be converted to 48-bit big-endian)
          - hex string (e.g. '0xFF00AA...') representing up to 48 bits

    Returns:
        list[int]: 48 bits read back from the shift register.

    Raises:
        ValueError: if bit list length is not 48 or contains invalid values.
        TypeError: if data type is unsupported.
    """
    # Convert various formats into a list of 48 bits (MSB first)
    if isinstance(data, str):  # hex string
        # parse hex, then extract bits
        val = int(data, 16)
        bits = [(val >> i) & 1 for i in range(47, -1, -1)]
    elif isinstance(data, int):  # integer
        val = data
        bits = [(val >> i) & 1 for i in range(47, -1, -1)]
    elif isinstance(data, (list, tuple)):
        bits = list(data)
        if len(bits) != 48 or any(bit not in (0, 1) for bit in bits):
            raise ValueError("List must contain exactly 48 elements of 0 or 1.")
    else:
        raise TypeError("Data must be a 48-bit list, int, or hex string.")

    # Begin write sequence: enable outputs, clear latch
    SR_OE.value(0)       # Output enable (active low)
    SR_RCLK.value(0)      # Prepare latch

    # Shift bits into register (MSB first)
    for bit in bits:
        SR_SER.value(bit)
        time.sleep_us(1)
        SR_SRCLK.value(1)
        time.sleep_us(1)
        SR_SRCLK.value(0)

    # Latch shifted data to outputs
    SR_RCLK.value(1)
    time.sleep_us(1)
    SR_RCLK.value(0)

    # Read back current register state (optional)
    read_data = []
    for _ in range(48):
        SR_SRCLK.value(1)
        time.sleep_us(1)
        read_data.append(SR_OUT.value())
        SR_SRCLK.value(0)
        time.sleep_us(1)

    return read_data


def read_sense():
    """
    Read and print the raw antenna sense ADC value.

    Returns:
        int: 16-bit ADC reading.
    """
    value = antenna_sense.read_u16()
    print(f"Antenna Sense: {value}")
    return value


def read_mode():
    """
    Read the 4-bit mode select inputs and compute a mode value (0-15).

    Returns:
        int: Combined mode value from pins [bit3,bit2,bit1,bit0].
    """
    bits = [pin.value() for pin in mode_pins]
    mode = (bits[0] << 3) | (bits[1] << 2) | (bits[2] << 1) | bits[3]
    print(f"Current Mode bits: {bits[0]}{bits[1]}{bits[2]}{bits[3]}, Mode value: {mode}")
    return mode


def set_fan_speed(percentage):
    """
    Set the fan PWM duty based on percentage.

    Args:
        percentage (int | float): Fan speed from 0 to 100%.
    """
    if not (0 <= percentage <= 100):
        print("Fan speed must be between 0 and 100.")
        return
    if percentage < 20:
        fan_pwm.duty_u16(0)
        print("Below 20% threshold. Fan is off.")
    else:
        duty = int((percentage / 100) * 65535)
        fan_pwm.duty_u16(duty)
        print(f"Fan speed set to {percentage}%")
