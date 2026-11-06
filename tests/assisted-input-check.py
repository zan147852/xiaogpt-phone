"""Exercise assisted input locally without credentials or network requests."""
import asyncio
import json
import tempfile
from pathlib import Path

import configure


async def check():
    with tempfile.TemporaryDirectory() as directory:
        configure.TASK = Path(directory) / 'task'
        configure.PRIVATE = Path(directory) / 'private'
        configure.TASK.mkdir()
        configure.PRIVATE.mkdir()
        configure.ASSISTED = True
        request_path = configure.TASK / 'input-request.json'
        response_path = configure.PRIVATE / 'pending-response.json'
        worker = asyncio.create_task(configure.request_input('speaker', 'Offline check'))
        await asyncio.sleep(0)
        request = json.loads(request_path.read_text())
        response_path.write_text(json.dumps({'kind': 'speaker', 'request_id': 'old-request', 'value': 'n'}))
        await asyncio.sleep(0.6)
        assert not worker.done()
        response_path.write_text(json.dumps({**request, 'value': 'y'}))
        assert await asyncio.wait_for(worker, 2) == 'y'
        assert not request_path.exists() and not response_path.exists()
        worker = asyncio.create_task(configure.request_input('otp', 'Cancellation check'))
        await asyncio.sleep(0)
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        assert not request_path.exists() and not response_path.exists()
        print('Assisted input: matching request, stale response rejection, cleanup PASS (offline)')


asyncio.run(check())
