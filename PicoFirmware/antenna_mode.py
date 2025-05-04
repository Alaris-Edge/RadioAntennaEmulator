"""
antenna_mode.py

Controls the 48-bit shift registers for antenna modes via a 50-pin connector,
reads antenna sense and mode inputs, and manages fan speed.
Supports list, integer, binary string, and hex string inputs for shift-register data,
with validation and automatic truncation to 48 bits.
"""

import time
from config import SR_SER, SR_SRCLK, SR_RCLK, SR_OE, SR_OUT, antenna_sense, mode_pins, fan_pwm


def update_shift_registers(data):
    """
    Update the 48-bit shift registers and read back their state.

    Args:
        data (list[int] | int | str): 48-bit pattern to write. Accepted formats:
          - list or tuple of exactly 48 bits (0 or 1)
          - non-negative integer (will be truncated to lower 48 bits)
          - binary string of '0' and '1' (any length; trimmed to last 48 bits)
          - hex string (e.g. '0xFF00AA'); up to 12 hex digits (truncated to lower 48 bits)

    Returns:
        list[int]: 48 bits read back from the shift register.

    Raises:
        ValueError: for invalid list length or binary string too short.
        TypeError: if `data` is not list, tuple, int, or str.
    """
    # Convert input to 48-bit list (MSB first)
    if isinstance(data, str):
        data_str = data
        if all(c in '01' for c in data_str):
            # Binary string
            if len(data_str) < 48:
                raise ValueError("Binary string must have at least 48 bits.")
            if len(data_str) > 48:
                print("Warning: binary string longer than 48 bits; truncating.")
                data_str = data_str[-48:]
            bits = [int(c) for c in data_str]
        else:
            # Hex string
            try:
                val = int(data_str, 16)
            except ValueError:
                raise ValueError("String data must be binary or hex.")
            if val < 0:
                raise ValueError("Hex value cannot be negative.")
            if val >= (1 << 48):
                print("Warning: hex value exceeds 48 bits; truncating.")
                val &= (1 << 48) - 1
            bits = [(val >> i) & 1 for i in range(47, -1, -1)]
    elif isinstance(data, int):
        val = data
        if val < 0:
            raise ValueError("Integer must be non-negative.")
        if val >= (1 << 48):
            print("Warning: integer exceeds 48 bits; truncating.")
            val &= (1 << 48) - 1
        bits = [(val >> i) & 1 for i in range(47, -1, -1)]
    elif isinstance(data, (list, tuple)):
        bits = list(data)
        if len(bits) != 48 or any(bit not in (0, 1) for bit in bits):
            raise ValueError("List must contain exactly 48 elements of 0 or 1.")
    else:
        raise TypeError("Data must be list, tuple, int, or str.")

    # Write sequence: enable outputs, clear latch
    SR_OE.value(0)
    SR_RCLK.value(0)

    # Shift in bits
    for bit in bits:
        SR_SER.value(bit)
        time.sleep_us(1)
        SR_SRCLK.value(1)
        time.sleep_us(1)
        SR_SRCLK.value(0)

    # Latch data
    SR_RCLK.value(1)
    time.sleep_us(1)
    SR_RCLK.value(0)

    return readshift_registers()


def readshift_registers():
    # Read back 48 bits
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
    Read the 3-bit mode select inputs (mode_pins[1..3]) and return a mode value (0–7).

    Returns:
        int: Mode value between 0 and 7.
    """
    bits = [pin.value() for pin in mode_pins]
    # Combine bits 1,2,3 into a 3-bit number
    mode = (bits[1] << 2) | (bits[2] << 1) | bits[3]
    # print(f"Mode bits: {bits[1]}{bits[2]}{bits[3]}, Mode value: {mode}")
    return mode


def set_fan_speed(percentage):
    """
    Set the fan PWM duty based on percentage (0-100%).
    Accepts integer or float, which is rounded to the nearest integer.

    Args:
        percentage (int | float | str): Desired fan speed from 0 to 100%.
    """
    # Parse and clamp percentage
    try:
        pct = float(percentage)
    except (ValueError, TypeError):
        print("Invalid percentage value. Please provide a number between 0 and 100.")
        return
    pct = max(0.0, min(100.0, pct))
    int_pct = int(round(pct))

    # Below threshold: fan off
    if int_pct < 20:
        fan_pwm.duty_u16(0)
        print(f"Below 20% threshold. Fan is off. (Requested: {pct}%, rounded to {int_pct}%)")
        return

    # Compute and apply duty cycle
    duty = int((int_pct / 100) * 65535)
    fan_pwm.duty_u16(duty)
    print(f"Fan speed set to {int_pct}% (requested {pct}%)")
