# 小爱手机助手 · XiaoGPT Phone

用闲置安卓手机给初代小爱音箱接上大模型，保留对着音箱说话的习惯。

手机负责转接和保存少量记忆，云端模型负责回答。无需拆机、Root、刷机或购买新电脑。

```text
你 → 小爱音箱收音 → 小米云端识别 → 安卓手机 → DeepSeek 等模型
                          小爱音箱播报 ← 手机取得回答 ←┘
```

> 已在 **小米 9 Pro 5G / Android 11 / 初代小米 AI 音箱 MDZ-25-DA（S12）** 上实测。
> 当前仍需每轮说“小爱同学”，原生回复也可能先响一小段，再被大模型回答接管。
> 请先接受这两项限制，再决定是否安装。[兼容性与限制](docs/architecture.md)

## 能做什么

| 能力 | 使用体验 |
|---|---|
| 大模型问答 | “小爱同学，请解释一下彩虹。” |
| 接着追问 | 回答后 90 秒内说“小爱同学，再简单一点。” |
| 自然人格 | 默认温和、简短、像家人聊天，可自行修改提示 |
| 长期记忆 | “记住……”直接保存；发现明确偏好时先询问，确认后保存 |
| 删除偏好 | 查看记忆、按内容或编号删除、二次确认清空 |
| 手机常驻 | Termux 运行，支持启动、停止、状态和重启 |
| 原声与音色试听 | 默认小爱原声；可播放微软 Edge 固定样本进行对比 |

本项目是在 [XiaoGPT](https://github.com/yihong0618/xiaogpt) 之上的手机部署与体验优化层。模型默认使用 DeepSeek，也支持通义千问及其他 HTTPS OpenAI 兼容接口。它依赖小米云端和模型 API，不能完全离线使用。

## 准备好这四样

- 一台正常联网、绑定到你小米账号的小米 AI 音箱。**S12 已实测；S12A 仅有向导筛选支持，尚未实测。**
- 一台 ARM64 安卓手机。参考环境为 Android 11、约 12GB 内存；这不是最低配置声明，其他型号需自行验证。
- [官方 Termux](https://github.com/termux/termux-app#installation)，以及能登录的小米账号。
- 一个平台的模型 API 密钥和少量可用余额。聊天 App 会员通常不等于 API 额度。

首次下载 Python 依赖较大，请预留数 GB 空间和稳定网络。正式使用时手机需要持续联网，电脑可关闭。

## 快速开始

以下命令在**手机 Termux** 里运行。先阅读脚本再执行也可以，不使用远程脚本直接管道执行。

```bash
pkg update
pkg install git
git clone https://github.com/zan147852/xiaogpt-phone.git
cd xiaogpt-phone
bash scripts/install.sh
xiaoai configure
```

向导依次检查模型 API、小米登录、音箱测试播报和测试提问读取。密码、验证码、密钥输入时不显示字符，凭证只保存在手机私有目录。听到测试句后再确认，全部通过后才会启动服务。

然后说：**“小爱同学，请用三句话解释为什么天空是蓝色的。”**

详细步骤、手机后台设置、升级方法见 [安装指南](docs/installation.md)。首次安装流程经过代码和离线检查；完整设备实测基于先前手动部署的参考环境，尚未做另一台全新手机的一键安装验收。

## 每天怎么用

在 Termux 输入 `xiaoai` 打开中文菜单，也可以直接执行：

```bash
xiaoai status     # 查看状态
xiaoai start      # 启动
xiaoai stop       # 停止
xiaoai restart    # 重启
xiaoai help      # 查看全部命令
```

| 想做的事 | 对音箱说 |
|---|---|
| 普通问答 | 小爱同学，请推荐晚饭 |
| 继续追问 | 小爱同学，换一个简单做法 |
| 保存偏好 | 小爱同学，记住我喜欢清淡的饭菜 |
| 确认自动建议 | 小爱同学，记住这条 |
| 拒绝自动建议 | 小爱同学，不要记 |
| 查看 | 小爱同学，查看记忆 |
| 删除一条 | 小爱同学，忘记清淡的饭菜／忘记编号3 |
| 全部删除 | 小爱同学，清空记忆；30 秒内再说“确认清空记忆” |
| 结束追问状态 | 小爱同学，结束聊天 |

自动记忆目前用轻量规则识别明确自述的偏好和习惯，不能理解所有日常事实。**未确认的建议不会写入数据库**；同一进程内最多每 5 分钟提议一次，120 秒过期或换话题时取消。

更多设置见 [使用指南](docs/usage.md)，遇到问题见 [常见问题](docs/troubleshooting.md)。

## 数据会去哪里

- 收音与语音识别经过小米服务；提问文字和最近对话上下文发送到你配置的模型平台。
- 记忆保存在手机私有 SQLite 中。回答时最多选取 8 条、1600 字作为模型上下文；因此相关记忆也可能发送到模型平台。
- 默认不将完整聊天写入文件。最近 5 轮上下文只在进程内存中，重启会清空。
- 默认小爱原声。执行 `xiaoai voice-sample` 才会把固定公开样本交给微软合成；不会切换日常音色。
- 仓库包含通用代码和文档，不包含个人账号、密钥、设备 token、记忆库或安装包。

详见 [隐私与记忆](docs/privacy.md)。

## 项目结构与开发

```text
app/                 问答封装、记忆、提示、语音缓冲、配置向导
phone/               手机上运行的服务脚本与中文菜单
scripts/install.sh   ARM64 Termux 安装／升级入口
scripts/check.py     离线回归检查
tests/               记忆确认、会话处理与播报缓冲检查
docs/                安装、使用、原理、隐私和排障
examples/            无凭证的配置示例
```

核心检查只需要 Python 3.12+，不访问小米或模型服务：

```bash
python scripts/check.py
```

完整检查需要安装依赖，建议在 Linux Python 3.12 环境运行：

```bash
python -m pip install -r requirements.txt
python scripts/check.py --full
```

GitHub Actions 会执行这两组检查和 Shell 语法检查。[贡献说明](CONTRIBUTING.md)

## 致谢与许可

本项目依赖 [XiaoGPT](https://github.com/yihong0618/xiaogpt)、[MiService](https://github.com/Yonsm/MiService)、[Termux](https://github.com/termux/termux-app)、[PRoot-Distro](https://github.com/termux/proot-distro) 及相关开源库。安装时从上游获取依赖，不在仓库分发其二进制文件。各依赖遵循各自许可。

本项目新增代码按 [MIT License](LICENSE) 发布；与小米、DeepSeek、微软均无官方关联。
