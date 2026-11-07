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

from aiohttp import ClientTimeout
from xiaogpt.config import Config, LATEST_ASK_API
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
    path = TASK / 'service-status'
    value = state + '\n'
    if not path.exists() or path.read_text(encoding='utf-8') != value:
        path.write_text(value, encoding='utf-8')


class CheckedMiGPT(MiGPT):
    @functools.cached_property
    def chatbot(self):
        return MemoryChatbot(self.config, PRIVATE / 'memory.sqlite3')

    def __init__(self, config):
        super().__init__(config)
        self._chat_until = 0.0
        self._pause_lock = asyncio.Lock()
        self._paused_record = None
        self._poll_healthy = False
        self._poll_failures = 0
        self._last_poll_write = 0.0
        self._answering = False
        self._poll_stopped = asyncio.Event()
        self._poll_task = None
        self._poll_exception = None

    def _idle_state(self):
        if not self._poll_healthy:
            return 'reconnecting' if self._poll_failures else 'checking_connection'
        return 'listening_manual_wakeup' if self.in_conversation and not AUTO_WAKEUP_ENABLED else 'listening'

    async def get_latest_ask_from_xiaoai(self, session):
        # Keep retrying a temporary outage with the existing session. The stock
        # method hides network failures and may reinitialize login on bad JSON.
        try:
            url = LATEST_ASK_API.format(hardware=self.config.hardware,
                                        timestamp=str(int(time.time() * 1000)))
            async with session.get(url, timeout=ClientTimeout(total=15)) as response:
                response.raise_for_status()
                data = await response.json()
            if not isinstance(data, dict) or 'data' not in data:
                raise ValueError('Invalid latest-ask response')
            code = data.get('code', 0)
            if str(code) != '0':
                raise ValueError('Latest-ask API rejected request')
            record = self._get_last_query(data)
        except Exception as error:
            self._poll_healthy = False
            self._poll_failures += 1
            (TASK / 'last-poll-error.json').write_text(json.dumps(safe_error_details(error)))
            if not self._answering:
                status('reconnecting')
            await asyncio.sleep(5)
            return None
        self._poll_healthy = True
        self._poll_failures = 0
        now = time.monotonic()
        if not self._last_poll_write or now - self._last_poll_write >= 10:
            (TASK / 'last-poll-time').write_text(str(int(time.time())) + '\n', encoding='ascii')
            self._last_poll_write = now
        (TASK / 'last-poll-error.json').unlink(missing_ok=True)
        if not self._answering:
            status(self._idle_state())
        return record

    async def poll_latest_ask(self):
        self._poll_task = asyncio.current_task()
        try:
            await super().poll_latest_ask()
        except Exception as error:
            self._poll_exception = error
        finally:
            self._poll_stopped.set()

    async def run_forever(self):
        # The upstream poller is a detached task. If it exits unexpectedly,
        # stop this runner so the supervisor can restart it instead of hanging.
        runner = asyncio.create_task(super().run_forever())
        monitor = asyncio.create_task(self._poll_stopped.wait())
        try:
            done, _ = await asyncio.wait((runner, monitor), return_when=asyncio.FIRST_COMPLETED)
            if monitor in done:
                raise RuntimeError('Question polling stopped') from self._poll_exception
            await runner
        finally:
            tasks = [runner, monitor]
            if self._poll_task is not None:
                tasks.append(self._poll_task)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

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
            status(self._idle_state())
            return False
        try:
            result = await super().wakeup_xiaoai()
        except Exception as error:
            (TASK / 'last-wakeup-error.json').write_text(json.dumps(safe_error_details(error)))
            status('followup_wakeup_failed')
            return False
        else:
            (TASK / 'last-wakeup-error.json').unlink(missing_ok=True)
            status(self._idle_state())
            return result

    async def init_all_data(self, *args, **kwargs):
        await super().init_all_data(*args, **kwargs)
        status('checking_connection')

    async def speak(self, text_stream):
        self._answering = True
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
            status(self._idle_state())
        finally:
            self._answering = False


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
    except Exception as error:
        (TASK / 'last-runtime-error.json').write_text(json.dumps(safe_error_details(error)))
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
