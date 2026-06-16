#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

"""Generate Table 3 and Table 4 from evaluation results as markdown + LaTeX.

Reads a TOML config specifying algorithms, KBs, and table settings.
Parses result files, averages across iterations, and outputs formatted tables.

Usage:
    python -m apps.results_table_gen apps/conf/table_gen.toml
"""

import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

ROOT_PROJECT_FOLDER = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AlgorithmConfig:
    key: str
    display_name: str
    lam: int = 0  # lambda parameter (0 = not applicable)


@dataclass
class KBConfig:
    name: str
    display_name: str
    num_constraints: int = 0
    total_diagnoses: int = 0
    table4_test_size: int = 25


@dataclass
class Table3Config:
    enabled: bool
    test_sizes: List[int]
    groups: List[List[str]]


@dataclass
class Table4Config:
    enabled: bool
    leading_diagnoses: List[int]


@dataclass
class Table7KBConfig:
    """Per-KB config for Table 7 (ratio-varied speedup table).

    Includes version_suffix to filter scenarios when multiple versions
    exist per cardinality (e.g., linux rev1 has both _0 and _1).
    """
    name: str
    display_name: str
    num_constraints: int = 0
    version_suffix: int = 0  # filter scenarios to this version index


@dataclass
class Table7Config:
    """Table 7 (Concern 2 rebuttal): speedup = HSDAG_time / KBDiag_time
    across ratios (columns) × cardinalities (rows), 1 sub-table per KB.
    """
    enabled: bool
    result_paths: Dict[str, Path]  # ratio_key (e.g. "r10") → result root
    cardinalities: List[int]
    kbs: List[Table7KBConfig]


@dataclass
class Table8KBConfig:
    """Per-KB config for Table 8 (Diagnosis Quality)."""
    name: str          # internal name (e.g. "REAL-FM-11")
    display_name: str  # paper alias (e.g. "HIS")


@dataclass
class Table8Config:
    """Table 8 (Phase 1 / Concern 1): diagnosis quality per KB.

    Combines per-KB summary counts (comparable / identical / mismatch) with
    per-scenario mismatch rank details from verify reports.
    """
    enabled: bool
    results_dir: Path           # source for comparable/identical counts
    verify_baseline: Path        # rev1 cap=10 verify report
    verify_mismatches: Path      # cap=130 verify report
    kbs: List[Table8KBConfig]


@dataclass
class Table9Config:
    """Table 9 (Phase 4): cognitive load by testcase size."""
    enabled: bool
    compare_m_report: Path       # compare-kbdiag-m.txt
    overhead_report: Path        # verify-m2-overhead.txt
    test_sizes: List[int]        # rows to emit (e.g. [5, 10, 25, 50, 100, 250, 500])


@dataclass
class TableGenConfig:
    result_path: Path
    output_path: Path
    table3: Table3Config
    table4: Table4Config
    table7: Optional['Table7Config']
    table8: Optional['Table8Config']
    table9: Optional['Table9Config']
    algorithms: List[AlgorithmConfig]
    kbs: List[KBConfig]


def load_config(config_path: str) -> TableGenConfig:
    """Load and validate TOML config."""
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    general = raw["general"]
    result_path = ROOT_PROJECT_FOLDER / general["result_path"]
    output_path = ROOT_PROJECT_FOLDER / general["output_path"]

    t3 = raw["table3"]
    table3 = Table3Config(
        enabled=t3["enabled"],
        test_sizes=t3["test_sizes"],
        groups=t3["groups"],
    )

    t4 = raw["table4"]
    table4 = Table4Config(
        enabled=t4["enabled"],
        leading_diagnoses=t4["leading_diagnoses"],
    )

    algorithms = []
    for a in raw["algorithm"]:
        algorithms.append(AlgorithmConfig(
            key=a["key"],
            display_name=a["display_name"],
            lam=a.get("lambda", 0),
        ))

    kbs = []
    for k in raw["kb"]:
        kbs.append(KBConfig(
            name=k["name"],
            display_name=k["display_name"],
            num_constraints=k.get("num_constraints", 0),
            total_diagnoses=k.get("total_diagnoses", 0),
            table4_test_size=k.get("table4_test_size", 25),
        ))

    # Optional [table7] section for Concern 2 rebuttal
    table7: Optional[Table7Config] = None
    if "table7" in raw:
        t7 = raw["table7"]
        t7_paths = {
            k: ROOT_PROJECT_FOLDER / v for k, v in t7["result_paths"].items()
        }
        t7_kbs = [Table7KBConfig(
            name=k["name"],
            display_name=k["display_name"],
            num_constraints=k.get("num_constraints", 0),
            version_suffix=k.get("version_suffix", 0),
        ) for k in t7["kb"]]
        table7 = Table7Config(
            enabled=t7.get("enabled", True),
            result_paths=t7_paths,
            cardinalities=t7["cardinalities"],
            kbs=t7_kbs,
        )

    # Optional [table8] section (Phase 1 — Diagnosis Quality)
    table8: Optional[Table8Config] = None
    if "table8" in raw:
        t8 = raw["table8"]
        t8_kbs = [Table8KBConfig(
            name=k["name"],
            display_name=k["display_name"],
        ) for k in t8["kb"]]
        table8 = Table8Config(
            enabled=t8.get("enabled", True),
            results_dir=ROOT_PROJECT_FOLDER / t8["results_dir"],
            verify_baseline=ROOT_PROJECT_FOLDER / t8["verify_baseline"],
            verify_mismatches=ROOT_PROJECT_FOLDER / t8["verify_mismatches"],
            kbs=t8_kbs,
        )

    # Optional [table9] section (Phase 4 — Cognitive Load)
    table9: Optional[Table9Config] = None
    if "table9" in raw:
        t9 = raw["table9"]
        table9 = Table9Config(
            enabled=t9.get("enabled", True),
            compare_m_report=ROOT_PROJECT_FOLDER / t9["compare_m_report"],
            overhead_report=ROOT_PROJECT_FOLDER / t9["overhead_report"],
            test_sizes=t9["test_sizes"],
        )

    return TableGenConfig(
        result_path=result_path,
        output_path=output_path,
        table3=table3,
        table4=table4,
        table7=table7,
        table8=table8,
        table9=table9,
        algorithms=algorithms,
        kbs=kbs,
    )


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------

@dataclass
class Task1Result:
    kb: str
    testcases_file: str
    cc: int
    runtime_s: float
    diag_size: int = -1  # -1 = not parsed; 0 = empty diagnosis (anomaly: treat as T/O)
    timeout: bool = False


