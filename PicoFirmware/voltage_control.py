"""
voltage_control.py

Handles ADC readings for fixed and adjustable voltage rails, shutdown, wiper control,
calibration routines with settling polls, persistent storage, and debug accessors.
"""

import time
import ujson as json
import os

from config import kill_pin, fan_pwm, fixed_measure, adjustable_measure, cs, spi, FILTER_ALPHA

CALIB_FILE = 'voltage_calibration.json'

# ADC constants and nominal divider
_ADC_MAX = 65535
_VREF = 3.3
_NOMINAL_DIVIDER = 3.7
_DEFAULT_SLOPE = (_VREF * _NOMINAL_DIVIDER) / _ADC_MAX

# Calibration store: slope and intercept per channel
_calibration = {
    'fixed':      {'slope': _DEFAULT_SLOPE, 'intercept': 0.0},
    'adjustable': {'slope': _DEFAULT_SLOPE, 'intercept': 0.0},
}


def load_calibration():
    global _calibration
    try:
        with open(CALIB_FILE, 'r') as f:
            data = json.load(f)
            for ch in ('fixed', 'adjustable'):
                entry = data.get(ch)
                if isinstance(entry, dict):
                    _calibration[ch]['slope'] = float(entry.get('slope', _DEFAULT_SLOPE))
                    _calibration[ch]['intercept'] = float(entry.get('intercept', 0.0))
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
        'adjustable': {'slope': _DEFAULT_SLOPE, 'intercept': 0.0},
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
    raw_value = value
    # raw_value = 255 - value if pot == 0 else value
    cmd = 0x11 if pot == 0 else 0x12
    cs.value(0)
    spi.write(bytes((cmd, raw_value)))
    cs.value(1)


def _read_raw_count(channel):
    if channel == 'fixed':
        return fixed_measure.read_u16()
    elif channel == 'adjustable':
        return adjustable_measure.read_u16()
    else:
        raise ValueError("Invalid channel. Use 'fixed' or 'adjustable'.")


def read_voltage(channel):
    """Return calibrated voltage: slope*count + intercept."""
    if channel not in _calibration:
        raise ValueError(f"Invalid channel '{channel}'. Use 'fixed' or 'adjustable'.")
    count = _read_raw_count(channel)
    cal = _calibration[channel]
    return cal['slope'] * count + cal['intercept']


def calibrate_channel(channel, pot):
    print(f"\n-- Calibrating '{channel}' channel (pot {pot}) --")
    # Calibrate low end
    set_wiper(pot, 0)
    print("Waiting for voltage to settle at wiper=0", end="")
    prev = _read_raw_count(channel)
    while True:
        time.sleep(1)
        curr = _read_raw_count(channel)
        print(".", end="")
        if abs(curr - prev) <= 2:
            break
        prev = curr
    print(" done")
    raw_low = curr
    print(f"Settled raw count at wiper=0: {raw_low}")
    v_low = float(input("Measured voltage at wiper=0 (V): "))

    # Calibrate high end
    set_wiper(pot, 255)
    print("Waiting for voltage to settle at wiper=255", end="")
    prev = _read_raw_count(channel)
    while True:
        time.sleep(1)
        curr = _read_raw_count(channel)
        print(".", end="")
        if abs(curr - prev) <= 2:
            break
        prev = curr
    print(" done")
    raw_high = curr
    print(f"Settled raw count at wiper=255: {raw_high}")
    v_high = float(input("Measured voltage at wiper=255 (V): "))

    # Ensure ordering
    if raw_high < raw_low:
        raw_low, raw_high = raw_high, raw_low
        v_low, v_high = v_high, v_low
    if raw_high == raw_low:
        raise ValueError("Calibration error: identical raw counts.")

    slope = (v_high - v_low) / (raw_high - raw_low)
    intercept = v_low - slope * raw_low
    _calibration[channel]['slope'] = slope
    _calibration[channel]['intercept'] = intercept
    save_calibration()
    print(f"Saved calibration: slope={slope:.9f}, intercept={intercept:.6f}\n")


def calibrate_all():
    calibrate_channel('adjustable', 0)
    calibrate_channel('fixed', 1)


def get_raw_count(channel):
    return _read_raw_count(channel)


def get_calibration(channel):
    """Get (slope, intercept) tuple for a channel."""
    if channel not in _calibration:
        raise ValueError(f"Invalid channel '{channel}'. Use 'fixed' or 'adjustable'.")
    cal = _calibration[channel]
    return cal['slope'], cal['intercept']

# Load calibration on import
load_calibration()

# --- New high-level voltage control API ---

def set_voltage_target(channel, target, filtered_voltages, target_voltages):
    """Set a new target voltage and reset its filtered value."""
    if channel not in target_voltages:
        raise ValueError(f"Invalid channel '{channel}' for target.")
    target_voltages[channel] = target
    #filtered_voltages[channel] = target


def voltage_control_step(filtered_voltages, target_voltages, current_wipers, debug=False, calibrating=False):
    """Perform one iteration of the voltage control loop: adjust wipers toward targets."""
    # Skip automatic control during calibration
    if calibrating:
        return
    for ch, tgt in target_voltages.items():
        raw = read_voltage(ch)
        filtered_voltages[ch] = FILTER_ALPHA * raw + (1 - FILTER_ALPHA) * filtered_voltages[ch]
        current = filtered_voltages[ch]
        if debug:
            print(f"[VCTRL] {ch}: filtered={current:.3f}, target={tgt:.3f}, wiper={current_wipers[ch]}")
        diff = current - tgt
        if abs(diff) >= 0.009:
            step = 1 if diff > 0 else -1
            new_w = max(0, min(255, current_wipers[ch] + step))
            if new_w != current_wipers[ch]:
                current_wipers[ch] = new_w
                set_wiper(1 if ch == 'fixed' else 0, new_w)
                #time.sleep_ms(25)
