# Multiple-Issue Tomasulo Simulator

This is the provided `tomasulo-python` simulator (Tomasulo's algorithm with a ROB, register renaming and a load/store queue), extended to **issue 1 to 4 instructions per cycle in program order**, with the **1-bit branch predictor and 8-entry BTB** from the handout (wrong-path instructions are squashed, and fetch resumes 2 cycles after a misprediction is found). I kept the starter code's files, data structures and stage functions, and made small, local changes. Every change is listed in [`changes_from_starter.diff`](changes_from_starter.diff), and [report.tex](report.tex) explains each one next to the original code.

## Requirements

Python 3.6 or newer. No other packages.

## Running

```sh
cd code
python3 main.py                                  # runs test_case.txt (the starter's test)
python3 main.py ../tests/handout_sample.txt      # issue width from the input file (default 1)
python3 main.py ../tests/handout_sample.txt 4    # override the issue width (1-4)
```

## Input format

The input format follows the assignment. The text is case insensitive, commas between operands are optional, and lines starting with `#` are ignored.

```
                 # of rs   Cycles in EX   Cycles in Mem   # of FUs
Integer adder    2         1                              1
FP adder         3         3                              1
FP multiplier    2         20                             1
Load/store unit  3         1              4               1

ROB entries = 128
Issue width = 2
R1=10, R2=20, F2=30.1
Mem[4]=1, Mem[8]=2, Mem[12]=3.4

Add.d F1, F2, F3
Ld F4, 8(R1)
Addi R2, R2, -10
Bne R2, R3, -4
```

* **Instructions:** `Ld`, `Sd`, `Beq`, `Bne`, `Add`, `Addi`, `Sub`, `Add.d`, `Sub.d`, `Mult.d`.
* **Branch offsets** are in words: the target is PC + 4 + (offset << 2), so `-4` jumps back 3 instructions.
* **Memory** has 256 entries indexed by byte address, as in the starter code. Stores round values to single precision.
* **Load/store unit row:** `# of rs` is the size of the load/store queue. There is one address adder, so `# of FUs` is not used for this unit.

## Output

The simulator prints:
* one row per instruction as it commits, with its ISSUE, EX, MEM, WB and COMMIT cycles;
* all register values and the non-zero memory;
* the issue width, total cycles and number of committed instructions;
* the number of branch mispredictions and the table rows of the mispredicted branches.

## Tests

```sh
cd tests
python3 run_tests.py            # every test at widths 1-4, plus 1000 random programs
python3 run_tests.py --save     # also writes each output to ../results/<test>_w<width>.txt
```

Each run is checked in two ways:
* **Sequential model:** the final registers, memory and committed instruction sequence must match `tests/golden.py`, which executes the program one instruction at a time.
* **Timing rules:**
  * EX starts after issue and lasts the configured latency;
  * no register is used before it is broadcast;
  * issue and commit stay in order and within the issue width, with at most one broadcast per cycle;
  * the integer adder, the address adder and the memory port are never double-booked;
  * after a mispredicted branch, the correct path issues at least 2 cycles after the branch resolves;
  * the total cycle count matches the last commit or memory access.

## Layout

```
code/                       the simulator (starter files with my changes); test_case.txt is the starter's test
tests/                      test inputs (*.txt), golden.py (sequential model), run_tests.py (test driver)
results/                    output of every test at widths 1-4, and test_summary.txt
changes_from_starter.diff   every change compared with tomasulo-python/code
report.tex                  the report (LaTeX); REPORT.md is a short Markdown version
```
