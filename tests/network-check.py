"""Boot networking: delayed availability, bounded failure and invalid inputs."""
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
from wait_network import HOST, required_endpoints, wait_for_network


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
    elapsed = 0
    endpoints = ((HOST, 443), ('example.invalid', 8443))
    observed = []

    def model_offline(address, timeout):
        observed.append(address)
        if address == endpoints[1]:
            raise OSError('model connection unavailable')
        return nullcontext()

    assert not wait_for_network(timeout=5, interval=5, endpoints=endpoints,
                                connect=model_offline, clock=clock, sleep=sleep)
    assert observed == list(endpoints)
    with tempfile.TemporaryDirectory() as directory:
        config = Path(directory) / 'private.json'
        config.write_text(json.dumps({'api_base': 'https://example.invalid:8443/v1',
                                      'api_key': 'unused-local-test'}))
        assert required_endpoints(config) == endpoints
        config.write_text('{"api_base": "http://example.invalid"}')
        try:
            required_endpoints(config)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid model endpoint accepted')
    for parameters in ({'timeout': 0}, {'interval': 0}, {'probe_timeout': 0}):
        try:
            wait_for_network(**parameters)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid timing accepted')
    print('Network wait / both endpoints required / configured port / bounded retry: PASS (offline)')


check()
