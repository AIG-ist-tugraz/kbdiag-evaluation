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
  - `verify_diagnosis_quality.py` — diagnosis position analysis (Table 6)
  - `compare_kbdiag_m.py` — FlexDiag minimality/accuracy by test-case size (Table 8)
  - `verify_m2_overhead.py` — λ=2 extra-constraint validity check (Table 8)
  - `conf/` — TOML configuration files for all scripts (incl. `ratio-varied/`, `cognitive/`, `diagnosis-verify/`)
- `data/jiis/` — datasets and evaluation results
  - `fms/` — feature models in UVL format
  - `scenarios/` — test case files (`.testcases`), default 20% inconsistency ratio
  - `scenarios-ratio/` — test cases at 10/30/50% inconsistency ratios (`r10/`, `r30/`, `r50/`) for Table 5
  - `classifiedTS/` — classified test suites
  - `testsuite/` — raw generated test suites
  - `results/` — main evaluation output (Tables 4a, 4b, 7)
  - `results-ratio/` — ratio-varied evaluation output (Table 5)
  - `results-cognitive/` — cognitive-load reports for λ=1 vs λ=2 (Table 8)
  - `results-diagnosis-quality/` — diagnosis position verification reports (Table 6)
  - `tables/` — generated result tables (Markdown and LaTeX), one file per article table
- `solver_apps/` — external SAT solver JARs (SAT4J) - just for test_diagnosis.py, not used in our evaluation
- `tests/` — unit tests
- `LICENSE` — MIT License

## Requirements

