"""Add explicit local memory to XiaoGPT without saving chat history."""
import republic
from xiaogpt.bot import Chatbot
from local_memory import MemoryStore, parse_command
from voice_settings import AUTOMATIC_MEMORY_PROPOSALS


class MemoryChatbot(Chatbot):
    def __init__(self, config, path):
        super().__init__(config)
        self.memory = MemoryStore(path)

    def _messages(self, query):
        messages = super()._messages(query)
        context = self.memory.context(query)
        if context:
            messages.insert(1 if self.config.prompt else 0, republic.system(context))
        return messages

    def local_answer(self, query):
        answer = self.memory.handle(query)
        command = parse_command(query)
        if answer is not None and command[0] in ('delete', 'confirm_clear'):
            self.history.clear()
        return answer

    async def ask_stream(self, query, **options):
        answer = self.local_answer(query)
        if answer is not None:
            yield answer
            return
        async for sentence in super().ask_stream(query, **options):
            yield sentence
        if AUTOMATIC_MEMORY_PROPOSALS:
            proposal = self.memory.propose(query)
            if proposal:
                yield proposal

    async def ask(self, query, **options):
        answer = self.local_answer(query)
        if answer is not None:
            return answer
        answer = await super().ask(query, **options)
        proposal = self.memory.propose(query) if AUTOMATIC_MEMORY_PROPOSALS else ''
        return answer + ('。' + proposal if proposal else '')

    async def close(self):
        self.memory.close()
        await super().close()
