"""
config.py

Centralized hardware configuration and pin assignments for the Pico-based control system.
"""

# Standard library imports
import time
import _thread

# MicroPython hardware imports
from machine import Pin, PWM, ADC, SPI

# --- Power Control ---
# Latching power trigger (kill pin) keeps Pico powered until explicitly shut down.
kill_pin = Pin(22, Pin.OUT)
kill_pin.value(0)  # 0 = keep power latched, 1 = release and shut down

# --- LED Shift Register (for status LEDs) ---
# Pins for LED shift register control
LED_OE     = Pin(11, Pin.OUT)  # Output Enable (active LOW)
LED_RCK    = Pin(12, Pin.OUT)  # Latch/RCLK
LED_SRCLR  = Pin(13, Pin.OUT)  # Shift Register Clear (active HIGH for normal)
LED_SRCK   = Pin(18, Pin.OUT)  # Serial Clock
LED_SER_IN = Pin(19, Pin.OUT)  # Serial Data In

# Initialize LED shift register control pins
LED_OE.value(0)     # Enable outputs
LED_SRCLR.value(1)  # Disable clear (normal operation)
LED_RCK.value(0)

# Storage for LED RGB states: list of [R, G, B] for each LED
leds = [[0, 0, 0] for _ in range(4)]

# Predefined color thresholds for adjustable voltage LED
# Format: ([R, G, B], voltage_threshold)
adjustable_led_color_options = [
    ([1, 0, 0], 3.0),    # Red at 3.0V
    ([1, 1, 0], 4.0),    # Yellow at 4.0V
    ([0, 1, 0], 5.0),    # Green at 5.0V
    ([0, 1, 1], 6.0),    # Cyan at 6.0V
    ([0, 0, 1], 7.0),    # Blue at 7.0V
    ([1, 0, 1], 8.0),    # Magenta at 8.0V
    ([1, 1, 1], 9.0),    # White at 9.0V
]

# --- Large Shift Registers (50-pin connector) ---
# 47 outputs across 6 chained shift registers
SR_SER   = Pin(6,  Pin.OUT)  # Data input
SR_OE    = Pin(7,  Pin.OUT)  # Output enable
SR_SRCLK = Pin(8,  Pin.OUT)  # Shift clock
SR_RCLK  = Pin(9,  Pin.OUT)  # Latch clock
SR_OUT   = Pin(10, Pin.IN)   # Serial output (for readback)

# Default mode pins (4-bit mode selector)
mode_pins = [Pin(n, Pin.IN) for n in (2, 3, 4, 5)]

# Original mapping order for shift-register outputs to physical pins
original_mapping = [
    3, 34, 35, 18, 1, 2, 37, 20,
    38, 21, 4, 39, 22, 5, 23, 6,
    40, 24, 7, 41, 25, 42, 9, 26,
    43, 10, 27, 11, 44, 28, 12, 45,
    29, 13, 46, 30, 14, 47, 15, 31,
    48, 16, 32, 49, 17, 33, 50
]

# --- Fan Control (PWM) ---
fan_pwm = PWM(Pin(21))
fan_pwm.freq(1000)      # 1 kHz PWM frequency
fan_pwm.duty_u16(0)     # Fan off by default

# --- Analog-to-Digital Converters ---
# ADC channels for voltage measurements
fixed_measure      = ADC(Pin(26))  # Fixed 3.3V rail
antenna_sense      = ADC(Pin(27))  # Antenna sense input
adjustable_measure = ADC(Pin(28))  # Adjustable rail measurement

# --- Digital Potentiometer (MCP42010 via SPI) ---
# SPI configuration for digital pots on PORTE
SCK_PIN  = 14
MOSI_PIN = 15
CS_PIN   = 16

cs = Pin(CS_PIN, Pin.OUT)
spi = SPI(
    1,                    # SPI channel 1
    baudrate=1_000_000,   # 1 MHz
    polarity=0,           # Clock idle low
    phase=0,              # Data valid on rising edge
    sck=Pin(SCK_PIN),
    mosi=Pin(MOSI_PIN),
    miso=None             # No MISO needed
)
