"""Describe integration failures without recording network payloads or secrets."""
import re


def safe_error_details(error):
    message = str(error).lower()
    frames = []
    traceback = error.__traceback__
    while traceback:
        frames.append(traceback.tb_frame.f_code.co_name)
        traceback = traceback.tb_next
    known = ('login failed', 'otp', 'verification', 'rate limit', 'too many',
             'device not found', 'invalid command', 'invalid params', 'permission',
             'auth', 'timeout', 'connect', 'miot_action', 'xiaomiio',
             'signature', 'encrypt', 'decrypt', 'invalid', 'expired', 'nonce',
             'security', 'sign', 'client withdraw', '签名', '认证', '参数', '加密', '解密', '过期', '超时', '授权')
    return {
        'type': type(error).__name__,
        'codes': re.findall(r'["\x27]?(?:code|error_code)["\x27]?\s*[:=]\s*(-?\d+)', message),
        'retry_after_seconds': re.findall(r'["\x27]?wait_second["\x27]?\s*[:=]\s*(\d+)', message),
        'categories': [term for term in known if term in message],
        'functions': frames[-6:],
    }
