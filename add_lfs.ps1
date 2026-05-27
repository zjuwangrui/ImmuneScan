# Add files larger than 100MB to Git LFS, excluding files matched by .gitignore
# Usage: .\add_lfs.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (git rev-parse --show-toplevel 2>&1)
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not in a git repository."
    exit 1
}
$repoRoot = $repoRoot.Trim().Replace("/", "\")

Write-Host "Repository root: $repoRoot"
Write-Host "Scanning for files > 100MB..."

# Get all files larger than 100MB (excluding .git directory)
$largeFiles = Get-ChildItem -Path $repoRoot -Recurse -File |
    Where-Object { $_.FullName -notmatch '\\.git\\' } |
    Where-Object { $_.Length -gt 100MB }

if ($largeFiles.Count -eq 0) {
    Write-Host "No files larger than 100MB found."
    exit 0
}

Write-Host "Found $($largeFiles.Count) file(s) larger than 100MB. Checking against .gitignore..."

$filesToTrack = @()

foreach ($file in $largeFiles) {
    # Get path relative to repo root
    $relativePath = $file.FullName.Substring($repoRoot.Length).TrimStart("\").Replace("\", "/")

    # Use git check-ignore to test if the file is ignored
    $ignored = git check-ignore -q "$relativePath" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  SKIP (gitignored): $relativePath"
        continue
    }

    $sizeMB = [math]::Round($file.Length / 1MB, 2)
    Write-Host "  TRACK: $relativePath ($sizeMB MB)"
    $filesToTrack += $relativePath
}

if ($filesToTrack.Count -eq 0) {
    Write-Host "All large files are gitignored. Nothing to add to LFS."
    exit 0
}

Write-Host ""
Write-Host "Adding $($filesToTrack.Count) file(s) to Git LFS..."

foreach ($path in $filesToTrack) {
    # Check if already tracked by LFS
    $alreadyTracked = git lfs ls-files --name-only 2>&1 | Where-Object { $_ -eq $path }
    if ($alreadyTracked) {
        Write-Host "  Already in LFS: $path"
        continue
    }

    # Register the exact file path in .gitattributes via git lfs track
    git lfs track "$path"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "  Failed to track: $path"
        continue
    }

    # Re-add the file so git registers the LFS pointer
    git add "$path"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "  Failed to stage: $path"
    } else {
        Write-Host "  Staged for LFS: $path"
    }
}

# Stage the updated .gitattributes
git add .gitattributes
Write-Host ""
Write-Host "Done. Run 'git commit' to save the changes."
Write-Host "Tip: run 'git lfs ls-files' to verify tracked files."
