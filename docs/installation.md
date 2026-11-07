# 安装与升级

[返回首页](../README.md) · [日常使用](usage.md) · [排障](troubleshooting.md)

## 1. 安装 Termux

从 [Termux 官方安装说明](https://github.com/termux/termux-app#installation) 选择官方来源。参考环境使用 GitHub ARM64 版 v0.118.3；不同来源的 Termux 和插件不要混装。此项目不附带 APK，也不需要 Root 或解锁 Bootloader。

打开 Termux，确认出现命令行。手机保持联网，预留数 GB 空间。iPad 不适合作为此后台运行环境。

## 2. 安装项目

```bash
pkg update
pkg install git
git clone https://github.com/zan147852/xiaogpt-phone.git
cd xiaogpt-phone
bash scripts/install.sh
```

安装入口仅支持 ARM64，使用 PRoot-Distro 5.x，以 `xiaogpt` 为容器名。首次从 Ubuntu 官方站下载 Ubuntu Base 24.04.3 ARM64，用固定 SHA256 校验，再安装 Python 3.12 虚拟环境和 `xiaogpt[locked]==3.24`。

Ubuntu 文件 SHA256：

```text
7b2dced6dd56ad5e4a813fa25c8de307b655fdabc6ea9213175a92c48dabb048
```

安装会联网下载依赖，语言检测相关依赖较大；即使日常中文播报已跳过语言检测，这个上游依赖仍会安装。脚本不修改手机固件。

安装位置：

| 内容 | 位置 |
|---|---|
| Git 克隆目录 | `~/xiaogpt-phone`，用于阅读与更新 |
| 运行代码 | `~/xiaogpt`，Termux 私有存储 |
| Ubuntu 容器 | 名称 `xiaogpt` |
| 容器内代码映射 | `/opt/xiaogpt` |
| Python | `/root/xiaogpt-venv/bin/python` |
| 凭证、记忆 | 容器内 `/root/.config/xiaogpt/` |

## 3. 配置与验收

```bash
xiaoai configure
```

向导会停止已有问答服务，再按顺序完成：

1. 选模型平台，填写 API 地址、模型、密钥。DeepSeek 和通义千问有预设；其他平台必须提供 HTTPS OpenAI 兼容接口。
2. 发一次很短的模型请求，确认接口可用，可能产生少量 API 费用。
3. 登录音箱绑定的小米账号。若要求验证码，输入本次新收到的验证码。
4. 选择目标 S12/S12A 音箱；听到“你好，手机已经连接到小爱音箱”后才能确认。
5. 按向导提示对音箱说“小爱同学，帮我做一次连接测试”，验证能读取新提问。

只有以上全部通过，服务才会自动启动。不能把“环境装好了”当作“音箱接入成功”。

## 4. 实际试用

先测试一轮问答和一轮追问，再锁屏测试：

```text
小爱同学，请解释一下彩虹。
（等回答结束）小爱同学，再简单一点。
```

测试记忆确认：

```text
小爱同学，请帮我推荐早餐，我喜欢早上吃面条。
（听到询问后）小爱同学，记住这条。
小爱同学，查看记忆。
```

MIUI 中建议将 Termux 省电策略设为无限制、允许应用自启动，并按系统实际情况保留后台。项目启动时申请 Termux 唤醒锁，停止时释放。请用长时间锁屏后的真实问答检查后台稳定性。

**应用自启动权限不等于脚本开机自启。** 未配置下方开机入口时，手机重启后需要打开 Termux，输入 `xiaoai start`。

## 开机自启

1. 安装 [官方 Termux:Boot](https://github.com/termux/termux-boot)，来源与 Termux 必须一致。GitHub 版 Termux 配 GitHub 版插件，F-Droid 版配 F-Droid 版，签名不能混用；不要为换插件而卸载已有 Termux。
2. 安装后**打开 Termux:Boot 一次**，解除 Android 的首次启动限制。
3. 在 MIUI 等系统中，允许 Termux 和 Termux:Boot 的自启动／后台运行，按需将省电策略设为无限制。
4. 在 Termux 中执行：

```bash
xiaoai autostart enable
xiaoai autostart status
```

此命令只注册本项目的 `~/.termux/boot/20-xiaogpt`，不改其他启动脚本，不自动下载插件。
开机入口最多等待网络 10 分钟才开始访问小米账号；网络等待只检测小米公开 TCP 端口，不发送凭证。
联网后仍需按原流程通过账号接口；若网络超时，状态为 `boot_network_timeout`，联网后手动 `xiaoai start`。

重启手机，**先解锁一次**，保持 Wi-Fi 可用，再试听问答。仅看到脚本存在不能证明系统会实际执行。
若状态仍显示旧值，`xiaoai status` 会同时报告进程锁与开机阶段；脚本注册成功、模拟执行通过和真实重启通过是不同的验收结果。

关闭下次开机自启：

```bash
xiaoai autostart disable
```

关闭不会停止当前问答；需要停用时再执行 `xiaoai stop`。升级会保留已注册的开机入口，但升级后要按提示启动或重启服务。

## 升级

```bash
xiaoai stop
cd ~/xiaogpt-phone
git pull --ff-only
bash scripts/install.sh
xiaoai start
```

安装器会把旧运行代码备份到 `~/xiaogpt/rollback-日期时间/`，不删除记忆库和账号配置。安装器会重新应用当前版本 `app/voice_settings.py` 的公开偏好；如果改过人格，请先把自己的修改保留到 Git 分支或单独文件，升级后重新应用。

首次安装请先完成向导，不能手动把状态文件改成成功来跳过验证。安装失败可修复网络后重试，不要频繁重新登录小米。

## 停用与移除

先执行 `xiaoai stop`，音箱就恢复由原有服务响应。清理长期记忆优先使用语音“清空记忆 → 确认清空记忆”。删除整个 Termux 应用或 PRoot 容器会同时失去私有配置和记忆，请先确认自己不再需要它们。
