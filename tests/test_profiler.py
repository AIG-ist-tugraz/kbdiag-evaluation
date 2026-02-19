"""
Test suite for the Profiler implementation.
Demonstrates usage patterns and validates functionality.
"""

#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

import multiprocessing as mp
import sys
import time

from explanation.operations.algorithms.profiler import use_global_profiler, ProfilerPreset, count_calls, measure_time, \
    ProfilerError, Profiler


# ========== Basic Usage Tests ==========

def test_basic_counter():
    """Test basic counter functionality."""
    print("\n" + "="*60)
    print("TEST: Basic Counter")
    print("="*60)

    profile = use_global_profiler(ProfilerPreset.BENCHMARK)

    profile.reset()
    profile.start()
    
    # Increment counter
    for i in range(10):
        profile.increment("loop_iterations")
    
    # Check value
    count = profile.get_metric("loop_iterations")
    print(f"Loop iterations: {count}")
    assert count == 10, f"Expected 10, got {count}"
    
    profile.stop()
    print("✅ PASSED")


def test_basic_timer():
    """Test basic timer functionality."""
    print("\n" + "="*60)
    print("TEST: Basic Timer")
    print("="*60)

    profile = use_global_profiler(ProfilerPreset.BENCHMARK)
    
    profile.reset()
    profile.start()
    
    # Record some timings
    for i in range(5):
        start = time.perf_counter()
        time.sleep(0.01)  # Sleep 10ms
        duration = time.perf_counter() - start
        profile.record_time("operation_time", duration)
    
    # Get statistics
    stats = profile.get_stats("operation_time")
    print(f"Statistics: {stats}")
    
    assert stats is not None
    assert stats['count'] == 5
    assert 0.01 <= stats['mean'] <= 0.02  # Should be ~10ms
    
    profile.stop()
    print("✅ PASSED")


def test_gauge_metric():
    """Test gauge metric functionality."""
    print("\n" + "="*60)
    print("TEST: Gauge Metric")
    print("="*60)

    profile = use_global_profiler(ProfilerPreset.BENCHMARK)

    profile.reset()
    profile.start()

    # Set various gauge values
    profile.set_gauge("status", "running")
    profile.set_gauge("max_depth", 42)
    profile.set_gauge("config", {"solver": "glucose", "timeout": 300})

    # Retrieve values
    status = profile.get_metric("status")
    max_depth = profile.get_metric("max_depth")
    config = profile.get_metric("config")

    print(f"Status: {status}")
    print(f"Max depth: {max_depth}")
    print(f"Config: {config}")

    assert status == "running"
    assert max_depth == 42
    assert config["solver"] == "glucose"

    profile.stop()
    print("✅ PASSED")


# ========== Decorator Tests ==========

def test_count_calls_decorator():
    """Test @count_calls decorator."""
    print("\n" + "="*60)
    print("TEST: Count Calls Decorator")
    print("="*60)

    profile = use_global_profiler(ProfilerPreset.BENCHMARK)

    profile.reset()
    profile.start()

    @count_calls("function_calls")
    def my_function(x):
        return x * 2

    # Call function multiple times
    for i in range(7):
        my_function(i)

    calls = profile.get_metric("function_calls")
    print(f"Function called: {calls} times")
    assert calls == 7

    profile.stop()
    print("✅ PASSED")


def test_measure_time_decorator():
    """Test @measure_time decorator."""
    print("\n" + "="*60)
    print("TEST: Measure Time Decorator")
    print("="*60)

    profile = use_global_profiler(ProfilerPreset.BENCHMARK)

    profile.reset()
    profile.start()

    @measure_time("function_time")
    def slow_function():
        time.sleep(0.01)
        return "done"

    # Call function multiple times
    for _ in range(3):
        result = slow_function()
        assert result == "done"

    stats = profile.get_stats("function_time")
    print(f"Timing stats: {stats}")

    assert stats is not None, "Stats should not be None"
    assert stats['count'] == 3
    assert stats['mean'] >= 0.01

    profile.stop()
    print("✅ PASSED")


def test_combined_decorators():
    """Test combining multiple decorators."""
    print("\n" + "="*60)
    print("TEST: Combined Decorators")
    print("="*60)

    profile = use_global_profiler(ProfilerPreset.BENCHMARK)

    profile.reset()
    profile.start()

    @measure_time("compute_time")
    @count_calls("compute_calls")
    def compute(n):
        total = 0
        for i in range(n):
            total += i
        return total

    # Call with different parameters
    compute(1000)
    compute(2000)
    compute(3000)

    calls = profile.get_metric("compute_calls")
    stats = profile.get_stats("compute_time")

    print(f"Calls: {calls}")
    print(f"Time stats: {stats}")

    assert calls == 3
    assert stats['count'] == 3

    profile.stop()
    print("✅ PASSED")


