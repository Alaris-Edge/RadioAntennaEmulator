"""
config.py

Centralized hardware configuration and pin assignments for the Pico-based control system.
"""

from machine import Pin, PWM, ADC, SPI

# --- Power Control ---
kill_pin = Pin(22, Pin.OUT)
kill_pin.value(0)  # 0=latched, 1=shutdown

# Onboard LED
onboard_led = Pin("LED", Pin.OUT)

# --- LED Shift Register (status LEDs) ---
LED_OE     = Pin(11, Pin.OUT)  # Output Enable (active LOW)
LED_RCK    = Pin(12, Pin.OUT)  # Latch
LED_SRCLR  = Pin(13, Pin.OUT)  # Clear (active HIGH)
LED_SRCK   = Pin(18, Pin.OUT)  # Shift Clock
LED_SER_IN = Pin(19, Pin.OUT)  # Serial Data
LED_OE.value(0)
LED_SRCLR.value(1)
LED_RCK.value(0)

# Storage for LED RGB states: 4 LEDs, each [R, G, B]
leds = [[0, 0, 0] for _ in range(4)]

# --- Large Shift Registers (48 channels) ---
SR_SER   = Pin(6,  Pin.OUT)
SR_OE    = Pin(7,  Pin.OUT)
SR_SRCLK = Pin(8,  Pin.OUT)
SR_RCLK  = Pin(9,  Pin.OUT)
SR_OUT   = Pin(10, Pin.IN)

# EMA smoothing factor for voltage readings (0 < alpha < 1)
FILTER_ALPHA = 0.9

# Mode select inputs (3-bit)
mode_pins = [Pin(n, Pin.IN) for n in (2, 3, 4, 5)]

# Fan control (PWM)
fan_pwm = PWM(Pin(21))
fan_pwm.freq(1000)
fan_pwm.duty_u16(0)

# ADC measurements
fixed_measure      = ADC(Pin(26))  # Fixed 3.3V rail
antenna_sense      = ADC(Pin(27))  # Antenna sense
adjustable_measure = ADC(Pin(28))  # Adjustable rail

# Digital potentiometer (MCP42010) via SPI
SCK_PIN  = 14
MOSI_PIN = 15
CS_PIN   = 16
cs       = Pin(CS_PIN, Pin.OUT)
spi = SPI(
    1,
    baudrate=1_000_000,
    polarity=0,
    phase=0,
    sck=Pin(SCK_PIN),
    mosi=Pin(MOSI_PIN),
    miso=None
)

# Default voltage targets for rails
DEFAULT_TARGET_VOLTAGES = {'fixed': 3.3, 'adjustable': 5.0}
