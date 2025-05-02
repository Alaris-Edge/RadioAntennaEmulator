from config import *
import time

def update_shift_registers(data):
    """
    Shifts 48 bits into the registers and reads back 48 bits.
    
    Args:
        data (list of int): A list of 48 values (0 or 1).
        
    Returns:
        list of int: The bits read from the shift register output.
    """
    if len(data) != 48:
        raise ValueError("Data must be a list of 48 bits (0 or 1).")
    
    read_data = []
    
    # Disable outputs if needed (assuming active low, so 0 enables outputs)
    SR_OE.value(0)
    
    # Shift out 48 bits: 
    # For each bit, set SER then pulse the SR_CLK
    for bit in data:
        SR_SER.value(bit)
        # Give the data a moment to settle
        time.sleep_us(1)
        SR_SRCLK.value(1)
        time.sleep_us(1)
        SR_SRCLK.value(0)
    
    # Latch the data into the output registers
    SR_RCLK.value(1)
    time.sleep_us(1)
    SR_RCLK.value(0)
    
    # Now, read back 48 bits from SR_OUT
    # Here we pulse the shift clock and read the bit at each pulse.
    for i in range(48):
        SR_SRCLK.value(1)
        time.sleep_us(1)
        bit = SR_OUT.value()
        read_data.append(bit)
        SR_SRCLK.value(0)
        time.sleep_us(1)

def set_wiper(pot, value):
    """
    Writes 'value' (0–255) to the MCP42010's selected pot.
    pot=0 -> Pot0, pot=1 -> Pot1
    """
    # Choose command byte based on pot selection
    if pot == 0:
        command = 0x11  # Write to Pot0
    elif pot == 1:
        command = 0x12  # Write to Pot1
    else:
        raise ValueError("Pot number must be 0 or 1")

    # Start SPI transaction
    cs.value(0)
    spi.write(bytearray([command, value]))
    cs.value(1)
    

def read_sense():
    print(f"Antenna Sense: {antenna_sense.read_u16()}")

def read_mode():
    """
    Reads the mode from GPIO pins 2, 3, 4, and 5 and returns it as a 4-bit integer.
    The order is: Pin2 (MSB), Pin3, Pin4, Pin5 (LSB).
    """
    print(f"Current Mode: {mode_pin0.value()}{mode_pin1.value()}{mode_pin2.value()}{mode_pin3.value()}")
    
def set_fan_speed(percentage):
    """
    Sets the PWM fan speed.
    percentage: An integer between 0 (off) and 100 (full speed).
    If the percentage is below 20, the fan is turned off.
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
