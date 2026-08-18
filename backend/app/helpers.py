"""Windows / macOS / Linux 安装运行时。

核心目标：彻底避免 winget「找不到匹配的版本：17.4」这类错误。
策略：
1. 永远用 --id 精确包名，不用中文/英文软件名去碰运气
2. 用户要的 17.4 只是前缀，必须先在本机 winget 版本列表里解析成完整号
3. 解析失败就安装该包默认最新版，绝不把短版本传给 --version
4. 指定版本的运行时优先走官方安装包 URL
"""

PS_HELPER = r'''
# ===== 装了吗 · 安装运行时（Windows PowerShell）=====
# 把 chcp / UTF-8 / PATH 刷新 / winget 安全安装 放在所有脚本前面
$ErrorActionPreference = "Continue"
try { chcp 65001 > $null } catch {}
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Zlm {
    param([string]$Message, [string]$Level = "INFO")
    $prefix = switch ($Level) {
        "OK"    { "[装了]" }
        "WARN"  { "[注意]" }
        "ERR"   { "[没装上]" }
        default { "[进行中]" }
    }
    Write-Host "$prefix $Message"
}

function Refresh-ZlmPath {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $merged = @()
    $seen = @{}
    foreach ($part in @(($env:Path -split ';') + ($machine -split ';') + ($user -split ';'))) {
        $t = "$part".Trim()
        if (-not $t) { continue }
        $key = $t.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        $merged += $t
    }
    $env:Path = ($merged -join ';')
}

function Add-ZlmUserPath {
    param([Parameter(Mandatory=$true)][string]$Directory)
    if (-not (Test-Path $Directory)) { return }
    $env:Path = "$Directory;$env:Path"
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $user) { $user = "" }
    if ($user -notlike "*$Directory*") {
        $next = if ($user) { "$Directory;$user" } else { $Directory }
        [System.Environment]::SetEnvironmentVariable("Path", $next, "User")
        Write-Zlm "已把 $Directory 写入用户 PATH"
    }
}

function Resolve-ZlmCommandPath {
    param([Parameter(Mandatory=$true)][string]$Command)
    $cmd = Get-Command $Command -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    $exe = if ($Command -match '\.exe$') { $Command } else { "$Command.exe" }
    $globs = switch ($Command.ToLower()) {
        "psql" { @(
            "$env:ProgramFiles\PostgreSQL\*\bin\psql.exe",
            "${env:ProgramFiles(x86)}\PostgreSQL\*\bin\psql.exe"
        ) }
        "postgres" { @("$env:ProgramFiles\PostgreSQL\*\bin\postgres.exe") }
        "pg_isready" { @("$env:ProgramFiles\PostgreSQL\*\bin\pg_isready.exe") }
        "java" { @(
            "$env:ProgramFiles\Eclipse Adoptium\*\bin\java.exe",
            "$env:ProgramFiles\Microsoft\jdk-*\bin\java.exe",
            "$env:ProgramFiles\Java\*\bin\java.exe"
        ) }
        "mvn" { @("$env:ProgramFiles\Apache\maven\*\bin\mvn.cmd", "$env:ProgramFiles\Maven\*\bin\mvn.cmd") }
        "go" { @("$env:ProgramFiles\Go\bin\go.exe") }
        "git" { @("$env:ProgramFiles\Git\cmd\git.exe", "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe") }
        "node" { @("$env:ProgramFiles\nodejs\node.exe") }
        "python" { @("$env:LOCALAPPDATA\Programs\Python\*\python.exe", "$env:ProgramFiles\Python*\python.exe") }
        "nginx" { @("$env:USERPROFILE\nginx\nginx.exe", "$env:ProgramFiles\nginx*\nginx.exe") }
        default { @(
            "$env:ProgramFiles\*\bin\$exe",
            "$env:ProgramFiles\*\$exe",
            "$env:LOCALAPPDATA\Programs\*\bin\$exe",
            "$env:LOCALAPPDATA\Programs\*\$exe"
        ) }
    }
    foreach ($g in $globs) {
        $hit = Get-Item $g -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

function Test-ZlmAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ZlmWingetVersions {
    param([Parameter(Mandatory=$true)][string]$PackageId)
    $raw = & winget show --id $PackageId --exact --versions --accept-source-agreements 2>&1 | Out-String
    $versions = @()
    foreach ($line in ($raw -split "`r?`n")) {
        $t = $line.Trim()
        if ($t -match '^\d+(\.\d+){1,4}([.-][\w]+)?$') {
            $versions += $t
        }
    }
    return $versions
}

function Resolve-ZlmWingetVersion {
    param(
        [Parameter(Mandatory=$true)][string]$PackageId,
        [string]$Requested = ""
    )
    if (-not $Requested -or $Requested -match '^(latest|stable|lts|最新|稳定|最新稳定版)$') {
        return $null
    }
    $req = $Requested.Trim().TrimStart("v", "V")
    $list = @(Get-ZlmWingetVersions -PackageId $PackageId)
    if ($list.Count -eq 0) {
        Write-Zlm "读不到 $PackageId 的版本清单，将安装默认最新版，避免把「$req」直接丢给 winget。" "WARN"
        return $null
    }
    if ($list -contains $req) { return $req }
    $prefixHits = @($list | Where-Object { $_ -eq $req -or $_ -like "$req.*" })
    if ($prefixHits.Count -gt 0) {
        $best = $prefixHits | Sort-Object { $_.Length } -Descending | Select-Object -First 1
        Write-Zlm "版本 $req 已解析为源里的 $best" "OK"
        return $best
    }
    $featureHits = @($list | Where-Object { $_.StartsWith($req) })
    if ($featureHits.Count -gt 0) {
        $best = $featureHits | Select-Object -First 1
        Write-Zlm "版本 $req 模糊匹配到 $best" "OK"
        return $best
    }
    Write-Zlm "源里没有与 $req 匹配的版本（这就是「找不到匹配的版本」的原因）。改装 $PackageId 的默认最新版。" "WARN"
    return $null
}

function Assert-ZlmWinget {
    $cmd = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "本机没有 winget。请先打开 Microsoft Store 安装「应用安装程序」，或从 https://aka.ms/getwinget 安装。"
    }
    try { & winget source update --disable-interactivity 2>$null | Out-Null } catch {}
}

function Install-ZlmWinget {
    param(
        [Parameter(Mandatory=$true)][string]$PackageId,
        [string]$RequestedVersion = "",
        [string]$FallbackId = "",
        [string]$CommandName = ""
    )
    Assert-ZlmWinget
    Write-Zlm "准备安装包 ID: $PackageId"

    $probe = & winget list --id $PackageId --exact --disable-interactivity --accept-source-agreements 2>&1 | Out-String
    $already = $false
    if ($CommandName) {
        Refresh-ZlmPath
        if (Resolve-ZlmCommandPath -Command $CommandName) { $already = $true }
    }
    if (-not $already -and $probe -match [regex]::Escape($PackageId) -and $probe -notmatch '找不到与输入条件匹配的已安装程序包|No installed package found') {
        $already = $true
    }
    if ($already) {
        Write-Zlm "$PackageId 已经在本机，跳过下载，刷新 PATH 后做验证。" "OK"
        Refresh-ZlmPath
        return
    }

    $search = & winget search --id $PackageId --exact --accept-source-agreements 2>&1 | Out-String
    $found = $search -match [regex]::Escape($PackageId) -and $search -notmatch '找不到与输入条件匹配的程序包|No package found matching'
    if (-not $found -and $FallbackId) {
        Write-Zlm "没找到 $PackageId，改用备用 ID $FallbackId" "WARN"
        $PackageId = $FallbackId
        $found = $true
    }
    if (-not $found) {
        throw "winget 源里没有精确 ID「$PackageId」。不要用软件中文名或短版本号硬装。"
    }

    $exactVersion = Resolve-ZlmWingetVersion -PackageId $PackageId -Requested $RequestedVersion
    $args = @(
        "install", "--id", $PackageId, "--exact",
        "--accept-package-agreements", "--accept-source-agreements",
        "--disable-interactivity"
    )
    if ($exactVersion) {
        $args += @("--version", $exactVersion)
        Write-Zlm "使用已解析的精确版本 $exactVersion"
    } else {
        Write-Zlm "不向 winget 传递 --version，安装该 ID 的默认最新版（这是故意的，用来躲开版本号对不上）。"
    }

    Write-Zlm "执行: winget $($args -join ' ')"
    & winget @args
    $code = $LASTEXITCODE
    if ($code -ne 0 -and $code -ne -1978335189) {
        # -1978335189 = already installed
        if ($exactVersion) {
            Write-Zlm "带版本安装失败（exit $code），去掉 --version 再试一次。" "WARN"
            $args = @(
                "install", "--id", $PackageId, "--exact",
                "--accept-package-agreements", "--accept-source-agreements",
                "--disable-interactivity"
            )
            & winget @args
            $code = $LASTEXITCODE
        }
        if ($code -ne 0 -and $code -ne -1978335189) {
            throw "winget 安装 $PackageId 失败，退出码 $code"
        }
    }
    Refresh-ZlmPath
    Write-Zlm "winget 阶段完成" "OK"
}

function Install-ZlmMsi {
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [Parameter(Mandatory=$true)][string]$FileName,
        [string]$ExtraArgs = "/qn /norestart"
    )
    $dest = Join-Path $env:TEMP $FileName
    Write-Zlm "下载 $Url"
    try {
        Invoke-WebRequest -Uri $Url -OutFile $dest -UseBasicParsing
    } catch {
        throw "下载失败: $Url 。请检查版本号是否真实存在。"
    }
    if (-not (Test-Path $dest) -or (Get-Item $dest).Length -lt 10000) {
        throw "下载的安装包异常小，URL 很可能 404。文件: $dest"
    }
    Write-Zlm "静默安装 $dest"
    $p = Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$dest`" $ExtraArgs" -Wait -PassThru
    if ($p.ExitCode -ne 0 -and $p.ExitCode -ne 3010) {
        throw "MSI 安装失败，退出码 $($p.ExitCode)"
    }
    Refresh-ZlmPath
}

function Install-ZlmExe {
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [Parameter(Mandatory=$true)][string]$FileName,
        [string]$Args = "/quiet"
    )
    $dest = Join-Path $env:TEMP $FileName
    Write-Zlm "下载 $Url"
    Invoke-WebRequest -Uri $Url -OutFile $dest -UseBasicParsing
    if (-not (Test-Path $dest) -or (Get-Item $dest).Length -lt 10000) {
        throw "下载的安装包异常小，URL 很可能 404。"
    }
    Write-Zlm "运行安装程序 $dest $Args"
    $p = Start-Process -FilePath $dest -ArgumentList $Args -Wait -PassThru
    if ($p.ExitCode -ne 0 -and $p.ExitCode -ne 3010) {
        throw "安装程序失败，退出码 $($p.ExitCode)"
    }
    Refresh-ZlmPath
}

function Assert-ZlmCommand {
    param(
        [Parameter(Mandatory=$true)][string]$Command,
        [string]$VersionArgs = "--version"
    )
    Refresh-ZlmPath
    $resolved = Resolve-ZlmCommandPath -Command $Command
    if (-not $resolved) {
        Start-Sleep -Seconds 2
        Refresh-ZlmPath
        $resolved = Resolve-ZlmCommandPath -Command $Command
    }
    if (-not $resolved) {
        throw "验证失败：找不到命令 $Command。新装的软件有时要重新打开终端才进 PATH。"
    }
    Add-ZlmUserPath (Split-Path $resolved -Parent)
    Refresh-ZlmPath
    Write-Zlm "验证: $resolved $VersionArgs"
    $argList = @()
    if ($VersionArgs -and $VersionArgs.Trim()) {
        $argList = $VersionArgs.Trim().Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
    }
    & $resolved @argList
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "验证失败：$Command 已找到但执行退出码 $LASTEXITCODE"
    }
    Write-Zlm "$Command 已出现在本机" "OK"
}
'''

