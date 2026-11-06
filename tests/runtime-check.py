"""Offline integration smoke check; no credentials and no network requests."""
import asyncio
import importlib.metadata
import inspect
import sys

import aiohttp
from miservice import MiNAService
from xiaogpt.bot import Chatbot
from xiaogpt.config import Config, HARDWARE_COMMAND_DICT
from xiaogpt.xiaogpt import MiAccount
from run import CheckedMiGPT


async def main():
    assert sys.version_info[:2] == (3, 12)
    assert 'S12' in HARDWARE_COMMAND_DICT
    assert 'otp_callback' in inspect.signature(MiAccount).parameters
    assert callable(MiNAService.device_list)
    assert callable(MiNAService.text_to_speech)
    config = Config(
        hardware='S12', model='openai:smoke-check', api_key='unused-local-check',
        api_base='https://example.invalid/v1', api_format='chat',
        tts='mi', stream=False, mute_xiaoai=True,
    )
    client = CheckedMiGPT(config)
    await client.close()
    bot = Chatbot(config)
    await bot.close()
    print('Python:', sys.version.split()[0])
    print('XiaoGPT:', importlib.metadata.version('xiaogpt'))
    print('MiService:', importlib.metadata.version('miservice'))
    print('S12 / local runner / model adapter / OTP interfaces: PASS (offline)')


asyncio.run(main())
