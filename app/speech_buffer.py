"""Briefly join generated sentences to reduce separate speaker playback calls."""
import asyncio
import contextlib


async def join_ready_sentences(stream, window=0.4, max_chars=180):
    iterator = stream.__aiter__()
    pending = None
    loop = asyncio.get_running_loop()
    try:
        while True:
            if pending is None:
                pending = asyncio.create_task(iterator.__anext__())
            try:
                text = await pending
            except StopAsyncIteration:
                return
            pending = None
            deadline = loop.time() + window
            while len(text) < max_chars:
                if pending is None:
                    pending = asyncio.create_task(iterator.__anext__())
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                done, _ = await asyncio.wait({pending}, timeout=remaining)
                if not done:
                    break
                try:
                    text += pending.result()
                except StopAsyncIteration:
                    pending = None
                    yield text
                    return
                pending = None
            if text:
                yield text
    finally:
        if pending is not None:
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
                await pending
        if hasattr(iterator, 'aclose'):
            await iterator.aclose()
