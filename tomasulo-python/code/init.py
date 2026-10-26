# Qing 
# 21st May 2017 

from collections import namedtuple
import struct

'''define data types'''
# reservation station 
def rs_entry():
    rs_entry = namedtuple('rs_entry', 'busy, op, tag_1st, value_1st, valid_1st, tag_2nd, value_2nd, valid_2nd, dest_tag')
    temp = rs_entry
    return temp 
# functional unit 
def fu_entry():
    fu_entry = namedtuple('fu_entry', 'cycle, op, value1, value2, dest_tag')
    temp = fu_entry
    return temp
# function result 
def fu_result():
    fu_result = namedtuple('fu_result', 'value, dest_tag')
    temp = fu_result
    return temp
# ld/sd entry
def ld_sd_entry():
    ld_sd_entry = namedtuple('ld_sd_entry', 'ld_sd_tag, ready, op, address, data, dest_tag, immediate, reg_tag, reg_value, valid')
    temp = ld_sd_entry
    return temp
# ld/sd exe
def ld_sd_exe():
    ld_sd_exe = namedtuple('ld_sd_exe', 'busy, cycle, value1, value2, dest_tag')
    temp = ld_sd_exe
    return temp
# ld/sd mem
def ld_sd_mem():
    ld_sd_mem = namedtuple('ld_sd_mem', 'busy, cycle, op, data, address, dest_tag')
    temp = ld_sd_mem
    return temp
# cdb
def cdb():
    cdb = namedtuple('cdb', 'valid, value, dest_tag')
    temp = cdb
    return temp
# ROB_entry 
def ROB_entry():
    ROB_entry = namedtuple('ROB_entry', 'ROB_tag, PC, value, dest_tag, issue, exe, mem, cdb, commit')
    temp = ROB_entry
    temp.issue = []
    temp.exe = []
    temp.mem = []
    temp.cdb = []
    temp.commit =[]
    return temp
# PC 
def PC():
    PC = namedtuple('PC', 'PC, valid')
    temp = PC
    return temp
# function: read instructions
def read_instruction(codefile):
    with open(codefile) as f:
            instructions = f.read().splitlines()
    return instructions
# function: build rs
def build_rs(num):
    rs = []
    for _ in range(num):
        temp = rs_entry()
        temp.busy = 0
        rs.extend([temp])
    return rs


# function: round a value to single precision (memory holds 32-bit floats)
def to_single(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]

# function: read the input file in the format of the assignment:
# unit table, ROB entries, issue width, initial registers and memory, instructions.
# Instructions are returned as 'Op A B C' (commas removed, standard case), the
# format the rest of the code expects.
def read_input(path):
    config = {'Integer adder': [2, 1, 1], 'FP adder': [3, 3, 1], 'FP multiplier': [2, 20, 1],
              'Load/store unit': [3, 1, 4, 1], 'ROB entries': 128, 'Issue width': 1}
    ops = {'ld': 'Ld', 'sd': 'Sd', 'add': 'Add', 'addi': 'Addi', 'sub': 'Sub', 'add.d': 'Add.d',
           'sub.d': 'Sub.d', 'mult.d': 'Mult.d', 'bne': 'Bne', 'beq': 'Beq'}
    regs = {}
    memory = {}
    instructions = []
    with open(path) as f:
        lines = f.read().splitlines()
    for line in lines:
        line = line.strip()
        lower = line.lower()
        if (line == '') | line.startswith('#'):
            continue
        unit = [name for name in config if lower.startswith(name.lower())]
        if len(unit) > 0:
            numbers = [int(x) for x in line[len(unit[0]):].replace('=', ' ').split()]
            if unit[0] in ('ROB entries', 'Issue width'):
                config[unit[0]] = numbers[0]
            else:
                config[unit[0]][:len(numbers)] = numbers
        elif lower.startswith('mem['):
            for item in line.split(','):
                address, value = item.split('=')
                memory[int(address.strip()[4:-1])] = to_single(float(value))
        elif ('=' in line) & (lower[0] in 'rf'):
            for item in line.split(','):
                name, value = item.split('=')
                name = name.strip().upper()
                regs[name] = int(value) if name[0] == 'R' else float(value)
        else:
            tokens = line.replace(',', ' ').split()
            if tokens[0].lower() not in ops:
                raise ValueError('unknown instruction: ' + line)
            instructions.append(' '.join([ops[tokens[0].lower()]] + [t.upper() for t in tokens[1:]]))
    if not 1 <= config['Issue width'] <= 4:
        raise ValueError('issue width must be between 1 and 4')
    return config, regs, memory, instructions
