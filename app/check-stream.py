"""One short live streaming request; print metrics only, never credentials or text."""
import asyncio
import contextlib
import json
import os
import time
from pathlib import Path

from xiaogpt.bot import Chatbot
from xiaogpt.config import Config


async def check():
    config = Config(**json.loads(Path('/root/.config/xiaogpt/config.json').read_text()))
    bot = Chatbot(config)
    started = time.monotonic()
    first = None
    chunks = 0
    try:
        async with asyncio.timeout(60):
            async for sentence in bot.ask_stream('请用两句简短的口语解释什么是彩虹。', **config.gpt_options):
                if sentence.strip():
                    chunks += 1
                    if first is None:
                        first = time.monotonic() - started
        if first is None:
            return {'result': 'empty_stream'}
        return {'result': 'streaming_ok', 'first_sentence_seconds': round(first, 2),
                'generation_seconds': round(time.monotonic() - started, 2), 'segments': chunks}
    finally:
        await bot.close()


with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
    try:
        result = asyncio.run(check())
    except Exception as error:
        result = {'result': 'failed', 'error_type': type(error).__name__}
print(json.dumps(result))
