# Dot-source before installing project dependencies. Only this process and its
# children are affected; installed environments and global settings are unchanged.
$projectCacheRoot = Join-Path (Split-Path -Parent $PSScriptRoot) 'workspace/runtime/package_cache'
$env:UV_CACHE_DIR = Join-Path $projectCacheRoot 'uv'
$env:PIP_CACHE_DIR = Join-Path $projectCacheRoot 'pip'
New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR,$env:PIP_CACHE_DIR | Out-Null
Write-Output "Project package cache: $projectCacheRoot"
