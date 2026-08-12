<#
.SYNOPSIS
    Create Desktop and Start Menu shortcuts for qtxterm, with the app icon.

.DESCRIPTION
    Run after installing the app:

        uv tool install .
        powershell -ExecutionPolicy Bypass -File scripts\install-shortcut.ps1

    Windows has blocked programmatic taskbar pinning since Windows 10, so the
    last step is manual: find qtxterm in the Start Menu, right-click, and
    choose "Pin to taskbar".

.PARAMETER Exe
    Path to qtxtermw.exe. Defaults to the uv tool install location. Note the
    trailing "w": that is the console-less entry point, so starting from the
    shortcut doesn't leave a stray cmd window behind the app. Plain
    qtxterm.exe is the console one, for running from a terminal.

.PARAMETER Icon
    Path to the .ico. Defaults to the copy inside the installed package, and
    falls back to this repo's copy.
#>
[CmdletBinding()]
param(
    [string]$Exe  = (Join-Path $env:USERPROFILE ".local\bin\qtxtermw.exe"),
    [string]$Icon = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Exe)) {
    Write-Error "qtxtermw.exe not found at $Exe. Run 'uv tool install .' first, or pass -Exe."
}

if (-not $Icon) {
    # Prefer the icon shipped inside the installed package, so the shortcut
    # keeps working if this repo is moved or deleted. The tool directory is
    # asked of uv rather than hardcoded - it is %APPDATA%\uv\tools on Windows,
    # elsewhere on other platforms and older uv versions.
    $installed = ""
    try {
        $toolDir = (& uv tool dir 2>$null | Select-Object -Last 1)
        if ($toolDir) {
            $candidate = Join-Path $toolDir.Trim() "qtxterm\Lib\site-packages\qtxterm\assets\logo.ico"
            if (Test-Path $candidate) { $installed = $candidate }
        }
    } catch {
        # uv not on PATH; fall back to the repo copy below.
    }

    $repo = Join-Path $PSScriptRoot "..\src\qtxterm\assets\logo.ico"
    $Icon = if ($installed) { $installed } else { (Resolve-Path $repo).Path }
}

if (-not (Test-Path $Icon)) {
    Write-Error "Icon not found at $Icon. Run 'uv run python scripts/make_icon.py' first."
}

$shell = New-Object -ComObject WScript.Shell
$targets = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "qtxterm.lnk"),
    (Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\qtxterm.lnk")
)

foreach ($path in $targets) {
    $parent = Split-Path $path -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }

    $link = $shell.CreateShortcut($path)
    $link.TargetPath       = $Exe
    $link.IconLocation     = "$Icon,0"
    $link.Description      = "Cross-platform tabbed terminal"
    $link.WorkingDirectory = $env:USERPROFILE
    $link.Save()
    Write-Host "created $path"
}

Write-Host ""
Write-Host "Icon:   $Icon"
Write-Host "Target: $Exe"
Write-Host ""
Write-Host "To pin: open the Start Menu, find qtxterm, right-click -> Pin to taskbar."
Write-Host "(Windows blocks scripts from pinning, so that step has to be manual.)"
