# Qing 
# 24th May 2017

''' 
1. calculate valid instructions
    -- for ALU instructions, write results into fu_results, remove that fu entry  
    -- for LD/SD, write address result immediately back to ld_sd_queue
2. fetch instructions into function unit with spare space
    -- remove ALU instructions from rs
    -- don't remove ld/sd instructions
'''
from init import fu_entry, fu_result

# function: check rs and return valid instruction index
# (the oldest ready instruction that was issued in an earlier cycle)
def check_valid_ins_in_rs(rs, ROB, cycle):
    index = -1
    oldest = len(ROB)
    for i in range(len(rs)):
        if (rs[i].valid_1st==1)&(rs[i].valid_2nd==1)&(rs[i].busy==1):
            position = find_ROB_entry(ROB, rs[i].dest_tag)
            if (ROB[position].issue[0] < cycle) & (position < oldest):
                index = i
                oldest = position
    return index

# function: check ld_sd_queue and return valid instruction index
def check_valid_ins_in_ldsd(ldsd):
    index = -1
    if len(ldsd)!=0:
        for i in range(len(ldsd)):
            if (ldsd[i].valid==1) & (ldsd[i].ready==0):
                index = i
                break
    return index

# function: add entry into fu 
def add_entry_into_fu(fu, ins_in_rs):
    fu[-1].cycle = 0
    fu[-1].op = ins_in_rs.op
    fu[-1].value1 = ins_in_rs.value_1st
    fu[-1].value2 = ins_in_rs.value_2nd
    fu[-1].dest_tag = ins_in_rs.dest_tag

# function: find ROB entry by tag
def find_ROB_entry(ROB, tag):
    for index in range(len(ROB)):
        if ROB[index].ROB_tag == tag:
            break
    return index

# function: functional units execution 
def fu_exe(fu, fu_results, ROB, time_fu, cycle, PC):
    if len(fu)!=0:
        for element in fu:
            # fu_exe is called twice in a cycle when new instructions start,
            # so every entry is advanced only once per cycle
            if getattr(element, 'last_cycle', 0) != cycle:
                element.cycle += 1
                element.last_cycle = cycle
                # write starting cycle 
                if element.cycle == 1:
                    index = find_ROB_entry(ROB, element.dest_tag)
                    ROB[index].exe.append(cycle)
        # finish cycle (several entries can finish together with more than one FU)
        while (len(fu)!=0) and (fu[0].cycle == time_fu):
            index = find_ROB_entry(ROB, fu[0].dest_tag)
            ROB[index].exe.append(cycle)
            # calculation result
            fu_results.append(fu_result())
            fu_results[-1].dest_tag = fu[0].dest_tag
            if (fu[0].op=='Add')|(fu[0].op=='Add.d')|(fu[0].op=='Addi'):
                fu_results[-1].value = fu[0].value1 + fu[0].value2
            elif (fu[0].op=='Sub')|(fu[0].op=='Sub.d'):
                fu_results[-1].value = fu[0].value1 - fu[0].value2
            elif (fu[0].op=='Mult.d'):
                fu_results[-1].value = fu[0].value1 * fu[0].value2
            elif (fu[0].op=='Bne')|(fu[0].op=='Beq'):
                fu_results.pop()
                index = find_ROB_entry(ROB, fu[0].dest_tag)
                branch_pc = ROB[index].PC
                # target = PC + 4 + offset<<2, so the offset is in words
                target = branch_pc + 1 + ROB[index].dest_tag
                taken = (fu[0].value1 == fu[0].value2) == (fu[0].op=='Beq')
                # update the BTB entry and its 1-bit predictor
                PC.btb[branch_pc % 8] = [branch_pc, target, 1 if taken else 0]
                next_pc = target if taken else branch_pc + 1
                # misprediction: keep the oldest one found in this cycle;
                # main.py calls recover() after the EX stage
                if next_pc != ROB[index].pred_next:
                    ROB[index].mispredicted = True
                    if (PC.mispredict == '') or (index < find_ROB_entry(ROB, PC.mispredict)):
                        PC.mispredict = ROB[index].ROB_tag
                        PC.redirect = next_pc
            else:
                pass
            # remove from fu 
            fu.popleft()

