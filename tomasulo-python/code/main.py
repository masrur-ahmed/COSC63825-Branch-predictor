# Qing 
# 21st May 2017 

import sys
from copy import deepcopy
from collections import deque, namedtuple
from init import read_instruction, build_rs, ld_sd_entry, ld_sd_exe, ld_sd_mem, cdb, ROB_entry, PC, read_input
from print_status import ps, pss, print_registers, print_memory
from issue import issue, check_rs_space
from exe import exe, recover
from mem import mem
from wb import wb 
from commit import commit
'''initialize'''
# read the configuration, initial values and instructions from the input file
# usage: python3 main.py [input file] [issue width]
input_file = sys.argv[1] if len(sys.argv) > 1 else 'test_case.txt'
config, init_regs, init_memory, instructions = read_input(input_file)
issue_width = int(sys.argv[2]) if len(sys.argv) > 2 else config['Issue width']
if not 1 <= issue_width <= 4:
    sys.exit('issue width must be between 1 and 4')
'''initialize regs, RAT, memory''' 
# integer REG
reg_int = []
for i in range(32):
    reg_int.extend([0])
# fp REG
reg_fp = []
for i in range(32):
    reg_fp.extend([0])
for name in init_regs:
    if (name[0] == 'R') & (name != 'R0'):
        reg_int[int(name[1:])] = init_regs[name]
    elif name[0] == 'F':
        reg_fp[int(name[1:])] = init_regs[name]
rat_int = deepcopy(reg_int)
rat_fp = deepcopy(reg_fp)
# memory 
memory = []
for i in range(256):
    memory.extend([0])
for address in init_memory:
    memory[address] = init_memory[address]
'''intialize reservation stations'''
# config row: # of rs, cycles in EX, (cycles in Mem,) # of FUs
size_rs_int_adder = config['Integer adder'][0]
rs_int_adder = build_rs(size_rs_int_adder)
size_rs_fp_adder = config['FP adder'][0]
rs_fp_adder = build_rs(size_rs_fp_adder)
size_rs_fp_multi = config['FP multiplier'][0]
rs_fp_multi = build_rs(size_rs_fp_multi)
'''initilize function unit'''
fu_int_adder = deque()
time_fu_int_adder = config['Integer adder'][1]
fu_fp_adder = deque()
time_fu_fp_adder = config['FP adder'][1]
fu_fp_multi = deque()
time_fu_fp_multi = config['FP multiplier'][1]
num_fu = [config['Integer adder'][2], config['FP adder'][2], config['FP multiplier'][2]]
'''initialize load/store queue'''
ld_sd_queue = deque()
size_ld_sd_queue = config['Load/store unit'][0]
ld_sd_exe = ld_sd_exe()
ld_sd_exe.busy = 0
time_ld_sd_exe = config['Load/store unit'][1]
ld_sd_mem = ld_sd_mem()
ld_sd_mem.busy = 0
time_ld_sd_mem = config['Load/store unit'][2]
'''initialize ROB'''
ROB = deque()
size_ROB = config['ROB entries']
committed = []
'''initialize CDB'''
results_buffer = deque()
cdb = cdb()
cdb.valid = 0
"""issue first instruction"""
# instruction pointer 
PC = PC()
PC.PC = 0
PC.valid = 1 
# branch prediction: 8-entry BTB with a 1-bit predictor, and misprediction recovery
PC.btb = [None] * 8
PC.mispredict = ''
PC.redirect = 0
PC.resume = 0
cycle = 1

# print title 
item = ''.ljust(30)
item += 'ISSUE'.ljust(15)
item += 'EXE'.ljust(15)
item += 'MEM'.ljust(15)
item += 'WB'.ljust(15)
item += 'COMMIT'.ljust(15)
print (item)

# main: run until the ROB is empty, there is nothing left to issue,
# and the last store has finished writing memory
while (len(ROB)>0)|((PC.PC>=0)&(PC.PC<len(instructions)))|(ld_sd_mem.busy==1):
    if cycle > 100000:
        sys.exit('program did not finish within 100000 cycles')
    
    '''ISSUE stage'''
    if (PC.PC<len(instructions))&(PC.valid==1):
        issue(cycle, PC, instructions, ROB, size_ROB, 
                rs_int_adder, 
                rs_fp_adder, 
                rs_fp_multi, 
                ld_sd_queue, size_ld_sd_queue, 
                rat_int, rat_fp, issue_width)

    '''EXE stage'''
    exe(fu_int_adder, time_fu_int_adder, 
        fu_fp_adder, time_fu_fp_adder, 
        fu_fp_multi, time_fu_fp_multi, results_buffer,  
        rs_int_adder, rs_fp_adder, rs_fp_multi, 
        ld_sd_exe, time_ld_sd_exe, ld_sd_queue,
        cycle, ROB, PC, num_fu)
    # a branch was mispredicted at the end of EX: squash the younger instructions
    if PC.mispredict != '':
        recover(PC, ROB, rat_int, rat_fp, reg_int, reg_fp,
                rs_int_adder, rs_fp_adder, rs_fp_multi,
                fu_int_adder, fu_fp_adder, fu_fp_multi,
                ld_sd_queue, ld_sd_exe, ld_sd_mem, results_buffer, cdb, cycle)

    '''MEM stage'''
    mem(ld_sd_queue, ld_sd_mem, time_ld_sd_mem, results_buffer,
        memory, ROB, cycle)

    '''CDB stage'''
    wb(cdb, rat_int, rat_fp, 
        rs_int_adder, rs_fp_adder, rs_fp_multi,
        ld_sd_queue, ROB, cycle,
        results_buffer) 
    
    '''COMMIT stage'''
    commit(ROB, reg_int, reg_fp, cycle, instructions, issue_width, committed)
    
    # cycle number 
    cycle +=1

# results
print('')
print_registers(reg_int, reg_fp)
print('')
print_memory(memory)
print('')
# total cycles: the last commit or the end of the last memory write, whichever is later
total_cycles = cycle - 1
for entry in committed:
    total_cycles = max([total_cycles] + entry.commit + entry.mem)
print('Issue width: %d   Total cycles: %d   Instructions committed: %d'
      % (issue_width, total_cycles, len(committed)))
mispredicted = [str(i + 1) for i in range(len(committed)) if getattr(committed[i], 'mispredicted', False)]
print('Branch mispredictions: %d%s' % (len(mispredicted),
      ' (rows ' + ', '.join(mispredicted) + ')' if mispredicted else ''))
