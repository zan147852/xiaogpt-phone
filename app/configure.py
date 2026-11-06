"""Run interactively on the phone; never send credentials to the PC console."""
import argparse
import asyncio
import getpass
import json
import logging
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from miservice import MiNAService
from xiaogpt.config import Config, LATEST_ASK_API
from xiaogpt.xiaogpt import MiAccount
from voice_settings import VOICE_SETTINGS


TASK = Path('/opt/xiaogpt')
PRIVATE = Path('/root/.config/xiaogpt')
TOKEN = PRIVATE / 'mi.token'
CONFIG = PRIVATE / 'config.json'
ASSISTED = False
logging.disable(logging.CRITICAL)


def status(value):
    (TASK / 'setup-status').write_text(value + '\n', encoding='utf-8')


def prompt(label, default=''):
    suffix = f' [{default}]' if default else ''
    return input(label + suffix + ': ').strip() or default


def save_private(path, content):
    temporary = path.with_suffix(path.suffix + '.new')
    fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(content)
    os.replace(temporary, path)
    path.chmod(0o600)


async def request_input(kind, label, default='', secret=False):
    if not ASSISTED:
        if secret:
            return getpass.getpass(label).strip()
        return prompt(label, default)
    response_path = PRIVATE / 'pending-response.json'
    request_path = TASK / 'input-request.json'
    response_path.unlink(missing_ok=True)
    request_id = uuid.uuid4().hex
    request_path.write_text(json.dumps({'kind': kind, 'request_id': request_id}), encoding='utf-8')
    print(label)
    print('当前为电脑协助模式，请在聊天回复；电脑会代为提交。')
    try:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if response_path.is_file():
                response = json.loads(response_path.read_text(encoding='utf-8'))
                response_path.unlink()
                if response.get('request_id') == request_id and response.get('kind') == kind:
                    value = response.get('value', '')
                    if not isinstance(value, str):
                        raise ValueError('协助输入格式无效。')
                    return value.strip() or default
            await asyncio.sleep(0.5)
        raise RuntimeError('等待输入超时，请重新发起配置。')
    finally:
        request_path.unlink(missing_ok=True)
        response_path.unlink(missing_ok=True)


async def otp(method):
    status('xiaomi_verification_needed')
    print(f'小米需要 {method} 验证码，请查看你账号对应的短信或邮箱。')
    value = await request_input('otp', '请输入本次新收到的验证码：', secret=True)
    status('submitting_xiaomi_verification')
    return value


