# Automated Testing and Debugging of Configuration Knowledge Bases With Direct Diagnosis

A Python tool for diagnosing conflicts in configuration knowledge bases and feature models
using direct diagnosis algorithms.

This repository contains the implementation and evaluation of the **KBDiag** algorithm,
presented in the paper entitled
*Automated Testing and Debugging of Configuration Knowledge Bases With Direct Diagnosis* [1].
The research community can fully exploit this repository to reproduce the work described in our paper.

## Repository structure

- `explanation/` — core diagnosis library (models, algorithms, transformations)
  - `models/` — data models for diagnosis problems (KB, test cases, profiler)
  - `operations/` — diagnosis algorithms (KBDiag, FastDiag/FastDiagP, WipeOutR, QuickXPlain)
  - `transformations/` — readers for feature models (UVL via flamapy), test suites, and DIMACS
- `apps/` — evaluation and utility scripts
  - `eval_runner.py` — main evaluation script (TOML-driven)
  - `testsuite_gen.py` — test suite generator from feature models
  - `testcases_classifier.py` — test case classifier (violated/non-violated)
  - `testcases_selector.py` — diversity-optimized test case selection
  - `results_table_gen.py` — generates Markdown and LaTeX result tables
  - `verify_diagnosis_quality.py` — diagnosis quality analysis (Table 8)
  - `compare_kbdiag_m.py` — FlexDiag minimality/accuracy by test-case size (Table 9)
  - `verify_m2_overhead.py` — λ=2 overhead constraint validity check (Table 9)
  - `conf/` — TOML configuration files for all scripts (incl. `ratio-varied/`, `cognitive/`, `diagnosis-verify/`)
- `data/jiis/` — datasets and evaluation results
  - `fms/` — feature models in UVL format
  - `scenarios/` — test case files (`.testcases`), default 20% inconsistency ratio
  - `scenarios-ratio/` — test cases at 10/30/50% inconsistency ratios (`r10/`, `r30/`, `r50/`) for Table 7
  - `classifiedTS/` — classified test suites
  - `testsuite/` — raw generated test suites
  - `results/` — main evaluation output (Tables 3, 4)
  - `results-ratio/` — ratio-varied evaluation output (Table 7)
  - `results-cognitive/` — cognitive-load reports for λ=1 vs λ=2 (Table 9)
  - `results-diagnosis-quality/` — diagnosis quality verification reports (Table 8)
  - `tables/` — generated result tables (Markdown and LaTeX)
- `solver_apps/` — external SAT solver JARs (SAT4J) - just for test_diagnosis.py, not used in our evaluation
- `tests/` — unit tests
- `LICENSE` — MIT License

## Requirements

