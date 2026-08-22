$ErrorActionPreference = "Stop"

Set-Location C:\Users\hamid\Desktop\nerva-trust

$path = ".\nerva-spec-v0.1.md"
$backup = ".\nerva-spec-v0.1.md.before-layer3-conformant.bak"

if (-not (Test-Path -LiteralPath $path)) {
    throw "Specification file not found: $path"
}

git status --short

if ($LASTEXITCODE -ne 0) {
    throw "git status failed."
}

Copy-Item -LiteralPath $path -Destination $backup -Force

$content = [System.IO.File]::ReadAllText(
    (Resolve-Path $path),
    [System.Text.Encoding]::UTF8
)

$newline = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }
$text = $content.Replace("`r`n", "`n")


function Replace-ExactlyOnce {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Text,

        [Parameter(Mandatory = $true)]
        [string] $Old,

        [Parameter(Mandatory = $true)]
        [string] $New,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    $count = [regex]::Matches(
        $Text,
        [regex]::Escape($Old)
    ).Count

    if ($count -ne 1) {
        throw "$Label : expected exactly 1 match, found $count"
    }

    return $Text.Replace($Old, $New)
}


# ============================================================
# 1. Conformance Scope
# ============================================================

$text = Replace-ExactlyOnce `
    -Text $text `
    -Old '**Conformance Scope:** Layer 0, Layer 1, Layer 2, and Layer 3' `
    -New '**Conformance Scope:** Layer 0, Layer 1, Layer 2, and Layer 3' `
    -Label "Conformance Scope"


# ============================================================
# 2. Section 1 — Layer 3 status
# ============================================================

$oldSection1 = @'
Layer 3 implementation and conformance tests are complete.

Layer 3 is formally `CONFORMANT`.
'@

$newSection1 = @'
Layer 3 implementation and conformance tests are complete.

Layer 3 is formally `CONFORMANT`.
'@

$text = Replace-ExactlyOnce `
    -Text $text `
    -Old $oldSection1 `
    -New $newSection1 `
    -Label "Section 1 Layer 3 status"


# ============================================================
# 3. RN-006 — Layer 3 reconstruction note
# ============================================================

$oldRn006 = @'
Layer 3 implementation and conformance tests are complete. Local quality gates and project CI pass on all supported Python versions. Its current formal conformance state is recorded in Section 17.
'@

$newRn006 = @'
Layer 3 implementation and conformance tests are complete. Local quality gates and project CI pass on all supported Python versions. Its current formal conformance state is recorded in Section 17.
'@

$text = Replace-ExactlyOnce `
    -Text $text `
    -Old $oldRn006 `
    -New $newRn006 `
    -Label "RN-006 Layer 3 status"


# ============================================================
# 4. Section 17 — Conformance table
# ============================================================

$text = Replace-ExactlyOnce `
    -Text $text `
    -Old '| Layer 3 / Workflow Orchestration | CONFORMANT ✅ |' `
    -New '| Layer 3 / Workflow Orchestration | CONFORMANT ✅ |' `
    -Label "Section 17 Layer 3 table row"


# ============================================================
# 5. Section 17 — Layer 3 explanatory state
# ============================================================

$oldSection17 = @'
Layer 3 Workflow Orchestration has been adopted as an Explicit Semantic Revision covering requirements R-WORKFLOW-001 through R-WORKFLOW-012.

Layer 3 implementation and conformance tests are complete. The Workflow Orchestration implementation satisfies requirements R-WORKFLOW-001 through R-WORKFLOW-012 under the local conformance suite.

Local formatting, linting, static type checking, and test gates pass successfully. Project CI has passed successfully on all supported Python versions (3.10, 3.11, 3.12).

Layer 3 is now formally CONFORMANT.
'@

$newSection17 = @'
Layer 3 Workflow Orchestration has been adopted as an Explicit Semantic Revision covering requirements R-WORKFLOW-001 through R-WORKFLOW-012.

Layer 3 implementation and conformance tests are complete. The Workflow Orchestration implementation satisfies requirements R-WORKFLOW-001 through R-WORKFLOW-012 under the local conformance suite.

Local formatting, linting, static type checking, and test gates pass successfully. Project CI has passed successfully on all supported Python versions (3.10, 3.11, 3.12).

Layer 3 is now formally CONFORMANT.
'@

$text = Replace-ExactlyOnce `
    -Text $text `
    -Old $oldSection17 `
    -New $newSection17 `
    -Label "Section 17 Layer 3 explanatory state"


# ============================================================
# 6. Section 18 — Status
# ============================================================

$text = Replace-ExactlyOnce `
    -Text $text `
    -Old '**Status:** CONFORMANT' `
    -New '**Status:** CONFORMANT' `
    -Label "Section 18 status"


# ============================================================
# 7. Preserve original newline convention
# ============================================================

if ($newline -eq "`r`n") {
    $text = $text.Replace("`n", "`r`n")
}


# ============================================================
# 8. Write UTF-8 without BOM
# ============================================================

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

[System.IO.File]::WriteAllText(
    (Resolve-Path $path),
    $text,
    $utf8NoBom
)


# ============================================================
# 9. Audit
# ============================================================

git --no-pager diff -- .\nerva-spec-v0.1.md

git diff --check

Select-String `
    -Path .\nerva-spec-v0.1.md `
    -Pattern "Conformance Scope|Layer 3 / Workflow Orchestration|R-WORKFLOW-001|R-WORKFLOW-012|Status:\*\* CONFORMANT|Layer 3 is now formally CONFORMANT"


# ============================================================
# 10. Gates
# ============================================================

py -m ruff format --check .
if ($LASTEXITCODE -ne 0) {
    throw "ruff format --check failed."
}

py -m ruff check . --no-cache
if ($LASTEXITCODE -ne 0) {
    throw "ruff check failed."
}

py -m mypy src
if ($LASTEXITCODE -ne 0) {
    throw "mypy failed."
}

py -m pytest -q
if ($LASTEXITCODE -ne 0) {
    throw "pytest failed."
}

git diff --check
if ($LASTEXITCODE -ne 0) {
    throw "git diff --check failed."
}


# ============================================================
# 11. Final status before commit
# ============================================================

git status --short


# ============================================================
# 12. Remove backup only after all gates pass
# ============================================================

Remove-Item `
    -LiteralPath $backup `
    -Force `
    -ErrorAction SilentlyContinue


# ============================================================
# 13. Commit
# ============================================================

git add .\nerva-spec-v0.1.md

git commit `
    -m "docs(spec): mark Layer 3 conformant" `
    -m "Record completed implementation and conformance coverage for R-WORKFLOW-001..012." `
    -m "Local quality gates and project CI pass on Python 3.10, 3.11, and 3.12."

if ($LASTEXITCODE -ne 0) {
    throw "git commit failed."
}


# ============================================================
# 14. Push
# ============================================================

git push origin main

if ($LASTEXITCODE -ne 0) {
    throw "git push failed."
}


# ============================================================
# 15. Final verification
# ============================================================

git status

git log --oneline -5