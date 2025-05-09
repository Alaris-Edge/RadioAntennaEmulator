"""
main.py

Entry point: startup sequence, CLI command listener, periodic LED and voltage control loops,
manual and automatic control for potentiometers, LEDs, and CPLD functional blocks,
and onboard LED toggle.
"""

import _thread
import time
from machine import Pin

from config import *
from antenna_mode import (
    update_shift_registers,
    read_shift_registers,
    read_az,
    read_el,
    read_fm,
    read_at,
    read_pe,
    read_ss,
    read_mode,
    read_command,
    read_sense,
    set_fan_speed,
    build_cpld_pattern,
    AZ_STAGES, EL_STAGES, FM_STAGES, AT_STAGES, PE_STAGES, SS_STAGES
)
from led_control import update_leds
from voltage_control import (
    read_voltage,
    shutdown_pico,
    set_wiper,
    set_voltage_target,
    voltage_control_step,
    calibrate_channel,
    calibrate_all,
    get_raw_count,
    get_calibration,
    reset_calibration,
)

onboard_led = Pin(25, Pin.OUT)
onboard_led.value(0)

commands = {}
debug_enabled = False

help_text = """
General:
  help                     Show this help message
  shutdown                 Shutdown the Pico (LED, voltage, CPLD states remain as-is after power-down)

Voltage Control and Potentiometer:
  setres <pot> <value>     Set wiper; pot 0=adjustable,1=fixed
  setvolt <ch> <V>         Set voltage target; ch='fixed' or 'adjustable'
  readvolt [ch]            Read current and target voltage; optional channel

Calibration:
  calibrate <ch>           Calibrate channel; 'fixed', 'adjustable', or 'all'
  calibrate_all            Calibrate both channels
  resetcal                 Reset calibration to defaults

Debug:
  debugvolt [ch]           Show raw count, calibration, and voltage
  debug                    Toggle debug messages on/off

CPLD Interface (Antenna Blocks):
  setaz <value>            Set 24-bit azimuth pattern (hex, bin, or int)
  setel <value>            Set 2-bit elevation (0-3)
  setfm <value>            Set 4-bit FEM mode (0-15)
  setat <value>            Set 3-bit antenna test (0-7)
  setpe <value>            Set 2-bit power enable (0-3)
  setss <value>            Set 5-bit sensor select (0-31)
  cpld_write <data>        Write raw 48-bit pattern (list, hex, bin, or int)

Status Queries:
  readcpld                 Read full CPLD shift-register state
  readaz                   Read 24-bit azimuth value
  readel                   Read 2-bit elevation value
  readfm                   Read 4-bit FEM mode value
  readat                   Read 3-bit antenna test value
  readpe                   Read 2-bit power enable value
  readss                   Read 5-bit sensor select value
  readcommand              Report all block values sequentially

LED Control:
  setled <idx> <rgb>       Set LED idx (0-3) with contiguous RGB bits (e.g. 010)
  setled <idx> auto        Re-enable automatic update for LED idx
"""

target_voltages = DEFAULT_TARGET_VOLTAGES.copy()
current_wipers = {'fixed': 255, 'adjustable': 255}
filtered_voltages = {ch: 0.0 for ch in target_voltages}
calibrating = False
auto_control = {ch: True for ch in target_voltages}
auto_update_led = {i: True for i in range(4)}

# Command handlers
def command_help():
    print(help_text.lstrip())

def command_shutdown():
    leds[3] = [1, 0, 0] # Set red LED
    mode = read_mode()
    update_leds(filtered_voltages, mode, auto_update_led, debug = debug_enabled)
    shutdown_pico()

def command_setres(pot, value):
    try:
        key = pot.lower() if pot.isalpha() else ('fixed' if int(pot) == 1 else 'adjustable')
        p = 1 if key == 'fixed' else 0
        v = int(value)
        set_wiper(p, v)
        current_wipers[key] = v
        auto_control[key] = False
        print(f"Pot {p} ({key}) set to {v}")
    except Exception as e:
        print(f"Error in setres: {e}")
        try:
            import sys; sys.print_exception(e)
        except:
            pass
        print("Usage: setres <pot> <value>")
        print("Usage: setres <pot> <value>")

