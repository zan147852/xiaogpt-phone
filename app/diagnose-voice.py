"""Trace one public voice sample, without reading or logging conversations."""
import argparse
import asyncio
import contextlib
import json
import os
import time
import urllib.request
from pathlib import Path

import run  # Sets the private token path and disables upstream logging.
import xiaogpt.tts.file as file_tts
from safe_errors import safe_error_details
from xiaogpt.config import Config
from xiaogpt.xiaogpt import MiGPT

REQUESTS = []
SAMPLE_PATH = None
STATE = Path('/opt/xiaogpt/voice-diagnostic.json')


class TracedHandler(file_tts.HTTPRequestHandler):
    def send_response(self, code, message=None):
        if SAMPLE_PATH and self.path.split('?', 1)[0] == '/' + SAMPLE_PATH.name:
            agent = self.headers.get('User-Agent', '')
            source = ('pc_probe' if agent == 'XiaoGPT-PC-Probe' else
                      'self_probe' if agent == 'XiaoGPT-Self-Probe' else
                      'audio_player')
            REQUESTS.append({'source': source, 'method': self.command,
                             'status': code, 'range': bool(self.headers.get('Range'))})
        super().send_response(code, message)

    def do_GET(self):
        if SAMPLE_PATH and self.path.split('?', 1)[0] == '/' + SAMPLE_PATH.name:
            super().do_GET()
        else:
            self.send_error(404)

    def do_HEAD(self):
        if SAMPLE_PATH and self.path.split('?', 1)[0] == '/' + SAMPLE_PATH.name:
            super().do_HEAD()
        else:
            self.send_error(404)


def probe(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'XiaoGPT-Self-Probe'})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status == 200 and bool(response.read(256))


async def main(play_type):
    global SAMPLE_PATH
    config = Config(**json.loads(Path('/root/.config/xiaogpt/config.json').read_text()))
    config.tts = 'edge'
    config.tts_options = {'voice': 'zh-CN-XiaoxiaoNeural', 'rate': '+0%', 'pitch': '-2Hz'}
    file_tts.HTTPRequestHandler = TracedHandler
    client = MiGPT(config)
    try:
        await asyncio.wait_for(client.init_all_data(), 30)
        started = time.monotonic()
        SAMPLE_PATH, duration = await asyncio.wait_for(client.tts.make_audio_file(
            'zh-CN', '你好，这是新声音的连接测试。我们可以慢慢聊，我会认真听。'), 30)
        url = f'http://{client.tts.hostname}:{client.tts.port}/{SAMPLE_PATH.name}'
        result = {'phase': 'ready', 'url': url, 'audio_seconds': round(duration, 2),
                  'audio_bytes': SAMPLE_PATH.stat().st_size, 'play_type': play_type,
                  'synthesis_seconds': round(time.monotonic() - started, 2),
                  'self_fetch_ok': await asyncio.to_thread(probe, url)}
        STATE.write_text(json.dumps(result), encoding='utf-8')
        response = await asyncio.wait_for(client.mina_service._ubus_request(
            client.device_id, 'player_play_url', 'mediaplayer',
            {'url': url, 'type': play_type, 'media': 'app_ios'}), 20)
        result['cloud_code'] = response.get('code')
        inner = response.get('data') or {}
        if isinstance(inner, str):
            try:
                inner = json.loads(inner)
            except ValueError:
                inner = {}
        result['device_code'] = inner.get('code') if isinstance(inner, dict) else None
        result['play_request_accepted'] = result['cloud_code'] == 0
        # Keep the URL alive long enough to observe asynchronous speaker requests.
        for _ in range(30):
            await asyncio.sleep(1)
            result['requests'] = list(REQUESTS)
            STATE.write_text(json.dumps(result), encoding='utf-8')
        result['phase'] = 'finished'
        STATE.write_text(json.dumps(result), encoding='utf-8')
        return result
    finally:
        await client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--play-type', type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            result = asyncio.run(main(args.play_type))
        except Exception as error:
            result = {'phase': 'failed', 'error': safe_error_details(error)}
            STATE.write_text(json.dumps(result), encoding='utf-8')
    print(json.dumps(result))
