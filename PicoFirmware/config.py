from machine import Pin, PWM, ADC, I2C, SoftSPI
import machine
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

read_data = []
    
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

adjustable_led_color_options = [
        ([1, 0, 0], 3.0),  # red
        ([1, 1, 0], 4.0),  # yellow
        ([0, 1, 0], 5.0),  # green
        ([0, 1, 1], 6.0),  # cyan
        ([0, 0, 1], 7.0),  # blue
        ([1, 0, 1], 8.0),  # magenta
        ([1, 1, 1], 9.0)   # white
    ]

# Original mapping order for the shift registers (47 outputs corresponding to physical pins)
original_mapping = [3, 34, 35, 18, 1, 2, 37, 20, 38, 21, 4, 39, 22, 5, 23, 6, 40, 24, 7, 41, 25, 42, 9, 26, 43, 10, 27, 11, 44, 28, 12, 45, 29, 13, 46, 30, 14, 47, 15, 31, 48, 16, 32, 49, 17, 33, 50]
# Note: Physical pins 8, 19, and 36 are not connected to this shift register.