@dataclass
class TaskAllResult:
    kb: str
    testcases_file: str
    diagnosis_times: List[float]  # per-diagnosis t= values (seconds)
    num_diagnoses: int
    cc: int
    runtime_s: float
    timeout: bool = False


# Regex patterns
HEADER_RE = re.compile(r"^(\S+)\s+(\S+\.testcases)\s*$")
CC_RE = re.compile(r"^\tCC:\s+(\d+)")
RUNTIME_RE = re.compile(r"^\t.+runtime:\s+([\d.]+)\s+s")
DIAG_TIME_RE = re.compile(r"^\tDiagnosis\s+\d+\s+\(.*?t=([\d.]+)s\)")
NUM_DIAG_RE = re.compile(r"^\t#Diagnoses:\s+(\d+)")
TIMEOUT_RE = re.compile(r"^\t(Diag:\s*TO|Time:.*timeout)", re.IGNORECASE)
DIAG_SIZE_RE = re.compile(r"^\t\|D\|:\s+(\d+)")


def _split_into_blocks(filepath: Path) -> List[List[str]]:
    """Split a result file into blocks, each starting with a header line."""
    blocks: List[List[str]] = []
    current: List[str] = []

    with open(filepath) as f:
        for line in f:
            line = line.rstrip("\n")
            if HEADER_RE.match(line):
                if current:
                    blocks.append(current)
                current = [line]
            else:
                current.append(line)

    if current:
        blocks.append(current)
    return blocks


def parse_task1_file(filepath: Path) -> List[Task1Result]:
    """Parse a task=1 result file into a list of per-iteration results."""
    if not filepath.exists():
        return []

    results = []
    for block in _split_into_blocks(filepath):
        m = HEADER_RE.match(block[0])
        if not m:
            continue
        kb, tc_file = m.group(1), m.group(2)

        cc, runtime, diag_size, is_timeout = 0, 0.0, -1, False
        for line in block[1:]:
            if TIMEOUT_RE.match(line):
                is_timeout = True
                continue
            cm = CC_RE.match(line)
            if cm:
                cc = int(cm.group(1))
            rm = RUNTIME_RE.match(line)
            if rm:
                runtime = float(rm.group(1))
            dm = DIAG_SIZE_RE.match(line)
            if dm:
                diag_size = int(dm.group(1))

        results.append(Task1Result(kb=kb, testcases_file=tc_file,
                                   cc=cc, runtime_s=runtime,
                                   diag_size=diag_size, timeout=is_timeout))
    return results


def parse_task_all_file(filepath: Path) -> List[TaskAllResult]:
    """Parse a task=all result file into a list of per-iteration results."""
    if not filepath.exists():
        return []

    results = []
    for block in _split_into_blocks(filepath):
        m = HEADER_RE.match(block[0])
        if not m:
            continue
        kb, tc_file = m.group(1), m.group(2)

        diag_times: List[float] = []
        num_diag, cc, runtime, is_timeout = 0, 0, 0.0, False

        for line in block[1:]:
            if TIMEOUT_RE.match(line):
                is_timeout = True
                continue
            dm = DIAG_TIME_RE.match(line)
            if dm:
                diag_times.append(float(dm.group(1)))
                continue
            nm = NUM_DIAG_RE.match(line)
            if nm:
                num_diag = int(nm.group(1))
                continue
            cm = CC_RE.match(line)
            if cm:
                cc = int(cm.group(1))
                continue
            rm = RUNTIME_RE.match(line)
            if rm:
                runtime = float(rm.group(1))

        results.append(TaskAllResult(
            kb=kb, testcases_file=tc_file,
            diagnosis_times=diag_times, num_diagnoses=num_diag,
            cc=cc, runtime_s=runtime, timeout=is_timeout,
        ))
    return results


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _extract_test_size(tc_file: str) -> int:
    """Extract test size from filename like 'DELL_c25_0.testcases'."""
    m = re.search(r"_c(\d+)_", tc_file)
    return int(m.group(1)) if m else 0


def _result_file_path(config: TableGenConfig, algo: AlgorithmConfig,
                      kb_name: str, task: str) -> Path:
    """Build path to a result file."""
    suffix = "_m2" if algo.key == "kbdiag_m2" else ""
    algo_key = "kbdiag" if algo.key == "kbdiag_m2" else algo.key
    filename = f"results_{algo_key}_{kb_name}{suffix}_{task}.txt"
    return config.result_path / task / filename


TIMEOUT_SENTINEL = (float("inf"), float("inf"))

# key: (algo_key, kb_name, test_size), value: (avg_cc, avg_runtime_ms) or TIMEOUT_SENTINEL
Task1Data = Dict[Tuple[str, str, int], Tuple[float, float]]


def aggregate_task1(config: TableGenConfig) -> Task1Data:
    """Parse all task=1 files and average across iterations.

    Runtime correction: the task=1 file's "<algo> runtime: X s" line is only
    reliably the first-diag time for diagnosis-type labelers (kbdiag). For
    conflict-type labelers like quickxplain_with_testcases (HSDAG-wrapped),
    HSDAG.compute() runs once and emits N diagnoses internally, so the runtime
    line equals TOTAL compute time — not first-diag time — when the file was
    populated via task=all dual-output. The per-diagnosis cumulative time
    `Diagnosis 1 (t=X.XXs)` in the task=all file IS the correct first-diag
    time (always, for both labeler families). When a task=all file exists,
    prefer its diagnosis_times[0] for the runtime metric.
    """
    data: Task1Data = {}

    for algo in config.algorithms:
        for kb in config.kbs:
            task1_path = _result_file_path(config, algo, kb.name, "1")
            taskall_path = _result_file_path(config, algo, kb.name, "all")
            results_1 = parse_task1_file(task1_path)
            results_all = parse_task_all_file(taskall_path)
            if not results_1:
                continue

            # Build lookup: tc_file → list of first-diag times across iterations
            # (only entries with non-empty diagnosis_times and no timeout).
            first_diag_times: Dict[str, List[float]] = {}
            for r in results_all:
                if not r.timeout and r.diagnosis_times:
                    first_diag_times.setdefault(
                        r.testcases_file, []
                    ).append(r.diagnosis_times[0])

            # Group task=1 results by tc_file for n_iter averaging
            groups: Dict[str, List[Task1Result]] = {}
            for r in results_1:
                groups.setdefault(r.testcases_file, []).append(r)

            for tc_file, iters in groups.items():
                size = _extract_test_size(tc_file)
                if any(r.timeout for r in iters):
                    data[(algo.key, kb.name, size)] = TIMEOUT_SENTINEL
                else:
                    avg_cc = sum(r.cc for r in iters) / len(iters)
                    # Prefer task=all's per-diagnosis t= for the first diag —
                    # it is the authoritative first-diag time for both labeler
                    # families. Fall back to task=1 file's runtime line only
                    # when task=all data is unavailable.
                    corrected_times = first_diag_times.get(tc_file)
                    if corrected_times:
                        avg_runtime_ms = (
                            sum(corrected_times) / len(corrected_times) * 1000
                        )
                    else:
                        avg_runtime_ms = (
                            sum(r.runtime_s for r in iters)
                            / len(iters) * 1000
                        )
                    data[(algo.key, kb.name, size)] = (avg_cc, avg_runtime_ms)

    return data


