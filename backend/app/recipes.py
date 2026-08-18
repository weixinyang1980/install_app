from __future__ import annotations

from .helpers import BASH_HELPER, PS_HELPER


def _md(title: str, platform: str, version: str, body: str, script: str, lang: str, extra: str = "") -> str:
    fence = "powershell" if lang == "powershell" else "bash"
    parts = [
        f"# {title}",
        "",
        f"- 平台：`{platform}`",
        f"- 版本：`{version}`",
        "",
        "## 一键安装脚本",
        "",
        f"```{fence}",
        script.strip(),
        "```",
        "",
        "## 脚本运行说明",
        "",
        body.strip(),
        "",
        "## 执行后建议",
        "",
        extra.strip() or "- 关掉当前终端，新开一个窗口，再跑验证命令，PATH 才会稳定生效。",
        "",
    ]
    return "\n".join(parts)


def _ps(body: str) -> str:
    return PS_HELPER.strip() + "\n\n" + body.strip() + "\n"


def _sh(body: str) -> str:
    return BASH_HELPER.strip() + "\n\n" + body.strip() + "\n"


def _linux_pkg() -> str:
    return r'''
if command -v apt-get >/dev/null 2>&1; then
  PKG=apt
elif command -v dnf >/dev/null 2>&1; then
  PKG=dnf
elif command -v yum >/dev/null 2>&1; then
  PKG=yum
else
  echo "未识别的 Linux 包管理器" >&2
  exit 1
fi
sudo() { command sudo "$@"; }
'''


def official_plan(name: str, version: str, platform: str, url: str, tips: str) -> dict:
    md = f"""# {name}

- 平台：`{platform}`
- 版本：`{version}`

## 官方安装入口

请打开官方下载页安装，不要用脚本猜版本号。

**下载：** [{url}]({url})

{tips}

## 脚本运行说明

本软件有官方安装器 / 下载页。装完后在新终端里用自带的 `Help > About` 或命令行验证即可。

## 执行后建议

- 用官方安装器自带的选项把「加到 PATH / 添加到系统」勾上。
"""
    return {
        "markdown": md,
        "script": "",
        "script_language": "",
        "official_url": url,
        "source": "official",
    }


def build_recipe(software, version: str, platform: str) -> dict | None:
    slug = software.slug
    fn = RECIPES.get(slug)
    if not fn:
        return None
    return fn(software, version, platform)


def _git(software, version, platform):
    if platform == "windows":
        script = _ps(f'''
$RequestedVersion = "{version}"
Write-Zlm "开始安装 Git"
Install-ZlmWinget -PackageId "Git.Git" -RequestedVersion $RequestedVersion -CommandName git
Refresh-ZlmPath
# Git 安装器常把 git.exe 放到这个固定目录
$gitCmd = "$env:ProgramFiles\\Git\\cmd"
if (Test-Path $gitCmd) {{ $env:Path = "$gitCmd;$env:Path" }}
Assert-ZlmCommand git " --version"
''')
        return {
            "markdown": _md("Git", platform, version, """
- Windows 用 winget 精确 ID `Git.Git`。
- 若你选了具体版本，脚本会先列出源里的真实版本再匹配；匹配不上就装默认最新版，**绝不会**把 `17.4` 这种短号直接传给 winget。
- 需要管理员权限时，请在弹出的 UAC 窗口点「是」。
""", script, "powershell", "- 新开终端执行 `git --version`。\n- 首次使用可设置：`git config --global user.name \"你的名字\"` 和 `git config --global user.email \"you@example.com\"`。"),
            "script": script,
            "script_language": "powershell",
            "official_url": software.official_url,
            "source": "recipe",
        }
    if platform == "macos":
        script = _sh("""
zlm_brew_install git
zlm_assert git --version
""")
        return _plain("Git", version, platform, script, "bash", software.official_url, "macOS 走 Homebrew 公式 `git`。")
    script = _sh(_linux_pkg() + """
case "$PKG" in
  apt) sudo apt-get update && sudo apt-get install -y git ;;
  dnf) sudo dnf install -y git ;;
  yum) sudo yum install -y git ;;
esac
zlm_assert git --version
""")
    return _plain("Git", version, platform, script, "bash", software.official_url, "Linux 走发行版仓库。")