# ========== Context Manager Tests ==========

def test_timer_context_manager():
    """Test timer context manager."""
    print("\n" + "="*60)
    print("TEST: Timer Context Manager")
    print("="*60)

    profile = use_global_profiler(ProfilerPreset.BENCHMARK)

    profile.reset()
    profile.start()

    # Use context manager
    with profile.timer("block_1"):
        time.sleep(0.02)

    with profile.timer("block_1"):
        time.sleep(0.03)

    stats = profile.get_stats("block_1")
    print(f"Block timing: {stats}")

    assert stats['count'] == 2
    assert stats['total'] >= 0.05

    profile.stop()
    print("✅ PASSED")


# ========== Type Safety Tests ==========

def test_metric_type_validation():
    """Test that metrics enforce type consistency."""
    print("\n" + "="*60)
    print("TEST: Metric Type Validation")
    print("="*60)

    profile = use_global_profiler(ProfilerPreset.BENCHMARK)

    profile.reset()
    profile.start()

    # Register as counter
    profile.increment("my_metric")

    # Try to use as timer (should fail)
    try:
        profile.record_time("my_metric", 1.0)
        assert False, "Should have raised ProfilerError"
    except ProfilerError as e:
        print(f"✅ Correctly caught error: {e}")

    profile.stop()
    print("✅ PASSED")


# ========== Multiprocessing Tests ==========

def worker_with_profiler(task_id):
    """Worker function that creates its own Profiler instance.

    Each worker creates an independent profiler, records metrics,
    and returns the profiler data for aggregation in the main process.
    """

    # Each worker creates its own Profiler instance (not singleton!)
    worker_profiler = Profiler()
    worker_profiler.start()

    try:
        # Record metrics using profiler API
        worker_profiler.increment("worker_calls")

        with worker_profiler.timer("computation"):
            result = sum(range(task_id * 1000))
            time.sleep(0.01)

        worker_profiler.stop()

        # Return both result and profiler metrics
        return result, worker_profiler.to_dict()
    finally:
        pass


def test_multiprocessing_with_profiler_instances():
    """Test multiprocessing with independent Profiler instances.

    Demonstrates the recommended pattern: workers create their own Profiler
    instances and return metrics for aggregation in the main process.

    This pattern is clear, type-safe, and leverages the full Profiler API.
    """
    print("\n" + "="*60)
    print("TEST: Multiprocessing with Profiler Instances")
    print("="*60)

    # Main process profiler
    main_profiler = use_global_profiler(ProfilerPreset.BENCHMARK)
    main_profiler.reset()
    main_profiler.start()

    try:
        # Run workers with their own profilers
        with mp.Pool(processes=4) as pool:
            tasks = range(1, 11)  # 10 tasks
            results = pool.map(worker_with_profiler, tasks)

        # Aggregate metrics from all workers
        total_calls = 0
        all_computation_times = []

        for result, worker_metrics in results:
            # Extract metrics from each worker
            calls = worker_metrics.get('worker_calls', 0)
            total_calls += calls

            # Extract computation stats (could be dict with stats or single value)
            comp_stats = worker_metrics.get('computation', {})
            if isinstance(comp_stats, dict) and 'total' in comp_stats:
                all_computation_times.append(comp_stats['total'])

        # Record aggregated metrics in main profiler
        main_profiler.set_gauge("total_worker_calls", total_calls)
        main_profiler.set_gauge("worker_count", len(results))

        for comp_time in all_computation_times:
            main_profiler.record_time("aggregated_computation", comp_time)

        print(f"Total worker calls: {total_calls}")
        print(f"Worker computations: {len(all_computation_times)}")
        print(f"Mean computation time: {sum(all_computation_times)/len(all_computation_times):.4f}s")

        main_profiler.print_summary()

        # Verify results
        assert total_calls == 10, f"Expected 10 calls, got {total_calls}"
        assert len(all_computation_times) == 10, f"Expected 10 timing records, got {len(all_computation_times)}"
        assert all(t >= 0.01 for t in all_computation_times), "All times should be >= 10ms"

        print("✅ PASSED")
    finally:
        main_profiler.stop()


# ========== Real-world Scenario Tests ==========