def _is_cumulative(times: List[float]) -> bool:
    """Check if per-diagnosis times are cumulative (monotonically non-decreasing)."""
    if len(times) <= 1:
        return True
    return all(times[i] <= times[i + 1] * 1.01 for i in range(len(times) - 1))


def _time_for_n_leading(diag_times: List[float], n: int,
                        cumulative: bool) -> float:
    """Get wall-clock time (seconds) for first n diagnoses."""
    if n > len(diag_times):
        return float("nan")
    if cumulative:
        return diag_times[n - 1]
    else:
        return sum(diag_times[:n])


# key: (algo_key, kb_name, n_leading), value: avg_runtime_ms
TaskAllData = Dict[Tuple[str, str, int], float]


def aggregate_task_all(config: TableGenConfig) -> TaskAllData:
    """Parse all task=all files and compute n-leading-diagnosis times."""
    data: TaskAllData = {}
    leading_ns = config.table4.leading_diagnoses

    for algo in config.algorithms:
        for kb in config.kbs:
            filepath = _result_file_path(config, algo, kb.name, "all")
            results = parse_task_all_file(filepath)
            if not results:
                continue

            # Use per-KB test_size
            test_size = kb.table4_test_size

            # Filter to target test_size, skip timeouts
            target_results = [r for r in results
                              if _extract_test_size(r.testcases_file) == test_size
                              and not r.timeout]
            if not target_results:
                continue

            # Auto-detect cumulative vs incremental from first iteration
            cumulative = _is_cumulative(target_results[0].diagnosis_times)

            for n in leading_ns:
                times_per_iter = []
                for r in target_results:
                    t = _time_for_n_leading(r.diagnosis_times, n, cumulative)
                    if not math.isnan(t):
                        times_per_iter.append(t)

                if times_per_iter:
                    avg_ms = sum(times_per_iter) / len(times_per_iter) * 1000
                    data[(algo.key, kb.name, n)] = avg_ms

    return data


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_value(val: float, decimals: int = 2) -> str:
    """Format a numeric value: NaN -> '-', >=100 -> int, else -> *decimals* places."""
    if math.isnan(val):
        return "-"
    if decimals == 0 or val >= 100:
        return str(round(val))
    return f"{val:.{decimals}f}"


def _is_timeout(cc: float, runtime_ms: float) -> bool:
    """Check if values represent a timeout sentinel."""
    return cc == float("inf") or runtime_ms == float("inf")


def format_cell_table3(cc: float, runtime_ms: float) -> str:
    """Format as 'CC / runtime' or 'T/O' for timeouts."""
    if _is_timeout(cc, runtime_ms):
        return "T/O"
    return f"{format_value(cc, 0)} / {format_value(runtime_ms)}"


# ---------------------------------------------------------------------------
# Table 3 generators
# ---------------------------------------------------------------------------

def _algo_col_header(algo: AlgorithmConfig) -> str:
    """Short column header for an algorithm."""
    if algo.lam:
        return f"{algo.display_name} λ={algo.lam}"
    return algo.display_name


def _is_bold_algo(algo: AlgorithmConfig) -> bool:
    """MSD λ=1 gets bold formatting."""
    return algo.display_name == "MSD" and algo.lam == 1


def generate_table3_md(data: Task1Data, kb_names: List[str],
                       config: TableGenConfig, suffix: str) -> None:
    """Generate Table 3 markdown for a group of KBs."""
    kbs = [kb for kb in config.kbs if kb.name in kb_names]
    algos = config.algorithms
    lines: List[str] = []

    # Header row 1: KB grouping
    header1 = f"| |T_π|"
    for kb in kbs:
        label = kb.display_name
        if kb.num_constraints:
            label += f" (|C|={kb.num_constraints})"
        span = len(algos)
        header1 += f" | {label}" + " |" * (span - 1)
    header1 += " |"

    # Header row 2: algorithm columns
    header2 = "| |T_π|"
    for kb in kbs:
        for algo in algos:
            header2 += f" | {_algo_col_header(algo)}"
    header2 += " |"

    # Separator
    sep = "|---:" + "|---:" * (len(kbs) * len(algos)) + "|"

    lines.append(header1)
    lines.append(header2)
    lines.append(sep)

    # Data rows
    for size in config.table3.test_sizes:
        row = f"| {size}"
        for kb in kbs:
            for algo in algos:
                key = (algo.key, kb.name, size)
                if key in data:
                    cc, rt = data[key]
                    cell = format_cell_table3(cc, rt)
                else:
                    cell = "-"
                if _is_bold_algo(algo) and cell not in ("-", "T/O"):
                    cell = f"**{cell}**"
                row += f" | {cell}"
        row += " |"
        lines.append(row)

    outfile = config.output_path / f"table3{suffix}.md"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


def generate_table3_tex(data: Task1Data, kb_names: List[str],
                        config: TableGenConfig, suffix: str) -> None:
    """Generate Table 3 LaTeX for a group of KBs."""
    kbs = [kb for kb in config.kbs if kb.name in kb_names]
    algos = config.algorithms
    algo_cols = "r" * len(algos)
    col_spec = "r" + "|".join([algo_cols] * len(kbs))

    lines: List[str] = []
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")
    lines.append("\\scriptsize")
    lines.append(f"\\begin{{tabular}}{{|{col_spec}|}}")
    lines.append("\\hline")

    # Header row 1: multicolumn KB grouping
    hdr1 = "\\rotatebox{90}{$|T_\\pi|$}"
    for kb in kbs:
        label = kb.display_name
        if kb.num_constraints:
            label += f" ($|C|$={kb.num_constraints})"
        hdr1 += f" & \\multicolumn{{{len(algos)}}}{{c|}}{{{label}}}"
    hdr1 += " \\\\"
    lines.append(hdr1)

    # Header row 2: algorithm columns
    hdr2 = ""
    for kb in kbs:
        for algo in algos:
            hdr2 += f" & \\rotatebox{{90}}{{{_algo_col_header(algo)}}}"
    hdr2 += " \\\\"
    lines.append(hdr2)
    lines.append("\\hline")

    # Data rows
    for size in config.table3.test_sizes:
        row = str(size)
        for kb in kbs:
            for algo in algos:
                key = (algo.key, kb.name, size)
                if key in data:
                    cc, rt = data[key]
                    cell = format_cell_table3(cc, rt)
                else:
                    cell = "-"
                if _is_bold_algo(algo) and cell not in ("-", "T/O"):
                    cell = f"\\textbf{{{cell}}}"
                row += f" & {cell}"
        row += " \\\\"
        lines.append(row)

    lines.append("\\hline")
    lines.append("\\end{tabular}")
    lines.append(f"\\caption{{Table 3{suffix}: One minimal diagnosis}}")
    lines.append(f"\\label{{tab:table3{suffix}}}")
    lines.append("\\end{table}")

    outfile = config.output_path / f"table3{suffix}.tex"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