def _plain(title, version, platform, script, lang, url, explain, extra=""):
    return {
        "markdown": _md(title, platform, version, explain, script, lang, extra),
        "script": script,
        "script_language": lang,
        "official_url": url,
        "source": "recipe",
    }


def _nodejs(software, version, platform):
    ver = version.lstrip("vV")
    if version in ("latest", "lts", "最新", "最新稳定版"):
        ver = ""
    if platform == "windows":
        if ver and ver.count(".") >= 2:
            script = _ps(f'''
$ver = "{ver}"
Write-Zlm "按官方 MSI 安装 Node.js $ver（不走 winget --version，避免版本对不上）"
$url = "https://nodejs.org/dist/v$ver/node-v$ver-x64.msi"
Install-ZlmMsi -Url $url -FileName "node-v$ver-x64.msi"
$nodeDir = "$env:ProgramFiles\\nodejs"
if (Test-Path $nodeDir) {{ $env:Path = "$nodeDir;$env:Path" }}
Assert-ZlmCommand node "-v"
Assert-ZlmCommand npm "-v"
''')
        else:
            script = _ps(f'''
$RequestedVersion = "{version}"
Write-Zlm "安装 Node.js LTS（winget ID: OpenJS.NodeJS.LTS）"
Install-ZlmWinget -PackageId "OpenJS.NodeJS.LTS" -RequestedVersion $RequestedVersion -FallbackId "OpenJS.NodeJS" -CommandName node
$nodeDir = "$env:ProgramFiles\\nodejs"
if (Test-Path $nodeDir) {{ $env:Path = "$nodeDir;$env:Path" }}
Assert-ZlmCommand node "-v"
Assert-ZlmCommand npm "-v"
''')
        return _plain("Node.js", version, platform, script, "powershell", software.official_url,
                      "- 完整三点版本（如 22.11.0）走 nodejs.org 官方 MSI。\n- 选 latest/LTS 时用 winget 精确 ID `OpenJS.NodeJS.LTS`，不传短版本号。",
                      "- 新终端执行 `node -v` 和 `npm -v`。")
    if platform == "macos":
        if ver and ver.split(".")[0].isdigit():
            major = ver.split(".")[0]
            script = _sh(f"""
zlm_need_brew
zlm_info "安装 node@{major}"
brew install node@{major} || brew install node
brew link --overwrite --force node@{major} 2>/dev/null || true
zlm_assert node -v
zlm_assert npm -v
""")
        else:
            script = _sh("""
zlm_brew_install node
zlm_assert node -v
zlm_assert npm -v
""")
        return _plain("Node.js", version, platform, script, "bash", software.official_url, "macOS 用 Homebrew。")
    script = _sh(f"""
{_linux_pkg()}
curl -fsSL https://deb.nodesource.com/setup_lts.x -o /tmp/nodesource.sh || true
if [ "$PKG" = apt ]; then
  if [ -s /tmp/nodesource.sh ]; then sudo bash /tmp/nodesource.sh; fi
  sudo apt-get install -y nodejs
else
  sudo $PKG install -y nodejs npm
fi
zlm_assert node -v
zlm_assert npm -v
""")
    return _plain("Node.js", version, platform, script, "bash", software.official_url, "Linux 优先 NodeSource LTS。")


