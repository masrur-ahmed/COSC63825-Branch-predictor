# Test driver.
#
# Every test input is run with code/main.py at issue widths 1-4, and the printed
# output is checked two ways:
#   1. against a sequential golden model: final registers, final memory and the
#      committed instruction sequence must match exactly;
#   2. against the pipeline timing rules (see check_timing), including the
#      2-cycle recovery after every mispredicted branch.
# Then randomly generated programs are run on randomly generated machine
# configurations and checked the same way.
#
# Usage: python3 run_tests.py [--fuzz N] [--save]
#   --save writes each test's output to ../results/<test>_w<width>.txt

import argparse
import ast
import glob
import os
import random
import re
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(HERE, '..', 'code')
sys.path.insert(0, CODE)

from print_status import format_value
from golden import run_golden

UNIT = {'Add': 'Integer adder', 'Addi': 'Integer adder', 'Sub': 'Integer adder', 'Bne': 'Integer adder',
        'Beq': 'Integer adder', 'Add.d': 'FP adder', 'Sub.d': 'FP adder', 'Mult.d': 'FP multiplier',
        'Ld': 'Load/store unit', 'Sd': 'Load/store unit'}
ROW = re.compile(r'^(.*?)\s+(\[[^\]]*\])\s+(\[[^\]]*\])\s+(\[[^\]]*\])\s+(\[[^\]]*\])\s+(\[[^\]]*\])\s*$')


def run_simulator(path, width):
    out = subprocess.run([sys.executable, 'main.py', path, str(width)], cwd=CODE,
                         capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or out.stdout.strip())
    return out.stdout


def parse_output(text):
    rows, regs, memory = [], {}, {}
    lines = text.splitlines()
    for line in lines[1:]:
        m = ROW.match(line)
        if m:
            fields = [ast.literal_eval(g) for g in m.groups()[1:]]
            rows.append(dict(text=m.group(1).strip(), issue=fields[0], ex=fields[1], mem=fields[2],
                             wb=fields[3], commit=fields[4]))
    for k, line in enumerate(lines):
        if re.match(r'^\s+[RF]\d+\s+[RF]\d+', line):
            regs.update(zip(line.split(), lines[k + 1].split()[1:]))
    after = text.split('Addresses')[1].split('Issue width:')[0]
    for address, value in re.findall(r'^(\d+)\s+(\S+)$', after, re.M):
        memory[int(address)] = value
    total = int(re.search(r'Total cycles: (\d+)', text).group(1))
    m = re.search(r'Branch mispredictions: (\d+)(?: \(rows ([\d, ]+)\))?', text)
    mispredicted = [int(x) for x in m.group(2).split(', ')] if m.group(2) else []
    if len(mispredicted) != int(m.group(1)):
        raise ValueError('misprediction count and rows do not match')
    return rows, regs, memory, total, mispredicted


