param(
    [string]$SourceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) "releases"),
    [string]$Version = (Get-Date -Format "yyyyMMdd-HHmmss")
)

$ErrorActionPreference = "Stop"
$source = (Resolve-Path -LiteralPath $SourceRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $source "server.py") -PathType Leaf)) {
    throw "SourceRoot is not an ArchAI Builder directory: $source"
}

if (-not (Test-Path -LiteralPath $OutputRoot)) {
    New-Item -ItemType Directory -Path $OutputRoot | Out-Null
}
$output = (Resolve-Path -LiteralPath $OutputRoot).Path
$release = Join-Path $output $Version
if (Test-Path -LiteralPath $release) {
    throw "Release already exists: $release"
}
New-Item -ItemType Directory -Path $release | Out-Null
$release = (Resolve-Path -LiteralPath $release).Path
if (-not $release.StartsWith($output, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Release path escaped OutputRoot"
}

function Copy-ReleaseFile {
    param([string]$RelativePath)
    $from = Join-Path $source $RelativePath
    if (-not (Test-Path -LiteralPath $from -PathType Leaf)) {
        throw "Required release file is missing: $RelativePath"
    }
    $to = Join-Path $release $RelativePath
    $parent = Split-Path -Parent $to
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
    Copy-Item -LiteralPath $from -Destination $to
}

function Copy-ReleaseTree {
    param([string]$RelativeRoot)
    $treeRoot = Join-Path $source $RelativeRoot
    if (-not (Test-Path -LiteralPath $treeRoot -PathType Container)) {
        throw "Required release directory is missing: $RelativeRoot"
    }
    Get-ChildItem -LiteralPath $treeRoot -File -Recurse | Where-Object {
        $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and
        $_.FullName -notmatch '[\\/]shots[\\/]' -and
        $_.Name -notlike '*-e2e.png' -and
        $_.Extension -notin @('.pyc', '.pyo', '.log', '.key')
    } | ForEach-Object {
        $relative = $_.FullName.Substring($source.Length).TrimStart('\', '/')
        Copy-ReleaseFile $relative
    }
}

function Get-Sha256 {
    param([string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    try {
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace("-", "").ToLowerInvariant()
        } finally {
            $sha.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
}

Get-ChildItem -LiteralPath $source -File -Filter "*.py" | Where-Object {
    -not $_.Name.StartsWith("_")
} | ForEach-Object {
    Copy-ReleaseFile $_.Name
}

@(
    "requirements.txt",
    "README.md",
    ".env.example"
) | ForEach-Object { Copy-ReleaseFile $_ }

Get-ChildItem -LiteralPath $source -File -Filter "*.bat" |
    ForEach-Object { Copy-ReleaseFile $_.Name }

@(
    "ArchAI_Image_DB",
    "data",
    "images",
    "knowledge",
    "modules",
    "prompts",
    "vector_db"
) | ForEach-Object { Copy-ReleaseTree $_ }

Get-ChildItem -LiteralPath (Join-Path $source "demo") -File -Filter "*.html" |
    ForEach-Object { Copy-ReleaseFile ("demo/" + $_.Name) }
Copy-ReleaseTree "demo/vendor"

$manifestPath = Join-Path $release "manifest.sha256"
$manifestLines = Get-ChildItem -LiteralPath $release -File -Recurse |
    Where-Object { $_.FullName -ne $manifestPath } |
    Sort-Object FullName |
    ForEach-Object {
        $relative = $_.FullName.Substring($release.Length).TrimStart('\', '/').Replace('\', '/')
        $hash = Get-Sha256 $_.FullName
        "$hash  $relative"
    }
[IO.File]::WriteAllLines($manifestPath, $manifestLines, [Text.UTF8Encoding]::new($false))

Write-Output $release
