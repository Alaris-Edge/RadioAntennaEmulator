"""
voltage_control.py

Handles ADC readings for fixed and adjustable voltage rails, shutdown, wiper control,
calibration routines with persistent storage, and exposes debug getters.
"""

import time
import ujson as json
import os

from config import (
    kill_pin,
    fan_pwm,
    fixed_measure,
    adjustable_measure,
    cs,
    spi,
)

CALIB_FILE = 'voltage_calibration.json'

# ADC constants
_ADC_MAX = 65535
_VREF = 3.3

# Nominal divider and default slope
_NOMINAL_DIVIDER = 3.7
_DEFAULT_SLOPE = (_VREF * _NOMINAL_DIVIDER) / _ADC_MAX

_calibration = {
    'fixed':      {'slope': _DEFAULT_SLOPE, 'intercept': 0.0},
    'adjustable': {'slope': _DEFAULT_SLOPE, 'intercept': 0.0}
}


def load_calibration():
    global _calibration
    try:
        with open(CALIB_FILE, 'r') as f:
            data = json.load(f)
            for ch in ('fixed', 'adjustable'):
                entry = data.get(ch)
                if isinstance(entry, dict):
                    _calibration[ch] = {
                        'slope': float(entry.get('slope', _DEFAULT_SLOPE)),
                        'intercept': float(entry.get('intercept', 0.0))
                    }
    except Exception:
        pass


def save_calibration():
    try:
        with open(CALIB_FILE, 'w') as f:
            json.dump(_calibration, f)
    except Exception as e:
        print("Failed to save calibration:", e)


def reset_calibration():
    global _calibration
    _calibration = {
        'fixed':      {'slope': _DEFAULT_SLOPE, 'intercept': 0.0},
        'adjustable': {'slope': _DEFAULT_SLOPE, 'intercept': 0.0}
    }
    try:
        os.remove(CALIB_FILE)
    except OSError:
        pass


def shutdown_pico():
    print("Shutting down... Goodbye!")
    fan_pwm.duty_u16(0)
    time.sleep_ms(100)
    kill_pin.value(1)


def set_wiper(pot, value):
    if pot not in (0, 1):
        raise ValueError("Pot must be 0 or 1.")
    if not 0 <= value <= 255:
        raise ValueError("Value must be between 0 and 255.")
    raw_value = 255 - value if pot == 0 else value
    cmd = 0x11 if pot == 0 else 0x12
    cs.value(0)
    spi.write(bytes((cmd, raw_value)))
    cs.value(1)


def _read_raw_count(channel):
    if channel == 'fixed':
        return fixed_measure.read_u16()
    if channel == 'adjustable':
        return adjustable_measure.read_u16()
    raise ValueError("Invalid channel. Use 'fixed' or 'adjustable'.")


def read_voltage(channel):
    count = _read_raw_count(channel)
    cal = _calibration.get(channel, {})
    return cal['slope'] * count + cal['intercept']


def calibrate_channel(channel, pot):
    print(f"\n-- Calibrating '{channel}' channel (pot {pot}) --")
    set_wiper(pot, 0)
    print("Waiting for voltage to settle at wiper=0", end="")
    prev = _read_raw_count(channel)
    start = time.time()
    while True:
        time.sleep(1)
        curr = _read_raw_count(channel)
        elapsed = int(time.time() - start)
        print(f" [{elapsed}s: {curr}]", end="")
        if abs(curr - prev) <= 2:
            break
        prev = curr
    print(" done")
    raw0 = curr
    print(f"Settled raw count at wiper=0: {raw0}")
    v0 = float(input("Measured voltage at wiper=0 (V): "))
    set_wiper(pot, 255)
    print("Waiting for voltage to settle at wiper=255", end="")
    prev = _read_raw_count(channel)
    start = time.time()
    while True:
        time.sleep(1)
        curr = _read_raw_count(channel)
        elapsed = int(time.time() - start)
        print(f" [{elapsed}s: {curr}]", end="")
        if abs(curr - prev) <= 2:
            break
        prev = curr
    print(" done")
    raw1 = curr
    print(f"Settled raw count at wiper=255: {raw1}")
    v1 = float(input("Measured voltage at wiper=255 (V): "))
    if raw1 < raw0:
        raw0, raw1 = raw1, raw0
        v0, v1 = v1, v0
    if raw1 == raw0:
        raise ValueError("Calibration error: identical raw counts after sorting.")
    slope = (v1 - v0) / (raw1 - raw0)
    intercept = v0 - slope * raw0
    _calibration[channel] = {'slope': slope, 'intercept': intercept}
    save_calibration()
    print(f"Saved calibration: slope={slope:.9f}, intercept={intercept:.6f}\n")


def calibrate_all():
    calibrate_channel('adjustable', 0)
    calibrate_channel('fixed', 1)


def get_raw_count(channel):
    return _read_raw_count(channel)


def get_calibration(channel):
    cal = _calibration.get(channel, {})
    return cal.get('slope'), cal.get('intercept')

load_calibration()