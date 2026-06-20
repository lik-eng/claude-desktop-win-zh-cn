<#
.SYNOPSIS
    非交互安装 Claude Desktop 中文补丁（自动提权）。
.DESCRIPTION
    等价于 claude-zh-cn.ps1 -Action install，供脚本/快捷方式直接调用。
#>
[CmdletBinding()]
param()
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ScriptDir 'claude-zh-cn.ps1') -Action install
