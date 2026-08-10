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


def test_global_limiter_reserves_distinct_slots_for_concurrent_callers():
    limiter = GlobalMinIntervalLimiter(2.0, clock=lambda: 0.0, sleeper=lambda _: None)
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