# ---------------------------------------------------------------------------
# Table 4 generators
# ---------------------------------------------------------------------------

def generate_table4_md(data: TaskAllData, config: TableGenConfig) -> None:
    """Generate Table 4 markdown."""
    kbs = config.kbs
    algos = config.algorithms
    lines: List[str] = []

    # Header row 1: KB grouping with per-KB |T_π|
    header1 = "| n"
    for kb in kbs:
        parts = [f"|T_π|={kb.table4_test_size}"]
        if kb.num_constraints:
            parts.append(f"|C|={kb.num_constraints}")
        if kb.total_diagnoses:
            parts.append(f"|Δ|={kb.total_diagnoses}")
        label = f"{kb.display_name} ({', '.join(parts)})"
        header1 += f" | {label}" + " |" * (len(algos) - 1)
    header1 += " |"

    # Header row 2: algorithm columns
    header2 = "| n"
    for kb in kbs:
        for algo in algos:
            header2 += f" | {_algo_col_header(algo)}"
    header2 += " |"

    sep = "|---:" + "|---:" * (len(kbs) * len(algos)) + "|"

    lines.append(header1)
    lines.append(header2)
    lines.append(sep)

    # Data rows
    for n in config.table4.leading_diagnoses:
        row = f"| {n}"
        for kb in kbs:
            for algo in algos:
                key = (algo.key, kb.name, n)
                if key in data:
                    cell = format_value(data[key])
                else:
                    cell = "-"
                if _is_bold_algo(algo) and cell != "-":
                    cell = f"**{cell}**"
                row += f" | {cell}"
        row += " |"
        lines.append(row)

    outfile = config.output_path / "table4.md"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


def generate_table4_tex(data: TaskAllData, config: TableGenConfig) -> None:
    """Generate Table 4 LaTeX."""
    kbs = config.kbs
    algos = config.algorithms
    algo_cols = "r" * len(algos)
    col_spec = "r" + "|".join([algo_cols] * len(kbs))

    lines: List[str] = []
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")
    lines.append("\\scriptsize")
    lines.append(f"\\begin{{tabular}}{{|{col_spec}|}}")
    lines.append("\\hline")

    # Header row 1: multicolumn KB grouping with per-KB |T_π|
    hdr1 = "\\rotatebox{90}{$n$}"
    for kb in kbs:
        # parts = [f"$|T_\\pi|$={kb.table4_test_size}"]
        # if kb.num_constraints:
        #     parts.append(f"$|C|$={kb.num_constraints}")
        # if kb.total_diagnoses:
        #     parts.append(f"$|\\Delta|$={kb.total_diagnoses}")
        label = f"{kb.display_name}"
        hdr1 += f" & \\multicolumn{{{len(algos)}}}{{c|}}{{{label}}}"
    hdr1 += " \\\\"
    lines.append(hdr1)

    # Sub header row 1 - test size, constraints, diagnoses
    sub_hdr1 = ""
    for kb in kbs:
        parts = [f"$|T_\\pi|$={kb.table4_test_size}"]
        if kb.num_constraints:
            parts.append(f"$|C|$={kb.num_constraints}")
        if kb.total_diagnoses:
            parts.append(f"$|\\Delta|$={kb.total_diagnoses}")
        label = f"({', '.join(parts)})"
        sub_hdr1 += f" & \\multicolumn{{{len(algos)}}}{{c|}}{{{label}}}"
    sub_hdr1 += " \\\\"
    lines.append(sub_hdr1)

    # Header row 2: algorithm columns
    hdr2 = ""
    for kb in kbs:
        for algo in algos:
            hdr2 += f" & \\rotatebox{{90}}{{{_algo_col_header(algo)}}}"
    hdr2 += " \\\\"
    lines.append(hdr2)
    lines.append("\\hline")

    # Data rows
    for n in config.table4.leading_diagnoses:
        row = str(n)
        for kb in kbs:
            for algo in algos:
                key = (algo.key, kb.name, n)
                if key in data:
                    cell = format_value(data[key])
                else:
                    cell = "-"
                if _is_bold_algo(algo) and cell != "-":
                    cell = f"\\textbf{{{cell}}}"
                row += f" & {cell}"
        row += " \\\\"
        lines.append(row)

    lines.append("\\hline")
    lines.append("\\end{tabular}")
    lines.append("\\caption{Table 4: $n$ leading diagnoses}")
    lines.append("\\label{tab:table4}")
    lines.append("\\end{table}")

    outfile = config.output_path / "table4.tex"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


# ---------------------------------------------------------------------------
# Table 7 (Concern 2 rebuttal): speedup across ratios
# ---------------------------------------------------------------------------

# key: (ratio_key, kb_name, cardinality), value: speedup = hsdag_ms / kbdiag_ms
#   float('inf') = T/O on either side; missing key = data not available
Table7Data = Dict[Tuple[str, str, int], float]


def _avg_runtime_ms(results: List[Task1Result], tc_file: str) -> Optional[float]:
    """Average runtime across iterations of a specific testcase file.

    Returns None if no iterations found, float('inf') if any iter:
    - is a timeout, OR
    - has empty diagnosis (|D|=0) — anomaly treated as T/O per Cowork 2026-05-25 12:00
      (e.g. HIS r30 c500 finished in 356s but found no diagnoses).
    """
    iters = [r for r in results if r.testcases_file == tc_file]
    if not iters:
        return None
    if any(r.timeout for r in iters):
        return float("inf")
    if any(r.diag_size == 0 for r in iters):
        return float("inf")
    return sum(r.runtime_s for r in iters) / len(iters) * 1000


