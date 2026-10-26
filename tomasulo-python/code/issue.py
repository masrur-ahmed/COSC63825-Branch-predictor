# Qing 
# 21st May 2017

"""
1. put 1 instruction in ROB
2. put this instruction in RS/ld_sd_queue
3. update RAT
"""
from collections import namedtuple, deque
from init import ld_sd_entry, ROB_entry

# function: find a tag for ld_sd_entry 
def find_tag_new_ldsd_entry(ld_sd_queue, size_ld_sd_queue):
    existing_tag = []
    tag_pool = []
    for i in range(len(ld_sd_queue)):
        existing_tag.append(ld_sd_queue[i].ld_sd_tag)
    for i in range(size_ld_sd_queue):
        tag_pool.append('ldsd'+str(i))
    return list(set(tag_pool)-set(existing_tag))[0]

# function put ins into ROB 
def put_ins_into_ROB(ROB, size_ROB, PC, cycle, ins, ldsd_tag):
    ROB.append(ROB_entry())
    # ROB_tag
    if len(ROB)==1:
        ROB[-1].ROB_tag = 'ROB0'
    else:
        index = ROB[-2].ROB_tag[3:]
        ROB[-1].ROB_tag = 'ROB'+str((int(index)+1)%size_ROB)
    # PC
    ROB[-1].PC = PC.PC
    # dest_tag
    if ins.split(' ')[0]=='Sd': # SD
        ROB[-1].dest_tag = ldsd_tag
    elif (ins.split(' ')[0]=='Bne')|(ins.split(' ')[0]=='Beq'): # BNE/BEQ
        ROB[-1].dest_tag = int(ins.split(' ')[-1]) 
    else: # ALU and LD instructions
        ROB[-1].dest_tag = ins.split(' ')[1]
    # issue 
    ROB[-1].issue.append(cycle)

# function: put ins into reservation station
def put_ins_into_rs(station, index, ins, ROB, rat_int, rat_fp):
    entry = station[index]
    entry.busy = 1
    entry.op = ins.split(' ')[0]
    # reg 1
    register = ins.split(' ')[2] # register name 
    if register[0] == 'F':
        if (type(rat_fp[int(register[1:])]) == str):
            entry.tag_1st = rat_fp[int(register[1:])]
            entry.valid_1st = 0
        else:
            entry.value_1st = rat_fp[int(register[1:])]
            entry.valid_1st = 1
    elif register[0] == 'R':
        if (type(rat_int[int(register[1:])]) == str):
            entry.tag_1st = rat_int[int(register[1:])]
            entry.valid_1st = 0
        else:
            entry.value_1st = rat_int[int(register[1:])]
            entry.valid_1st = 1
    else:
        pass
    # reg 2
    register = ins.split(' ')[3] # register name 
    if register[0] == 'F':
        if (type(rat_fp[int(register[1:])]) == str):
            entry.tag_2nd = rat_fp[int(register[1:])]
            entry.valid_2nd = 0
        else:
            entry.value_2nd = rat_fp[int(register[1:])]
            entry.valid_2nd = 1
    elif register[0] == 'R':
        if (type(rat_int[int(register[1:])]) == str):
            entry.tag_2nd = rat_int[int(register[1:])]
            entry.valid_2nd = 0
        else:
            entry.value_2nd = rat_int[int(register[1:])]
            entry.valid_2nd = 1
    else: # immediate number
        entry.value_2nd = int(ins.split(' ')[3])
        entry.valid_2nd = 1
    # dest_tag
    entry.dest_tag = ROB[-1].ROB_tag

