from config import SR_SER, SR_SRCLK, SR_RCLK, SR_OE, SR_OUT, antenna_sense, mode_pins, fan_pwm
import time

def update_shift_registers(data):
    if len(data) != 48:
        raise ValueError("Data must be a list of 48 bits (0 or 1).")
    read_data = []
    SR_OE.value(0)
    for bit in data:
        SR_SER.value(bit)
        time.sleep_us(1)
        SR_SRCLK.value(1)
        time.sleep_us(1)
        SR_SRCLK.value(0)
    SR_RCLK.value(1)
    time.sleep_us(1)
    SR_RCLK.value(0)
    for _ in range(48):
        SR_SRCLK.value(1)
        time.sleep_us(1)
        read_data.append(SR_OUT.value())
        SR_SRCLK.value(0)
        time.sleep_us(1)
    return read_data

def read_sense():
    value = antenna_sense.read_u16()
    print(f"Antenna Sense: {value}")
    return value

def read_mode():
    bits = [pin.value() for pin in mode_pins]
    mode = (bits[0] << 3) | (bits[1] << 2) | (bits[2] << 1) | bits[3]
    print(f"Current Mode bits: {bits[0]}{bits[1]}{bits[2]}{bits[3]}, Mode value: {mode}")
    return mode

def set_fan_speed(percentage):
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
