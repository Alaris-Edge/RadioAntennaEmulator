# Pico Control System

## Overview & Objectives

This software package controls a Raspberry Pi Pico-based hardware platform featuring:

* **Dual voltage rails** (fixed 3.3 V and adjustable up to 9 V) with closed-loop regulation via digital potentiometers.
* **4 status LEDs** driven through a shift register: one displays a heat-map of adjustable voltage, another shows antenna mode, and two are reserved for user-defined indicators.
* **48-bit CPLD interface** over a 50-pin connector, handling antenna array steering (azimuth/elevation), amplifier modes, test port routing, power enable, and sensor multiplexing.
* **Command-line and (future) Bluetooth CLI** for real-time user interaction.
* **I²C EEPROM** for data storage (e.g. calibration maps).

The goals are:

1. **Stable, responsive voltage control** with configurable smoothing and auto/manual override.
2. **Modular, maintainable code** separating config, hardware drivers, control loops, and user interface.
3. **Comprehensive CLI** for setup, monitoring, and dynamic operation of all subsystems.
4. **Clear documentation and logging** to facilitate troubleshooting and future enhancements.

---

## System Architecture & Interfaces

### 1. Configuration (`config.py`)

* Central hardware pin assignments: LEDs, ADC channels, digital potentiometer SPI, shift-register control pins, fan PWM, I²C pins.
* Constants for EMA filter, heat-map thresholds, and default target voltages.
* Provides `DEFAULT_TARGET_VOLTAGES` dict used to initialize control loops.

### 2. Voltage Control (`voltage_control.py`)

* Reads raw ADC counts for fixed and adjustable rails.
* Applies calibration (slope/intercept) loaded from `voltage_calibration.json`.
* Implements two-point calibration and JSON persistence.
* Offers a high-level API:

  * `set_voltage_target(channel, target, filtered_voltages, target_voltages)`
  * `voltage_control_step(filtered_voltages, target_voltages, current_wipers, debug=False, calibrating=False)`

### 3. LED Control (`led_control.py`)

* Manages 4 RGB LEDs via a serial-in, parallel-out shift register.
* LED0: heat-map of adjustable rail voltage.
* LED1: displays antenna mode.
* LED2–LED3: manual override with future auto-update placeholders.
* Supports per-LED auto/manual flags and optional debug logging.

### 4. Antenna & CPLD Interface (`antenna_mode.py`)

This module defines how 48 *software* bits map through the 50‑pin connector to physical signals, and groups them into functional blocks. In hardware, **7** of those outputs are wired directly to ground, and **1** carries the MUX’s sensor‑output. The remaining **40** bits implement your protocol:

* **D50 Connector Mapping:**

  * Software bits are shifted out in a fixed order (0–47). Each index → connector pin (1–50) via `D50_PINS`, then → signal name via `PIN_TO_SIGNAL`.
  * Of the 50 connector pins, 48 are driven by the shift register; 2 are unused.
  * **7 pins** (`DGND`) are grounded in hardware and always read/write `0`.
  * **1 pin** (`SENS_OUT`) feeds back the selected sensor from the SS multiplexer.

* **Functional Blocks (40 bits):**

  * **AZ** (24 bits): azimuth steering control.
  * **EL** (2 bits): elevation beam select.
  * **FM** (4 bits): amplifier (FEM) mode select.
  * **AT** (3 bits): antenna test port routing.
  * **PE** (2 bits): power enable for external supplies (8 V and 3.3 V).
  * **SS** (5 bits): selects which sensor channel appears on `SENS_OUT`.

* **Effective Command Word:** 40 active bits + 7 ground bits + 1 feedback bit = 48 total bits.

* **API Helpers:**

  * `build_cpld_pattern(AZ=…, EL=…, FM=…, AT=…, PE=…, SS=…)` updates only the specified block bits, preserving all others.
  * `update_shift_registers(bits)` writes the full 48‑bit pattern (including ground and unused bits) to the hardware.
  * `read_shift_registers()` reads back all 48 bits, including `SENS_OUT` on its dedicated bit index.

### 5. I²C EEPROM (`i2c.py`)

I²C EEPROM (`i2c.py`)

* Interfaces with a 24LC32AT via I²C for data storage.
* `data_write(start_address, data)`: page-write with ACK polling.
* `data_read(start_address, num_bytes)`: bounds-checked burst read.

### 6. Main Application & CLI (`main.py`)

* Starts three periodic loops in dedicated threads:

  * **Voltage loop** (\~100 Hz) handles ADC smoothing and wiper adjustments.
  * **LED loop** (4 Hz) updates status LEDs based on voltage, mode, and manual overrides.
  * **Onboard LED toggle** (1 Hz) provides a heartbeat indicator.
* Registers a robust CLI with commands for all subsystems.

## CLI Command Reference

Below is a detailed reference of all supported CLI commands, their behavior, and usage examples.