def aggregate_table7(t7: Table7Config) -> Table7Data:
    """For each (ratio, kb, cardinality) compute speedup = HSDAG/KBDiag.

    Reads from t7.result_paths[ratio] / "1" / results_<algo>_<kb>_1.txt.
    Filters scenarios to kb.version_suffix for cross-ratio comparability.
    """
    data: Table7Data = {}

    for ratio_key, root in t7.result_paths.items():
        for kb in t7.kbs:
            kbdiag_path = root / "1" / f"results_kbdiag_{kb.name}_1.txt"
            hsdag_path = root / "1" / f"results_quickxplain_with_testcases_{kb.name}_1.txt"
            kbdiag_results = parse_task1_file(kbdiag_path)
            hsdag_results = parse_task1_file(hsdag_path)
            if not kbdiag_results or not hsdag_results:
                # missing input files → leave cells absent
                continue

            for card in t7.cardinalities:
                tc_file = f"{kb.name}_c{card}_{kb.version_suffix}.testcases"
                kbdiag_ms = _avg_runtime_ms(kbdiag_results, tc_file)
                hsdag_ms = _avg_runtime_ms(hsdag_results, tc_file)
                if kbdiag_ms is None or hsdag_ms is None:
                    continue
                # T/O on either side → T/O sentinel
                if math.isinf(kbdiag_ms) or math.isinf(hsdag_ms):
                    data[(ratio_key, kb.name, card)] = float("inf")
                elif kbdiag_ms <= 0:
                    data[(ratio_key, kb.name, card)] = float("nan")
                else:
                    data[(ratio_key, kb.name, card)] = hsdag_ms / kbdiag_ms

    return data


def format_speedup(speedup: float) -> str:
    """Compact format: T/O / "-" / 0.17 / 1.7 / 14 / 220 / 1.2k / 14k.

    Picks decimals/suffix by magnitude to keep cell width small.
    """
    if math.isnan(speedup):
        return "-"
    if math.isinf(speedup):
        return "T/O"
    if speedup < 1.0:
        return f"{speedup:.2f}"
    if speedup < 10.0:
        return f"{speedup:.1f}"
    if speedup < 1000.0:
        return f"{speedup:.0f}"
    if speedup < 10000.0:
        return f"{speedup/1000:.1f}k"
    return f"{speedup/1000:.0f}k"


def _ratio_label_md(ratio_key: str) -> str:
    """e.g. 'r10' → 'r=10%'."""
    digits = "".join(ch for ch in ratio_key if ch.isdigit())
    return f"r={digits}%"


def _ratio_label_tex(ratio_key: str) -> str:
    """e.g. 'r10' → '$r$=10\\%' for LaTeX."""
    digits = "".join(ch for ch in ratio_key if ch.isdigit())
    return f"$r$={digits}\\%"


def generate_table7_md(data: Table7Data, t7: Table7Config,
                       config: TableGenConfig) -> None:
    """Unified Markdown table: KB | Card | r10 | r20 | r30 | r50.

    KB column repeats per-row (Markdown lacks multirow); LaTeX version uses
    \\multirow for cleaner visual grouping.
    """
    ratios = list(t7.result_paths.keys())  # preserves config order
    lines: List[str] = []

    # Header
    header = "| KB | |T_π|"
    for r in ratios:
        header += f" | {_ratio_label_md(r)}"
    header += " |"
    sep = "|:---|---:" + "|---:" * len(ratios) + "|"
    lines.append(header)
    lines.append(sep)

    # Rows: one per (KB, cardinality)
    for kb in t7.kbs:
        for card in t7.cardinalities:
            row = f"| {kb.display_name} | {card}"
            for r in ratios:
                key = (r, kb.name, card)
                cell = format_speedup(data[key]) if key in data else "-"
                row += f" | {cell}"
            row += " |"
            lines.append(row)

    outfile = config.output_path / "table7.md"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


def generate_table7_tex(data: Table7Data, t7: Table7Config,
                        config: TableGenConfig) -> None:
    """Unified LaTeX table: multirow KB column + cardinality + ratios."""
    ratios = list(t7.result_paths.keys())
    n_cards = len(t7.cardinalities)
    col_spec = "l|r|" + "r" * len(ratios)

    lines: List[str] = []
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")
    lines.append("\\scriptsize")
    lines.append(f"\\begin{{tabular}}{{|{col_spec}|}}")
    lines.append("\\hline")

    # Header row
    hdr = "KB & $|T_\\pi|$"
    for r in ratios:
        hdr += f" & {_ratio_label_tex(r)}"
    hdr += " \\\\"
    lines.append(hdr)
    lines.append("\\hline")

    # Data rows: multirow KB cell + cardinality rows
    for kb_idx, kb in enumerate(t7.kbs):
        for card_idx, card in enumerate(t7.cardinalities):
            if card_idx == 0:
                kb_label = f"\\multirow{{{n_cards}}}{{*}}{{{kb.display_name}}}"
            else:
                kb_label = ""
            row = f"{kb_label} & {card}"
            for r in ratios:
                key = (r, kb.name, card)
                cell = format_speedup(data[key]) if key in data else "-"
                row += f" & {cell}"
            row += " \\\\"
            lines.append(row)
        # \hline between KB groups (except after last)
        if kb_idx < len(t7.kbs) - 1:
            lines.append("\\hline")

    lines.append("\\hline")
    lines.append("\\end{tabular}")
    lines.append("\\caption{Table 7: speedup factors (HSDAG/MSSDirect) across inconsistency ratios}")
    lines.append("\\label{tab:table7}")
    lines.append("\\end{table}")

    outfile = config.output_path / "table7.tex"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