def _python(software, version, platform):
    ver = version.lstrip("vV")
    if platform == "windows":
        if ver.count(".") >= 2:
            script = _ps(f'''
$ver = "{ver}"
Write-Zlm "按官方安装器安装 Python $ver，并写入 PATH"
$url = "https://www.python.org/ftp/python/$ver/python-$ver-amd64.exe"
Install-ZlmExe -Url $url -FileName "python-$ver-amd64.exe" -Args "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1"
Refresh-ZlmPath
$pyRoot = "$env:LocalAppData\\Programs\\Python"
Get-ChildItem $pyRoot -ErrorAction SilentlyContinue | ForEach-Object {{ $env:Path = "$($_.FullName);$($_.FullName)\\Scripts;$env:Path" }}
Assert-ZlmCommand python "--version"
python -m pip install -U pip
''')
        else:
            major = "3.12"
            if ver and ver[0].isdigit():
                parts = ver.split(".")
                if len(parts) >= 2:
                    major = f"{parts[0]}.{parts[1]}"
                elif parts[0] == "3":
                    major = "3.12"
            winget_id = f"Python.Python.{major}"
            script = _ps(f'''
Write-Zlm "安装 {winget_id}（版本写在 ID 里，不使用 --version 短号）"
Install-ZlmWinget -PackageId "{winget_id}" -FallbackId "Python.Python.3.13" -CommandName python
Refresh-ZlmPath
Assert-ZlmCommand python "--version"
python -m pip install -U pip
''')
        return _plain("Python", version, platform, script, "powershell", software.official_url,
                      "- 完整版本用 python.org 官方 exe，参数 `PrependPath=1`。\n- 只有 3.12 这种大版本时，用 winget ID `Python.Python.3.12`，**不要** `--version 3.12`。")
    if platform == "macos":
        script = _sh("""
zlm_brew_install python
zlm_assert python3 --version
python3 -m pip install -U pip
""")
        return _plain("Python", version, platform, script, "bash", software.official_url, "macOS 用 brew python，命令是 python3。")
    script = _sh(_linux_pkg() + """
case "$PKG" in
  apt) sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv ;;
  dnf) sudo dnf install -y python3 python3-pip ;;
  yum) sudo yum install -y python3 python3-pip ;;
esac
zlm_assert python3 --version
""")
    return _plain("Python", version, platform, script, "bash", software.official_url, "Linux 走发行版 python3。")


def _jdk(software, version, platform):
    feature = "21"
    ver = version.lstrip("vV")
    if ver and ver[0].isdigit():
        feature = ver.split(".")[0]
        if feature == "1":
            feature = "8"
    if platform == "windows":
        script = _ps(f'''
$feature = "{feature}"
Write-Zlm "安装 Temurin JDK $feature（winget ID 自带大版本，禁止把短版本号传给 --version）"
$pkg = "EclipseAdoptium.Temurin.$feature.JDK"
Install-ZlmWinget -PackageId $pkg -FallbackId "EclipseAdoptium.Temurin.21.JDK" -CommandName java
Refresh-ZlmPath
# 常见安装路径补进当前会话
Get-ChildItem "C:\\Program Files\\Eclipse Adoptium" -ErrorAction SilentlyContinue | ForEach-Object {{
  $bin = Join-Path $_.FullName "bin"
  if (Test-Path $bin) {{ $env:Path = "$bin;$env:Path"; $env:JAVA_HOME = $_.FullName }}
}}
Get-ChildItem "C:\\Program Files\\Microsoft" -Filter "jdk-*" -ErrorAction SilentlyContinue | ForEach-Object {{
  $bin = Join-Path $_.FullName "bin"
  if (Test-Path $bin) {{ $env:Path = "$bin;$env:Path"; $env:JAVA_HOME = $_.FullName }}
}}
Assert-ZlmCommand java "-version"
if ($env:JAVA_HOME) {{
  Write-Zlm "JAVA_HOME=$env:JAVA_HOME" "OK"
  [System.Environment]::SetEnvironmentVariable("JAVA_HOME", $env:JAVA_HOME, "User")
}}
''')
        return _plain("Java (JDK)", version, platform, script, "powershell", software.official_url,
                      f"- 使用 Eclipse Temurin，winget ID 为 `EclipseAdoptium.Temurin.{feature}.JDK`。\n- 这能避开把 `17.4` 传给 `--version` 导致的「找不到匹配的版本」。\n- 脚本会写入用户级 `JAVA_HOME`。")
    if platform == "macos":
        script = _sh(f"""
zlm_need_brew
brew install --cask temurin@{feature} 2>/dev/null || brew install --cask temurin || brew install openjdk@{feature} || brew install openjdk
zlm_assert java -version
""")
        return _plain("Java (JDK)", version, platform, script, "bash", software.official_url, "macOS 用 Temurin cask。")
    script = _sh(_linux_pkg() + f"""
case "$PKG" in
  apt) sudo apt-get update && sudo apt-get install -y temurin-{feature}-jdk || sudo apt-get install -y openjdk-{feature}-jdk ;;
  *) sudo $PKG install -y java-{feature}-openjdk-devel || sudo $PKG install -y java-21-openjdk-devel ;;
esac
zlm_assert java -version
""")
    return _plain("Java (JDK)", version, platform, script, "bash", software.official_url, "Linux 装 Temurin/OpenJDK。")


