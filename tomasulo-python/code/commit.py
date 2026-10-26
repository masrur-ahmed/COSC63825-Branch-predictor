# Qing 
# 29th may 2017
'''
1. commit ROB_buffer
2. fetch header into ROB_buffer
'''

# function: print ROB entry 
def print_ROB(entry, instructions):
    item = instructions[entry.PC].ljust(30)
    item += str(entry.issue).ljust(15) 
    item += str(entry.exe).ljust(15) 
    item += str(entry.mem).ljust(15)
    item += str(entry.cdb).ljust(15)
    item += str(entry.commit)
    print(item)
# function: modify architectual reg
def modify_arch_reg(entry, reg_int, reg_fp):
    if entry.dest_tag[0] == 'F':
        reg_fp[int(entry.dest_tag[1:])] = entry.value
    elif (entry.dest_tag[0] == 'R') & (entry.dest_tag != 'R0'):
        reg_int[int(entry.dest_tag[1:])] = entry.value
    else:
        pass

# function: commit up to commit_width instructions per cycle, in program order
def commit(ROB, reg_int, reg_fp, cycle, instructions, commit_width, committed):
    for i in range(commit_width):
        if len(ROB)==0:
            break
        op = instructions[ROB[0].PC].split(' ')[0]
        if (op=='Bne')|(op=='Beq'):
            # a branch commits in a cycle after its EX has finished
            if (len(ROB[0].exe)!=2) or (ROB[0].exe[1] >= cycle):
                break
            ROB[0].commit.append(cycle)
            entry = ROB.popleft()
        elif (len(ROB[0].cdb)!=0) and (ROB[0].cdb[0] < cycle): # broadcasted in an earlier cycle
            ROB[0].commit.append(cycle)
            entry = ROB.popleft()
            modify_arch_reg(entry, reg_int, reg_fp)
        elif len(ROB[0].commit)!=0: # Sd
            entry = ROB.popleft()
        else:
            break
        print_ROB(entry, instructions)
        committed.append(entry)