# Expected values from Cowork 2026-05-25 12:00 progress entry — used for
# generator validation. Mismatch → warning printed.
TABLE7_EXPECTED = {
    ("HIS", 10):  {"r10": "1.7",  "r20": "2.4",   "r30": "1.6",  "r50": "3.0"},
    ("HIS", 25):  {"r10": "2.0",  "r20": "2.1",   "r30": "1.4",  "r50": "14"},
    ("HIS", 50):  {"r10": "1.7",  "r20": "5.5",   "r30": "1.7",  "r50": "14k"},
    ("HIS", 100): {"r10": "2.5",  "r20": "217",   "r30": "55",   "r50": "T/O"},
    ("HIS", 250): {"r10": "17",   "r20": "T/O",   "r30": "6.6k", "r50": "T/O"},
    ("HIS", 500): {"r10": "74",   "r20": "T/O",   "r30": "T/O",  "r50": "T/O"},
    ("Win8", 10):  {"r10": "0.92", "r20": "1.8",  "r30": "0.94", "r50": "1.3"},
    ("Win8", 25):  {"r10": "1.1",  "r20": "3.1",  "r30": "1.6",  "r50": "9.7"},
    ("Win8", 50):  {"r10": "1.4",  "r20": "11",   "r30": "27",   "r50": "114"},
    ("Win8", 100): {"r10": "2.4",  "r20": "18",   "r30": "21",   "r50": "73"},
    ("Win8", 250): {"r10": "5.5",  "r20": "7.2",  "r30": "8.4",  "r50": "19"},
    ("Win8", 500): {"r10": "4.0",  "r20": "3.2",  "r30": "2.8",  "r50": "6.3"},
    ("Linux", 10):  {"r10": "0.03", "r20": "0.07", "r30": "0.09", "r50": "0.20"},
    ("Linux", 25):  {"r10": "0.08", "r20": "0.18", "r30": "0.33", "r50": "0.66"},
    ("Linux", 50):  {"r10": "0.17", "r20": "0.33", "r30": "25",   "r50": "83"},
    ("Linux", 100): {"r10": "0.34", "r20": "5.3",  "r30": "T/O",  "r50": "T/O"},
    ("Linux", 250): {"r10": "1.1",  "r20": "T/O",  "r30": "T/O",  "r50": "T/O"},
    ("Linux", 500): {"r10": "T/O",  "r20": "T/O",  "r30": "T/O",  "r50": "T/O"},
}


def validate_table7(data: Table7Data, t7: Table7Config) -> None:
    """Compare generated values against Cowork's expected table; log discrepancies."""
    mismatches = []
    for kb in t7.kbs:
        for card in t7.cardinalities:
            expected_row = TABLE7_EXPECTED.get((kb.display_name, card))
            if expected_row is None:
                continue
            for r in t7.result_paths.keys():
                expected = expected_row.get(r)
                if expected is None:
                    continue
                actual = format_speedup(data[(r, kb.name, card)]) if (r, kb.name, card) in data else "-"
                if actual != expected:
                    mismatches.append(f"  {kb.display_name} c={card} {r}: expected {expected!r}, got {actual!r}")
    if mismatches:
        print(f"  ⚠ {len(mismatches)} discrepancies vs Cowork expected values:")
        for m in mismatches:
            print(m)
    else:
        print("  ✓ All values match Cowork's expected table (12:00 progress entry)")


# ---------------------------------------------------------------------------
# Table 8 (Phase 1 — Diagnosis Quality)
# ---------------------------------------------------------------------------

# Row: (kb_display, comparable, identical, mismatch, mismatch_details_str)
Table8Row = Tuple[str, int, int, int, str]


# Parses a ranking-summary line from a verify report, e.g.:
#   "DELL         DELL_c25_0.testcases                     5      10  exact #4/10"
# Returns (kb, tc_file, rank_info_str) or None.
_VERIFY_RANK_RE = re.compile(
    r"^(\S+)\s+(\S+\.testcases)\s+\d+\s+\d+\s+(exact\s+#\d+/\d+|constraint-level.*)$"
)


def parse_verify_ranks(filepath: Path) -> Dict[str, str]:
    """Extract scenario → rank-info from a verify report's RANKING SUMMARY section.

    Returns dict: tc_file (e.g. "DELL_c25_0.testcases") → "#4/10" (or
    "constraint-level: ..." for Tier 2 entries).
    """
    if not filepath.exists():
        return {}
    in_table = False
    ranks: Dict[str, str] = {}
    for line in filepath.read_text().splitlines():
        if "RANKING SUMMARY" in line:
            in_table = True
            continue
        if not in_table:
            continue
        m = _VERIFY_RANK_RE.match(line)
        if m:
            tc_file = m.group(2)
            rank_info = m.group(3)
            # Normalize "exact #N/M" → "#N/M"; keep "constraint-level..." as-is
            short = (rank_info.replace("exact ", "")
                     if rank_info.startswith("exact ") else rank_info)
            ranks[tc_file] = short
    return ranks


def _count_kb_comparable(results_dir: Path, kb_name: str) -> Tuple[int, set, set]:
    """For a given KB, return (comparable_count, comparable_tc_set, mismatch_tc_set).

    A scenario is 'comparable' if both kbdiag and qxwithtc completed
    (neither timed out). 'Mismatch' set is filled by aggregate_table8 later.
    """
    kbdiag_file = results_dir / f"results_kbdiag_{kb_name}_1.txt"
    hsdag_file = results_dir / f"results_quickxplain_with_testcases_{kb_name}_1.txt"

    def get_scenarios(filepath):
        scenarios = {}  # tc -> is_timeout
        for line in filepath.read_text().splitlines():
            m = HEADER_RE.match(line)
            if m:
                tc = m.group(2)
                scenarios.setdefault(tc, False)
                current = tc
            elif TIMEOUT_RE.match(line):
                # caller's loop already iterating in order; mark last-seen tc
                # (TIMEOUT lines appear inside a block following its header)
                pass
        # Second pass: detect timeouts per block
        current = None
        for line in filepath.read_text().splitlines():
            m = HEADER_RE.match(line)
            if m:
                current = m.group(2)
            elif current and TIMEOUT_RE.match(line):
                scenarios[current] = True
        return scenarios

    if not kbdiag_file.exists() or not hsdag_file.exists():
        return (0, set(), set())

    kbdiag_s = get_scenarios(kbdiag_file)
    hsdag_s = get_scenarios(hsdag_file)
    common = set(kbdiag_s) & set(hsdag_s)
    comparable_tcs = {tc for tc in common
                      if not kbdiag_s[tc] and not hsdag_s[tc]}
    return (len(comparable_tcs), comparable_tcs, set())