- **Python**: 3.10+
- **Key dependencies**:
  - [flamapy](https://flamapy.github.io) 2.0+ — feature model framework (UVL parsing, SAT operations)
  - [PySAT](https://pysathq.github.io) 0.1.8+ — SAT solver (Glucose3, incremental solving)

## Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Datasets

Six feature models in UVL format are provided in `data/jiis/fms/`:

| Knowledge Base | File | |C| (constraints) |
|----------------|------|------------------:|
| REAL-FM-11 | `REAL-FM-11.uvl` | 64 |
| DELL | `DELL.uvl` | 121 |
| REAL-FM-4 | `REAL-FM-4.uvl` | 233 |
| windows8 | `windows8.uvl` | 405 |
| CNNl | `Ghamizi2019-light.uvl` | 1,637 |
| linux | `linux-2.6.33.3.uvl` | 13,972 |

Each KB has 70 test case files in `data/jiis/scenarios/` with 7 cardinalities
(|T_π| = 5, 10, 25, 50, 100, 250, 500) and 10 versions each.
Test case naming convention: `<KB>_c<size>_<version>.testcases`.

## Reproducing the evaluation

### Running the evaluation

The evaluation is driven by TOML configuration files in `apps/conf/`.

**Run KBDiag evaluation** (corresponds to the main runtime tables — Tables 3 and 4):

```bash
python -m apps.eval_runner apps/conf/kbdiag_eval.toml
python -m apps.eval_runner apps/conf/qxwithtc_eval.toml
```

Configuration options in `apps/conf/kbdiag_eval.toml` and `apps/conf/qxwithtc_eval.toml` include:
- `algorithm` — `"kbdiag"` or `"quickxplain_with_testcases"` (HSD baseline)
- `task` — `"1"` (first diagnosis) or `"all"` (all diagnoses)
- `m` — λ parameter for KBDiag (1 or 2)
- `num_iterations` — number of measurement iterations (default: 3)
- `timeout` / `timeout_all` — timeout per scenario in seconds

Results are written to `data/jiis/results/`.

### Revision-2 experiments

**Inconsistency-ratio variation (Table 7)** — runs the three feature models HIS (`REAL-FM-11`), Win8 (`windows8`), and Linux at 10/30/50% inconsistency ratios (the 20% case reuses `data/jiis/results/`):

```bash
for r in r10 r30 r50; do
  python -m apps.eval_runner apps/conf/ratio-varied/kbdiag_eval_$r.toml
  python -m apps.eval_runner apps/conf/ratio-varied/qxwithtc_eval_$r.toml
done
```

**Diagnosis quality (Table 8)** — verifies KBDiag's first diagnosis against the HSDAG all-diagnoses set:

```bash
python -m apps.verify_diagnosis_quality apps/conf/diagnosis-verify/diagnosis_quality_verify.toml
```

**Cognitive load, λ=1 vs λ=2 (Table 9)**:

```bash
python -m apps.compare_kbdiag_m  apps/conf/cognitive/compare_kbdiag_m.toml
python -m apps.verify_m2_overhead apps/conf/cognitive/verify_m2_overhead.toml
```

### Generating result tables

After running the evaluations, regenerate the paper's tables:

```bash
python -m apps.results_table_gen apps/conf/table_gen_original.toml  # Tables 3a, 3b, 4
python -m apps.results_table_gen apps/conf/table7_gen.toml          # Table 7
python -m apps.results_table_gen apps/conf/table89_gen.toml         # Tables 8, 9
```

Output tables (Markdown and LaTeX) are written to `data/jiis/tables/`.

### Other utility scripts

**Generate test suites from feature models:**
```bash
python -m apps.testsuite_gen apps/conf/testsuite_gen.toml
```

**Classify test cases (violated/non-violated):**
```bash
python -m apps.testcases_classifier apps/conf/testcases_classifier.toml
```

**Select diversity-optimized test cases:**
```bash
python -m apps.testcases_selector apps/conf/testcases_selector.toml
```

### Running tests

```bash
python -m unittest discover -s tests -v
```

## Algorithms

- **KBDiag (MSD)** — direct diagnosis algorithm computing diagnoses by finding maximal satisfiable subsets via multi-split decomposition, parameterized by λ (split factor)
- **QuickXPlain with test cases (HSD baseline)** — HS-DAG-based approach using QuickXPlain as the conflict detection labeler to compute all diagnoses

## Test case format

Each `.testcases` file contains one test case per line as boolean feature expressions:

```
5
ProductCategory & ~XPSLaptops & StudioXPSLaptops & ~a80GB
ProductCategory & ~MiniNotebooks & ~XPSLaptops & WindowsVista64bit & ~BluRayDisc
...
```

The first line indicates the number of test cases, followed by the test case expressions.

## License

This project is licensed under the MIT License — see `LICENSE` for details.

## References

[1] A. Felfernig, V.M. Le, D. Garber, S. Lubos, T.N.T. Tran. Automated Testing and Debugging of Configuration Knowledge Bases With Direct Diagnosis. In *Journal of Intelligent Information Systems (JIIS)*. 2026. [revision 2 submitted].