def _mysql(software, version, platform):
    if platform == "windows":
        script = _ps(f'''
$RequestedVersion = "{version}"
Write-Zlm "安装 MySQL Server（精确 ID Oracle.MySQL）"
Install-ZlmWinget -PackageId "Oracle.MySQL" -RequestedVersion $RequestedVersion -FallbackId "Oracle.MySQLCommunityServer"
Refresh-ZlmPath
$mysqlBin = "$env:ProgramFiles\\MySQL"
Get-ChildItem $mysqlBin -ErrorAction SilentlyContinue | ForEach-Object {{
  $bin = Join-Path $_.FullName "bin"
  if (Test-Path $bin) {{ $env:Path = "$bin;$env:Path" }}
}}
Write-Zlm "若 mysql 命令还没有，打开「MySQL Installer」完成 Server 组件安装并记住 root 密码。" "WARN"
Get-Command mysql -ErrorAction SilentlyContinue | Out-Null
if (Get-Command mysql -ErrorAction SilentlyContinue) {{
  mysql --version
  Write-Zlm "MySQL 客户端已就绪" "OK"
}} else {{
  Write-Zlm "winget 可能只拉起了 MySQL Installer，请在图形向导里勾选 MySQL Server 再 Finish。" "WARN"
}}
''')
        return _plain("MySQL", version, platform, script, "powershell", software.official_url,
                      "- Windows 的 MySQL 经常先装 Installer 再装 Server。脚本用精确 ID，匹配不到所选版本就装默认版。\n- 不要手工执行 `winget install mysql --version 8.0`。")
    if platform == "macos":
        script = _sh("""
zlm_brew_install mysql
zlm_info "启动服务 brew services start mysql"
brew services start mysql || true
zlm_assert mysql --version
""")
        return _plain("MySQL", version, platform, script, "bash", software.official_url, "macOS 用 brew mysql，随后 brew services start mysql。")
    script = _sh(_linux_pkg() + """
case "$PKG" in
  apt) sudo apt-get update && sudo apt-get install -y mysql-server ;;
  dnf) sudo dnf install -y mysql-server ;;
  yum) sudo yum install -y mysql-server ;;
esac
sudo systemctl enable --now mysql || sudo systemctl enable --now mysqld || true
zlm_assert mysql --version
""")
    return _plain("MySQL", version, platform, script, "bash", software.official_url, "Linux 用发行版 mysql-server。")


def _maven(software, version, platform):
    if platform == "windows":
        script = _ps(f'''
Write-Zlm "安装 Maven，ID=Apache.Maven"
Install-ZlmWinget -PackageId "Apache.Maven" -RequestedVersion "{version}" -CommandName mvn
Refresh-ZlmPath
Assert-ZlmCommand mvn "-version"
''')
        return _plain("Maven", version, platform, script, "powershell", software.official_url, "需要本机已有 JDK。先装 Java 再装 Maven。")
    if platform == "macos":
        script = _sh("zlm_brew_install maven\nzlm_assert mvn -version\n")
        return _plain("Maven", version, platform, script, "bash", software.official_url, "brew install maven")
    script = _sh(_linux_pkg() + """
case "$PKG" in
  apt) sudo apt-get update && sudo apt-get install -y maven ;;
  *) sudo $PKG install -y maven ;;
esac
zlm_assert mvn -version
""")
    return _plain("Maven", version, platform, script, "bash", software.official_url, "发行版 maven 包。")


