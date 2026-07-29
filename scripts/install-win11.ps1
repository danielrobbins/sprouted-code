<#
.SYNOPSIS
Installs a downloaded Sprouted Code Windows archive.

.DESCRIPTION
Finds the newest matching Sprouted Code archive in the current directory, the
script directory, or the user's Downloads directory and installs it. An
existing installation is replaced only after confirmation.

.PARAMETER Archive
Path to a specific Sprouted Code Windows ZIP archive.

.PARAMETER Architecture
Windows build architecture. The default, auto, detects x64 or ARM64.

.PARAMETER Force
Replace an existing installation without prompting.
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string] $Archive,

    [ValidateSet('auto', 'x64', 'arm64')]
    [string] $Architecture = 'auto',

    [string] $InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Sprouted Code'),

    [string] $StartMenuDirectory = (
        Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
    ),

    [switch] $Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Architecture -eq 'auto') {
    $Architecture = switch (
        [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
    ) {
        ([System.Runtime.InteropServices.Architecture]::X64)   { 'x64' }
        ([System.Runtime.InteropServices.Architecture]::Arm64) { 'arm64' }
        default { throw "Unsupported Windows architecture: $_" }
    }
}

if ($Archive) {
    $ArchivePath = (Resolve-Path -LiteralPath $Archive).Path
} else {
    $Pattern = "sprouted-code-*-win32-$Architecture.zip"
    $SearchDirectories = @(
        (Get-Location).Path
        $PSScriptRoot
        (Join-Path $HOME 'Downloads')
    ) | Select-Object -Unique

    $ArchivePath = $SearchDirectories |
        Where-Object { Test-Path -LiteralPath $_ -PathType Container } |
        ForEach-Object {
            Get-ChildItem -LiteralPath $_ -Filter $Pattern -File
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName

    if (-not $ArchivePath) {
        throw "Could not find $Pattern. Put the downloaded archive in this directory or pass its path to -Archive."
    }
}

$ArchiveFile = Get-Item -LiteralPath $ArchivePath
$ArchivePattern = '^sprouted-code-(?<version>\d{4}\.\d{2}\.\d+)-win32-(?<architecture>x64|arm64)\.zip$'
if ($ArchiveFile.Name -notmatch $ArchivePattern) {
    throw "The archive name is not recognized: $($ArchiveFile.Name)"
}
if ($Matches.architecture -ne $Architecture) {
    throw "The selected archive is for $($Matches.architecture), but the requested architecture is $Architecture."
}

$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$InstallParent = Split-Path -Parent $InstallDir
$InstallRoot = [System.IO.Path]::GetPathRoot($InstallDir)
$RelativeInstallPath = $InstallDir.Substring($InstallRoot.Length).Trim('\', '/')
$InstallDepth = ($RelativeInstallPath -split '[\\/]').Count

if (
    $InstallDepth -lt 2 -or
    $InstallDir -eq [System.IO.Path]::GetFullPath($HOME) -or
    $InstallDir -eq [System.IO.Path]::GetFullPath($env:LOCALAPPDATA)
) {
    throw "Refusing to replace unsafe installation directory: $InstallDir"
}

if ((Test-Path -LiteralPath $InstallDir) -and -not $Force) {
    Write-Host "An existing Sprouted Code installation was found at:"
    Write-Host "  $InstallDir"
    Write-Host "All files inside that directory will be removed."
    $Response = Read-Host 'Replace it? [y/N]'
    if ($Response -notmatch '(?i)^(y|yes)$') {
        Write-Host 'Installation cancelled.'
        return
    }
}

$StagingDir = Join-Path $InstallParent (
    '.Sprouted Code.installing-' + [guid]::NewGuid().ToString('N')
)
$BackupDir = Join-Path $InstallParent (
    '.Sprouted Code.backup-' + [guid]::NewGuid().ToString('N')
)
$ShortcutPath = Join-Path $StartMenuDirectory 'Sprouted Code.lnk'
$InstalledNewVersion = $false

New-Item -ItemType Directory -Force -Path $InstallParent | Out-Null

try {
    Write-Host "Installing $($ArchiveFile.Name)..."
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $StagingDir

    $StagedExecutable = Join-Path $StagingDir 'Sprouted Code.exe'
    if (-not (Test-Path -LiteralPath $StagedExecutable -PathType Leaf)) {
        throw "The archive does not contain the expected Sprouted Code executable."
    }

    if (Test-Path -LiteralPath $InstallDir) {
        try {
            Move-Item -LiteralPath $InstallDir -Destination $BackupDir
        } catch {
            throw "Unable to replace the existing installation. Close Sprouted Code and try again. $($_.Exception.Message)"
        }
    }

    Move-Item -LiteralPath $StagingDir -Destination $InstallDir
    $InstalledNewVersion = $true

    New-Item -ItemType Directory -Force -Path $StartMenuDirectory | Out-Null
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = Join-Path $InstallDir 'Sprouted Code.exe'
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.IconLocation = "$($Shortcut.TargetPath),0"
    $Shortcut.Description = 'Sprouted Code'
    $Shortcut.Save()

    if (Test-Path -LiteralPath $BackupDir) {
        Remove-Item -LiteralPath $BackupDir -Recurse -Force
    }
} catch {
    if (
        $InstalledNewVersion -and
        (Test-Path -LiteralPath $InstallDir)
    ) {
        Remove-Item -LiteralPath $InstallDir -Recurse -Force
    }
    if (
        (Test-Path -LiteralPath $BackupDir) -and
        -not (Test-Path -LiteralPath $InstallDir)
    ) {
        Move-Item -LiteralPath $BackupDir -Destination $InstallDir
    }
    throw
} finally {
    if (Test-Path -LiteralPath $StagingDir) {
        Remove-Item -LiteralPath $StagingDir -Recurse -Force
    }
}

Write-Host "Sprouted Code is installed at $InstallDir"
Write-Host 'Open the Start Menu and search for Sprouted Code.'
