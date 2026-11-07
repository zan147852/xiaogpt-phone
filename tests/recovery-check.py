"""Outage recovery and detached-poller failure, without network or credentials."""
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import run
from xiaogpt.config import Config
from xiaogpt.xiaogpt import MiGPT


class Response:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error

    async def __aenter__(self):
        if self.error:
            raise self.error
        return self

    async def __aexit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    async def json(self):
        return self.data


class Session:
    response = None

    def get(self, *args, **kwargs):
        return self.response


async def check():
    with tempfile.TemporaryDirectory() as directory:
        run.TASK = Path(directory)
        config = Config(hardware='S12', model='openai:check', api_key='unused',
                        api_base='https://example.invalid/v1', tts='mi')
        client = run.CheckedMiGPT(config)
        session = Session()
        login = AsyncMock(side_effect=AssertionError('Outage must not trigger login'))
        try:
            with patch.object(client, 'init_all_data', login), patch.object(run.asyncio, 'sleep', AsyncMock()) as sleep:
                session.response = Response(error=OSError('private connection detail'))
                assert await client.get_latest_ask_from_xiaoai(session) is None
                assert (run.TASK / 'service-status').read_text().strip() == 'reconnecting'
                assert not (run.TASK / 'last-poll-time').exists()
                assert 'private connection detail' not in (run.TASK / 'last-poll-error.json').read_text()
                sleep.assert_awaited_once_with(5)
                # A real successful empty poll is healthy and must not count as an answer.
                session.response = Response(data={'code': 0, 'data': json.dumps({'records': []})})
                assert await client.get_latest_ask_from_xiaoai(session) is None
                assert (run.TASK / 'service-status').read_text().strip() == 'listening'
                assert (run.TASK / 'last-poll-time').is_file()
                assert not (run.TASK / 'last-poll-error.json').exists()
                assert not (run.TASK / 'completed-answers').exists()
                # An error payload is not a successful poll, even if HTTP succeeded.
                session.response = Response(data={'code': 401, 'message': 'unused'})
                await client.get_latest_ask_from_xiaoai(session)
                assert (run.TASK / 'service-status').read_text().strip() == 'reconnecting'
                # A poll concurrent with speech must not replace the answering state.
                client._answering = True
                run.status('answering')
                session.response = Response(data={'code': 0, 'data': ''})
                await client.get_latest_ask_from_xiaoai(session)
                assert (run.TASK / 'service-status').read_text().strip() == 'answering'
                login.assert_not_awaited()
        finally:
            await client.close()

        # Reproduce an upstream detached poller crashing while its main loop waits.
        client = run.CheckedMiGPT(config)

        async def fake_runner(self):
            asyncio.create_task(self.poll_latest_ask())
            await asyncio.Event().wait()

        try:
            with patch.object(MiGPT, 'run_forever', fake_runner), \
                    patch.object(MiGPT, 'poll_latest_ask', AsyncMock(side_effect=RuntimeError('test'))):
                try:
                    await asyncio.wait_for(client.run_forever(), timeout=1)
                except RuntimeError as error:
                    assert str(error) == 'Question polling stopped'
                else:
                    raise AssertionError('Runner stayed alive after poller crashed')
                assert client._poll_task.done()
        finally:
            await client.close()
    print('Outage / safe status / recovery without login / poller crash detection: PASS (offline)')


asyncio.run(check())