def _redis(software, version, platform):
    if platform == "windows":
        script = _ps(f'''
Write-Zlm "Windows 上 Redis 官方已停止原生移植，依次尝试 Memurai 开发版 / Redis.Redis"
$ok = $false
try {{
  Install-ZlmWinget -PackageId "Memurai.MemuraiDeveloper" -RequestedVersion ""
  $ok = $true
}} catch {{
  Write-Zlm $_.Exception.Message "WARN"
}}
if (-not $ok) {{
  Install-ZlmWinget -PackageId "Redis.Redis" -RequestedVersion "{version}" -FallbackId "Redis.RedisStack"
}}
Refresh-ZlmPath
if (Get-Command redis-server -ErrorAction SilentlyContinue) {{
  Assert-ZlmCommand redis-server "--version"
}} elseif (Get-Command memurai -ErrorAction SilentlyContinue) {{
  memurai --version
  Write-Zlm "Memurai 已安装（Redis 兼容）" "OK"
}} else {{
  Write-Zlm "命令行尚未出现 redis-server。可改用 WSL: wsl --install 后在 Ubuntu 里 sudo apt install redis-server" "WARN"
}}
''')
        return _plain("Redis", version, platform, script, "powershell", software.official_url,
                      "- Windows 优先 Memurai Developer（Redis 协议兼容）。\n- 失败再试 winget `Redis.Redis`。\n- 都不行就走 WSL。")
    if platform == "macos":
        script = _sh("zlm_brew_install redis\nbrew services start redis || true\nzlm_assert redis-server --version\n")
        return _plain("Redis", version, platform, script, "bash", software.official_url, "brew redis + brew services start redis")
    script = _sh(_linux_pkg() + """
case "$PKG" in
  apt) sudo apt-get update && sudo apt-get install -y redis-server ;;
  *) sudo $PKG install -y redis ;;
esac
sudo systemctl enable --now redis-server || sudo systemctl enable --now redis || true
zlm_assert redis-server --version
""")
    return _plain("Redis", version, platform, script, "bash", software.official_url, "发行版 redis-server")


def _docker(software, version, platform):
    if platform == "windows":
        script = _ps('''
Write-Zlm "安装 Docker Desktop（需要 WSL2 + 重启）"
$wsl = Get-Command wsl -ErrorAction SilentlyContinue
if (-not $wsl) {
  Write-Zlm "未检测到 wsl，将尝试 wsl --install（可能要求重启）" "WARN"
  wsl --install --no-distribution
}
Install-ZlmWinget -PackageId "Docker.DockerDesktop" -RequestedVersion ""
Write-Zlm "Docker Desktop 装完后请从开始菜单启动一次，完成引擎初始化。" "WARN"
Refresh-ZlmPath
if (Get-Command docker -ErrorAction SilentlyContinue) {
  docker --version
} else {
  Write-Zlm "当前会话还没有 docker 命令，启动 Docker Desktop 后再开一个终端验证。" "WARN"
}
''')
        return _plain("Docker", version, platform, script, "powershell", software.official_url,
                      "- 必须启用虚拟化 / WSL2。\n- 安装器结束后重启一次再打开 Docker Desktop。")
    if platform == "macos":
        script = _sh("zlm_brew_cask docker\necho \"请从启动台打开 Docker Desktop 完成初始化\"\n")
        return _plain("Docker", version, platform, script, "bash", software.official_url, "brew --cask docker，然后手动打开 App。")
    script = _sh("""
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER" || true
sudo systemctl enable --now docker || true
docker --version || true
""")
    return _plain("Docker", version, platform, script, "bash", software.official_url, "Linux 用 get.docker.com 官方脚本。")


