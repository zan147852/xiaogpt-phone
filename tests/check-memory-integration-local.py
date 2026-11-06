"""Isolated local integration checks with a fake model; no external packages."""
import asyncio
import importlib.util
import sys
import types
import uuid
import shutil
from pathlib import Path


async def check():
    root = Path(__file__).resolve().parent
    directory = root / ('check-state-' + uuid.uuid4().hex)
    directory.mkdir()
    original_modules = {name: sys.modules.get(name) for name in ('republic', 'xiaogpt.bot')}

    class FakeChatbot:
        def __init__(self, config):
            self.config = config
            self.history = []
            self.calls = 0

        def _messages(self, query):
            return ['base-prompt', query]

        async def ask_stream(self, query, **options):
            self.calls += 1
            yield '先回答你的问题。'
            yield '再补充一句说明。'

        async def ask(self, query, **options):
            self.calls += 1
            return '正常回答。'

        async def close(self):
            pass

    sys.modules['republic'] = types.SimpleNamespace(system=lambda text: ('system', text))
    sys.modules['xiaogpt.bot'] = types.SimpleNamespace(Chatbot=FakeChatbot)
    spec = importlib.util.spec_from_file_location('tested_memory_bot', root.parent / 'app' / 'memory_bot.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bot = module.MemoryChatbot(types.SimpleNamespace(prompt='Family persona'), directory / 'memory.sqlite3')
    try:
        answer = [text async for text in bot.ask_stream('请帮我推荐晚饭我喜欢清淡的饭菜')]
        assert answer[:2] == ['先回答你的问题。', '再补充一句说明。']
        assert '记住这条' in answer[-1]
        assert bot.memory.connection.execute('SELECT COUNT(*) FROM notes').fetchone()[0] == 0
        calls = bot.calls
        assert '记住了' in ''.join([text async for text in bot.ask_stream('记住这条')])
        assert bot.calls == calls
        assert '清淡' in str(bot._messages('晚饭'))
        bot.memory.proposal_cooldown = 0
        assert '记住' in await bot.ask('我每天晚上散步')
        assert '没有保存' in await bot.ask('不要记')
        assert bot.memory.connection.execute('SELECT COUNT(*) FROM notes').fetchone()[0] == 1
        bot.history.append('private short-term turn')
        assert '已经删除' in await bot.ask('忘记清淡的饭菜')
        assert not bot.history
        assert not bot.memory.context('晚饭')
        print('Memory chatbot / answer-first streaming / confirmation without model / deletion: PASS (offline)')
    finally:
        await bot.close()
        for name, original in original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        assert directory.resolve().parent == root
        shutil.rmtree(directory)


asyncio.run(check())
