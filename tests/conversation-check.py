"""Offline checks for voice command handling and nonfatal pause failure."""
import asyncio
import json
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import run
from voice_settings import VOICE_SETTINGS
from xiaogpt.config import Config


async def check():
    with tempfile.TemporaryDirectory() as directory:
        run.TASK = Path(directory)
        config = Config(hardware='S12', model='openai:check', api_key='unused',
                        api_base='https://example.invalid/v1', **VOICE_SETTINGS)
        client = run.CheckedMiGPT(config)
        try:
            now = int(time.time() * 1000) + 1000
            data = {'data': json.dumps({'records': [{'query': '请开始聊天。', 'time': now}]})}
            assert client._get_last_query(data)['query'] == config.start_conversation
            client.last_record.get_nowait()
            wake = {'data': json.dumps({'records': [{'query': '小爱同学。', 'time': now + 1}]})}
            assert client._get_last_query(wake) is None and client.last_record.empty()
            assert client.need_ask_gpt({'query': '请解释彩虹'})
            assert client.need_ask_gpt({'query': '再简单一点'})
            client._chat_until = time.monotonic() - 1
            assert not client.need_ask_gpt({'query': '再简单一点'})
            client.mina_service = SimpleNamespace(player_pause=AsyncMock(side_effect=RuntimeError('test')))
            await client.stop_if_xiaoai_is_playing()
            assert (run.TASK / 'last-pause-error.json').is_file()
            pause = AsyncMock(return_value=True)
            client.mina_service = SimpleNamespace(player_pause=pause)
            await asyncio.gather(client.stop_if_xiaoai_is_playing(), client.stop_if_xiaoai_is_playing())
            assert pause.await_count == 1
            client.last_timestamp += 1
            await client.stop_if_xiaoai_is_playing()
            assert pause.await_count == 2
            assert await client.wakeup_xiaoai() is False
            print('Command normalization / follow-up context / idle expiry / nonfatal pause: PASS (offline)')
        finally:
            await client.close()


asyncio.run(check())