def _nginx(software, version, platform):
    if platform == "windows":
        script = _ps(f'''
Write-Zlm "安装 Nginx"
Install-ZlmWinget -PackageId "nginxinc.nginx" -RequestedVersion "{version}" -FallbackId "Nginx.Nginx" -CommandName nginx
Refresh-ZlmPath
if (Get-Command nginx -ErrorAction SilentlyContinue) {{
  nginx -v
  Write-Zlm "nginx 已就绪" "OK"
}} else {{
  Write-Zlm "若 winget 无包，将尝试官方 zip 到 $env:USERPROFILE\\nginx" "WARN"
  $ver = "{version}"
  if ($ver -notmatch '^\\d+\\.\\d+') {{ $ver = "1.26.2" }}
  $zip = Join-Path $env:TEMP "nginx.zip"
  $url = "https://nginx.org/download/nginx-$ver.zip"
  try {{
    Invoke-WebRequest $url -OutFile $zip -UseBasicParsing
    $dest = Join-Path $env:USERPROFILE "nginx"
    if (Test-Path $dest) {{ Remove-Item $dest -Recurse -Force }}
    Expand-Archive $zip -DestinationPath $env:USERPROFILE -Force
    Get-ChildItem $env:USERPROFILE -Filter "nginx-*" -Directory | Select-Object -First 1 | ForEach-Object {{
      Rename-Item $_.FullName $dest -ErrorAction SilentlyContinue
      $env:Path = "$($_.FullName);$env:Path"
      & (Join-Path $_.FullName "nginx.exe") -v
    }}
  }} catch {{
    Write-Zlm "官方 zip 下载失败，请打开 https://nginx.org/en/download.html" "ERR"
    throw
  }}
}}
''')
        return _plain("Nginx", version, platform, script, "powershell", software.official_url, "先 winget，失败再下官方 Windows zip。")
    if platform == "macos":
        script = _sh("zlm_brew_install nginx\nzlm_assert nginx -v\n")
        return _plain("Nginx", version, platform, script, "bash", software.official_url, "brew nginx")
    script = _sh(_linux_pkg() + """
case "$PKG" in
  apt) sudo apt-get update && sudo apt-get install -y nginx ;;
  *) sudo $PKG install -y nginx ;;
esac
sudo systemctl enable --now nginx || true
zlm_assert nginx -v
""")
    return _plain("Nginx", version, platform, script, "bash", software.official_url, "发行版 nginx")


def _go(software, version, platform):
    ver = version.lstrip("vV")
    if ver.count(".") == 1:
        ver = ""
    if platform == "windows":
        if ver.count(".") >= 2:
            script = _ps(f'''
$ver = "{ver}"
Write-Zlm "用 go.dev 官方 MSI 安装 Go $ver"
$url = "https://go.dev/dl/go$ver.windows-amd64.msi"
Install-ZlmMsi -Url $url -FileName "go$ver.windows-amd64.msi"
$goBin = "$env:ProgramFiles\\Go\\bin"
if (Test-Path $goBin) {{ $env:Path = "$goBin;$env:Path" }}
Assert-ZlmCommand go "version"
''')
        else:
            script = _ps('''
Write-Zlm "安装 GoLang.Go（不传 --version）"
Install-ZlmWinget -PackageId "GoLang.Go" -RequestedVersion "" -CommandName go
$goBin = "$env:ProgramFiles\\Go\\bin"
if (Test-Path $goBin) { $env:Path = "$goBin;$env:Path" }
Assert-ZlmCommand go "version"
''')
        return _plain("Go", version, platform, script, "powershell", software.official_url, "完整版本走官方 MSI；否则 winget `GoLang.Go` 最新稳定版。")
    if platform == "macos":
        script = _sh("zlm_brew_install go\nzlm_assert go version\n")
        return _plain("Go", version, platform, script, "bash", software.official_url, "brew go")
    script = _sh(_linux_pkg() + """
case "$PKG" in
  apt) sudo apt-get update && sudo apt-get install -y golang-go ;;
  *) sudo $PKG install -y golang ;;
esac
zlm_assert go version
""")
    return _plain("Go", version, platform, script, "bash", software.official_url, "发行版 golang")