#### General Commands

* `help`

  * **What it does:** Lists all available commands with brief descriptions.
  * **Expected behavior:** Prints the help text.
  * **Example:**

    ```
    > help
    ```

* `shutdown`

  * **What it does:** Powers down the Pico; leaves LEDs, voltage, and CPLD outputs in their last state.
  * **Example:**

    ```
    > shutdown
    ```

#### Voltage Control & Potentiometer

* `setres <pot> <value>`

  * **What it does:** Manually sets the digital potentiometer wiper.
  * **Parameters:**

    * `<pot>`: `0` or `adjustable`, `1` or `fixed`.
    * `<value>`: integer 0–255.
  * **Expected behavior:** Updates wiper and prints confirmation. Disables automatic voltage control for that channel.
  * **Example:**

    ```
    > setres adjustable 128
    Pot 0 (adjustable) set to 128
    ```

* `setvolt <channel> <voltage>`

  * **What it does:** Sets the target voltage for the specified rail and re-enables automatic control.
  * **Parameters:**

    * `<channel>`: `fixed` or `adjustable`.
    * `<voltage>`: float in volts.
  * **Example:**

    ```
    > setvolt fixed 3.3
    fixed target set to 3.300 V
    ```

* `readvolt [channel]`

  * **What it does:** Reads and displays the current and target voltage.
  * **Parameters:**

    * Optional `[channel]`: `fixed` or `adjustable`.
  * **Example:**

    ```
    > readvolt
    fixed voltage: 3.300 V (target: 3.30 V)
    adjustable voltage: 5.000 V (target: 5.00 V)
    ```

#### Calibration Commands

* `calibrate <channel>`

  * **What it does:** Runs two-point calibration for the specified channel.
  * **Example:**

    ```
    > calibrate adjustable
    -- Calibrating 'adjustable' channel (pot 0) --
    ```

* `calibrate_all`

  * **What it does:** Calibrates both channels sequentially.
  * **Example:**

    ```
    > calibrate_all
    ```

* `resetcal`

  * **What it does:** Resets calibration data to defaults and deletes the JSON file.
  * **Example:**

    ```
    > resetcal
    Calibration reset to defaults.
    ```

* `debugvolt [channel]`

  * **What it does:** Shows raw ADC count, calibration slope/intercept, and voltage.
  * **Example:**

    ```
    > debugvolt adjustable
    adjustable raw_count=12345, slope=0.000184, intercept=0.000000, voltage=5.000 V
    ```

* `debug`

  * **What it does:** Toggles verbose debug messages for loops.
  * **Example:**

    ```
    > debug
    Debug messages enabled.
    ```

#### CPLD Interface Commands

* `cpld_write <data>`

  * **What it does:** Writes a full 48-bit pattern in binary (48 chars) or hex (`0x...`) to the CPLD.
  * **Example:**

    ```
    > cpld_write 0x123456789ABC
    CPLD interface updated.
    ```

* `setaz <value>`

  * **What it does:** Sets the 24-bit azimuth block; preserves other blocks.
  * **Parameters:** binary (24 bits) or hex/int.
  * **Example:**

    ```
    > setaz 0x00FFAA
    Azimuth set to 0xFFAA (65450)
    ```

* `setel <value>`

  * **What it does:** Sets the 2-bit elevation block.
  * **Example:**

    ```
    > setel 2
    Elevation set to 0x2 (10)
    ```

* `setfm <value>` / `setat <value>` / `setpe <value>` / `setss <value>`

  * Similar to `setaz`, but for FEM mode (4 bits), antenna test (3 bits), power enable (2 bits), and sensor select (5 bits), respectively.

* `setled <idx> <rgb|auto>`

  * **What it does:** Manually sets LED index (`0`–`3`) via a 3-bit RGB string (e.g. `010`), or re-enables auto-update with `auto`.
  * **Example:**

    ```
    > setled 2 101
    LED 2 set to [1,0,1]
    ```

#### Status Query Commands

* `readcpld`

  * **What it does:** Reads and prints the full 48-bit CPLD register in hex and binary.
  * **Example:**

    ```
    > readcpld
    CPLD full pattern: 0x123456789ABC 0001...1011
    ```

* `readaz` / `readel` / `readfm` / `readat` / `readpe` / `readss`

  * **What they do:** Read and report the current value of each functional block in hex and binary.
  * **Example:**

    ```
    > readaz
    AZ (24-bit): 0x00FFAA 0000000011111111101010
    ```

* `readcommand`

  * **What it does:** Runs all `read*` queries in sequence to display each block’s current value.
  * **Example:**

    ```
    > readcommand
    AZ: 0x00FFAA 0000000011111111101010
    EL: 0x2     10
    FM: 0x9     1001
    AT: 0x3     011
    PE: 0x1     01
    SS: 0x12    10010
    ```

For screenshots or further guidance, refer to the individual module docstrings and inline examples.
