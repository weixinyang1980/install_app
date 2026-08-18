from __future__ import annotations

import json
import re

import httpx

from .config import settings


SYSTEM_PARSE = """你是「装了吗」的导购员。用户会用一句话描述想装的开发软件。
只输出 JSON，不要 Markdown。字段：
{
  "name": "软件常用名",
  "slug": "小写英文短名",
  "kind": "runtime|tool|database|ide|library|other",
  "version_source": "npm|pypi|github|maven|endoflife|ai",
  "source_key": "npm包名 或 pypi包名 或 owner/repo 或 group:artifact 或 endoflife产品名",
  "use_official_link": false,
  "official_url": "",
  "platforms": "windows,macos,linux"
}
规则：
- 不要推荐学习资源，不要介绍软件是干什么的。
- Visual Studio / VS 2022 不要解析成 VS Code。
- Java 默认 Temurin JDK。
- 如果是有官方安装器的 IDE（VS Code、IntelliJ、PyCharm、Android Studio），use_official_link=true 并给出官方下载页。
"""

SYSTEM_GENERATE = """你是「装了吗」的安装工程师。只输出安装方案 Markdown，禁止推荐教程/书籍/课程/博客，禁止介绍软件功能。

必须包含这些二级标题：
## 一键安装脚本
## 脚本运行说明
## 执行后建议

硬性规则：
1. Windows 脚本必须是 powershell 代码块；macOS/Linux 必须是 bash 代码块。
2. 脚本要有中文注释、安装后刷新 PATH、用命令做验证。
3. 绝对禁止 `winget install xxx --version 17.4` 这种短版本。winget 必须 `--id 精确ID --exact`。没有把握就不要传 --version。
4. 有官方下载页的 GUI 软件（VS Code、IDEA 等）不要给脚本，给官方链接。
5. 不要写 chocolatey，除非用户环境明确只有 choco。
6. 常见问题只写安装失败怎么处理，不要写怎么学习这个软件。
"""

SYSTEM_VERSIONS = """根据软件名给出可安装的稳定版本列表。只输出 JSON：
{"versions": [{"version": "x.y.z", "channel": "stable|lts", "is_latest_stable": true}]}
最多 8 个，最新稳定版放第一个并标记 is_latest_stable。不要预发布版。"""


async def _chat(messages: list[dict], temperature: float = 0.2) -> str:
    if not settings.ai_api_key:
        raise RuntimeError("未配置 AI_API_KEY")
    url = settings.ai_base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": settings.ai_model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }
    last_error: Exception | None = None
    # 本机代理挂了时 httpx 会连 7897 失败；自动再直连一次
    for trust_env in (True, False):
        try:
            async with httpx.AsyncClient(timeout=45.0, trust_env=trust_env) as client:
                r = await client.post(url, headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
            return data["choices"][0]["message"]["content"].strip()
        except (httpx.ConnectError, httpx.ProxyError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            last_error = e
            print(f"[ai] trust_env={trust_env} failed: {type(e).__name__}: {e}")
            continue
    raise RuntimeError(f"AI 调用失败：{last_error}")


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


async def parse_query(query: str) -> dict:
    raw = await _chat(
        [
            {"role": "system", "content": SYSTEM_PARSE},
            {"role": "user", "content": query},
        ]
    )
    return _extract_json(raw)


async def ai_versions(name: str) -> list[dict]:
    raw = await _chat(
        [
            {"role": "system", "content": SYSTEM_VERSIONS},
            {"role": "user", "content": name},
        ]
    )
    data = _extract_json(raw)
    versions = data.get("versions") or []
    out = []
    for i, v in enumerate(versions[:8]):
        if isinstance(v, str):
            out.append({"version": v, "channel": "stable", "is_latest_stable": i == 0})
        elif isinstance(v, dict) and v.get("version"):
            v.setdefault("channel", "stable")
            v.setdefault("is_latest_stable", i == 0)
            out.append(v)
    return out


async def generate_plan_markdown(context: dict) -> str:
    user = (
        f"软件：{context['name']}\n"
        f"版本：{context['version']}\n"
        f"平台：{context['platform']}\n"
        f"winget_id：{context.get('winget_id') or '未知'}\n"
        f"brew：{context.get('brew') or '未知'}\n"
        f"官方页：{context.get('official_url') or '无'}\n"
        f"是否必须官方链接：{context.get('use_official_link')}\n"
        f"参考脚本（必须优先采用其中的安装方式，你可以补注释和说明，但不要改坏版本处理）：\n"
        f"{context.get('recipe_script') or '无预置脚本，请按规则自行编写'}\n"
    )
    return await _chat(
        [
            {"role": "system", "content": SYSTEM_GENERATE},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
    )


def extract_script(markdown: str, platform: str) -> tuple[str, str]:
    lang_pref = "powershell" if platform == "windows" else "bash"
    blocks = re.findall(r"```([a-zA-Z0-9_-]*)\n(.*?)```", markdown, re.S)
    chosen = ""
    lang = ""
    for lang_name, body in blocks:
        l = (lang_name or "").lower()
        if lang_pref == "powershell" and l in {"powershell", "ps1", "pwsh"}:
            return body.strip(), "powershell"
        if lang_pref == "bash" and l in {"bash", "sh", "zsh", "shell"}:
            return body.strip(), "bash"
        if not chosen and l in {"powershell", "ps1", "pwsh", "bash", "sh", "zsh", "shell"}:
            chosen = body.strip()
            lang = "powershell" if l in {"powershell", "ps1", "pwsh"} else "bash"
    if chosen:
        return chosen, lang
    return "", ""
