"""Check the runtime's Xiaomi and model connections, without API requests."""
import argparse
import json
import socket
import time
from pathlib import Path
from urllib.parse import urlsplit

HOST = 'userprofile.mina.mi.com'


def wait_for_network(timeout=600, interval=10, probe_timeout=5, *,
                     endpoints=((HOST, 443),),
                     connect=socket.create_connection, clock=time.monotonic, sleep=time.sleep):
    if timeout <= 0 or interval <= 0 or probe_timeout <= 0 or not endpoints:
        raise ValueError('Timeouts and polling interval must be positive.')
    deadline = clock() + timeout
    while clock() < deadline:
        try:
            for endpoint in endpoints:
                if clock() >= deadline:
                    return False
                with connect(endpoint, timeout=min(probe_timeout, max(0.01, deadline - clock()))):
                    pass
            return True
        except OSError:
            remaining = deadline - clock()
            if remaining <= 0:
                break
            sleep(min(interval, remaining))
    return False


def required_endpoints(config_path):
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    address = urlsplit(config.get('api_base', ''))
    if address.scheme != 'https' or not address.hostname:
        raise ValueError('A configured HTTPS model endpoint is required.')
    return tuple(dict.fromkeys(((HOST, 443), (address.hostname, address.port or 443))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--config', type=Path, help='Private config; its contents are never printed.')
    args = parser.parse_args()
    try:
        endpoints = required_endpoints(args.config) if args.config else ((HOST, 443),)
    except (OSError, ValueError, TypeError):
        print('configuration_required')
        return 2
    ready = wait_for_network(timeout=args.timeout, endpoints=endpoints)
    print('network_ready' if ready else 'network_timeout')
    return 0 if ready else 75


if __name__ == '__main__':
    raise SystemExit(main())
