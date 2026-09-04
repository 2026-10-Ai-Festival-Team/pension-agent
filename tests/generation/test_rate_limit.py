import threading

from src.generation.rate_limit import GlobalMinIntervalLimiter


def test_global_limiter_reserves_minimum_interval_without_real_sleep():
    clock_value = [0.0]
    sleeps = []

    def clock():
        return clock_value[0]

    def sleeper(seconds):
        sleeps.append(seconds)
        clock_value[0] += seconds

    limiter = GlobalMinIntervalLimiter(2.0, clock=clock, sleeper=sleeper)

    assert limiter.acquire() == 0.0
    assert limiter.acquire() == 2.0
    assert sleeps == [2.0]


def test_global_limiter_serializes_actual_starts_for_concurrent_callers():
    clock_value = [0.0]

    def sleeper(seconds):
        clock_value[0] += seconds

    limiter = GlobalMinIntervalLimiter(2.0, clock=lambda: clock_value[0], sleeper=sleeper)
    barrier = threading.Barrier(3)
    waits = []

    def acquire():
        barrier.wait()
        waits.append(limiter.acquire())

    threads = [threading.Thread(target=acquire), threading.Thread(target=acquire)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert sorted(waits) == [0.0, 2.0]


def test_global_limiter_rechecks_after_an_early_wakeup():
    clock_value = [0.0]
    sleeps = []

    def sleeper(seconds):
        sleeps.append(seconds)
        # Simulate a scheduler that returns before the requested sleep elapsed.
        clock_value[0] += seconds / 2

    limiter = GlobalMinIntervalLimiter(2.0, clock=lambda: clock_value[0], sleeper=sleeper)

    assert limiter.acquire() == 0.0
    assert limiter.acquire() == 2.0
    assert clock_value[0] == 2.0
    assert sleeps[0] == 2.0
    assert len(sleeps) > 1
