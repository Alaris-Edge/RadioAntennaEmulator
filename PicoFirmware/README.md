# Pico Control System

**## Overview & Objectives**

This firmware runs on a Raspberry Pi Pico W 2 and serves as the brain for a custom control PCB designed for the SBA1327BS‑DP FEM (active) antenna module. It provides:

* **Full CLI interface** over USB‑UART (and optional Bluetooth/Wi‑Fi) so operators can send commands in real time to the on‑antenna CPLD.
* **Voltage rail management** for the dual supplies on the control board: a fixed 3.3 V rail and an adjustable rail up to 9 V, both under closed‑loop regulation via digital potentiometers. Note that the PCB allows the "fixed" rail to be adjusted from about 1.7 to 5.8 V, but it is not reccomended to adjust this voltage, as the SBA1327BS-DP-FEM will be damaged when powered with a voltage other than 3.3 V. The control boards have been calibrated by COJOT prior to delivery, and updating the firmware will not overwrite the factory calibration.
* **Antenna mode control** via a 48‑bit shift register chain driving the CPLD: azimuth/elevation steering, FEM mode selection, test port routing, power‑enable flags, and sensor‑channel multiplexing.
* **LED status reporting** and debug logging to give immediate visual feedback on voltages, FEM mode, system state, and calibration progress.
* **Non‑volatile calibration storage** for retention of voltage‑rail and ADC calibration data.

**Supply Input & Thermal Considerations:**
The control PCB accepts a single 12 V input via banana plugs (reverse‑polarity protected). Onboard linear regulators generate a fixed 3.3 V rail and an adjustable rail (up to 9 V). Because linear regulation dissipates the voltage drop as heat, we recommend limiting the input-to-output differential to approximately 2 V when operating at high current for extended periods. Under heavy load, both the PCB and its aluminum mounting plate can become very hot—use caution and allow adequate cooling before handling.

---

**## System Architecture & Interfaces**

### D50 Connector Pinout

```
Pin 1   : SS_04
Pin 2   : SS_02
Pin 3   : SS_01
Pin 4   : AT_02
Pin 5   : AT_01
Pin 6   : DGND*
Pin 7   : DGND*
Pin 8   : ANT_SENSE_OUT
Pin 9   : AZ_23
Pin 10  : AZ_21
Pin 11  : AZ_20
Pin 12  : AZ_18
Pin 13  : DGND
Pin 14  : AZ_16
Pin 15  : AZ_15
Pin 16  : AZ_13
Pin 17  : AZ_12
Pin 18  : SS_03
Pin 19  : IF_I2C1_SDA
Pin 20  : SS_00
Pin 21  : FM_03
Pin 22  : AT_00
Pin 23  : FM_00
Pin 24  : DGND*
Pin 25  : EL_00
Pin 26  : AZ_22
Pin 27  : AZ_09
Pin 28  : AZ_19
Pin 29  : AZ_06
Pin 30  : AZ_17
Pin 31  : AZ_04
Pin 32  : AZ_14
Pin 33  : AZ_01
Pin 34  : ANT_8P0V_EN
Pin 35  : ANT_3P3V_EN
Pin 36  : IF_I2C1_SCL
Pin 37  : DGND*
Pin 38  : FM_02
Pin 39  : FM_01
Pin 40  : DGND*
Pin 41  : EL_01
Pin 42  : AZ_11
Pin 43  : AZ_10
Pin 44  : AZ_08
Pin 45  : AZ_07
Pin 46  : DGND*
Pin 47  : AZ_05
Pin 48  : AZ_03
Pin 49  : AZ_02
Pin 50  : AZ_00
```

* Digital ground pins may be tied together on board.

### 1. Configuration (`config.py`)

* Defines pin assignments (LEDs, ADCs, SPI/I²C, shift‑register control, fan PWM).
* Filter constants, heat‑map thresholds, default voltage setpoints.

### 2. Voltage Control (`voltage_control.py`)

* ADC readings, calibration via `voltage_calibration.json`.
* Two‑point linear calibration with JSON persistence.
* **Default rails:** fixed = 3.3 V, adjustable = 5 V (adjustable can be set up to 9 V).

**Tested Load Conditions:**

* 3.3 V @ 6 A → 19.8 W

* 5 V @ 10 A → 50 W

* 8 V @ 15 A → 120 W

