"""Boot networking: delayed availability, bounded failure and invalid inputs."""
from contextlib import nullcontext
from wait_network import wait_for_network


def check():
    elapsed = 0.0
    calls = 0

    def clock():
        return elapsed

    def sleep(seconds):
        nonlocal elapsed
        elapsed += seconds

    def delayed(address, timeout):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise OSError('offline')
        return nullcontext()

    assert wait_for_network(timeout=30, interval=5, connect=delayed, clock=clock, sleep=sleep)
    assert calls == 3 and elapsed == 10
    elapsed = 0

    def offline(*args, **kwargs):
        raise OSError('offline')

    assert not wait_for_network(timeout=12, interval=5, connect=offline, clock=clock, sleep=sleep)
    assert elapsed == 12
    for parameters in ({'timeout': 0}, {'interval': 0}, {'probe_timeout': 0}):
        try:
            wait_for_network(**parameters)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid timing accepted')
    print('Boot network wait / delayed connection / timeout / invalid timing: PASS (offline)')


check()