def command_setvolt(ch, voltage):
    try:
        ch = ch.lower()
        if ch not in target_voltages:
            raise ValueError(f"Unknown channel '{ch}'")
        t = float(voltage)
        set_voltage_target(ch, t, filtered_voltages, target_voltages)
        auto_control[ch] = True
        print(f"{ch} target set to {t:.3f} V")
    except Exception as e:
        print(f"Error in setvolt: {e}")
        try:
            import sys; sys.print_exception(e)
        except:
            pass
        print("Usage: setvolt <fixed|adjustable> <voltage>")
        print("Usage: setvolt <fixed|adjustable> <voltage>")

def command_readvolt(*args):
    for ch in (args or target_voltages.keys()):
        if ch not in target_voltages:
            print(f"Unknown channel '{ch}'")
        else:
            v = read_voltage(ch)
            tgt = target_voltages[ch]
            print(f"{ch} voltage: {v:.3f} V (target {tgt:.2f} V)")

def command_calibrate(ch):
    global calibrating
    if ch == 'all':
        return command_calibrate_all()
    if ch not in target_voltages:
        print("Usage: calibrate <fixed|adjustable|all>")
        return
    calibrating = True
    calibrate_channel(ch, 0 if ch == 'adjustable' else 1)
    calibrating = False

def command_calibrate_all():
    global calibrating
    calibrating = True
    calibrate_all()
    calibrating = False

def command_resetcal():
    reset_calibration()
    print("Calibration reset to defaults.")

def command_debugvolt(*args):
    for ch in (args or target_voltages.keys()):
        if ch not in target_voltages:
            print(f"Unknown channel '{ch}'")
            continue
        raw = get_raw_count(ch)
        sl, ic = get_calibration(ch)
        v = read_voltage(ch)
        print(f"{ch} raw={raw}, slope={sl:.9f}, intcpt={ic:.6f}, volts={v:.3f}")

def command_debug():
    global debug_enabled
    debug_enabled = not debug_enabled
    print(f"Debug {'on' if debug_enabled else 'off'}.")

def command_cpld_write(data):
    try:
        pat = update_shift_registers(data)
        print("CPLD updated")
    except Exception as e:
        print(f"Error: {e}")

def command_setaz(value):
    try:
        az = int(value, 0)
        # preserve current EL, FM, AT, PE, SS when updating AZ
        current_el = read_el()
        current_fm = read_fm()
        current_at = read_at()
        pe_dict = read_pe()
        current_ss = read_ss()
        pat = build_cpld_pattern(AZ=az, EL=current_el, FM=current_fm, AT=current_at, PE_val=pe_dict, SS=current_ss)
        update_shift_registers(pat)
        print(f"Azimuth set to 0x{az:X} ({az})")
    except Exception as e:
        print(f"Error in setaz: {e}")
        try:
            import sys
            sys.print_exception(e)
        except:
            pass
        print("Usage: setaz <hex|bin|int>")

def command_setel(value):
    try:
        el = int(value, 0)
        if not 0 <= el < 4: raise ValueError("Elevation must be 0-3")
        current_az = read_az(); current_fm = read_fm(); current_at = read_at(); pe_dict = read_pe(); current_ss = read_ss()
        pat = build_cpld_pattern(AZ=current_az, EL=el, FM=current_fm, AT=current_at, PE_val=pe_dict, SS=current_ss)
        update_shift_registers(pat)
        print(f"Elevation set to {el}")
    except Exception as e:
        print(f"Error in setel: {e}")
        try:
            import sys; sys.print_exception(e)
        except:
            pass
        print("Usage: setel <0-3>")

def command_setfm(value):
    try:
        fm = int(value, 0)
        if not 0 <= fm < 16: raise ValueError("FEM mode must be 0-15")
        current_az = read_az(); current_el = read_el(); current_at = read_at(); pe_dict = read_pe(); current_ss = read_ss()
        pat = build_cpld_pattern(AZ=current_az, EL=current_el, FM=fm, AT=current_at, PE_val=pe_dict, SS=current_ss)
        update_shift_registers(pat)
        print(f"FEM mode set to {fm}")
    except Exception as e:
        print(f"Error in setfm: {e}")
        try:
            import sys; sys.print_exception(e)
        except:
            pass
        print("Usage: setfm <0-15>")