* 9 V @ 14 A → 126 W (beyond 14 A, the voltage decreases even when set to 9 V)

* API:

  * `set_voltage_target(channel, target, filtered_voltages, target_voltages)`
  * `voltage_control_step(...)`

### 3. LED Control (`led_control.py`)

* Drives 4 LEDs through shift register.
* Supports auto/manual per‑LED.

**LED0 (Adjustable‑Rail Heat‑Map):**

* Voltage < 3.2 V  → off
* 3.2 – 3.5 V → blue
* 3.5 – 4.5 V → cyan
* 4.5 – 5.5 V → green
* 5.5 – 6.5 V → yellow
* 6.5 – 7.5 V → red
* 7.5 – 8.5 V → magenta
* 8.5 V → white

**LED1 (FEM Mode Indicator):**

* FM bits 000 → off
* 001 → blue
* 010 → cyan
* 011 → green
* 100 → yellow
* 101 → red
* 110 → magenta
* 111 → white

**LED2 (Future Sensor/Temperature):**

* Reserved (not yet implemented)

**LED3 (System Status):**

* Flashes green → normal control mode
* Flashes blue → calibration in progress
* Solid red → Pico powered down

### 4. Antenna & CPLD Interface (`antenna_mode.py`)

Antenna & CPLD Interface (`antenna_mode.py`)

* Explicit **stage→pin** mapping: 48 shift‑register stages → D50 connector pins.
* `STAGE_TO_PIN` built by reversing and rotating the board’s pin list.
* **Functional blocks** with sorted stage lists:

  * AZ (24 bits)
  * EL (2 bits)
  * FM (4 bits)
  * AT (3 bits)
  * PE (2 bits)
  * SS (5 bits)
* Helpers:

  * `convert_to_bits(data)` → 48‑bit LSB‑first list.
  * `build_cpld_pattern(AZ=…,EL=…,FM=…,AT=…,PE_val=…,SS=…)` overlays only specified bits.
  * `update_shift_registers(bits)` shifts LSB‑first and latches.
  * `read_shift_registers()` returns raw LSB‑first bits.
  * `read_az()`, `read_el()`, … `read_ss()`, `read_command()` for decoded feedback.
  * `map_shift_stages()` utility to manually map stage→pin with ENTER prompts.

### 5. I²C EEPROM (`i2c.py`) I²C EEPROM (`i2c.py`)

* **Future**: board also provides an I²C interface to an EEPROM on the antenna module itself (for storing antenna‑specific configuration and calibration). Firmware hooks will be added and tested in a later release to support remote EEPROM access over the same I²C bus.

### 6. Main Application & CLI (`main.py`)

* Three loops:

  * Voltage control (\~100 Hz)
  * LED update (4 Hz)
  * Heartbeat LED (1 Hz)
* CLI commands for all subsystems, with detailed usage and exception tracebacks.

---

**## CLI Command Reference**
Each CLI command follows the pattern:

```
> command_name [parameters]
```

Parameters may be specified in hexadecimal (`0x`), binary (`0b`), or decimal.

* `help`

  * **Params:** none
  * **Action:** Display help text and CLI usage summary.

* `shutdown`

  * **Params:** none
  * **Action:** Exit the CLI and halt the firmware loop.
    Voltage rails and outputs hold at their last values until restart.
    To restart: cycle board power or press the blue reset button on the PCB;
    CPLD outputs remain latched, and voltage rails reset to defaults (3.3 V fixed, 5 V adjustable).

* `debug`

  * **Params:** none
  * **Action:** Toggle debug logging on/off.
    When enabled, internal build steps and error tracebacks print to the console.

* `setres <pot> <v>`

  * **Params:**

    * `pot`: 0 (adjustable) or 1 (fixed)
    * `v`: integer 0–255
  * **Action:** Directly set the digital potentiometer wiper. Disables automatic regulation
    for the specified pot.

* `setvolt <ch> <V>`

  * **Params:**

    * `ch`: `fixed` or `adjustable`
    * `V`: target voltage in volts (float)
  * **Action:** Update the voltage target for channel `<ch>` and re-enable auto control.

* `readvolt [ch]`

  * **Params:** optional channel (`fixed`/`adjustable`)
  * **Action:** Read and display current and target voltages. If `[ch]` omitted, shows both.

