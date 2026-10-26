# Sequential reference model: executes the program one instruction at a time
# with no pipeline.  Used to check the simulator's final registers, memory and
# committed instruction sequence.

from init import read_input, to_single


def run_golden(path, max_steps=100000):
    config, init_regs, init_memory, instructions = read_input(path)
    regs = {'R%d' % i: 0 for i in range(32)}
    regs.update({'F%d' % i: 0 for i in range(32)})
    for name, value in init_regs.items():
        if name != 'R0':
            regs[name] = value
    memory = [0] * 256
    for address, value in init_memory.items():
        memory[address] = value

    trace = []
    pc = 0
    while 0 <= pc < len(instructions):
        if len(trace) >= max_steps:
            raise RuntimeError('program did not finish within %d instructions' % max_steps)
        trace.append(pc)
        parts = instructions[pc].split(' ')
        op = parts[0]
        nxt = pc + 1
        if op in ('Ld', 'Sd'):
            offset, base = parts[2][:-1].split('(')
            address = regs[base] + int(offset)
            if op == 'Ld':
                regs[parts[1]] = memory[address]
            else:
                memory[address] = to_single(regs[parts[1]])
        elif op in ('Bne', 'Beq'):
            equal = regs[parts[1]] == regs[parts[2]]
            if equal == (op == 'Beq'):
                nxt = pc + 1 + int(parts[3])
        else:
            a = regs[parts[2]]
            b = int(parts[3]) if op == 'Addi' else regs[parts[3]]
            if op in ('Add', 'Addi', 'Add.d'):
                value = a + b
            elif op in ('Sub', 'Sub.d'):
                value = a - b
            else:
                value = a * b
            if parts[1] != 'R0':
                regs[parts[1]] = value
        pc = nxt
    return regs, memory, [instructions[i] for i in trace], config