def simulate_algorithm_execution():
    """Simulate a diagnosis algorithm execution."""
    print("\n" + "="*60)
    print("TEST: Simulated Algorithm Execution")
    print("="*60)

    profile = use_global_profiler(ProfilerPreset.BENCHMARK)

    profile.reset()
    profile.start()

    try:
        @measure_time("algorithm_runtime")
        @count_calls("algorithm_calls")
        def find_diagnosis(constraints, background):
            # Simulate consistency checks
            for i in range(5):
                with profile.timer("consistency_check"):
                    profile.increment("is_consistent_calls")
                    time.sleep(0.001)  # Simulate solver time

            # Simulate recursive calls
            profile.increment("fd_calls", 3)

            return ["diagnosis"]

        # Run algorithm
        result = find_diagnosis([], [])

        # Print summary
        profile.print_summary()

        # Verify metrics
        assert profile.get_metric("algorithm_calls") == 1
        assert profile.get_metric("is_consistent_calls") == 5
        assert profile.get_metric("fd_calls") == 3

        stats = profile.get_stats("consistency_check")
        assert stats['count'] == 5

        print("✅ PASSED")
    finally:
        profile.stop()


def test_csv_export():
    """Test CSV export functionality."""
    print("\n" + "="*60)
    print("TEST: CSV Export")
    print("="*60)

    profile = use_global_profiler(ProfilerPreset.BENCHMARK)

    profile.reset()
    profile.start()

    try:
        # Record some metrics
        profile.increment("test_calls", 42)
        profile.record_time("test_time", 1.5)
        profile.record_time("test_time", 2.5)
        profile.set_gauge("test_config", "value123")

        # Export to CSV
        csv_file = "/tmp/profiler_test.csv"
        columns = ["test_calls", "test_time", "test_config"]

        profile.write_to_csv(csv_file, columns)

        # Read and verify
        with open(csv_file, 'r') as f:
            lines = f.readlines()
            print(f"CSV header: {lines[0].strip()}")
            print(f"CSV data: {lines[1].strip()}")

            assert "test_calls" in lines[0]
            assert "42" in lines[1]

        print("✅ PASSED")
    finally:
        profile.stop()


# ========== Performance Comparison Tests ==========

def test_performance_overhead():
    """Measure profiler overhead."""
    print("\n" + "="*60)
    print("TEST: Performance Overhead")
    print("="*60)

    iterations = 10000

    # Without profiling
    start = time.perf_counter()
    for i in range(iterations):
        _ = i * 2
    no_profile_time = time.perf_counter() - start

    # With profiling (disabled)
    profile = use_global_profiler(ProfilerPreset.BENCHMARK)
    profile.reset()
    # Don't call start() - profiling disabled

    @count_calls("ops")
    def operation(x):
        return x * 2

    start = time.perf_counter()
    for i in range(iterations):
        operation(i)
    disabled_time = time.perf_counter() - start

    # With profiling (enabled)
    profile.reset()
    profile.start()

    try:
        start = time.perf_counter()
        for i in range(iterations):
            operation(i)
        enabled_time = time.perf_counter() - start

        print(f"No profiling:       {no_profile_time*1000:.2f}ms")
        print(f"Profiling disabled: {disabled_time*1000:.2f}ms ({disabled_time/no_profile_time:.2f}x)")
        print(f"Profiling enabled:  {enabled_time*1000:.2f}ms ({enabled_time/no_profile_time:.2f}x)")
        print(f"Overhead when enabled: {(enabled_time - no_profile_time)*1000:.2f}ms")

        # Note: Decorator overhead exists even when profiling is disabled
        # because Python still calls the wrapper function. This is expected.
        # We just verify that enabled profiling is more expensive than disabled.
        assert enabled_time > disabled_time, "Enabled profiling should be slower than disabled"

        print("✅ PASSED")
    finally:
        profile.stop()


# ========== Run All Tests ==========

def run_all_tests():
    """Run all test cases."""
    print("\n" + "=" * 70)
    print(" PROFILER TEST SUITE ".center(70, "="))
    print("=" * 70)

    tests = [
        ("Basic Counter", test_basic_counter),
        ("Basic Timer", test_basic_timer),
        ("Gauge Metric", test_gauge_metric),
        ("Count Calls Decorator", test_count_calls_decorator),
        ("Measure Time Decorator", test_measure_time_decorator),
        ("Combined Decorators", test_combined_decorators),
        ("Timer Context Manager", test_timer_context_manager),
        ("Metric Type Validation", test_metric_type_validation),
        ("Multiprocessing with Profiler Instances", test_multiprocessing_with_profiler_instances),
        ("Simulated Algorithm", simulate_algorithm_execution),
        ("CSV Export", test_csv_export),
        ("Performance Overhead", test_performance_overhead),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n❌ FAILED: {name}")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f" TEST RESULTS: {passed} passed, {failed} failed ".center(70, "="))
    print("=" * 70 + "\n")

    return failed == 0


if __name__ == "__main__":
    # Required for multiprocessing on some platforms
    mp.set_start_method('spawn', force=True)

    success = run_all_tests()
    sys.exit(0 if success else 1)
