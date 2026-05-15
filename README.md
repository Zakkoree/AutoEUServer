# AutoEUServer

>  自动续期 EUserv 免费 IPv6 VPS 的轻量级解决方案。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/Zakkoree/AutoEUServer?style=social)](https://github.com/Zakkoree/AutoEUServer/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Zakkoree/AutoEUServer?style=social)](https://github.com/Zakkoree/AutoEUServer/network/members)

AutoEUServer 旨在简化 EUserv 免费 IPv6 VPS 的繁琐续期过程，通过自动化脚本避免因遗忘续期而导致的服务中断。项目支持多账户管理、自动验证码识别及多渠道通知，让你彻底解放双手。

##  功能特性

- ** 全自动续期**：自动获取账号内所有的 VPS 项目，智能检测并执行续期操作。
- ** 多账户支持**：支持配置多个 EUserv 账户，统一管理。
- ** 自动获取 PIN 码**：支持通过邮件转发规则解析（如 Parseur）自动获取邮箱验证 PIN 码。
- ** 验证码识别**：内置验证码识别功能，自动处理登录过程中的人机验证。
- ** Telegram 通知**：通过 Telegram Bot 实时推送续期成功或失败的状态通知。

## ️ 使用说明

本项目主要通过 **GitHub Actions** 进行自动化运行。只需 Fork 本仓库并配置相应的 Secrets 即可。

### 1. Fork 项目
点击仓库右上角的 **Fork** 按钮，将项目复制到你自己的 GitHub 账户下。

### 2. 配置 Secrets
进入你 Fork 后的仓库，点击 `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`，添加以下环境变量：

| 变量名 (Secret Name)            | 说明                                               | 必填 |
|:-----------------------------|:-------------------------------------------------|:---|
| `EUSERV_USERNAME`            | EUserv 登录邮箱                                      | 是  |
| `EUSERV_PASSWORD`            | EUserv 登录密码                                      | 是  |
| `GITHUB_TOKEN`               | GITHUB 令牌（用于保活Actions）                                      | 是  |
| `MAILPARSER_DOWNLOAD_URL_ID` | Mailparser & Parseur 或类似邮件解析服务的下载地址 (用于自动获取 PIN) | 是  |
| `TG_BOT_TOKEN`               | Telegram Bot 的 Token                             | 否  |
| `TG_USER_ID`                 | Telegram 接收消息的 Chat ID                           | 否  |
| `YESCAPTCHA_KEY`             | YesCaptCha API 密钥 (用于处理登录时偶尔会出现人机验证，选填)          | 否  |


### 3. 启动运行
配置完成后，Actions 会根据设定的 Cron 表达式自动运行（默认每7天 UTC 8 点运行一次）。你也可以在 `Actions` 页面手动触发一次运行以测试配置是否生效。

##  支持项目

开发不易，如果这个项目对你有帮助，请给一个 **Star** ️，这将是对我最大的鼓励！

如果你觉得项目不错，欢迎请作者喝杯咖啡：

- **TRC20 (USDT)**: `TUEEWiF1vJZoHtDA1bSTFjt7FMD1cDhxTh`

##  许可

本项目基于 MIT 许可协议。详情请查看 [LICENSE](LICENSE) 文件。