* `calibrate <ch>`

  * **Params:** `fixed`, `adjustable`, or `all`
  * **Action:** Perform two-point calibration on specified channel(s). Saves data to EEPROM.

* `resetcal`

  * **Params:** none
  * **Action:** Reset stored calibration data to factory defaults.

* `cpld_write <d>`

  * **Params:** raw 48-bit pattern (hex/bin/int or list)
  * **Action:** Write the specified bit pattern directly to the CPLD shift registers,
    overriding all functional block settings.

* `setaz <v>`

  * **Params:** `<v>` = 0x0–0xFFFFFF (hex) or decimal (0–16777215)
  * **Action:** Set the 24-bit azimuth block (AZ\_00 to AZ\_23).
  * **Example:** `> setaz 0x00123456`

* `setel <v>`

  * **Params:** `<v>` = 0x0–0x3 (hex) or decimal (0–3)
  * **Action:** Set the 2-bit elevation block (EL\_00 to EL\_01).
  * **Example:** `> setel 0x3`

* `setfm <v>`

  * **Params:** `<v>` = 0x0–0xF (hex) or decimal (0–15)
  * **Action:** Set the 4-bit FEM mode block (FM\_00 to FM\_03).
  * **Example:** `> setfm 0xA`

* `setat <v>`

  * **Params:** `<v>` = 0x0–0x7 (hex) or decimal (0–7)
  * **Action:** Set the 3-bit antenna test block (AT\_00 to AT\_02).
  * **Example:** `> setat 0x4`

* `setpe <v>`

  * **Params:** `<v>` = 0x0–0x3 (hex) or decimal (0–3)
  * **Action:** Set the 2-bit power enable block (PE\_8P0V\_EN, PE\_3P3V\_EN).
  * **Example:** `> setpe 0x1`

* `setss <v>`

  * **Params:** `<v>` = 0x0–0x1F (hex) or decimal (0–31)
  * **Action:** Set the 5-bit sensor select block (SS\_00 to SS\_04).
  * **Example:** `> setss 0x10`

* `readcpld`

  * **Params:** none
  * **Action:** Read and display the full 48-bit CPLD pattern in MSB-first order.

* `readaz`

  * **Params:** none
  * **Action:** Read and display the current azimuth value (0–2^24–1).

* `readel`

  * **Params:** none
  * **Action:** Read and display the current elevation value (0–3).

* `readfm`

  * **Params:** none
  * **Action:** Read and display the current FEM mode (0–15).

* `readat`

  * **Params:** none
  * **Action:** Read and display the current antenna test bits (0–7).

* `readpe`

  * **Params:** none
  * **Action:** Read and display the current power enable flags (0–3).

* `readss`

  * **Params:** none
  * **Action:** Read and display the current sensor select value (0–31).

* `readcommand`

  * **Params:** none
  * **Action:** Read and display all functional blocks together.

### CLI Usage Examples

Below are some sample CLI sessions. User input is prefixed with `>` and system responses follow.

**1. Reading and setting voltages**

```
> readvolt
fixed: 3.300 V (target 3.300 V)
adjustable: 5.000 V (target 5.000 V)
> setvolt adjustable 6.5
adjustable target set to 6.500 V
> readvolt adjustable
adjustable: 6.500 V (target 6.500 V)
```

**2. Toggling debug mode**

```
> debug
Debug on
> setaz 0x1
[DEBUG build] initial bits LSB-first: [ ... ]
[DEBUG build] applying AZ=1, stages=[0,1,3,...]
[DEBUG build] bits after AZ: [1,0,0,...]
Azimuth set to 0x1 (1)
> debug
Debug off
```

**3. Configuring antenna/CPLD fields**

```
> cpld_write 0x0
CPLD updated
> setaz 0x03
Azimuth set to 0x3 (3)
> setel 0x2
Elevation set to 2
> setfm 0x5
FEM mode set to 5
> setpe 0x2
Power enable set to 2
> setss 0x1
Sensor select set to 1
> readcommand
CPLD full: 0x00080000000F 00000000100000000000000000001111
AZ: 0x000003 000000000000000000000011
EL: 0x2 10
FM: 0x5 0101
AT: 0x0 000
PE: 0x2 10
SS: 0x1 00001
```

**4. Reading raw CPLD bits**

```
> readcpld
CPLD full: 0x00080000000F 00000000100000000000000000001111
```
---

End of README.