- **Python**: 3.10+ (verified on 3.10 and 3.13)
- **Key dependencies**:
  - [FLAMA](https://flamapy.github.io) 2.0.1 — feature model framework (UVL parsing, SAT operations),
    installed as the three sub-distributions actually used: `flamapy-fw`, `flamapy-fm`, `flamapy-sat`
  - [PySAT](https://pysathq.github.io) 0.1.8+ — SAT solver (Glucose3, incremental solving)

> **Do not `pip install flamapy`.** The FLAMA meta-package also requires
> `flamapy-bdd`, which pulls in `dd==0.5.7`; `dd` ships no wheels and its
> `setup.py` imports `pkg_resources`, which setuptools 81+ no longer provides, so
> the install fails with `ModuleNotFoundError: No module named 'pkg_resources'`.
> Nothing here uses BDDs. `requirements.txt` therefore names the three
> sub-distributions directly — the installed FLAMA code is identical, and the
> install works with a current setuptools. If you must install the meta-package
> for other reasons, `pip install "setuptools<81" wheel` first and add
> `--no-build-isolation`.

## Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Datasets

Six feature models in UVL format are provided in `data/jiis/fms/`.

**The article and the dataset use different names for the same knowledge bases.**
The article uses the short aliases in the first column; the files on disk use the
internal names in the second. Every generated table in `data/jiis/tables/` is
labelled with the article alias.

| Name in the article | Internal name | File | \|C\| (constraints) |
|---------------------|---------------|------|--------------------:|
| HIS | REAL-FM-11 | `REAL-FM-11.uvl` | 64 |
| DELL | DELL | `DELL.uvl` | 121 |
| B2C | REAL-FM-4 | `REAL-FM-4.uvl` | 233 |
| Win8 | windows8 | `windows8.uvl` | 405 |
| CNN | CNNl | `Ghamizi2019-light.uvl` | 1,637 |
| Linux | linux | `linux-2.6.33.3.uvl` | 13,972 |

Result files and test case files are named with the **internal** name, so a
scenario for B2C appears as `REAL-FM-4_c100_0.testcases`.

Each KB has 70 test case files in `data/jiis/scenarios/` with 7 cardinalities
(|T_π| = 5, 10, 25, 50, 100, 250, 500) and 10 versions each.
Test case naming convention: `<KB>_c<size>_<version>.testcases`.

## Reproducing the evaluation

### Running the evaluation

The evaluation is driven by TOML configuration files in `apps/conf/`.

**Run KBDiag evaluation** (corresponds to the main runtime tables — Tables 4a, 4b and 7):

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

Results are written to `data/jiis/results-rerun/`, **not** to `data/jiis/results/`.

> **Why a separate directory.** `eval_runner` opens its output files in *append*
> mode. Running it into a directory that already contains results silently
> concatenates the old and new runs; the table generators then average across
> both and produce tables that do not match the article. The evaluation configs
> therefore write to `-rerun` directories, so the published results shipped with
> this artifact cannot be damaged by re-running anything.
>
> To regenerate the tables from **your own** run rather than from the published
> results, set `result_path` in the corresponding `apps/conf/*_gen.toml` to the
> matching `-rerun` directory. Runtimes will differ from the article — they are
> hardware-dependent — while the diagnosis sizes (`|D|`) and diagnosis counts
> (`#Diag`) should match exactly.

### Additional experiments

**Inconsistency-ratio variation (Table 5)** — runs the three feature models HIS (`REAL-FM-11`), Win8 (`windows8`), and Linux (`linux`) at 10/30/50% inconsistency ratios (the 20% case reuses `data/jiis/results/`):

```bash
for r in r10 r30 r50; do
  python -m apps.eval_runner apps/conf/ratio-varied/kbdiag_eval_$r.toml
  python -m apps.eval_runner apps/conf/ratio-varied/qxwithtc_eval_$r.toml
done
```

**Diagnosis position (Table 6)** — locates KBDiag's first diagnosis within the HSDAG all-diagnoses set:

```bash
python -m apps.verify_diagnosis_quality apps/conf/diagnosis-verify/diagnosis_quality_verify.toml
```

**Cognitive load, λ=1 vs λ=2 (Table 8)**:

```bash
python -m apps.compare_kbdiag_m  apps/conf/cognitive/compare_kbdiag_m.toml
python -m apps.verify_m2_overhead apps/conf/cognitive/verify_m2_overhead.toml
```

### Generating result tables

After running the evaluations, regenerate the paper's tables:

```bash
python -m apps.results_table_gen apps/conf/tables47_gen.toml  # Tables 4a, 4b, 7
python -m apps.results_table_gen apps/conf/table5_gen.toml    # Table 5
python -m apps.results_table_gen apps/conf/tables68_gen.toml  # Tables 6, 8
```

Output tables (Markdown and LaTeX) are written to `data/jiis/tables/`, one file
per article table:

| Article table | Generated file | Content |
|---|---|---|
| Table 4a | `table4a.md` / `.tex` | Consistency checks / runtime, one minimal diagnosis — HIS, DELL, B2C |
| Table 4b | `table4b.md` / `.tex` | Same, for Win8, CNN, Linux |
| Table 5 | `table5.md` / `.tex` | Runtime speedup across inconsistency ratios |
| Table 6 | `table6.md` / `.tex` | Position of MSSDirect's diagnosis in HSDAG's enumeration |
| Table 7 | `table7.md` / `.tex` | Average runtime for the *n* leading diagnoses |
| Table 8 | `table8.md` / `.tex` | Cognitive-load metrics (minimality, accuracy, relevance) for λ=2 |

The generators for Tables 5, 6 and 8 also check every generated value against
the numbers printed in the article and report any discrepancy, so a successful
run confirms the tables were reproduced rather than merely produced.

Table 3 (knowledge base characteristics) is descriptive and has no generator;
its `|C|` column is the dataset table above.

Note for anyone reading the source: the generator's internal configuration
sections are still named `[table3]`, `[table4]`, `[table7]`, `[table8]` and
`[table9]`. That numbering predates the final article and does **not** match it.
Each config file documents its own mapping in the header; the file names,
captions and console output all use the article's numbering.

The reports under `results-cognitive/` use the earlier name *faulty rate* for
the metric published as *relevance(E)*. The values are the same, expressed as a
percentage in the report and as a decimal in Table 8.

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

[1] A. Felfernig, V.M. Le, D. Garber, S. Lubos, T.N.T. Tran. Automated Testing and Debugging of Configuration Knowledge Bases With Direct Diagnosis. *Journal of Intelligent Information Systems*, 2026. Accepted for publication; volume, pages and DOI to follow.

## Citing this repository

If you use this code or dataset, please cite the article above. `CITATION.cff`
in the repository root carries the same metadata in machine-readable form and
drives GitHub's "Cite this repository" button. Both will be updated with the
DOI once the article is published.