# function: ld_sd_execution 
def ld_sd_execution(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle):
    if ld_sd_exe.busy == 1:
        # write down starting cycle
        if ld_sd_exe.cycle == 0:            
            for element in ld_sd_queue:
                if element.ld_sd_tag == ld_sd_exe.dest_tag:
                    break
            index = find_ROB_entry(ROB, element.dest_tag)
            ROB[index].exe.append(cycle)
        # execute (every cycle, so address calculation can take more than 1 cycle)
        ld_sd_exe.cycle += 1
        # write address back to ld_sd_queue
        if ld_sd_exe.cycle == time_ld_sd_exe:
            address = ld_sd_exe.value1 + ld_sd_exe.value2
            for element in ld_sd_queue:
                if element.ld_sd_tag == ld_sd_exe.dest_tag:
                    element.address = address
                    element.ready = 1
                    element.ready_cycle = cycle
                    break
            # write down finish cycle
            index = find_ROB_entry(ROB, element.dest_tag)
            ROB[index].exe.append(cycle)
            ld_sd_exe.busy = 0

# function: execution
def exe(fu_int_adder, time_fu_int_adder,
        fu_fp_adder, time_fu_fp_adder,
        fu_fp_multi, time_fu_fp_multi, results_buffer,
        rs_int_adder, rs_fp_adder, rs_fp_multi, 
        ld_sd_exe, time_ld_sd_exe, ld_sd_queue,
        cycle, ROB, PC, num_fu):
    '''execution in fu and ld_sd address calculation'''
    # units that are busy at the start of the cycle cannot start a new
    # instruction in the same cycle (address adder and unpipelined integer adder)
    ld_sd_busy = ld_sd_exe.busy
    int_adder_busy = len(fu_int_adder)
    ld_sd_execution(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle) 
    # functional units 
    fu_exe(fu_int_adder, results_buffer, ROB, time_fu_int_adder, cycle, PC)
    fu_exe(fu_fp_adder, results_buffer, ROB, time_fu_fp_adder, cycle, PC)
    fu_exe(fu_fp_multi, results_buffer, ROB, time_fu_fp_multi, cycle, PC)
    '''fetch instructions from rs and ld_sd_queue'''
    # from ld_sd_queue
    # check valid ins in ld_sd_queue 
    index = check_valid_ins_in_ldsd(ld_sd_queue)
    # put ins into ld_sd_exe
    if (index>=0)&(ld_sd_exe.busy==0)&(ld_sd_busy==0):
        ld_sd_exe.busy = 1
        ld_sd_exe.cycle = 0
        ld_sd_exe.value1 = ld_sd_queue[index].reg_value
        ld_sd_exe.value2 = ld_sd_queue[index].immediate
        ld_sd_exe.dest_tag = ld_sd_queue[index].ld_sd_tag
        if ROB[find_ROB_entry(ROB, ld_sd_queue[index].dest_tag)].issue[0] < cycle:
            ld_sd_execution(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle)
    # from rs (up to one instruction per FU and cycle)
    # int_adder: unpipelined, so only FUs that were free at the start of the cycle
    # fetch valid instruction 
    for i in range(num_fu[0] - int_adder_busy):
        if check_valid_ins_in_rs(rs_int_adder, ROB, cycle)>=0:
            index = check_valid_ins_in_rs(rs_int_adder, ROB, cycle)
            fu_int_adder.append(fu_entry())
            add_entry_into_fu(fu_int_adder, rs_int_adder[index])
            # check if it's a waiting instruction
            if ROB[find_ROB_entry(ROB, rs_int_adder[index].dest_tag)].issue[0] < cycle:
                fu_exe(fu_int_adder, results_buffer, ROB, time_fu_int_adder, cycle, PC)
            # remove ins from rs 
            rs_int_adder[index].busy = 0
    # fp_adder
    for i in range(num_fu[1]):
        if check_valid_ins_in_rs(rs_fp_adder, ROB, cycle)>=0:
            index = check_valid_ins_in_rs(rs_fp_adder, ROB, cycle)
            fu_fp_adder.append(fu_entry())
            add_entry_into_fu(fu_fp_adder, rs_fp_adder[index])
            if ROB[find_ROB_entry(ROB, rs_fp_adder[index].dest_tag)].issue[0] < cycle:
                fu_exe(fu_fp_adder, results_buffer, ROB, time_fu_fp_adder, cycle, PC)
            # remove ins from rs 
            rs_fp_adder[index].busy = 0
    # fp_multi
    for i in range(num_fu[2]):
        if check_valid_ins_in_rs(rs_fp_multi, ROB, cycle)>=0:
            index = check_valid_ins_in_rs(rs_fp_multi, ROB, cycle)
            fu_fp_multi.append(fu_entry())
            add_entry_into_fu(fu_fp_multi, rs_fp_multi[index])
            if ROB[find_ROB_entry(ROB, rs_fp_multi[index].dest_tag)].issue[0] < cycle:
                fu_exe(fu_fp_multi, results_buffer, ROB, time_fu_fp_multi, cycle, PC)
            # remove ins from rs 
            rs_fp_multi[index].busy = 0