def check_timing(rows, config, width, total, mispredicted):
    errors = []
    lat = {u: config[u][1] for u in UNIT.values()}
    mem_lat = config['Load/store unit'][2]
    n_fu = {u: config[u][-1] for u in ('Integer adder', 'FP adder', 'FP multiplier')}
    writer = {}

    def err(r, msg):
        errors.append('%s (issue %s): %s' % (r['text'], r['issue'], msg))

    prev = None
    for r in rows:
        parts = r['text'].split(' ')
        op = parts[0]
        issue = r['issue'][0]
        if len(r['ex']) != 2 or r['ex'][0] <= issue:
            err(r, 'EX must start after ISSUE')
            continue
        start, end = r['ex']
        if end - start + 1 != lat[UNIT[op]]:
            err(r, 'EX length differs from the configured latency')
        if prev is not None:
            if issue < prev['issue'][0]:
                err(r, 'issued out of program order')
            if r['commit'][0] < prev['commit'][0]:
                err(r, 'commit cycle goes backwards')
        prev = r

        # operands: EX (or the store's memory write) starts after the producer's broadcast
        def needs(reg, cycle):
            if reg != 'R0' and reg in writer and cycle < writer[reg]['wb'][0] + 1:
                err(r, 'used %s before it was broadcast' % reg)
        if op in ('Ld', 'Sd'):
            needs(parts[2][:-1].split('(')[1], start)
            if op == 'Sd':
                needs(parts[1], r['mem'][0])
        elif op in ('Bne', 'Beq'):
            needs(parts[1], start)
            needs(parts[2], start)
        else:
            needs(parts[2], start)
            if op != 'Addi':
                needs(parts[3], start)

        if op == 'Ld':
            if not r['mem'] or r['mem'][0] <= end:
                err(r, 'MEM must follow EX')
            elif len(r['mem']) == 2 and r['mem'][1] - r['mem'][0] + 1 != mem_lat:
                err(r, 'memory access length is wrong')
            if not r['wb'] or r['wb'][0] <= r['mem'][-1]:
                err(r, 'WB must follow MEM')
        elif op not in ('Sd', 'Bne', 'Beq'):
            if not r['wb'] or r['wb'][0] <= end:
                err(r, 'WB must follow EX')
        if op == 'Sd':
            if r['mem'][0] != r['commit'][0]:
                err(r, 'a store writes memory when it commits')
        elif op in ('Bne', 'Beq'):
            if r['commit'][0] <= end:
                err(r, 'a branch commits after it is resolved')
        elif r['commit'][0] <= r['wb'][0]:
            err(r, 'COMMIT must follow WB')
        if op not in ('Sd', 'Bne', 'Beq') and parts[1] != 'R0':
            writer[parts[1]] = r

    def limit(cycles, n, what):
        for cycle, count in Counter(cycles).items():
            if count > n:
                errors.append('cycle %d: %d %s (limit %d)' % (cycle, count, what, n))

    limit([r['issue'][0] for r in rows], width, 'issues')
    limit([r['commit'][0] for r in rows], width, 'commits')
    limit([r['wb'][0] for r in rows if r['wb']], 1, 'CDB broadcasts')
    int_ops = [r['ex'] for r in rows if UNIT[r['text'].split(' ')[0]] == 'Integer adder']
    limit([c for s, e in int_ops for c in range(s, e + 1)], n_fu['Integer adder'], 'busy integer adders')
    for unit in ('FP adder', 'FP multiplier'):
        limit([r['ex'][0] for r in rows if UNIT[r['text'].split(' ')[0]] == unit], n_fu[unit], unit + ' starts')
    ls = [r['ex'] for r in rows if r['text'].split(' ')[0] in ('Ld', 'Sd')]
    limit([c for s, e in ls for c in range(s, e + 1)], 1, 'busy address units')
    port = [r['mem'] for r in rows if len(r['mem']) == 2]
    limit([c for s, e in port for c in range(s, e + 1)], 1, 'memory accesses')
    # after a misprediction the correct path is fetched 2 cycles after the branch resolves
    for n in mispredicted:
        branch = rows[n - 1]
        if branch['text'].split(' ')[0] not in ('Bne', 'Beq'):
            errors.append('row %d is listed as a mispredicted branch but is %s' % (n, branch['text']))
        elif n < len(rows) and rows[n]['issue'][0] < branch['ex'][1] + 2:
            errors.append('row %d issued before the misprediction in row %d was recovered' % (n + 1, n))
    end = max([r['commit'][0] for r in rows] + [r['mem'][-1] for r in rows if r['mem']] + [0])
    if total != end:
        errors.append('total cycles %d, but the last commit / memory access ends in cycle %d' % (total, end))
    return errors


def check(path, width):
    """Run one test at one width; return (total cycles, problems, output)."""
    try:
        text = run_simulator(path, width)
    except Exception as e:
        return None, ['simulator error: %s' % e], None
    try:
        rows, regs, memory, total, mispredicted = parse_output(text)
    except Exception as e:
        return None, ['could not read the simulator output: %r' % e], text
    g_regs, g_memory, g_trace, config = run_golden(path)
    problems = []
    if [r['text'] for r in rows] != g_trace:
        problems.append('committed instruction sequence differs from the golden model')
    want_regs = {name: format_value(value) for name, value in g_regs.items()}
    if regs != want_regs:
        diff = {k: (regs.get(k), want_regs[k]) for k in want_regs if regs.get(k) != want_regs[k]}
        problems.append('registers differ (simulator, golden): %s' % diff)
    want_mem = {a: format_value(v) for a, v in enumerate(g_memory) if v != 0}
    if memory != want_mem:
        problems.append('memory differs: %s vs golden %s' % (memory, want_mem))
    try:
        problems += check_timing(rows, config, width, total, mispredicted)
    except Exception as e:
        problems.append('malformed timing table: %r' % e)
    return total, problems, text


