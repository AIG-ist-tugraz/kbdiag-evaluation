# KBDiag

Model-based diagnosis system for knowledge bases with multiple observations.

## Overview

KBDiag is a research tool for identifying conflicts and inconsistencies in constraint-based knowledge bases, particularly feature models. The system implements multiple diagnosis algorithms to compute maximal satisfiable subsets (MSS) and minimal unsatisfiable subsets (MUS) when test cases violate knowledge base constraints.

Developed at TU Graz by Viet-Man Le. Licensed under MIT.

## Key Features

- **Core Diagnosis Algorithms**: KBDiag, FastDiag, FastDiagP, QuickXPlain, and Syntactic Relevance
- **Advanced Algorithms**: WipeOutR variants (feature model and test case optimization)
- **Hitting Set DAG (HS-DAG)**: Efficiently computes all diagnoses through shared computations with multiple labelers
- **SAT Solver Integration**: Choco (Java), PySAT (Python), and SAT4J solver support
- **Dual Implementation**: Both Java (primary, ~10.6K LOC) and expanded Python (~3.5K LOC in explanation/ module)
- **Evaluation Framework**: Comprehensive benchmarking against real-world and synthetic feature models
- **Comprehensive Testing**: Automated tests in tests/ directory with 14 resource files

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

# Run evaluation
python -m apps.kbdiag_eval apps/conf/kbdiag_eval.toml

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
├── src/main/java/at/tugraz/ist/ase/kbdiag/     # Java implementation (~10.6K LOC)
│   ├── debugging/algorithms/                     # Core diagnosis algorithms
│   ├── apps/real/                               # Evaluation framework
│   └── common/                                   # Shared utilities
├── apps/                                         # Evaluation scripts
│   ├── kbdiag_eval.py                           # TOML-driven evaluation
│   └── conf/kbdiag_eval.toml                    # Default config
├── explanation/                                  # Python implementation (~3.5K LOC, 42 files)
│   ├── models/                                  # Extended data models
│   ├── operations/                              # Advanced algorithms + SAT4J support
│   │   └── algorithms/                          # FastDiag, FastDiagP, WipeOutR, profiling
│   └── transformations/                         # DIMACS, FM conversions
├── tests/                                        # Comprehensive test suite (4 files + 14 resources)
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

- **ijcai24_25** (primary): 4 feature models (DELL, ubuntu, windows8, REAL-FM-11) in multiple formats (SPLOT, UVL, DIMACS, WCNF) with test cases at 7 sizes (5, 10, 25, 50, 100, 250, 500)
- **realworld**: Additional real-world feature models (legacy)
- **synthesized**: 126 synthetically generated test scenarios (legacy)

## Research Context

This implementation corresponds to research published in:
- IJCAI 2019: Model-based diagnosis with multiple observations
- AAAI 2023-2024: HS-DAG evaluation and syntactic relevance optimization
- IJCAI 2024-2025: Recent improvements and Python implementation

## License

MIT License. Copyright 2023-2025 Viet-Man Le.

## Contributing

For development guidelines, see [code-standards.md](./docs/code-standards.md) and [CLAUDE.md](./CLAUDE.md).