def aggregate_table8(t8: Table8Config) -> List[Table8Row]:
    """Build Table 8 rows + total. Mismatch ranks: prefer mismatches report
    (cap=130) over baseline (cap=10) when both reference the same scenario.
    """
    baseline_ranks = parse_verify_ranks(t8.verify_baseline)
    mismatch_ranks = parse_verify_ranks(t8.verify_mismatches)
    # Merge: mismatches (newer/higher-cap) overrides baseline
    all_ranks = dict(baseline_ranks)
    all_ranks.update(mismatch_ranks)

    rows: List[Table8Row] = []
    total_comparable, total_identical, total_mismatch = 0, 0, 0

    for kb in t8.kbs:
        comparable, comparable_tcs, _ = _count_kb_comparable(
            t8.results_dir, kb.name
        )
        # Mismatches for this KB = ranks-table entries with matching prefix.
        # (We use mismatch_ranks first, fall back to baseline_ranks for KBs
        # not re-run with cap>10 like DELL/REAL-FM-11/CNNl/linux.)
        mismatched_tcs = [
            tc for tc in all_ranks
            if tc in comparable_tcs and tc.startswith(kb.name + "_")
        ]
        mismatch = len(mismatched_tcs)
        identical = comparable - mismatch

        # Format mismatch details: "scenario_tag: rank; scenario_tag: rank"
        if mismatched_tcs:
            details = "; ".join(
                f"{_short_scenario(tc, kb.display_name)}: {all_ranks[tc]}"
                for tc in sorted(mismatched_tcs)
            )
        else:
            details = "—"

        rows.append((kb.display_name, comparable, identical, mismatch, details))
        total_comparable += comparable
        total_identical += identical
        total_mismatch += mismatch

    # Add Total row
    total_details = ("All mismatches: MSSDirect's diagnosis appears in "
                     "HSDAG's enumeration" if total_mismatch > 0 else "—")
    rows.append(("Total", total_comparable, total_identical, total_mismatch,
                 total_details))
    return rows


def _short_scenario(tc_file: str, kb_display: str) -> str:
    """Convert 'REAL-FM-4_c50_0.testcases' to 'B2C_c50_0' using KB display alias."""
    base = tc_file.replace(".testcases", "")
    # Replace the internal KB prefix with display alias (e.g. REAL-FM-4 -> B2C)
    parts = base.split("_", 1)
    if len(parts) == 2:
        return f"{kb_display}_{parts[1]}"
    return base


def generate_table8_md(rows: List[Table8Row], config: TableGenConfig) -> None:
    """Markdown Table 8."""
    lines = [
        "| KB | Comparable | Identical | Mismatch | Mismatch details |",
        "|:---|---:|---:|---:|:---|",
    ]
    for kb, comp, ident, mism, details in rows:
        if kb == "Total":
            lines.append(f"| **{kb}** | **{comp}** | **{ident}** | **{mism}** | {details} |")
        else:
            lines.append(f"| {kb} | {comp} | {ident} | {mism} | {details} |")
    outfile = config.output_path / "table8.md"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


def generate_table8_tex(rows: List[Table8Row], config: TableGenConfig) -> None:
    """LaTeX Table 8 using booktabs."""
    lines: List[str] = []
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")
    lines.append("\\scriptsize")
    lines.append("\\begin{tabular}{lrrrl}")
    lines.append("\\toprule")
    lines.append("KB & Comparable & Identical & Mismatch & Mismatch details \\\\")
    lines.append("\\midrule")
    for kb, comp, ident, mism, details in rows:
        # Escape LaTeX-special chars in details (underscores, sharps)
        d_tex = details.replace("_", "\\_").replace("#", "\\#")
        if kb == "Total":
            lines.append("\\midrule")
            lines.append(
                f"\\textbf{{{kb}}} & \\textbf{{{comp}}} & \\textbf{{{ident}}} "
                f"& \\textbf{{{mism}}} & {d_tex} \\\\"
            )
        else:
            lines.append(f"{kb} & {comp} & {ident} & {mism} & {d_tex} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\caption{Table 8: Diagnosis quality per knowledge base.}")
    lines.append("\\label{tab:table8}")
    lines.append("\\end{table}")
    outfile = config.output_path / "table8.tex"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


# Expected Table 8 values per Cowork's 16:45 spec — used for validation.
TABLE8_EXPECTED = {
    "HIS":   (5, 5, 0),
    "DELL":  (7, 5, 2),
    "B2C":   (7, 5, 2),
    "Win8":  (7, 4, 3),
    "CNN":   (6, 6, 0),
    "Linux": (10, 10, 0),
    "Total": (42, 35, 7),
}


def validate_table8(rows: List[Table8Row]) -> None:
    """Compare against Cowork's expected counts; log discrepancies."""
    mismatches = []
    for kb, comp, ident, mism, _ in rows:
        exp = TABLE8_EXPECTED.get(kb)
        if exp is None:
            continue
        if (comp, ident, mism) != exp:
            mismatches.append(
                f"  {kb}: expected {exp}, got ({comp}, {ident}, {mism})"
            )
    if mismatches:
        print(f"  ⚠ {len(mismatches)} discrepancies vs Cowork's spec:")
        for m in mismatches:
            print(m)
    else:
        print("  ✓ All counts match Cowork's expected Table 8 values")


# ---------------------------------------------------------------------------
# Table 9 (Phase 4 — Cognitive Load)
# ---------------------------------------------------------------------------

# Row: (tc_size_str, n_scenarios, minim_str, accur_str, faulty_rate_str)
Table9Row = Tuple[str, int, str, str, str]


# Matches lines in "Average ... by testcase size:" section, e.g.:
#   "       5 |          6 |      0.667 |      1.000"   (compare-kbdiag-m)
#   "       5 |          6 |           50.0%"           (verify-m2-overhead)
_AVG_MINIM_RE = re.compile(
    r"^\s*(\d+|ALL)\s+\|\s+(\d+)\s+\|\s+([\d.]+)\s+\|\s+([\d.]+)\s*$"
)
_AVG_FAULTY_RE = re.compile(
    r"^\s*(\d+|ALL)\s+\|\s+(\d+)\s+\|\s+([\d.]+%)\s*$"
)


def parse_avg_minim_accur(
    filepath: Path,
) -> Dict[str, Tuple[int, float, float]]:
    """From compare-kbdiag-m report, extract per-TC-size aggregates.

    Returns: { "5": (6, 0.667, 1.000), ..., "ALL": (42, 0.630, 0.992) }
    """
    if not filepath.exists():
        return {}
    in_section = False
    out: Dict[str, Tuple[int, float, float]] = {}
    for line in filepath.read_text().splitlines():
        if "Average Minimality" in line:
            in_section = True
            continue
        if not in_section:
            continue
        m = _AVG_MINIM_RE.match(line)
        if m:
            key = m.group(1)
            out[key] = (int(m.group(2)), float(m.group(3)), float(m.group(4)))
    return out


def parse_avg_faulty_rate(
    filepath: Path,
) -> Dict[str, Tuple[int, float]]:
    """From verify-m2-overhead report, extract per-TC-size faulty rates.

    Returns: { "5": (6, 50.0), ..., "ALL": (29, 22.8) }  (rates in %)
    """
    if not filepath.exists():
        return {}
    in_section = False
    out: Dict[str, Tuple[int, float]] = {}
    for line in filepath.read_text().splitlines():
        if "Average overhead faulty rate" in line:
            in_section = True
            continue
        if not in_section:
            continue
        m = _AVG_FAULTY_RE.match(line)
        if m:
            key = m.group(1)
            n = int(m.group(2))
            rate = float(m.group(3).rstrip("%"))
            out[key] = (n, rate)
    return out