def random_program(rng):
    lines = [
        'Integer adder %d %d %d' % (rng.randint(1, 4), rng.randint(1, 3), rng.randint(1, 2)),
        'FP adder %d %d %d' % (rng.randint(1, 4), rng.randint(1, 5), rng.randint(1, 2)),
        'FP multiplier %d %d %d' % (rng.randint(1, 4), rng.randint(1, 10), rng.randint(1, 2)),
        'Load/store unit %d %d %d 1' % (rng.randint(1, 6), rng.randint(1, 2), rng.randint(1, 6)),
        'ROB entries = %d' % rng.choice([2, 3, 4, 6, 8, 16, 32]),
    ]
    inits = ['R20=0', 'R21=16', 'R22=32', 'R30=%d' % rng.randint(1, 4)]
    inits += ['R%d=%d' % (i, rng.randint(-3, 3)) for i in range(1, 9)]
    inits += ['F%d=%s' % (i, rng.choice(['0.5', '1.0', '1.5', '2.0', '-1.0', '3.1'])) for i in range(1, 9)]
    lines.append(', '.join(inits))
    lines.append(', '.join('Mem[%d]=%d' % (4 * w, rng.randint(1, 9)) for w in range(0, 16, 2)))
    n = rng.randint(4, 14)
    body = []
    r = lambda: 'R%d' % rng.randint(0, 8)
    f = lambda: 'F%d' % rng.randint(0, 8)
    base = lambda: rng.choice(['R20', 'R21', 'R22', 'R24'])
    off = lambda: rng.choice([0, 4, 8, 16])
    for i in range(n):
        kind = rng.choice(['int', 'int', 'fp', 'fp', 'mul', 'ld', 'ld', 'sd', 'sd', 'br', 'base'])
        if kind == 'int':
            body.append(rng.choice(['Add %s, %s, %s' % (r(), r(), r()), 'Sub %s, %s, %s' % (r(), r(), r()),
                                    'Addi %s, %s, %d' % (r(), r(), rng.randint(-3, 3))]))
        elif kind == 'fp':
            body.append('%s %s, %s, %s' % (rng.choice(['Add.d', 'Sub.d']), f(), f(), f()))
        elif kind == 'mul':
            body.append('Mult.d %s, %s, %s' % (f(), f(), f()))
        elif kind == 'ld':
            body.append('Ld %s, %d(%s)' % (f(), off(), base()))
        elif kind == 'sd':
            body.append('Sd %s, %d(%s)' % (f(), off(), base()))
        elif kind == 'base':
            body.append('Sub R24, R24, R24')
            body.append('Addi R24, R24, %d' % (4 * rng.randint(0, 3)))
        else:
            body.append('%s %s, %s, %d' % (rng.choice(['Beq', 'Bne']), r(), r(), rng.randint(0, max(0, n - i - 1))))
    body.append('Addi R30, R30, -1')
    body.append('Bne R30, R0, %d' % -(len(body) + 1))
    return '\n'.join(lines + body) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fuzz', type=int, default=1000, help='number of random programs')
    ap.add_argument('--save', action='store_true', help='save the output of each test to ../results')
    args = ap.parse_args()

    failures = 0
    print('%-30s %6s %6s %6s %6s' % ('test (total cycles)', 'w=1', 'w=2', 'w=3', 'w=4'))
    for path in sorted(glob.glob(os.path.join(HERE, '*.txt'))):
        name = os.path.splitext(os.path.basename(path))[0]
        cells = []
        for width in (1, 2, 3, 4):
            total, problems, text = check(path, width)
            cells.append('FAIL' if problems else str(total))
            if problems:
                failures += 1
                print('FAIL %s width %d:\n  %s' % (name, width, '\n  '.join(problems[:8])))
            if args.save and text:
                with open(os.path.join(HERE, '..', 'results', '%s_w%d.txt' % (name, width)), 'w') as fh:
                    fh.write(text)
        print('%-30s %6s %6s %6s %6s' % (name, *cells))

    rng = random.Random(2026)
    fuzz_fail = 0
    mispredictions = 0
    tmp = os.path.join(HERE, '..', 'results', '.fuzz.txt')
    for i in range(args.fuzz):
        with open(tmp, 'w') as fh:
            fh.write(random_program(rng))
        for width in (1, 2, 3, 4):
            total, problems, text = check(tmp, width)
            m = re.search(r'Branch mispredictions: (\d+)', text or '')
            if m:
                mispredictions += int(m.group(1))
            if problems:
                fuzz_fail += 1
                if fuzz_fail <= 3:
                    print('FUZZ FAIL (program %d, width %d):\n%s\n  %s'
                          % (i, width, open(tmp).read(), '\n  '.join(problems[:8])))
    if os.path.exists(tmp):
        os.remove(tmp)
    print('\nrandom programs: %d programs x 4 widths, %d failures (%d branch mispredictions recovered)'
          % (args.fuzz, fuzz_fail, mispredictions))
    failures += fuzz_fail
    print('ALL TESTS PASSED' if failures == 0 else '%d FAILURES' % failures)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