async def main(platform=None):
    os.umask(0o077)
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    PRIVATE.chmod(0o700)
    provided = {}
    pending_input = PRIVATE / 'pending-input.json'
    if pending_input.is_file():
        provided = json.loads(pending_input.read_text(encoding='utf-8'))
        if not isinstance(provided, dict) or any(
            name not in ('api_key', 'account', 'password') or not isinstance(value, str)
            for name, value in provided.items()
        ):
            raise ValueError('一次性配置输入格式无效。')
        pending_input.unlink()
    status('waiting_for_local_credentials')
    print('\n小爱音箱本地配置向导\n')
    print('凭证保存在手机私有目录，向导不会显示密码、验证码或 API 密钥。')
    print('小米账号用于向小米服务验证；提问文字将发送到你选择的模型平台。')
    print('本向导会发送一条很短的模型测试请求，可能产生少量 API 费用。\n')

    existing = {}
    if CONFIG.is_file() and (ASSISTED or prompt('发现本机已保存配置，是否沿用？输入 y 沿用', 'y').lower() == 'y'):
        existing = json.loads(CONFIG.read_text(encoding='utf-8'))
    if existing:
        choice = 'saved'
    elif platform:
        choice = {'deepseek': '1', 'qwen': '2'}[platform]
    else:
        status('waiting_for_model_platform')
        choice = prompt('模型平台：1 DeepSeek，2 通义千问，3 其他兼容接口', '1')
    presets = {
        '1': ('https://api.deepseek.com/v1', 'deepseek-chat'),
        '2': ('https://dashscope.aliyuncs.com/compatible-mode/v1', 'qwen-plus'),
    }
    base_default, model_default = presets.get(choice, ('', ''))
    base = existing.get('api_base')
    if not base:
        status('waiting_for_api_address')
        base = base_default if platform else prompt('API 基础地址（填到 /v1 等基础路径）', base_default)
    base = base.rstrip('/')
    parsed = urlparse(base)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('API 地址必须是没有内嵌凭证的 HTTPS 地址。')
    model = existing.get('model', '').removeprefix('openai:')
    if not model:
        status('waiting_for_model_name')
        model = model_default if platform else prompt('模型名称', model_default)
    print(f'API 地址：{base}\n模型名称：{model}')
    status('waiting_for_api_key')
    key = provided.get('api_key') or existing.get('api_key')
    pending_key = PRIVATE / 'pending-api-key'
    if not key and pending_key.is_file():
        key = pending_key.read_text(encoding='utf-8').strip()
        pending_key.unlink()
        print('已载入本次提供的 API 密钥（不显示）。')
    if not key:
        key = getpass.getpass('API 密钥（不显示）: ').strip()
    if not model or not key:
        raise ValueError('模型名称和 API 密钥不能为空。')

    timeout = aiohttp.ClientTimeout(total=75)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        status('testing_model_api')
        async with session.post(
            base + '/chat/completions',
            headers={'Authorization': 'Bearer ' + key},
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': '请只回复：连接成功。'}],
                'max_tokens': 64,
                'stream': False,
            },
        ) as response:
            if response.status != 200:
                raise RuntimeError(f'模型测试失败，HTTP {response.status}；请检查地址、模型、余额和密钥。')
            result = await response.json()
            if not result.get('choices', [{}])[0].get('message', {}).get('content'):
                raise RuntimeError('模型返回了空回答，请检查模型是否支持普通对话接口。')
    print('模型 API 测试通过。')

    print('\n现在配置绑定这台音箱的小米账号。')
    status('waiting_for_xiaomi_account')
    user = provided.get('account') or existing.get('account') or prompt('小米账号（小米 ID、手机号或邮箱）')
    status('waiting_for_xiaomi_password')
    password = provided.get('password') or existing.get('password') or getpass.getpass('小米密码（不显示）: ')
    if not user or not password:
        raise ValueError('小米账号和密码不能为空。')

    status('logging_in_to_xiaomi')
    async with aiohttp.ClientSession(timeout=timeout) as session:
        account = MiAccount(session, user, password, str(TOKEN), otp_callback=otp)
        service = MiNAService(account)
        try:
            devices = await service.device_list()
        except Exception as error:
            message = str(error).lower()
            if 'rate limit' in message or 'too many' in message:
                detail = '小米限制登录频率，请稍后再试。'
            elif 'otp verification' in message or 'verification failed' in message:
                detail = '验证码验证或登录恢复失败，请使用本次新收到的验证码。'
            elif isinstance(error, (TimeoutError, aiohttp.ClientError)):
                detail = '小米服务连接超时或网络中断。'
            else:
                detail = '请检查账号、验证码与小米账号的风控提示。'
            raise RuntimeError('小米账号登录或设备读取失败。' + detail) from None
        candidates = [d for d in devices if d.get('hardware') in ('S12', 'S12A')]
        if not candidates:
            available = ', '.join(sorted({str(d.get('hardware', '?')) for d in devices}))
            raise RuntimeError('账号下没有找到 S12/S12A 音箱。已发现机型：' + (available or '无'))
        for number, device in enumerate(candidates, 1):
            print(f"{number}. {device.get('name', '小米 AI 音箱')} ({device.get('hardware')})")
        if len(candidates) == 1:
            selected = 0
            print('仅发现一台符合型号的音箱，已选择。')
        else:
            status('waiting_for_device_selection')
            selected = int(await request_input('device', '选择目标音箱序号', '1')) - 1
        if not 0 <= selected < len(candidates):
            raise ValueError('音箱序号无效。')
        device = candidates[selected]
        if not device.get('miotDID'):
            raise RuntimeError('目标音箱没有返回 miotDID，需进一步检查。')
        if TOKEN.exists():
            TOKEN.chmod(0o600)

        # Keep a private draft so a failed voice check does not require retyping secrets.
        draft = {
            'hardware': device['hardware'], 'mi_did': str(device['miotDID']),
            'account': user, 'password': password, 'model': 'openai:' + model,
            'api_base': base, 'api_format': 'chat', 'api_key': key,
            'tts': 'mi', 'stream': False, 'mute_xiaoai': True, 'verbose': 0,
        }
        Config(**draft)
        save_private(CONFIG, json.dumps(draft, ensure_ascii=False, indent=2))

        status('testing_speaker_output')
        await service.text_to_speech(device['deviceID'], '你好，手机已经连接到小爱音箱。')
        if (await request_input('speaker', '音箱是否播报了测试句？输入 y 确认', 'n')).lower() != 'y':
            raise RuntimeError('播报尚未确认，暂停配置以检查连接。')

        status('testing_question_reading')
        test_start = int(time.time() * 1000)
        await request_input('question_ready', '准备好后回复，再对音箱说：小爱同学，帮我做一次连接测试。')
        cookies = {
            'deviceId': device['deviceID'],
            'serviceToken': account.token['micoapi'][1],
            'userId': account.token['userId'],
        }
        received = False
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            address = LATEST_ASK_API.format(hardware=device['hardware'], timestamp=int(time.time() * 1000))
            async with session.get(address, cookies=cookies) as response:
                if response.status != 200:
                    raise RuntimeError(f'对话读取失败，HTTP {response.status}。')
                data = await response.json(content_type=None)
            inner = data.get('data')
            if isinstance(inner, str):
                inner = json.loads(inner)
            records = (inner or {}).get('records', [])
            if any(int(record.get('time', 0)) >= test_start and '连接测试' in record.get('query', '') for record in records):
                received = True
                break
            await asyncio.sleep(2)
        if not received:
            raise RuntimeError('没有读到测试提问。请确认音箱正常识别这句话，随后再检查小米对话接口。')

    config = {
        'hardware': device['hardware'],
        'mi_did': str(device['miotDID']),
        'account': user,
        'password': password,
        'model': 'openai:' + model,
        'api_base': base,
        'api_format': 'chat',
        'api_key': key,
        'tts': 'mi',
        'stream': False,
        'mute_xiaoai': True,
        'verbose': 0,
        'keyword': ['帮我', '请'],
        'prompt': '你是家庭语音助手。用自然、清楚的中文回答，通常不超过150字。先回答问题，再按需解释。不要输出Markdown、表格或链接；不确定时如实说明。',
    }
    config.update(VOICE_SETTINGS)
    Config(**config)
    save_private(CONFIG, json.dumps(config, ensure_ascii=False, indent=2))
    status('configured_checks_passed')
    print('\n模型、音箱播报和提问读取均已通过。配置已保存在手机私有目录。')
    print('下一步启动服务，并做一次实际问答测试。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='在手机本地配置小爱音箱。')
    parser.add_argument('--platform', choices=('deepseek', 'qwen'), help='预填平台的公开 API 地址与模型名。')
    parser.add_argument('--assisted', action='store_true', help='通过手机私有的一次性文件接收电脑协助输入。')
    arguments = parser.parse_args()
    ASSISTED = arguments.assisted
    (TASK / 'last-configuration-error').unlink(missing_ok=True)
    try:
        asyncio.run(main(arguments.platform))
    except (KeyboardInterrupt, EOFError):
        status('configuration_interrupted')
        print('\n配置已暂停。')
    except Exception as error:
        status('configuration_needs_attention')
        # Never print raw network exception payloads, which may contain credentials.
        safe = str(error) if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__
        (TASK / 'last-configuration-error').write_text(safe + '\n', encoding='utf-8')
        print('\n配置尚未完成：' + safe)
    if not ASSISTED:
        input('\n按回车返回。')