def _rust(software, version, platform):
    if platform == "windows":
        script = _ps('''
Write-Zlm "通过 rustup 安装 Rust（不要给 winget 传 rustc 小版本）"
$rustup = Join-Path $env:TEMP "rustup-init.exe"
Invoke-WebRequest "https://win.rustup.rs/x86_64" -OutFile $rustup -UseBasicParsing
Start-Process $rustup -ArgumentList "-y" -Wait
Refresh-ZlmPath
$cargoBin = "$env:USERPROFILE\\.cargo\\bin"
if (Test-Path $cargoBin) { $env:Path = "$cargoBin;$env:Path" }
Assert-ZlmCommand rustc "--version"
Assert-ZlmCommand cargo "--version"
''')
        return _plain("Rust", version, platform, script, "powershell", software.official_url, "始终 rustup -y。默认 stable 工具链。")
    script = _sh("""
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
. "$HOME/.cargo/env"
zlm_assert rustc --version
zlm_assert cargo --version
""")
    return _plain("Rust", version, platform, script, "bash", software.official_url, "官方 rustup 脚本。")


def _mongodb(software, version, platform):
    if platform == "windows":
        script = _ps(f'''
Write-Zlm "安装 MongoDB Server"
Install-ZlmWinget -PackageId "MongoDB.Server" -RequestedVersion "{version}" -FallbackId "MongoDB.Community"
Refresh-ZlmPath
if (Get-Command mongod -ErrorAction SilentlyContinue) {{
  mongod --version
}} else {{
  Write-Zlm "mongod 未进 PATH。检查服务 MongoDB 是否已在 services.msc 里运行。" "WARN"
}}
''')
        return _plain("MongoDB", version, platform, script, "powershell", software.official_url, "winget `MongoDB.Server`，版本解析失败则装默认。")
    if platform == "macos":
        script = _sh("""
zlm_need_brew
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community || true
mongod --version || true
""")
        return _plain("MongoDB", version, platform, script, "bash", software.official_url, "brew tap mongodb/brew && mongodb-community")
    script = _sh(_linux_pkg() + """
echo "请按 https://www.mongodb.com/docs/manual/administration/install-on-linux/ 使用官方源。"
case "$PKG" in
  apt) sudo apt-get update && sudo apt-get install -y mongodb 2>/dev/null || sudo apt-get install -y mongodb-org || true ;;
  *) sudo $PKG install -y mongodb-org || true ;;
esac
mongod --version || true
""")
    return _plain("MongoDB", version, platform, script, "bash", software.official_url, "Linux 建议走 MongoDB 官方源。")


def _postgresql(software, version, platform):
    major = "16"
    ver = version.lstrip("vV")
    if ver and ver[0].isdigit():
        major = ver.split(".")[0]
    if platform == "windows":
        script = _ps(f'''
Write-Zlm "安装 PostgreSQL（ID 不带短版本；若存在 PostgreSQL.PostgreSQL.{major} 会优先）"
$tried = $false
try {{
  Install-ZlmWinget -PackageId "PostgreSQL.PostgreSQL.{major}" -RequestedVersion "" -CommandName psql
  $tried = $true
}} catch {{ Write-Zlm $_.Exception.Message "WARN" }}
if (-not $tried) {{
  Install-ZlmWinget -PackageId "PostgreSQL.PostgreSQL" -RequestedVersion "{version}" -CommandName psql
}}
# EDB 安装器经常不写 PATH；等 bin 落地再手工挂上
$psql = $null
for ($i = 0; $i -lt 20; $i++) {{
  $psql = Resolve-ZlmCommandPath -Command psql
  if ($psql) {{ break }}
  Start-Sleep -Seconds 1
}}
if (-not $psql) {{
  throw "PostgreSQL 装完后仍找不到 psql.exe。请看 C:\\Program Files\\PostgreSQL\\<版本>\\bin 是否存在。"
}}
Add-ZlmUserPath (Split-Path $psql -Parent)
Assert-ZlmCommand psql "--version"
''')
        return _plain("PostgreSQL", version, platform, script, "powershell", software.official_url,
                      f"- 优先 `PostgreSQL.PostgreSQL.{major}`，避免 `--version 16` 这种无效写法。")
    if platform == "macos":
        script = _sh(f"zlm_brew_install postgresql@{major} || zlm_brew_install postgresql\nzlm_assert psql --version\n")
        return _plain("PostgreSQL", version, platform, script, "bash", software.official_url, "brew postgresql@N")
    script = _sh(_linux_pkg() + """
case "$PKG" in
  apt) sudo apt-get update && sudo apt-get install -y postgresql postgresql-contrib ;;
  *) sudo $PKG install -y postgresql-server postgresql-contrib || sudo $PKG install -y postgresql ;;
esac
sudo systemctl enable --now postgresql || true
zlm_assert psql --version
""")
    return _plain("PostgreSQL", version, platform, script, "bash", software.official_url, "发行版 postgresql")


