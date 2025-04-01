from machine import Pin, PWM, ADC, I2C, SoftSPI
import time
import _thread

# --- Pin Setup ---

# Latching power trigger (kill pin)
kill_pin = Pin(22, Pin.OUT)
kill_pin.value(0)  # Pico stays powered on

# LED Shift Register Pins (for LED control)
LED_OE     = Pin(11, Pin.OUT)  # Output Enable (active low)
LED_RCK    = Pin(12, Pin.OUT)  # Latch (Reset Clock)
LED_SRCLR  = Pin(13, Pin.OUT)  # Shift Register Clear (normally held high)
LED_SRCK   = Pin(18, Pin.OUT)  # Shift Register Clock
LED_SER_IN = Pin(19, Pin.OUT)  # Serial Data In

# Set default states for LED shift register control pins
LED_OE.value(0)     # Enable outputs (active low)
LED_SRCLR.value(1)  # Normal operation (not clearing)
LED_RCK.value(0)

# Shift Register Pins for 50-pin connector (47 outputs via 6 shift registers)
SR_SER   = Pin(6, Pin.OUT)   # Shift Register Serial
SR_OE    = Pin(7, Pin.OUT)   # Shift Register Output Enable
SR_SRCLK = Pin(8, Pin.OUT)   # Shift Register Serial Clock
SR_RCLK  = Pin(9, Pin.OUT)   # Shift Register Reset Clock
SR_OUT   = Pin(10, Pin.IN)   # Shift Register Output

# --- Mode Pins Setup ---
mode_pin0 = Pin(2, Pin.IN)
mode_pin1 = Pin(3, Pin.IN)
mode_pin2 = Pin(4, Pin.IN)
mode_pin3 = Pin(5, Pin.IN)

# --- Fan PWM Setup ---
fan_pwm = PWM(Pin(21))
fan_pwm.freq(1000)      # Set frequency to 1kHz (adjust as needed)
fan_pwm.duty_u16(0)     # Fan PWM is off by default

# Analog Voltage Pins
fixed_measure = ADC(Pin(26))       # ADC for fixed 3.3V rail measurement
adjustable_measure = ADC(Pin(28))  # ADC for adjustable measurement
antenna_sense = ADC(Pin(27))       # ADC for the antenna sense measurement

# Digital Potentiometers (MCP42010) SPI Pins
# Pin definitions
SCK_PIN = 14   # GPIO 14
MOSI_PIN = 15  # GPIO 15
CS_PIN = 16    # GPIO 16

cs = Pin(CS_PIN, Pin.OUT)
    
# Set up SPI on the Pico
spi = machine.SPI(
    1,                  # Using SPI(1)
    baudrate=1_000_000, # 1 MHz (adjust as needed)
    polarity=0,         # Clock idle low
    phase=0,            # Data latched on rising edge
    sck=machine.Pin(SCK_PIN),
    mosi=machine.Pin(MOSI_PIN),
    miso=None           # We don't need MISO
)

# Define the 2D array for your 4 RGB LEDs.
# Each sub-array represents [R, G, B] for one LED.
leds = [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0]
]

# Original mapping order for the shift registers (47 outputs corresponding to physical pins)
original_mapping = [3, 34, 35, 18, 1, 2, 37, 20, 38, 21, 4, 39, 22, 5, 23, 6, 40, 24, 7, 41, 25, 42, 9, 26, 43, 10, 27, 11, 44, 28, 12, 45, 29, 13, 46, 30, 14, 47, 15, 31, 48, 16, 32, 49, 17, 33, 50]
# Note: Physical pins 8, 19, and 36 are not connected to this shift register.

# --- Functions ---

def shutdown_pico():
    print("Shutdown in 1000 ms – say goodbye to your Pico!")
    fan_pwm.duty_u16(0)
    time.sleep_ms(1000)
    kill_pin.value(1)

def update_leds():
    """Update the LED shift register with the current values from the 'leds' array."""
    LED_OE.value(0)
    LED_RCK.value(0)
    for led in leds:
        for bit in led:
            LED_SER_IN.value(bit)
            LED_SRCK.value(1)
            time.sleep_us(1)
            LED_SRCK.value(0)
            time.sleep_us(1)
    LED_RCK.value(1)
    time.sleep_us(1)
    LED_RCK.value(0)

def update_shift_register(data):
    """
    Update the 6 chained shift registers (controlling 47 outputs) with the provided data array.
    
    data: A list of 0s and 1s. It should contain 47 values.
    """
    SR_OE.value(0)
    SR_RCLK.value(0)
    for bit in data:
        SR_SER.value(bit)
        SR_SRCLK.value(1)
        time.sleep_us(1)
        SR_SRCLK.value(0)
        time.sleep_us(1)
    SR_RCLK.value(1)
    time.sleep_us(1)
    SR_RCLK.value(0)

