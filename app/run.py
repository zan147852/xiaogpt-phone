"""Run XiaoGPT locally, exposing only a status and a completion counter."""
import asyncio
import contextlib
import functools
import json
import logging
import os
import re
import signal
import sys
import time
from pathlib import Path

from xiaogpt.config import Config
from xiaogpt.xiaogpt import MiGPT
from safe_errors import safe_error_details
from voice_settings import AUTO_WAKEUP_ENABLED, CHAT_IDLE_SECONDS
from memory_bot import MemoryChatbot
from local_memory import parse_command
from speech_buffer import join_ready_sentences

TASK = Path('/opt/xiaogpt')
PRIVATE = Path('/root/.config/xiaogpt')
os.environ['XIAOGPT_MI_TOKEN_PATH'] = str(PRIVATE / 'mi.token')
logging.disable(logging.CRITICAL)


def status(state):
    (TASK / 'service-status').write_text(state + '\n', encoding='utf-8')


class CheckedMiGPT(MiGPT):
    @functools.cached_property
    def chatbot(self):
        return MemoryChatbot(self.config, PRIVATE / 'memory.sqlite3')

    def __init__(self, config):
        super().__init__(config)
        self._chat_until = 0.0
        self._pause_lock = asyncio.Lock()
        self._paused_record = None

    def _get_last_query(self, data):
        inner = data.get('data')
        if not inner:
            return None
        if isinstance(inner, str):
            inner = json.loads(inner)
        records = inner.get('records') or []
        if not records:
            return None
        record = dict(records[0])
        compact = re.sub(r'[\s，。！？、,.!?：:；;“”"]', '', record.get('query', ''))
        if compact in ('小爱同学', '小爱'):
            self.last_timestamp = max(self.last_timestamp, int(record.get('time', 0)))
            return None
        command = re.sub(r'^(?:小爱同学)?(?:请|帮我)?', '', compact)
        if command in ('开始聊天', '开始持续对话', '开始连续对话'):
            record['query'] = self.config.start_conversation
        elif command in ('结束聊天', '结束持续对话', '结束连续对话', '退出聊天'):
            record['query'] = self.config.end_conversation
        return super()._get_last_query({'data': json.dumps({**inner, 'records': [record]})})

    def need_ask_gpt(self, record):
        if not record:
            return False
        query = record.get('query', '')
        if query == self.config.start_conversation:
            self._chat_until = time.monotonic() + CHAT_IDLE_SECONDS
            return False
        if query == self.config.end_conversation:
            self._chat_until = 0.0
            self.in_conversation = False
            return False
        if self.in_conversation and time.monotonic() > self._chat_until:
            self.in_conversation = False
        accepted = parse_command(query) is not None or super().need_ask_gpt(record)
        if accepted:
            self.in_conversation = True
            self._chat_until = time.monotonic() + CHAT_IDLE_SECONDS
        return accepted

    async def do_tts(self, value):
        if value == f'正在问{self.chatbot.name}请耐心等待':
            return
        return await super().do_tts(value)

    async def stop_if_xiaoai_is_playing(self):
        # Pause promptly; the stock implementation first spends a round trip
        # querying status, which may already let the original reply play.
        async with self._pause_lock:
            record_timestamp = self.last_timestamp
            if self._paused_record == record_timestamp:
                return
            try:
                await self.mina_service.player_pause(self.device_id)
            except Exception as error:
                (TASK / 'last-pause-error.json').write_text(json.dumps(safe_error_details(error)))
            else:
                self._paused_record = record_timestamp

    async def wakeup_xiaoai(self):
        if not AUTO_WAKEUP_ENABLED:
            status('listening_manual_wakeup')
            return False
        try:
            result = await super().wakeup_xiaoai()
        except Exception as error:
            (TASK / 'last-wakeup-error.json').write_text(json.dumps(safe_error_details(error)))
            status('followup_wakeup_failed')
            return False
        else:
            (TASK / 'last-wakeup-error.json').unlink(missing_ok=True)
            status('listening')
            return result

    async def init_all_data(self, *args, **kwargs):
        await super().init_all_data(*args, **kwargs)
        status('listening')

    async def speak(self, text_stream):
        status('answering')
        try:
            # Native MiTTS ignores language. Avoid loading language detection
            # models for Chinese speech on the phone.
            if self.config.tts == 'mi':
                await self.tts.synthesize('zh-CN', join_ready_sentences(text_stream))
            else:
                await super().speak(text_stream)
        except Exception:
            status('answer_failed')
            raise
        else:
            count_file = TASK / 'completed-answers'
            try:
                count = int(count_file.read_text().strip())
            except (OSError, ValueError):
                count = 0
            count_file.write_text(str(count + 1) + '\n', encoding='ascii')
            (TASK / 'last-answer-time').write_text(str(int(time.time())) + '\n', encoding='ascii')
            if self.in_conversation:
                self._chat_until = time.monotonic() + CHAT_IDLE_SECONDS
            status('listening')


async def main():
    os.umask(0o077)
    if not (PRIVATE / 'config.json').is_file():
        status('configuration_required')
        return 2
    config = Config(**json.loads((PRIVATE / 'config.json').read_text(encoding='utf-8')))
    client = CheckedMiGPT(config)
    worker = asyncio.create_task(client.run_forever())
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.cancel)
    try:
        await worker
    except asyncio.CancelledError:
        status('stopped')
        return 0
    except Exception:
        status('connection_failed')
        return 1
    finally:
        for task in asyncio.all_tasks():
            if task not in (asyncio.current_task(), worker):
                task.cancel()
        await client.close()


if __name__ == '__main__':
    # Stock XiaoGPT prints questions and answers; discard that output here.
    with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            exit_code = asyncio.run(main())
        except Exception:
            status('startup_failed')
            exit_code = 1
    sys.exit(exit_code or 0)