def _homebrew(software, version, platform):
    if platform == "windows":
        md = """# Homebrew

Windows 没有官方 Homebrew。请改用：

- winget（本机已自带）
- 或在 WSL 里安装 brew / apt

macOS / Linux 请把平台切换后再生成方案。
"""
        return {"markdown": md, "script": "", "script_language": "", "official_url": software.official_url, "source": "recipe"}
    script = _sh("""
if command -v brew >/dev/null 2>&1; then
  zlm_ok "Homebrew 已存在"
  brew --version
  exit 0
fi
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
if [ -x /opt/homebrew/bin/brew ]; then
  echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x /home/linuxbrew/.linuxbrew/bin/brew ]; then
  echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> "$HOME/.profile"
  eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
fi
zlm_assert brew --version
""")
    return _plain("Homebrew", version, platform, script, "bash", software.official_url, "官方安装脚本。结束后把 shellenv 写入 profile。")


def _nvm(software, version, platform):
    if platform == "windows":
        script = _ps(f'''
Write-Zlm "安装 nvm-windows（CoreyButler.NVMforWindows）"
Install-ZlmWinget -PackageId "CoreyButler.NVMforWindows" -RequestedVersion "{version}" -CommandName nvm
Refresh-ZlmPath
$nvmDir = "$env:APPDATA\\nvm"
if (Test-Path "$nvmDir\\nvm.exe") {{ $env:Path = "$nvmDir;$env:Path" }}
if (Get-Command nvm -ErrorAction SilentlyContinue) {{
  nvm version
  Write-Zlm "接下来可执行: nvm install lts; nvm use lts" "OK"
}} else {{
  Write-Zlm "nvm 需要新开一个终端才能进 PATH。" "WARN"
}}
''')
        return _plain("nvm", version, platform, script, "powershell", software.official_url, "Windows 用 nvm-windows，和 macOS 的 nvm-sh 不是同一个项目。")
    script = _sh("""
if [ -s "$HOME/.nvm/nvm.sh" ]; then
  . "$HOME/.nvm/nvm.sh"
  zlm_ok "nvm 已存在"
  nvm --version
  exit 0
fi
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
zlm_assert nvm --version
echo "随后可执行: nvm install --lts && nvm use --lts"
""")
    return _plain("nvm", version, platform, script, "bash", software.official_url, "官方 nvm-sh 安装脚本。")


def _vscode(software, version, platform):
    urls = {
        "windows": "https://code.visualstudio.com/sha/download?build=stable&os=win32-x64-user",
        "macos": "https://code.visualstudio.com/sha/download?build=stable&os=darwin-universal",
        "linux": "https://code.visualstudio.com/Download",
    }
    return official_plan(
        "VS Code",
        version,
        platform,
        software.official_url,
        f"- 直链（当前平台）：{urls.get(platform, software.official_url)}\n- 也可以用商店 / winget `Microsoft.VisualStudioCode`，但官方页最稳。",
    )


def _idea(software, version, platform):
    return official_plan(
        "IntelliJ IDEA",
        version,
        platform,
        software.official_url,
        "- Community 免费版即可学习。\n- 用 Toolbox 也可以，但仍以官方页为准。",
    )


RECIPES = {
    "git": _git,
    "nodejs": _nodejs,
    "python": _python,
    "jdk": _jdk,
    "mysql": _mysql,
    "maven": _maven,
    "redis": _redis,
    "docker": _docker,
    "nginx": _nginx,
    "go": _go,
    "rust": _rust,
    "mongodb": _mongodb,
    "postgresql": _postgresql,
    "homebrew": _homebrew,
    "nvm": _nvm,
    "vscode": _vscode,
    "idea": _idea,
}