BASH_HELPER = r'''
# ===== 装了吗 · 安装运行时（macOS / Linux Bash）=====
set -euo pipefail

zlm_ok()   { echo "[装了] $*"; }
zlm_info() { echo "[进行中] $*"; }
zlm_warn() { echo "[注意] $*"; }
zlm_err()  { echo "[没装上] $*"; }

zlm_need_brew() {
  if ! command -v brew >/dev/null 2>&1; then
    zlm_info "没找到 Homebrew，先装 brew"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [ -x /opt/homebrew/bin/brew ]; then
      eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
      eval "$(/usr/local/bin/brew shellenv)"
    fi
  fi
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew 安装后仍不在 PATH，请按 brew 安装结束时的提示把 shellenv 写进 ~/.zprofile 后再跑一次。" >&2
    exit 1
  fi
}

zlm_brew_install() {
  local formula="$1"
  zlm_need_brew
  if brew list --formula "$formula" >/dev/null 2>&1 || brew list --cask "$formula" >/dev/null 2>&1; then
    zlm_ok "$formula 已经装过"
    return
  fi
  zlm_info "brew install $formula"
  brew install "$formula"
}

zlm_brew_cask() {
  local cask="$1"
  zlm_need_brew
  if brew list --cask "$cask" >/dev/null 2>&1; then
    zlm_ok "$cask 已经装过"
    return
  fi
  zlm_info "brew install --cask $cask"
  brew install --cask "$cask"
}

zlm_assert() {
  local cmd="$1"
  shift || true
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "验证失败：找不到命令 $cmd。请新开一个终端再试。" >&2
    exit 1
  fi
  zlm_info "验证: $cmd $*"
  "$cmd" "$@"
  zlm_ok "$cmd 已出现在本机"
}
'''