# function: put bne into rs
def put_bne_into_rs(rs_int_adder, index, ins, rat_int, rat_fp, ROB):
    entry = rs_int_adder[index]
    entry.busy = 1
    entry.op = ins.split(' ')[0]
    # reg 1
    register = ins.split(' ')[1] # register name 
    if register[0] == 'F':
        if (type(rat_fp[int(register[1:])]) == str):
            entry.tag_1st = rat_fp[int(register[1:])]
            entry.valid_1st = 0
        else:
            entry.value_1st = rat_fp[int(register[1:])]
            entry.valid_1st = 1
    elif register[0] == 'R':
        if (type(rat_int[int(register[1:])]) == str):
            entry.tag_1st = rat_int[int(register[1:])]
            entry.valid_1st = 0
        else:
            entry.value_1st = rat_int[int(register[1:])]
            entry.valid_1st = 1
    else:
        pass
    # reg 2
    register = ins.split(' ')[2] # register name 
    if register[0] == 'F':
        if (type(rat_fp[int(register[1:])]) == str):
            entry.tag_2nd = rat_fp[int(register[1:])]
            entry.valid_2nd = 0
        else:
            entry.value_2nd = rat_fp[int(register[1:])]
            entry.valid_2nd = 1
    elif register[0] == 'R':
        if (type(rat_int[int(register[1:])]) == str):
            entry.tag_2nd = rat_int[int(register[1:])]
            entry.valid_2nd = 0
        else:
            entry.value_2nd = rat_int[int(register[1:])]
            entry.valid_2nd = 1
    # dest_tag
    entry.dest_tag = ROB[-1].ROB_tag 

# function: put ins into ld_sd_queue
def put_ins_into_ldsd(ldsd_tag, ld_sd_queue, ins, ROB, rat_int, rat_fp):
    ld_sd_queue.append(ld_sd_entry())
    # ld_sd_tag
    ld_sd_queue[-1].ld_sd_tag = ldsd_tag
    ld_sd_queue[-1].ready = 0
    ld_sd_queue[-1].op = ins.split(' ')[0]
    if ld_sd_queue[-1].op == 'Sd':
        register = ins.split(' ')[1] # register name 
        ld_sd_queue[-1].data = rat_fp[int(register[1:])]
        
    ld_sd_queue[-1].dest_tag = ROB[-1].ROB_tag
    # immediate and reg value 
    offset, register = ins.split(' ')[-1][:-1].split('(') # offset and register name
    ld_sd_queue[-1].immediate = int(offset)
    if (type(rat_int[int(register[1:])]) == str):
        ld_sd_queue[-1].reg_tag = rat_int[int(register[1:])]
        ld_sd_queue[-1].valid = 0
    else:
        ld_sd_queue[-1].reg_value = rat_int[int(register[1:])]
        ld_sd_queue[-1].valid = 1

# function: check space of reservation station
def check_rs_space(station):
    index = -1
    for i in range(len(station)):
        if station[i].busy == 0:
            index = i
            break 
    return index

# update RAT
def update_rat(ROB, rat_int, rat_fp):
    if ROB[-1].dest_tag[0] == 'F':
        rat_fp[int(ROB[-1].dest_tag[1:])] = ROB[-1].ROB_tag
    elif (ROB[-1].dest_tag[0] == 'R') & (ROB[-1].dest_tag != 'R0'):
        rat_int[int(ROB[-1].dest_tag[1:])] = ROB[-1].ROB_tag
    else:
        pass

# function: predict a branch with the BTB (8 entries, indexed by the low 3 bits
# of the word address) and its 1-bit predictor; a BTB miss predicts not taken
def predict_branch(PC, pc):
    entry = PC.btb[pc % 8]
    if (entry is not None) and (entry[0] == pc) and (entry[2] == 1):
        return entry[1]
    return pc + 1

# function: issue up to issue_width instructions per cycle, in program order
def issue(cycle, PC, instructions, ROB, size_ROB, 
        rs_int_adder, 
        rs_fp_adder, 
        rs_fp_multi, 
        ld_sd_queue, size_ld_sd_queue, 
        rat_int, rat_fp, issue_width):
    # after a misprediction, fetch starts again two cycles after it was found
    if cycle < PC.resume:
        return
    for i in range(issue_width):
        # stop at the end of the program
        if (PC.PC < 0) | (PC.PC >= len(instructions)) | (PC.valid == 0):
            break
        rob_size = len(ROB)
        pc = PC.PC
        issue_one_instruction(cycle, PC, instructions, ROB, size_ROB,
                rs_int_adder, rs_fp_adder, rs_fp_multi,
                ld_sd_queue, size_ld_sd_queue, rat_int, rat_fp)
        # stop when the instruction could not be issued (no ROB/RS/queue entry);
        # the instructions after it have to wait too
        if len(ROB) == rob_size:
            break
        # a branch predicted taken ends the group; fetch continues at its target
        if PC.PC != pc + 1:
            break

