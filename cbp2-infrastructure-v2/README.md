# Assignment 1: Pentium M Hybrid Branch Predictor (2-way global predictor)

This directory holds an implementation of the Pentium M branch *direction* predictor, built on the CBP2 branch prediction infrastructure. It combines a 4096-entry bimodal table with a tagged **2-way** set-associative global predictor. The handout allows a 2-way global predictor in place of the 4-way one in the Pentium M diagram, and this version uses that option.

See [REPORT.md](REPORT.md) for the design, verification and results.

## What changed

| File | Purpose |
|---|---|
| `src/my_predictor.h` | **`pm_update` / `pm_predictor` implemented.** The `gshare_predictor` sample and the `cpm_predictor` extra-credit stub are unchanged. |
| `tests/example_test.cc` | Replays the 22-branch worked example from the handout (Appendix B, which itself uses a 2-way global predictor) and checks every local, global and final prediction against the handout tables. |
| `experiments/sweep.cc`, `experiments/run_sweep.sh` | Run several predictor configurations side by side on all traces (baselines and ablations). |
| `experiments/results.tsv` | Sweep output: MPKI per trace per configuration. |
| `experiments/run_traces_output.txt` | Output of the official `run traces` script. |
| `REPORT.md` | Report (Markdown). |
| `report.tex` | Report in LaTeX, written in the style of the Milenkovic et al. paper. |
| `experiments/example_test_output.txt` | Output of the worked-example test. |

Everything else (`predict.cc`, `trace.cc`, `run`, the traces, ...) is the original CBP2 infrastructure.

## Build and run

```sh
cd src
make                    # builds ./predict (and ./predict_extra_credit)
cd ..
./run traces            # or: csh ./run traces
```

`run` prints the MPKI (direction mispredictions per 1000 instructions) for each trace and the average (**8.660** for this version). To run a single trace:

```sh
./src/predict traces/164.gzip/gzip.trace.bz2
```

### Verify against the handout example

```sh
cd tests
g++ -Wall -O2 -o example_test example_test.cc
./example_test          # expects "22/22 rows match the handout"
```

### Reproduce the comparison table

```sh
./experiments/run_sweep.sh   # about 1 minute; writes experiments/results.tsv
```

## Configuration

The predictor's geometry and policies are set by `#define`s at the top of the `pm_predictor` section of `src/my_predictor.h`:

| Define | Default | Meaning |
|---|---|---|
| `PM_BIMODAL_BITS` | 12 | 4096-entry bimodal table, index = IP[11:0] |
| `PM_INDEX_BITS` | 9 | 512 global-predictor sets, index = HASH[14:6] |
| `PM_TAG_BITS` | 6 | 6-bit tags, tag = HASH[5:0] |
| `PM_WAYS` | **2** | global predictor associativity |
| `PM_ADDR_SHIFT` | 0 | HASH = (IP >> shift) XOR GHR, 15 bits wide |
| `PM_ALLOC_COUNTER` | `PM_ALLOC_KEEP` | counter of a newly allocated entry: keep and train the old value (handout), or `PM_ALLOC_RESET` to set it to weakly taken/not taken |
| `PM_ALLOC_ON_BIMODAL_MISS` | `false` | `true` allocates a global entry only when the bimodal predictor mispredicted |

The defaults follow the assignment diagram (with 2 ways) and the handout's worked example and give **8.660 MPKI**. Setting `PM_ALLOC_COUNTER` to `PM_ALLOC_RESET` and `PM_ALLOC_ON_BIMODAL_MISS` to `true` gives **6.134 MPKI** (see the report).

## Environment notes

* Tested on macOS 27 with Apple clang 21 (`g++` resolves to clang). The build prints four deprecation warnings from the original `trace.cc` (`sprintf`); they are harmless.
* `src/trace.h` decompresses traces with `/usr/bin/bzip2`, which is present on macOS and Linux.
* No external cache code was used; the set-associative table and its LRU replacement are written from scratch in `my_predictor.h`.