def aggregate_table9(t9: Table9Config) -> List[Table9Row]:
    """Build Table 9 rows by joining per-size data from the two reports."""
    minim = parse_avg_minim_accur(t9.compare_m_report)
    faulty = parse_avg_faulty_rate(t9.overhead_report)

    rows: List[Table9Row] = []
    for size in t9.test_sizes:
        key = str(size)
        n, m_val, a_val = minim.get(key, (0, float("nan"), float("nan")))
        f_entry = faulty.get(key)
        m_str = f"{m_val:.3f}" if not math.isnan(m_val) else "—"
        a_str = f"{a_val:.3f}" if not math.isnan(a_val) else "—"
        f_str = f"{f_entry[1]:.1f}%" if f_entry else "—"
        rows.append((key, n, m_str, a_str, f_str))

    # Aggregate "All" row
    n_all, m_all, a_all = minim.get("ALL", (0, float("nan"), float("nan")))
    f_all_entry = faulty.get("ALL")
    f_all_str = (f"{f_all_entry[1]:.1f}%*"
                 if f_all_entry else "—")
    rows.append((
        "All", n_all,
        f"{m_all:.3f}" if not math.isnan(m_all) else "—",
        f"{a_all:.3f}" if not math.isnan(a_all) else "—",
        f_all_str,
    ))
    return rows


def generate_table9_md(rows: List[Table9Row], config: TableGenConfig) -> None:
    """Markdown Table 9."""
    lines = [
        "| |T_π| | #scenarios | avg minimality | avg accuracy | avg faulty rate |",
        "|---:|---:|---:|---:|---:|",
    ]
    for size, n, minim, accur, faulty in rows:
        if size == "All":
            lines.append(
                f"| **{size}** | **{n}** | **{minim}** | **{accur}** | **{faulty}** |"
            )
        else:
            lines.append(f"| {size} | {n} | {minim} | {accur} | {faulty} |")
    lines.append("")
    lines.append("*Aggregated over 29 scenarios with |T_π| ≤ 100 "
                 "(no overhead data for |T_π| ∈ {250, 500}).")
    outfile = config.output_path / "table9.md"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


def generate_table9_tex(rows: List[Table9Row], config: TableGenConfig) -> None:
    """LaTeX Table 9 using booktabs."""
    lines: List[str] = []
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")
    lines.append("\\scriptsize")
    lines.append("\\begin{tabular}{rrrrr}")
    lines.append("\\toprule")
    lines.append(
        "$|T_\\pi|$ & \\#scenarios & avg minimality & avg accuracy "
        "& avg faulty rate \\\\"
    )
    lines.append("\\midrule")
    for size, n, minim, accur, faulty in rows:
        # Escape % for LaTeX
        f_tex = faulty.replace("%", "\\%").replace("*", "\\textsuperscript{*}")
        if size == "All":
            lines.append("\\midrule")
            lines.append(
                f"\\textbf{{{size}}} & \\textbf{{{n}}} & \\textbf{{{minim}}} "
                f"& \\textbf{{{accur}}} & \\textbf{{{f_tex}}} \\\\"
            )
        else:
            lines.append(f"{size} & {n} & {minim} & {accur} & {f_tex} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append(
        "\\caption{Table 9: Cognitive load by testcase size "
        "(\\textsuperscript{*}aggregated over 29 scenarios with "
        "$|T_\\pi| \\le 100$).}"
    )
    lines.append("\\label{tab:table9}")
    lines.append("\\end{table}")
    outfile = config.output_path / "table9.tex"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


# Expected Table 9 values per Cowork's 16:45 spec — used for validation.
TABLE9_EXPECTED = {
    "5":   (6,  "0.667", "1.000", "50.0%"),
    "10":  (6,  "0.556", "1.000", "16.7%"),
    "25":  (6,  "0.579", "1.000", "16.7%"),
    "50":  (6,  "0.584", "1.000", "17.8%"),
    "100": (6,  "0.601", "0.976", "10.9%"),
    "250": (6,  "0.701", "0.976", "—"),
    "500": (6,  "0.722", "0.990", "—"),
    "All": (42, "0.630", "0.992", "22.8%*"),
}


def validate_table9(rows: List[Table9Row]) -> None:
    """Compare Table 9 rows against Cowork's expected values."""
    mismatches = []
    for size, n, minim, accur, faulty in rows:
        exp = TABLE9_EXPECTED.get(size)
        if exp is None:
            continue
        if (n, minim, accur, faulty) != exp:
            mismatches.append(
                f"  size={size}: expected {exp}, got ({n}, {minim}, {accur}, {faulty})"
            )
    if mismatches:
        print(f"  ⚠ {len(mismatches)} discrepancies vs Cowork's spec:")
        for m in mismatches:
            print(m)
    else:
        print("  ✓ All values match Cowork's expected Table 9 values")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m apps.results_table_gen <config.toml>")
        sys.exit(1)

    config = load_config(sys.argv[1])
    config.output_path.mkdir(parents=True, exist_ok=True)

    if config.table3.enabled:
        print("Generating Table 3...")
        data1 = aggregate_task1(config)
        for i, group in enumerate(config.table3.groups):
            s = chr(97 + i)  # 'a', 'b', ...
            generate_table3_md(data1, group, config, suffix=s)
            generate_table3_tex(data1, group, config, suffix=s)

    if config.table4.enabled:
        print("Generating Table 4...")
        data_all = aggregate_task_all(config)
        generate_table4_md(data_all, config)
        generate_table4_tex(data_all, config)

    if config.table7 and config.table7.enabled:
        print("Generating Table 7 (Concern 2 rebuttal — speedup × ratio)...")
        data7 = aggregate_table7(config.table7)
        generate_table7_md(data7, config.table7, config)
        generate_table7_tex(data7, config.table7, config)
        validate_table7(data7, config.table7)

    if config.table8 and config.table8.enabled:
        print("Generating Table 8 (Phase 1 — Diagnosis Quality)...")
        rows8 = aggregate_table8(config.table8)
        generate_table8_md(rows8, config)
        generate_table8_tex(rows8, config)
        validate_table8(rows8)

    if config.table9 and config.table9.enabled:
        print("Generating Table 9 (Phase 4 — Cognitive Load)...")
        rows9 = aggregate_table9(config.table9)
        generate_table9_md(rows9, config)
        generate_table9_tex(rows9, config)
        validate_table9(rows9)

    print("Done.")


if __name__ == "__main__":
    main()
