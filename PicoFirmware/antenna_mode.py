"""
antenna_mode.py

Controls the 48-bit shift registers for antenna modes via a 50-pin connector,
reads antenna sense and mode inputs, and manages fan speed.

Refactored to explicit stage-to-pin mapping and correct hardware read/write.
"""
import time
try:
    import __main__ as _main
except ImportError:
    _main = None
from config import SR_SER, SR_SRCLK, SR_RCLK, SR_OE, SR_OUT, antenna_sense, mode_pins, fan_pwm

# --- Stage-to-pin and signal mapping ---
# --- Stage-to-pin mapping (fixed via reverse+rotate) ---
_raw = [
    3,34,35,18,1,2,37,20,38,21,4,39,22,5,23,6,8,40,24,7,
    41,25,42,9,26,43,10,27,11,44,28,12,45,29,13,46,30,14,47,15,
    31,48,16,32,49,17,33,50
]
_raw = [
    3,34,35,18,1,2,37,20,38,21,4,39,22,5,23,6,40,24,7,
    41,25,42,9,26,43,10,27,11,44,28,12,45,29,13,46,30,14,47,15,
    31,48,16,32,49,17,33,50,
    8# SENSOR OUTPUT IS HERE BECAUSE THIS PIN IS NOT ROUTED TO THE SHIFT REGISTERS
]

# reverse list so stage47->first element, stage0->last, then rotate right by one to align
rev = _raw[::-1]
STAGE_TO_PIN = rev
# STAGE_TO_PIN = [rev[-1]] + rev[:-1]  # now index 0 is stage0 pin, index 1 stage1 pin, etc.


# This is the orgiginal mapping as I expected it, but during testing some of the signals seem swapped in the shift register
# The error is probably a mistake in the order in which things are enumerated, not in the hardware
PIN_TO_SIGNAL = {
    1:'SS_04',2:'SS_02',3:'SS_01',4:'AT_02',5:'AT_01',6:'DGND',7:'DGND',8:'SENS_OUT',
    9:'AZ_23',10:'AZ_21',11:'AZ_20',12:'AZ_18',13:'DGND',14:'AZ_16',15:'AZ_15',16:'AZ_13',
    17:'AZ_12',18:'SS_03',19:'IF_I2C1_SDA',20:'SS_00',21:'FM_03',22:'AT_00',23:'FM_00',
   24:'DGND',25:'EL_00',26:'AZ_22',27:'AZ_09',28:'AZ_19',29:'AZ_06',30:'AZ_17',31:'AZ_04',
   32:'AZ_14',33:'AZ_01',34:'PE_8P0V_EN',35:'PE_3P3V_EN',36:'IF_I2C1_SCL',37:'DGND',
   38:'FM_02',39:'FM_01',40:'DGND',41:'EL_01',42:'AZ_11',43:'AZ_10',44:'AZ_08',45:'AZ_07',
   46:'DGND',47:'AZ_05',48:'AZ_03',49:'AZ_02',50:'AZ_00'
}

# correct the swapped bits
# PIN_TO_SIGNAL[21] = 'FM_02'
# PIN_TO_SIGNAL[38] = 'FM_01'

# PIN_TO_SIGNAL[5] = 'AT_00'
# PIN_TO_SIGNAL[22] = 'AT_01'

# PIN_TO_SIGNAL[2] = 'SS_01'
# PIN_TO_SIGNAL[1] = 'SS_02'
# PIN_TO_SIGNAL[3] = 'SS_04'