def update_shift_register_mapped(user_data):
    """
    Update the shift registers using a user-provided array corresponding to physical pin numbers 1-50.
    
    user_data: A list of 50 values (0s and 1s) for physical pins 1-50.
    
    This function uses the inverse mapping so that the bit for physical pin 3 (first in the shift registers)
    is placed in the first position of the output array.
    
    Note: Physical pins 8, 19, and 36 are not connected to the shift register and are skipped.
    """
    if len(user_data) != 50:
        print("Error: user_data array must have 50 elements.")
        return
    inverse_mapping = [None] * 50
    for i, pin in enumerate(original_mapping):
        inverse_mapping[pin - 1] = i
    mapped_data = [0] * len(original_mapping)
    for p in range(1, 51):
        inv_index = inverse_mapping[p - 1]
        if inv_index is not None:
            mapped_data[inv_index] = user_data[p - 1]
    update_shift_register(mapped_data)

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
    
def read_voltage(channel):
    """
    Reads the voltage from the specified channel and returns the computed voltage.
    channel: 'fixed' for the fixed 3.3V rail measurement,
             'adjustable' for the adjustable measurement.
    """
    if channel == "fixed":
        val = fixed_measure.read_u16()
        voltage = (val / 65535) * 3.3 * 3.7 # Adjust value for accurate voltage read
        print("Fixed voltage: {:.2f} V".format(voltage))
        return voltage
    elif channel == "adjustable":
        val = adjustable_measure.read_u16()
        voltage = (val / 65535) * 3.3 * 3.7 # Adjust value for accurate voltage read
        print("Adjustable voltage: {:.2f} V".format(voltage))
        return voltage
    else:
        print("Invalid channel. Use 'fixed' or 'adjustable'.")
        return None

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

    
def command_listener():
    """Background thread to listen for commands."""
    while True:
        cmd = input("Enter command: ").strip().lower()
        if cmd == "shutdown":
            shutdown_pico()
            break
        elif cmd.startswith("setres"):
            # Expected command format: setres <channel> <value>
            try:
                parts = cmd.split()
                if len(parts) == 3:
                    channel = parts[1]
                    res_value = int(parts[2])
                    if channel == "adjustable":
                        channel_value = 0
                    if channel == "fixed":
                        channel_value = 1
                    set_wiper(channel_value, res_value)
                else:
                    print("Usage: setres <channel> <position> (channel: adjustable or fixed, value: 0-255)")
            except Exception as e:
                print("Error parsing command:", e)
        elif cmd.startswith("readvolt"):
            # Expected command format: readvolt <fixed|adjustable>
            parts = cmd.split()
            if len(parts) == 2:
                read_voltage(parts[1])
            else:
                print("Usage: readvolt <fixed|adjustable>")
        elif cmd.startswith("readmode"):
            read_mode()
        elif cmd.startswith("antenna"):
            read_sense()
        elif cmd.startswith("setfan"):
            # Expected command format: setfan <percentage>
            parts = cmd.split()
            if len(parts) == 2:
                try:
                    speed = int(parts[1])
                    set_fan_speed(speed)
                except Exception as e:
                    print("Invalid speed value:", e)
        else:
            print("Unknown command '{}'. Try 'shutdown', 'setres <channel> <value>', or 'readvolt <fixed|adjustable>'.".format(cmd))

def startup():
    """
    Startup routine:
    - Turn all LEDs on (white).
    - Read both analog voltage levels.
    - Convert ADC readings to the real voltage (ADC reading * (3.3/65535) * 5).
    - Print the voltages.
    - Turn all LEDs off.
    - Set the first LED to a color corresponding to the adjustable voltage level:
         RED for 3.3V, GREEN for 5V, BLUE for 8V, WHITE for 9V.
    """
    for i in range(len(leds)):
        leds[i] = [1, 1, 1]
    update_leds()
    time.sleep(1)
    fixed_voltage = read_voltage("fixed")
    adjustable_voltage = read_voltage("adjustable")
    
    # DM Chip Select pin
    cs.value(1)

    for i in range(len(leds)):
        leds[i] = [0, 0, 0]
    update_leds()
    time.sleep(0.5)
    color_options = [
        ([1, 0, 0], 3.3),  # Red
        ([0, 1, 0], 5.0),  # Green
        ([0, 0, 1], 8.0),  # Blue
        ([1, 1, 1], 9.0)   # White
    ]
    closest_color = min(color_options, key=lambda x: abs(adjustable_voltage - x[1]))[0]
    leds[0] = closest_color
    update_leds()

# --- Main Execution ---

startup()
_thread.start_new_thread(command_listener, ())

# Example usage: Update the 50-pin connector's shift register using a test pattern.
test_user_data = [1 if i % 2 == 0 else 0 for i in range(50)]
update_shift_register_mapped(test_user_data)

while True:
    time.sleep(1)