""""""
def issue_one_instruction(cycle, PC, instructions, ROB, size_ROB, 
        rs_int_adder, 
        rs_fp_adder, 
        rs_fp_multi, 
        ld_sd_queue, size_ld_sd_queue, 
        rat_int, rat_fp):
    # fetch 1 instruction 
    ins = instructions[PC.PC]
    op = ins.split(' ')[0] 
    '''decode'''
    # LD/SD instructions
    if (op=='Ld')|(op=='Sd'):
        # check space
        if (len(ROB)<size_ROB)&(len(ld_sd_queue)<size_ld_sd_queue):
            # find ldsd_tag
            ldsd_tag = find_tag_new_ldsd_entry(ld_sd_queue, size_ld_sd_queue)
            # put ins into ROB
            put_ins_into_ROB(ROB, size_ROB, PC, cycle, ins, ldsd_tag)
            # put ins into ld_sd_queue
            put_ins_into_ldsd(ldsd_tag, ld_sd_queue, ins, ROB, rat_int, rat_fp)
            # update RAT
            update_rat(ROB, rat_int, rat_fp)
            # PC
            PC.PC +=1
    # integer adder instructions
    elif (op=='Add')|(op=='Addi')|(op=='Sub'):
        # check space
        if (len(ROB)<size_ROB)&(check_rs_space(rs_int_adder)>=0):
            # put ins into ROB
            put_ins_into_ROB(ROB, size_ROB, PC, cycle, ins, '')
            # put ins into rs_int_adder
            index = check_rs_space(rs_int_adder)
            put_ins_into_rs(rs_int_adder, index, ins, ROB, rat_int, rat_fp)
            # update RAT
            update_rat(ROB, rat_int, rat_fp)
            # PC
            PC.PC +=1
    # fp adder instructions
    elif (op=='Add.d')|(op=='Sub.d'):
        # check space
        if (len(ROB)<size_ROB)&(check_rs_space(rs_fp_adder)>=0):
            # put ins into ROB
            put_ins_into_ROB(ROB, size_ROB, PC, cycle, ins, '')
            # put ins into rs_fp_adder
            index = check_rs_space(rs_fp_adder)
            put_ins_into_rs(rs_fp_adder, index, ins, ROB, rat_int, rat_fp)
            # update RAT
            update_rat(ROB, rat_int, rat_fp)
            # PC
            PC.PC +=1
    # fp multiplier instructions
    elif (op=='Mult.d'): 
        # check space
        if (len(ROB)<size_ROB)&(check_rs_space(rs_fp_multi)>=0):
            # put ins into ROB
            put_ins_into_ROB(ROB, size_ROB, PC, cycle, ins, '')
            # put ins into rs_fp_multi
            index = check_rs_space(rs_fp_multi)
            put_ins_into_rs(rs_fp_multi, index, ins, ROB, rat_int, rat_fp)
            # update RAT
            update_rat(ROB, rat_int, rat_fp)
            # PC
            PC.PC +=1
    # Bne/Beq 
    elif (op=='Bne')|(op=='Beq'):
        # check space
        if (len(ROB)<size_ROB)&(check_rs_space(rs_int_adder)>=0):
            # put ins into ROB
            put_ins_into_ROB(ROB, size_ROB, PC, cycle, ins, '')
            # put ins into rs_int_adder
            index = check_rs_space(rs_int_adder)
            put_bne_into_rs(rs_int_adder, index, ins, rat_int, rat_fp, ROB)
            # PC: continue on the predicted path
            ROB[-1].pred_next = predict_branch(PC, PC.PC)
            PC.PC = ROB[-1].pred_next
    else:
        pass

