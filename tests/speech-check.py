"""Regression checks for bounded speech buffering and generator cleanup."""
import asyncio
from speech_buffer import join_ready_sentences


async def check():
    async def fast():
        yield '第一句。'
        yield '第二句。'
    assert [s async for s in join_ready_sentences(fast(), window=0.02)] == ['第一句。第二句。']
    gate = asyncio.Event()
    closed = asyncio.Event()
    async def slow():
        try:
            yield '先回答。'
            await gate.wait()
            yield '再说明。'
        finally:
            closed.set()
    stream = join_ready_sentences(slow(), window=0.01)
    assert await asyncio.wait_for(anext(stream), 0.2) == '先回答。'
    await stream.aclose()
    assert closed.is_set()
    print('Speech buffering / first response deadline / cancellation cleanup: PASS (offline)')


asyncio.run(check())
