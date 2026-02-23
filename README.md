# KBDiag

Model-based diagnosis system for knowledge bases with multiple observations.

## Overview

KBDiag is a research tool for identifying conflicts and inconsistencies in constraint-based knowledge bases, particularly feature models. The system implements multiple diagnosis algorithms to compute maximal satisfiable subsets (MSS) and minimal unsatisfiable subsets (MUS) when test cases violate knowledge base constraints.

Developed at TU Graz by Viet-Man Le. Licensed under MIT.

## Key Features

- **Core Diagnosis Algorithms**: KBDiag, FastDiag, QuickXPlain, and Syntactic Relevance
- **Extended Algorithms**: FastDiagP, WipeOutR variants (Python explanation/ module)
- **Hitting Set DAG (HS-DAG)**: Efficiently computes all diagnoses through shared computations with multiple labelers
- **SAT Solver Integration**: Choco (Java), PySAT and SAT4J (Python)
- **Dual Implementation**: Java primary (~8,040 LOC), Python extended (~10,770 LOC total)
- **Evaluation Framework**: Comprehensive benchmarking with TOML-driven configuration
- **Testing**: 16 Java test files + 4 Python test files with 14 resource fixtures

## Quick Start

### Java (Recommended)

**Requirements**: Java 21, Maven

```bash
# Build the project
mvn clean package

# Run tests
mvn test

# Run main application
java -jar target/main_v2-jar-with-dependencies.jar -e config.txt
```

### Python

**Requirements**: Python 3.11+

```bash
# Setup environment
python3 -m venv venv
source venv/bin/activate

# Generate test suites (optional)
python -m apps.testsuite_gen apps/conf/testsuite_gen.toml

# Run evaluation
python -m apps.eval_runner apps/conf/kbdiag_eval.toml

# Run tests
python -m unittest discover -s tests -v
```

## Documentation

See `/docs` directory for detailed documentation:

- [project-overview-pdr.md](./docs/project-overview-pdr.md) - Product requirements and research context
- [codebase-summary.md](./docs/codebase-summary.md) - Complete project structure and inventory
- [code-standards.md](./docs/code-standards.md) - Coding conventions and patterns
- [system-architecture.md](./docs/system-architecture.md) - Architecture design and algorithms
- [deployment-guide.md](./docs/deployment-guide.md) - Build, deployment, and runtime instructions

## Project Structure

```
KBDiag/
├── src/main/java/at/tugraz/ist/ase/kbdiag/     # Java implementation (~8,040 LOC, 44 files)
│   ├── debugging/algorithms/                     # Core diagnosis algorithms
│   ├── apps/real/                               # Evaluation framework (15 evaluator classes)
│   └── common/                                   # Shared utilities + configuration
├── apps/                                         # Python evaluation & generation scripts
│   ├── eval_runner.py                            # TOML-driven evaluation orchestrator
│   ├── testsuite_gen.py                         # Test suite generator from FMs
│   ├── testcases_classifier.py                  # TC classification (violated/non-violated)
│   ├── testcases_selector.py                    # Diversity-optimized TC selection
│   ├── results_table_gen.py                     # Markdown/LaTeX table generation
│   └── conf/                                    # Configuration files (TOML)
├── explanation/                                  # Python implementation (~5,944 LOC, 34 files)
│   ├── models/                                  # Extended data models + builders
│   ├── operations/                              # Diagnosis operations + SAT4J support
│   │   └── algorithms/                          # FastDiag(P), WipeOutR(FM/T), profiler
│   └── transformations/                         # DIMACS, FM, testsuite readers
├── tests/                                        # Python test suite (4 files + 14 resources)
│   ├── test_diagnosis.py
│   ├── test_profiler.py
│   ├── test_utils.py
│   └── resources/                               # Test fixtures (FM, testcases, DIMACS)
├── data/                                         # Feature models and test cases
│   ├── ijcai24_25/                              # Primary dataset (IJCAI 2024-2025)
│   │   ├── data/fms/                            # Feature models (.splx)
│   │   ├── data/classifiedTS/                   # Classified test suites
│   │   ├── data/testsuite/                      # Raw test suites
│   │   ├── data/scenarios/                      # Test cases (.testcases)
│   │   ├── data/wcnf/                           # WCNF/DIMACS/UVL models + scenarios
│   │   └── results/                             # Evaluation results
│   ├── realworld/                               # Real-world models (legacy)
│   └── synthesized/                             # Synthetic scenarios (legacy)
├── solver_apps/                                  # External SAT solvers
│   └── org.sat4j.core.jar                       # SAT4J solver library
└── docs/                                         # Documentation
```

## Core Algorithms

**KBDiag**: Main diagnosis algorithm computing all minimal diagnoses by finding maximal satisfiable subsets of constraints.

**FastDiag**: Optimized diagnosis for simpler cases using binary search over constraint sets.

**FastDiagP**: FastDiag variant with pruning for improved performance on specific constraint structures.

**QuickXPlain**: Efficient conflict detection computing minimal unsatisfiable subsets (both standalone and with test cases).

**WipeOutR**: Advanced algorithms for removing redundant constraints (feature models and test case variants).

**Syntactic Relevance**: Optimization technique reducing search space through syntactic feature model analysis.

**HS-DAG**: Hitting Set DAG framework computing all diagnoses through shared computation paths with multiple labelers.

## Datasets

- **jiis** (current): 9 feature models in UVL format with diversity-optimized test scenarios (630 test case files across 7 cardinalities)
- **ijcai24_25** (primary): 4 models (DELL, ubuntu, windows8, REAL-FM-11) in SPLOT, UVL, WCNF, DIMACS with 7 test case sizes
- **realworld**: Additional real-world models (legacy)
- **synthesized**: 126 synthetically generated scenarios (legacy)

## Research Context

This implementation corresponds to research published in:
- IJCAI 2019: Model-based diagnosis with multiple observations
- AAAI 2023-2024: HS-DAG evaluation and syntactic relevance optimization
- IJCAI 2024-2025: Recent improvements and Python implementation

## License

MIT License. Copyright 2023-2026 Viet-Man Le.

## Contributing

For development guidelines, see [code-standards.md](./docs/code-standards.md) and [CLAUDE.md](./CLAUDE.md).
