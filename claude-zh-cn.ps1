<#
.SYNOPSIS
    Claude Desktop 中文补丁 — 交互式安装 / 卸载 / 状态查看。
.DESCRIPTION
    自动提权到管理员；关闭 Claude；调用 Python 脚本完成打补丁或还原。
.NOTES
    需要：Windows + Python 3 + 管理员权限。
    每次 Claude Desktop 更新后需重新运行安装。
#>

[CmdletBinding()]
param(
    [ValidateSet('menu', 'install', 'uninstall', 'status')]
    [string]$Action = 'menu'
)

$ErrorActionPreference = 'Stop'
chcp 65001 > $null              # 控制台用 UTF-8，正确显示中文
$OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Scripts   = Join-Path $ScriptDir 'scripts'

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-SelfElevate {
    param([string]$ElevAction)
    Write-Host '需要管理员权限，正在请求提权...' -ForegroundColor Yellow
    $argList = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', "`"$($MyInvocation.MyCommand.Path)`"",
        '-Action', $ElevAction
    )
    try {
        Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $argList
    } catch {
        Write-Host '提权被取消或失败。请手动以管理员身份运行本脚本。' -ForegroundColor Red
    }
}

function Find-Python {
    foreach ($cmd in @('python', 'py')) {
        $exe = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($exe) {
            if ($cmd -eq 'py') { return @{ Exe = $exe.Source; Pre = @('-3') } }
            return @{ Exe = $exe.Source; Pre = @() }
        }
    }
    return $null
}

function Invoke-PyScript {
    param([string]$ScriptName, [string[]]$ExtraArgs = @())
    $py = Find-Python
    if (-not $py) {
        Write-Host '未检测到 Python。请先安装 Python 3 并加入 PATH：https://www.python.org/downloads/' -ForegroundColor Red
        return 1
    }
    $env:PYTHONIOENCODING = 'utf-8'
    $script = Join-Path $Scripts $ScriptName
    $allArgs = @($py.Pre + @($script) + $ExtraArgs)
    # 直接把 Python 的输出写到主机（立即显示、且不混入函数返回值）
    & $py.Exe @allArgs | Out-Host
    return $LASTEXITCODE
}

function Stop-ClaudeProcess {
    $procs = Get-Process -Name 'claude' -ErrorAction SilentlyContinue
    if ($procs) {
        Write-Host '正在关闭 Claude Desktop...' -ForegroundColor Yellow
        $procs | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
}

# ---------------------------------------------------------------------------
# 主操作
# ---------------------------------------------------------------------------

function Do-Install {
    Write-Host ''
    Write-Host '== 安装中文补丁 ==' -ForegroundColor Cyan
    # 先（在普通权限下也可）生成译文，需联网
    Write-Host '步骤 1/2：生成译文资源（需联网）...' -ForegroundColor Cyan
    $rc = Invoke-PyScript 'build_translations.py'
    if ($rc -ne 0) {
        Write-Host "生成译文失败（退出码 $rc）。" -ForegroundColor Red
        return
    }
    Write-Host ''
    Write-Host '步骤 2/2：应用补丁到安装目录...' -ForegroundColor Cyan
    Stop-ClaudeProcess
    $rc = Invoke-PyScript 'patch_install.py'
    if ($rc -ne 0) {
        Write-Host "打补丁失败（退出码 $rc）。" -ForegroundColor Red
    }
}

function Do-Uninstall {
    Write-Host ''
    Write-Host '== 卸载中文补丁 ==' -ForegroundColor Cyan
    Stop-ClaudeProcess
    $rc = Invoke-PyScript 'restore.py'
    if ($rc -ne 0) {
        Write-Host "卸载失败（退出码 $rc）。" -ForegroundColor Red
    }
}

function Do-Status {
    Write-Host ''
    Write-Host '== 状态 ==' -ForegroundColor Cyan
    # dry-run 会打印安装目录、白名单文件、入口 chunk 等定位信息
    $null = Invoke-PyScript 'patch_install.py' @('--dry-run')
}

function Show-Menu {
    while ($true) {
        Write-Host ''
        Write-Host '======================================' -ForegroundColor DarkCyan
        Write-Host '  Claude Desktop 中文补丁' -ForegroundColor Cyan
        Write-Host '======================================' -ForegroundColor DarkCyan
        Write-Host '  [1] 安装 / 更新中文补丁'
        Write-Host '  [2] 卸载（恢复官方原状）'
        Write-Host '  [3] 查看状态（探测安装与定位）'
        Write-Host '  [0] 退出'
        Write-Host ''
        $choice = Read-Host '请选择'
        switch ($choice) {
            '1' { Do-Install }
            '2' { Do-Uninstall }
            '3' { Do-Status }
            '0' { return }
            default { Write-Host '无效选择。' -ForegroundColor Yellow }
        }
    }
}

# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

# 安装/卸载需要管理员；menu 与 status 也建议管理员（status 只读可不强制）
$needsAdmin = ($Action -in @('install', 'uninstall', 'menu'))
if ($needsAdmin -and -not (Test-Admin)) {
    Invoke-SelfElevate -ElevAction $Action
    return
}

switch ($Action) {
    'install'   { Do-Install }
    'uninstall' { Do-Uninstall }
    'status'    { Do-Status }
    default     { Show-Menu }
}
