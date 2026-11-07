"""Wait for Xiaomi's public TCP endpoint, without login or personal data."""
import argparse
import socket
import time

HOST = 'userprofile.mina.mi.com'


def wait_for_network(timeout=600, interval=10, probe_timeout=5, *,
                     connect=socket.create_connection, clock=time.monotonic, sleep=time.sleep):
    if timeout <= 0 or interval <= 0 or probe_timeout <= 0:
        raise ValueError('Timeouts and polling interval must be positive.')
    deadline = clock() + timeout
    while clock() < deadline:
        try:
            with connect((HOST, 443), timeout=min(probe_timeout, max(0.01, deadline - clock()))):
                return True
        except OSError:
            remaining = deadline - clock()
            if remaining <= 0:
                break
            sleep(min(interval, remaining))
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=600)
    args = parser.parse_args()
    ready = wait_for_network(timeout=args.timeout)
    print('network_ready' if ready else 'network_timeout')
    return 0 if ready else 75


if __name__ == '__main__':
    raise SystemExit(main())