STAGE_TO_SIGNAL = [PIN_TO_SIGNAL[p] for p in STAGE_TO_PIN]
# print(STAGE_TO_SIGNAL)
# --- Block stage lists ---
# Build AZ stage list sorted by azimuth bit number (AZ_00 ... AZ_23)
AZ_STAGES = sorted(
    (i for i,s in enumerate(STAGE_TO_SIGNAL) if s.startswith('AZ_')),
    key=lambda st: int(STAGE_TO_SIGNAL[st].split('_')[1])
)  # now AZ_STAGES[n] is stage for AZ_n
# Build EL stage list sorted by elevation bit number (EL_00 ... EL_01)
EL_STAGES = sorted(
    (i for i,s in enumerate(STAGE_TO_SIGNAL) if s.startswith('EL_')),
    key=lambda st: int(STAGE_TO_SIGNAL[st].split('_')[1])
)
# Build FM stage list sorted by FEM mode bit number (FM_00 ... FM_03)
FM_STAGES = sorted(
    (i for i,s in enumerate(STAGE_TO_SIGNAL) if s.startswith('FM_')),
    key=lambda st: int(STAGE_TO_SIGNAL[st].split('_')[1])
)
# Build AT stage list sorted by antenna-test bit number (AT_00 ... AT_02)
AT_STAGES = sorted(
    (i for i,s in enumerate(STAGE_TO_SIGNAL) if s.startswith('AT_')),
    key=lambda st: int(STAGE_TO_SIGNAL[st].split('_')[1])
)
# Build PE stage list sorted by power-enable signal name (PE_3P3V_EN, PE_8P0V_EN)
PE_STAGES = sorted(
    (i for i,s in enumerate(STAGE_TO_SIGNAL) if s.startswith('PE_')),
    key=lambda st: STAGE_TO_SIGNAL[st]
)
# Build SS stage list sorted by sensor-select bit number (SS_00 ... SS_04)
SS_STAGES = sorted(
    (i for i,s in enumerate(STAGE_TO_SIGNAL) if s.startswith('SS_')),
    key=lambda st: int(STAGE_TO_SIGNAL[st].split('_')[1])
)
# SENS_STAGE = STAGE_TO_SIGNAL.index('SENS_OUT')
# print(EL_STAGES)
# print(FM_STAGES)
# print(AT_STAGES)
# print(PE_STAGES)
# print(SS_STAGES)

# --- Bit conversion (LSB-first) ---
def convert_to_bits(data):
    # Allow direct 48-bit list/tuple patterns
    if isinstance(data, (list, tuple)):
        if len(data) != 48 or any(bit not in (0,1) for bit in data):
            raise ValueError("List input must be 48 elements of 0 or 1.")
        return list(data)
    # Integer input: produce LSB-first bits

    if isinstance(data, int):
        val = data & ((1<<48)-1)
        return [(val>>i)&1 for i in range(48)]
    if isinstance(data, str):
        s = data.strip().lower()
        if s.startswith('0x'):
            hp = s[2:]
            if len(hp)<12: hp = '0'*(12-len(hp))+hp
            val = int(hp,16)
            return [(val>>i)&1 for i in range(48)]
        if all(c in '01' for c in s):
            bp = s[-48:]
            if len(bp)<48: bp = '0'*(48-len(bp))+bp
            return [int(c) for c in bp[::-1]]
    raise ValueError('Data must be int or hex/bin string')

# --- Low-level I/O ---
def update_shift_registers(data):
    bits = convert_to_bits(data)
    if _main and getattr(_main,'debug_enabled',False): print(f"[DEBUG] write bits LSB-first: {bits}")
    SR_OE.value(0); SR_RCLK.value(0)
    for b in bits:
        SR_SER.value(b); time.sleep_us(1)
        SR_SRCLK.value(1); time.sleep_us(1); SR_SRCLK.value(0)
    SR_RCLK.value(1); time.sleep_us(1); SR_RCLK.value(0)

def read_shift_registers():
    SR_RCLK.value(1); time.sleep_us(1); SR_RCLK.value(0); time.sleep_us(1)
    bits=[]
    for _ in range(48):
        bits.append(SR_OUT.value())
        SR_SRCLK.value(1); time.sleep_us(1); SR_SRCLK.value(0); time.sleep_us(1)
    # restore
    SR_OE.value(0); SR_RCLK.value(0)
    for b in bits:
        SR_SER.value(b); time.sleep_us(1)
        SR_SRCLK.value(1); time.sleep_us(1); SR_SRCLK.value(0)
    SR_RCLK.value(1); time.sleep_us(1); SR_RCLK.value(0)
    return bits  # LSB-first list