# function: recover from a branch misprediction found at the end of EX:
# squash every instruction after the branch, rebuild the RAT, and fetch the
# correct path two cycles later (one cycle for the recovery)
def recover(PC, ROB, rat_int, rat_fp, reg_int, reg_fp,
            rs_int_adder, rs_fp_adder, rs_fp_multi,
            fu_int_adder, fu_fp_adder, fu_fp_multi,
            ld_sd_queue, ld_sd_exe, ld_sd_mem, results_buffer, cdb, cycle):
    # ROB: remove the instructions after the branch
    branch = find_ROB_entry(ROB, PC.mispredict)
    squashed = []
    while len(ROB) > branch + 1:
        squashed.append(ROB.pop().ROB_tag)
    # reservation stations, functional units, finished results and the CDB
    for rs in (rs_int_adder, rs_fp_adder, rs_fp_multi):
        for entry in rs:
            if (entry.busy == 1) and (entry.dest_tag in squashed):
                entry.busy = 0
    for fu in (fu_int_adder, fu_fp_adder, fu_fp_multi):
        for entry in list(fu):
            if entry.dest_tag in squashed:
                fu.remove(entry)
    for entry in list(results_buffer):
        if entry.dest_tag in squashed:
            results_buffer.remove(entry)
    if (cdb.valid == 1) and (cdb.dest_tag in squashed):
        cdb.valid = 0
    # load/store queue, address adder and memory
    for entry in list(ld_sd_queue):
        if entry.dest_tag in squashed:
            ld_sd_queue.remove(entry)
    if (ld_sd_exe.busy == 1) and (ld_sd_exe.dest_tag not in [e.ld_sd_tag for e in ld_sd_queue]):
        ld_sd_exe.busy = 0
    # (a store in memory has already committed; its old ROB tag may be reused)
    if (ld_sd_mem.busy == 1) and (ld_sd_mem.op == 'Ld') and (ld_sd_mem.dest_tag in squashed):
        ld_sd_mem.busy = 0
    # RAT: committed registers, then the instructions still in the ROB
    for i in range(32):
        rat_int[i] = reg_int[i]
        rat_fp[i] = reg_fp[i]
    for entry in ROB:
        dest = entry.dest_tag
        if (type(dest) == str) and (dest[0] in 'RF') and (dest != 'R0'):
            rat = rat_int if dest[0] == 'R' else rat_fp
            rat[int(dest[1:])] = entry.value if len(entry.cdb) != 0 else entry.ROB_tag
    # fetch the correct path in cycle + 2
    PC.PC = PC.redirect
    PC.resume = cycle + 2
    PC.mispredict = ''
