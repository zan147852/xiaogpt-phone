"""Offline checks for persistence, deletion, retrieval and speech buffering."""
import asyncio
import os
import tempfile
from pathlib import Path

from local_memory import MemoryStore
from speech_buffer import join_ready_sentences
from memory_bot import MemoryChatbot
from voice_settings import VOICE_SETTINGS
from xiaogpt.config import Config


async def check():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'memory.sqlite3'
        memory = MemoryStore(path)
        assert memory.handle('今天吃什么') is None
        assert '记住了' in memory.handle('请记住我喜欢清淡的食物')
        assert '没有保存' in memory.handle('记住我的密码是测试')
        memory.close()
        memory = MemoryStore(path)
        assert '清淡' in memory.context('推荐晚饭')
        assert '没有找到' in memory.handle('忘记编号99')
        assert '已经删除' in memory.handle('忘记清淡的食物')
        assert not memory.context('食物')
        assert '记住了' in memory.handle('记住我喜欢自然的说话风格')
        assert '没有删除' in memory.handle('确认清空记忆')
        assert '三十秒' in memory.handle('清空记忆')
        assert '已清空' in memory.handle('确认清空记忆')
        memory.close()
        if os.name == 'posix':
            assert path.stat().st_mode & 0o777 == 0o600
        bot = MemoryChatbot(Config(hardware='S12', model='openai:offline', api_key='unused',
                                  api_base='https://example.invalid/v1', **VOICE_SETTINGS), path)
        try:
            saved = [part async for part in bot.ask_stream('记住我喜欢清淡的饭菜')]
            assert '记住了' in ''.join(saved)
            assert '清淡' in str(bot._messages('晚饭吃什么'))
            assert '已经删除' in await bot.ask('忘记清淡的饭菜')
            assert not bot.memory.context('晚饭')
        finally:
            await bot.close()
    async def fast():
        yield '第一句。'
        await asyncio.sleep(0)
        yield '第二句。'
    assert [text async for text in join_ready_sentences(fast(), window=0.05)] == ['第一句。第二句。']
    gate = asyncio.Event()
    async def delayed():
        yield '先回答。'
        await gate.wait()
        yield '再解释。'
    combined = join_ready_sentences(delayed(), window=0.01)
    assert await asyncio.wait_for(combined.__anext__(), 0.2) == '先回答。'
    gate.set()
    assert await asyncio.wait_for(combined.__anext__(), 0.2) == '再解释。'
    await combined.aclose()
    print('Explicit memory persistence / deletion / private permissions / speech buffering: PASS (offline)')


asyncio.run(check())
