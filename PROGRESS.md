# 装了吗 · 开发进度

## 当前阶段

全部完成。后端、桌面端、管理后台均可运行，并已在本机做过真实安装验证。

## 已完成

- FastAPI + SQLite 服务端：解析、版本源、方案生成、反馈、管理 API
- 17 个预置软件配方 + winget 安全安装运行时（禁止短版本号 `--version`）
- DeepSeek AI 生成 / 润色方案（预置软件脚本以配方为准）
- Electron + React 用户端（夜间小卖部 UI）
- Web 管理后台（密码登录、方案 CRUD、反馈、统计）
- 端到端：搜索 Git → 选 2.55.0 → 生成小票 → 展示脚本
- 真实安装：本机成功装上 Go `go1.26.5 windows/amd64`；Git 已存在时跳过下载并验证

## 进行中

无

## 问题及解决方案

| 问题 | 处理 |
| --- | --- |
| GitHub release 版本写入 SQLite 唯一约束冲突 | `save_versions` 去重 + flush |
| `re.sub` 把 PowerShell 的 `\d` 当转义，AI 润色失败 | 用函数替换脚本块 |
| 已安装 Git 仍从 GitHub 慢下载 | `Install-ZlmWinget -CommandName` 先查 PATH |
| Electron postinstall 被 npm allow-scripts 拦住 | `ELECTRON_MIRROR` + `node node_modules/electron/install.js` |
| wait-on 连不上 Vite | Vite 绑定 `127.0.0.1:5173` |

## 怎么开

1. `backend`: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8765`
2. `desktop`: `npm run dev`（Electron）
3. `admin`: `npm run dev`（http://127.0.0.1:5174 ，密码 `zhuanglema`）

或根目录 `start.ps1`。