def command_setat(value):
    try:
        at = int(value, 0)
        if not 0 <= at < 8: raise ValueError("Antenna test must be 0-7")
        current_az = read_az(); current_el = read_el(); current_fm = read_fm(); pe_dict = read_pe(); current_ss = read_ss()
        pat = build_cpld_pattern(AZ=current_az, EL=current_el, FM=current_fm, AT=at, PE_val=pe_dict, SS=current_ss)
        update_shift_registers(pat)
        print(f"Antenna test set to {at}")
    except Exception as e:
        print(f"Error in setat: {e}")
        try:
            import sys; sys.print_exception(e)
        except:
            pass
        print("Usage: setat <0-7>")

def command_setpe(value):
    try:
        pe = int(value, 0)
        if not 0 <= pe < 4: raise ValueError("Power enable must be 0-3")
        # preserve other fields
        current_az = read_az()
        current_el = read_el()
        current_fm = read_fm()
        current_at = read_at()
        current_ss = read_ss()
        # pass integer pe to builder
        pat = build_cpld_pattern(AZ=current_az, EL=current_el, FM=current_fm, AT=current_at, PE_val=pe, SS=current_ss)
        update_shift_registers(pat)
        print(f"Power enable set to {pe}")
    except Exception as e:
        print(f"Error in setpe: {e}")
        try:
            import sys; sys.print_exception(e)
        except:
            pass
        print("Usage: setpe <0-3>")

def command_setss(value):
    try:
        ss = int(value, 0)
        if not 0 <= ss < 32: raise ValueError("Sensor select must be 0-31")
        current_az = read_az(); current_el = read_el(); current_fm = read_fm(); current_at = read_at(); pe_dict = read_pe()
        pat = build_cpld_pattern(AZ=current_az, EL=current_el, FM=current_fm, AT=current_at, PE_val=pe_dict, SS=ss)
        update_shift_registers(pat)
        print(f"Sensor select set to {ss}")
    except Exception as e:
        print(f"Error in setss: {e}")
        try:
            import sys; sys.print_exception(e)
        except:
            pass
        print("Usage: setss <0-31>")

def command_setled(idx, mode):
    try:
        i = int(idx)
        if i not in auto_update_led: raise ValueError
        if mode == 'auto':
            auto_update_led[i] = True
            print(f"LED {i} auto-update enabled")
            return
        if len(mode) == 3 and all(c in '01' for c in mode):
            leds[i] = [int(c) for c in mode]
            auto_update_led[i] = False
            print(f"LED {i} set to {mode}")
            return
        raise ValueError
    except Exception:
        print("Usage: setled <0-3> <rgb>|auto")

def command_readcpld():
    try:
        pat = read_shift_registers()
        bits = ''.join(str(b) for b in pat)
        val = int(bits, 2)
        print(f"CPLD full: 0x{val:X} {bits}")
    except Exception as e:
        print(f"Error: {e}")

def command_readaz():
    try:
        az = read_az()
        print(f"AZ: 0x{az:06X} {az:024b}")
    except Exception as e:
        print(f"Error: {e}")

def command_readel():
    try:
        el = read_el()
        print(f"EL: 0x{el:X} {el:02b}")
    except Exception as e:
        print(f"Error: {e}")

def command_readfm():
    try:
        fm = read_fm()
        print(f"FM: 0x{fm:X} {fm:04b}")
    except Exception as e:
        print(f"Error: {e}")

def command_readat():
    try:
        at = read_at()
        print(f"AT: 0x{at:X} {at:03b}")
    except Exception as e:
        print(f"Error: {e}")

def command_readpe():
    try:
        pe = read_pe()
        # pe is integer
        print(f"PE: 0x{pe:X} {pe:02b}")
    except Exception as e:
        print(f"Error: {e}")

def command_readss():
    try:
        ss = read_ss()
        print(f"SS: 0x{ss:X} {ss:05b}")
    except Exception as e:
        print(f"Error: {e}")

def command_readcommand():
    """
    Read and display all CPLD block values via antenna_mode.read_command().
    """
    try:
        read_command()
    except Exception as e:
        print(f"Error reading command: {e}")