# --- Pattern builder ---
def build_cpld_pattern(AZ=None,EL=None,FM=None,AT=None,PE_val=None,SS=None):
    """Overlay provided block values onto current hardware state."""
    # 1) Snapshot hardware bits
    pat = read_shift_registers()
    if _main and getattr(_main,'debug_enabled',False):
        print(f"[DEBUG build] initial bits LSB-first: {pat}")
    # 2) Apply AZ
    if AZ is not None:
        if _main and getattr(_main,'debug_enabled',False):
            print(f"[DEBUG build] applying AZ={AZ}, stages={AZ_STAGES}")
        for bn,st in enumerate(AZ_STAGES): pat[st] = (AZ>>bn)&1
        if _main and getattr(_main,'debug_enabled',False):
            print(f"[DEBUG build] bits after AZ: {pat}")
    # 3) Apply EL
    if EL is not None:
        if _main and getattr(_main,'debug_enabled',False):
            print(f"[DEBUG build] applying EL={EL}, stages={EL_STAGES}")
        for bn,st in enumerate(EL_STAGES): pat[st] = (EL>>bn)&1
        if _main and getattr(_main,'debug_enabled',False):
            print(f"[DEBUG build] bits after EL: {pat}")
    # 4) Apply FM
    if FM is not None:
        if _main and getattr(_main,'debug_enabled',False):
            print(f"[DEBUG build] applying FM={FM}, stages={FM_STAGES}")
        for bn,st in enumerate(FM_STAGES): pat[st] = (FM>>bn)&1
        if _main and getattr(_main,'debug_enabled',False):
            print(f"[DEBUG build] bits after FM: {pat}")
    # 5) Apply AT
    if AT is not None:
        if _main and getattr(_main,'debug_enabled',False):
            print(f"[DEBUG build] applying AT={AT}, stages={AT_STAGES}")
        for bn,st in enumerate(AT_STAGES): pat[st] = (AT>>bn)&1
        if _main and getattr(_main,'debug_enabled',False):
            print(f"[DEBUG build] bits after AT: {pat}")
    # 6) Apply SS
    if SS is not None:
        if _main and getattr(_main,'debug_enabled',False):
            print(f"[DEBUG build] applying SS={SS}, stages={SS_STAGES}")
        for bn,st in enumerate(SS_STAGES): pat[st] = (SS>>bn)&1
        if _main and getattr(_main,'debug_enabled',False):
            print(f"[DEBUG build] bits after SS: {pat}")
    # 7) Apply PE
    if PE_val is not None:
        if _main and getattr(_main,'debug_enabled',False):
            print(f"[DEBUG build] applying PE_val={PE_val}, stages={PE_STAGES}")
        for i,st in enumerate(PE_STAGES): pat[st] = (PE_val>>i)&1
        if _main and getattr(_main,'debug_enabled',False):
            print(f"[DEBUG build] bits after PE: {pat}")
    return pat

# --- Read helpers ---
def read_az(): return sum(read_shift_registers()[st]<<i for i,st in enumerate(AZ_STAGES))
def read_el(): return sum(read_shift_registers()[st]<<i for i,st in enumerate(EL_STAGES))
def read_fm(): return sum(read_shift_registers()[st]<<i for i,st in enumerate(FM_STAGES))
def read_at(): return sum(read_shift_registers()[st]<<i for i,st in enumerate(AT_STAGES))
def read_pe(): return sum(read_shift_registers()[st]<<i for i,st in enumerate(PE_STAGES))
def read_ss(): return sum(read_shift_registers()[st]<<i for i,st in enumerate(SS_STAGES))

def read_sense(): return antenna_sense.read_u16()
# def read_mode(): bits=[pin.value() for pin in mode_pins]; return (bits[0]<<3)|(bits[1]<<2)|(bits[2]<<1)|bits[3]
def read_mode(): bits=[pin.value() for pin in mode_pins]; return (bits[0]<<2)|(bits[1]<<1)|bits[2]
def set_fan_speed(p):
    if p<0 or p>100: raise ValueError
    fan_pwm.duty_u16(0 if p<20 else int(p/100*65535))

def read_command():
    bits = read_shift_registers()  # LSB-first list
    # display MSB-first
    bits_msb = list(reversed(bits))
    val = int(''.join(str(b) for b in bits_msb), 2)
    print(f"CPLD full: 0x{val:X} {''.join(str(b) for b in bits_msb)}")
    print(f"AZ: 0x{read_az():06X} {read_az():024b}")
    print(f"EL: 0x{read_el():X} {read_el():02b}")
    print(f"FM: 0x{read_fm():X} {read_fm():04b}")
    print(f"AT: 0x{read_at():X} {read_at():03b}")
    pe=read_pe(); print(f"PE: 0x{pe:X} {pe:02b}")
    print(f"SS: 0x{read_ss():X} {read_ss():05b}")

__all__=[
    'convert_to_bits','update_shift_registers','read_shift_registers',
    'build_cpld_pattern','read_az','read_el','read_fm','read_at','read_pe','read_ss',
    'read_sense','read_mode','set_fan_speed','read_command',
    'AZ_STAGES','EL_STAGES','FM_STAGES','AT_STAGES','PE_STAGES','SS_STAGES'
]
