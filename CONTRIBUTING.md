# 参与改进

欢迎提交可复现的问题与小范围改进。请先看 [兼容范围](docs/architecture.md)，区分代码问题、小米接口限制和未实测设备。

## 开发检查

使用 Python 3.12；核心检查不需要额外安装库，不发送小米或模型请求：

```bash
python scripts/check.py
```

在 Linux 环境安装依赖后执行完整检查：

```bash
python -m pip install -r requirements.txt
python scripts/check.py --full
bash -n scripts/install.sh
```

`tests/` 使用临时数据库和假模型，不读取手机真实配置。测试覆盖候选未确认不保存、拒绝、超时、换话题、重启、无标点 ASR、引用／假设排除、流式回答顺序和播报取消清理。

## 修改边界

- 把可调整的偏好放在 `app/voice_settings.py`，保持配置集中。
- 修改语音口令、记忆或部署步骤时，同时更新用户文档。
- 修复错误时增加能复现问题的检查；不要为简单文案重复实现逻辑测试。
- 设备测试请明确标注手机、系统和音箱型号，不把模拟测试写成实测。
- 不提交凭证、日志、真实记忆、二进制依赖；发布前执行 `python scripts/release-check.py` 并检查 Git diff。
- 不通过反复登录、高频请求或规避服务限制解决小米风控错误。

本项目新增代码采用 MIT 许可；引入第三方代码时保留许可与来源说明。