def _register_commands():
    commands.clear()
    commands.update({
        'help': command_help,
        'shutdown': command_shutdown,
        'setres': command_setres,
        'setvolt': command_setvolt,
        'readvolt': command_readvolt,
        'calibrate': command_calibrate,
        'calibrate_all': command_calibrate_all,
        'resetcal': command_resetcal,
        'debugvolt': command_debugvolt,
        'debug': command_debug,
        'cpld_write': command_cpld_write,
        'setaz': command_setaz,
        'setel': command_setel,
        'setfm': command_setfm,
        'setat': command_setat,
        'setpe': command_setpe,
        'setss': command_setss,
        'setled': command_setled,
        'readcpld': command_readcpld,
        'readaz': command_readaz,
        'readel': command_readel,
        'readfm': command_readfm,
        'readat': command_readat,
        'readpe': command_readpe,
        'readss': command_readss,
        'readcommand': command_readcommand,
    })

def command_listener():
    while True:
        try:
            inp = input(">").strip().split()
        except (EOFError, KeyboardInterrupt):
            print("Exiting command listener.")
            break
        if not inp:
            continue
        cmd, *args = inp
        if cmd in commands:
            try:
                commands[cmd](*args)
            except TypeError as te:
                print(f"Invalid arguments for '{cmd}': {te}")
            except Exception as e:
                print(f"Error executing '{cmd}': {e}")
        else:
            print(f"Unknown command '{cmd}'. Type 'help'.")

def led_loop():
    while True:
        try:
            update_leds(filtered_voltages, read_mode(), auto_update_led, debug_enabled)
        except Exception as e:
            print(f"Error in LED loop: {e}")
        time.sleep(0.25)

def voltage_loop():
    while True:
        try:
            voltage_control_step(filtered_voltages, target_voltages, current_wipers, debug_enabled, calibrating)
        except Exception as e:
            print(f"Error in voltage loop: {e}")
        time.sleep(0.01)

def onboard_loop():
    while True:
        onboard_led.value(not onboard_led.value())
        time.sleep(1)

def startup():
    print("System started. Type 'help'.")
    try:
        filtered_voltages['fixed'] = read_voltage('fixed')
        filtered_voltages['adjustable'] = read_voltage('adjustable')
    except:
        pass

# Main loop
def main():
    leds[3] = [0, 1, 0]
    _register_commands()
    _thread.start_new_thread(command_listener, ())
    
    print("System started. Type 'help'.")
    time.sleep_ms(250)

    filtered_voltages['fixed'] = read_voltage('fixed')
    filtered_voltages['adjustable'] = read_voltage('adjustable')
    set_wiper(0, current_wipers['adjustable'])
    set_wiper(1, current_wipers['fixed'])

    time.sleep_ms(250)
    set_wiper(0, current_wipers['adjustable'])
    set_wiper(1, current_wipers['fixed'])

    mode = read_mode()

    LED_INTERVAL_MS = 250
    VOLT_INTERVAL_MS = 10
    TOGGLE_INTERVAL_MS = 1000
    last_led = last_volt = last_toggle = time.ticks_ms()
    while True:
        now = time.ticks_ms()
        
        # Onboard LED toggle every second
        if time.ticks_diff(now, last_toggle) >= TOGGLE_INTERVAL_MS:
            onboard_led.value(not onboard_led.value())
            # Onboard LED not working, let's use one of the other ones
            if not calibrating: 
                leds[3] = [0, not(leds[3][1]), 0] # Toggle blue LED
            else:
                leds[3] = [0, 0, not(leds[3][2])] # Toggle green LED
            update_leds(filtered_voltages, mode, auto_update_led, debug = debug_enabled)
            last_toggle = now


        # LED update at 4 Hz
        if time.ticks_diff(now, last_led) >= LED_INTERVAL_MS:
            try:
                if debug_enabled:
                    print("DEBUG: Reading antenna mode.")
                mode = read_mode()
                if debug_enabled:
                    print("DEBUG: Updating LEDs.")
                update_leds(filtered_voltages, mode, auto_update_led, debug = debug_enabled)
            except Exception as e:
                print(f"Error in LED loop: {e}")
            last_led = now

        # Voltage control at ~100 Hz
        # This block runs most often. I have moved it here so as not to bblock the slower periodic functions
        if time.ticks_diff(now, last_volt) >= VOLT_INTERVAL_MS:
            try:
                voltage_control_step(filtered_voltages, target_voltages, current_wipers, debug_enabled, calibrating, auto_control)
            except Exception as e:
                print(f"Error in voltage loop: {e}")
            last_volt = now
        time.sleep(0)

if __name__ == '__main__':
    main()
