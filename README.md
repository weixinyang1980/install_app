# 装了吗

口号：**今天你装了吗？**

帮学编程的同学一键查出版本、生成安装方案，并在本机真正执行安装脚本。Windows 走 PowerShell，macOS 走 Bash。GUI 软件（VS Code、IDEA）直接给官方下载页。

许可证：[MIT](LICENSE)

## 三件套

| 目录 | 作用 | 默认地址 |
| --- | --- | --- |
| `backend/` | FastAPI + SQLite + DeepSeek | http://127.0.0.1:8765 |
| `desktop/` | Electron + React 用户端 | Vite 5173 |
| `admin/` | Web 管理后台 | http://127.0.0.1:5174 |

## 配置（不要提交密钥）

把示例环境文件复制成本地文件，再填自己的 Key：

```powershell
copy backend\.env.example backend\.env
```

`backend/.env` 需要至少包含：

```
AI_API_KEY=你的 DeepSeek Key
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-chat
ADMIN_PASSWORD=请改成自己的后台密码
```

- `backend/.env` 已被 `.gitignore` 忽略，**不要**把真实 Key 提交到 GitHub
- 管理后台密码来自 `ADMIN_PASSWORD`；示例默认值是本地演示用的 `zhuanglema`，公开仓库请自行改掉

## 启动

先开服务端，再开桌面端 / 后台。

```powershell
# 1) 服务端
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765

# 2) 桌面 APP（另开终端）
cd desktop
npm install
npm run dev

# 3) 管理后台（另开终端）
cd admin
npm install
npm run dev
```

Windows 也可以直接跑仓库根目录的 `start.ps1`。