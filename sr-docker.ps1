# Run SendRepo from the container image, against the current directory.
#
#   .\sr-docker.ps1 my-project
#   .\sr-docker.ps1 my-project --dry-run
#
# Windows equivalent of ./sr-docker — needs only Docker Desktop, no WSL rsync
# setup, no Python. Override the defaults with environment variables:
#   SENDREPO_IMAGE, SENDREPO_CONFIG_DIR, SENDREPO_SSH_DIR, SENDREPO_WORKSPACE
$ErrorActionPreference = 'Stop'

$image     = if ($env:SENDREPO_IMAGE)      { $env:SENDREPO_IMAGE }      else { 'sendrepo-cli:latest' }
$configDir = if ($env:SENDREPO_CONFIG_DIR) { $env:SENDREPO_CONFIG_DIR } else { Join-Path $HOME '.config\sendrepo' }
$sshDir    = if ($env:SENDREPO_SSH_DIR)    { $env:SENDREPO_SSH_DIR }    else { Join-Path $HOME '.ssh' }
$workspace = if ($env:SENDREPO_WORKSPACE)  { $env:SENDREPO_WORKSPACE }  else { (Get-Location).Path }

if (-not (Test-Path (Join-Path $configDir 'config.yaml'))) {
    Write-Error "No config.yaml in $configDir — set SENDREPO_CONFIG_DIR to where yours lives."
}

$acceptNew = if ($env:SENDREPO_SSH_ACCEPT_NEW) { $env:SENDREPO_SSH_ACCEPT_NEW } else { '0' }
# Extra `docker run` flags, e.g. SENDREPO_DOCKER_ARGS="--network host"
$extra = if ($env:SENDREPO_DOCKER_ARGS) { $env:SENDREPO_DOCKER_ARGS -split '\s+' } else { @() }

docker run --rm -it `
    -v "${workspace}:/workspace" `
    -v "${configDir}:/config:ro" `
    -v "${sshDir}:/ssh-keys:ro" `
    -e "SENDREPO_SSH_ACCEPT_NEW=$acceptNew" `
    @extra `
    $image @args

exit $LASTEXITCODE
