param([string]$PluginRoot = $PSScriptRoot)

$ErrorActionPreference = "Stop"
function Assert-True([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Read-Utf8Strict([string]$Path) { return [Text.UTF8Encoding]::new($false, $true).GetString([IO.File]::ReadAllBytes($Path)) }
function Get-Sha256Bytes([byte[]]$Bytes) { $sha = [Security.Cryptography.SHA256]::Create(); try { return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace("-", "") } finally { $sha.Dispose() } }
function Assert-PngBytes([byte[]]$Bytes, [string]$Name) {
    $signature = @(137, 80, 78, 71, 13, 10, 26, 10)
    Assert-True ($Bytes.Length -gt 24) "PNG asset is empty or too short: $Name"
    for ($index = 0; $index -lt $signature.Count; $index++) { Assert-True ($Bytes[$index] -eq $signature[$index]) "Asset is not a Figma-compatible PNG: $Name" }
}

$required = @("manifest.json", "code.js", "ui.template.html", "ui.html", "build.ps1", "test-plugin.ps1", "README.md", "assets\quickrec-mark.png")
foreach ($relativePath in $required) { Assert-True (Test-Path -LiteralPath (Join-Path $PluginRoot $relativePath) -PathType Leaf) "Missing plugin file: $relativePath" }

$manifestPath = Join-Path $PluginRoot "manifest.json"; $codePath = Join-Path $PluginRoot "code.js"
$templatePath = Join-Path $PluginRoot "ui.template.html"; $uiPath = Join-Path $PluginRoot "ui.html"
$readmePath = Join-Path $PluginRoot "README.md"; $assetPath = Join-Path $PluginRoot "assets\quickrec-mark.png"
$manifest = Read-Utf8Strict $manifestPath | ConvertFrom-Json
Assert-True ($manifest.name -match "QR") "Plugin name must contain QR"
Assert-True ($manifest.name -ne "LetsMakeMoney v0.9 Design Builder") "Plugin name must not match LetsMakeMoney"
Assert-True ($manifest.editorType -contains "figma") "Plugin must target Figma Design"
Assert-True ($manifest.documentAccess -eq "dynamic-page") "Plugin must use dynamic-page"

$code = Read-Utf8Strict $codePath; $ui = Read-Utf8Strict $uiPath
$expectedPages = @("QR 01 Full Product Flow")
$legacyPages = @("QR 00 Foundations & Components", "QR 02 Material Library States")
Assert-True ($expectedPages.Count -le 3) "Starter file must not exceed three managed pages"
foreach ($pageName in $expectedPages) { Assert-True ($code.Contains($pageName)) "Missing QR page: $pageName" }
foreach ($pageName in $legacyPages) { Assert-True ($code.Contains($pageName)) "Missing exact legacy QR page cleanup target: $pageName" }
Assert-True ($code.Contains("const PAGE_NAMES")) "Missing page allowlist"
Assert-True ($code.Contains("const LEGACY_PAGE_NAMES")) "Missing legacy QR page allowlist"
Assert-True ($code.Contains("existing.get(name)")) "Page lookup must use exact names"
Assert-True ($code.Contains("for (const child of [...page.children]) child.remove()")) "Exact QR pages must be rebuildable"
Assert-True ($code.Contains("legacyPage.remove()")) "Obsolete QR 00 and QR 02 pages must be removed"
Assert-True (-not $code.Contains("filter((page) => !PAGE_NAMES.includes")) "Non-QR pages must be protected"
Assert-True (-not $code.Contains("figma.root.remove")) "Root document removal is forbidden"
Assert-True ($code.Contains("await figma.loadAllPagesAsync()")) "Dynamic page loading is required"
Assert-True ($code.Contains("await figma.setCurrentPageAsync(pages[0])")) "Async page switching is required"
Assert-True ($code.Contains('collection.name === "QR Primitives"')) "Variable cleanup must target QR Primitives only"
Assert-True ($code.Contains('collection.name === "QR Semantic"')) "Variable cleanup must target QR Semantic only"
Assert-True ($code.Contains('style.name.startsWith("QR/")')) "Style cleanup must target QR prefix only"
Assert-True (-not $code.Contains('setSharedPluginData("qr"')) "Shared plugin data namespace must contain at least three characters"
Assert-True ($code.Contains('setSharedPluginData("quickrec"')) "Shared plugin data must use the QuickRec namespace"
Assert-True ($code.Contains("const UI_ATLAS_ITEMS")) "Complete UI atlas inventory is required"
$atlasBlock = [Regex]::Match($code, 'const UI_ATLAS_ITEMS = \[(.*?)\];', [Text.RegularExpressions.RegexOptions]::Singleline)
Assert-True $atlasBlock.Success "UI atlas inventory could not be parsed"
$atlasItemCount = [Regex]::Matches($atlasBlock.Groups[1].Value, '"[^"\r\n]+"').Count
Assert-True ($atlasItemCount -ge 30) "UI atlas must contain at least 30 current states"
foreach ($helper in @("menuMock", "toolbarMock", "settingsMock", "windowSelectorMock", "areaSelectorMock", "overlayMock", "libraryShell", "dialogMock", "notificationMock")) { Assert-True ($code.Contains("function $helper")) "UI atlas helper is missing: $helper" }
Assert-True ($code.Contains("function buildRelationshipMap")) "Screen relationship map is required"
Assert-True ($code.Contains('band.resize(5120')) "Atlas sections must use the shared 5120px grid"
Assert-True ($code.Contains('row.counterAxisAlignItems = "MIN"')) "Atlas components must share a top alignment"
$buttonContractCount = [Regex]::Matches($code, 'buttonContract\(').Count - 1
Assert-True ($buttonContractCount -ge 57) "Every clickable product action must have a button contract"
Assert-True ($code.Contains("function contractSectionKey")) "Button contracts must be mapped to their prototype sections"
Assert-True ($code.Contains("function buildAssociatedContracts")) "Prototype-local button contract boards are required"
Assert-True (-not $code.Contains("root.appendChild(buildButtonContracts())")) "A standalone front-loaded contract board is forbidden"
Assert-True ($code.Contains("band.appendChild(buildAssociatedContracts(sectionKey))")) "Each prototype section must include its own contracts"
Assert-True ($code.Contains("function buildEmbeddedComponentRegistry")) "Core components must remain available inside QR 01"
Assert-True ($code.Contains("buildEmbeddedComponentRegistry(root)")) "QR 01 must include the compact component registry"
Assert-True (-not $code.Contains("buildFoundations(pages[")) "QR 00 foundations page must not be generated"
Assert-True (-not $code.Contains("buildMaterialStates(pages[")) "QR 02 material states page must not be generated"
Assert-True ($code.Contains('button-contract-ids')) "Prototype controls must expose their B-xxx contract identifiers"
Assert-True ($code.Contains("function attachButtonContract")) "Figma button nodes must receive contract descriptions"
Assert-True ($code.Contains('setSharedPluginData("quickrec", "button-label"')) "Button metadata must be stored in QuickRec plugin data"
Assert-True ($code.Contains('setSharedPluginData("quickrec", "button-contract"')) "Full button contracts must be stored in QuickRec plugin data"
Assert-True ($ui.Contains('message.type === "complete"')) "Plugin UI must re-enable after completion"

Assert-True (-not [Regex]::IsMatch($ui, '__[A-Z0-9_]+__')) "ui.html contains an unresolved placeholder"
$assetMatch = [Regex]::Match($ui, 'const\s+qrMarkBase64\s*=\s*"([A-Za-z0-9+/=]+)";')
Assert-True $assetMatch.Success "ui.html is missing the QR PNG asset"
$embeddedBytes = [Convert]::FromBase64String($assetMatch.Groups[1].Value); $sourceBytes = [IO.File]::ReadAllBytes($assetPath)
Assert-PngBytes $embeddedBytes "qrMarkBase64"; Assert-PngBytes $sourceBytes "assets/quickrec-mark.png"
Assert-True ((Get-Sha256Bytes $embeddedBytes) -eq (Get-Sha256Bytes $sourceBytes)) "Embedded and static PNG hashes differ"
Assert-True ($code.Contains("await image.getBytesAsync()")) "Plugin must read image bytes after writing"
Assert-True ($code.Contains("stored[index] !== decoded[index]")) "Plugin must compare written image bytes"
Assert-True (-not $code.Contains("runtime-reference")) "Generated Figma pages must not contain runtime screenshot nodes"
Assert-True (-not $code.Contains("referenceBoard")) "Generated Figma pages must not build screenshot boards"
Assert-True (-not $ui.Contains("qrReferenceAssets")) "Plugin UI must not embed runtime screenshots"
Assert-True (-not $ui.Contains("__QR_REFERENCE_ASSETS__")) "Screenshot placeholder must be removed"
Assert-True ($code.Contains('440, 447')) "Settings prototype must match the actual 440x447 client size"
Assert-True ($code.Contains('980, 560')) "Material library prototype must match the actual 980x560 client size"
Assert-True ($code.Contains('460, 340')) "Window selector prototype must match the actual 460x340 client size"
Assert-True ($code.Contains('900, 520')) "Area selector prototype must match the actual 900x520 client size"

$textFiles = @($manifestPath, $codePath, $templatePath, $uiPath, $readmePath, (Join-Path $PluginRoot "build.ps1"), (Join-Path $PluginRoot "test-plugin.ps1"))
$suspiciousCharacters = @([char]0xFFFD, [char]0x951F, [char]0x7F02, [char]0x93C4)
foreach ($path in $textFiles) {
    $content = Read-Utf8Strict $path
    foreach ($character in $suspiciousCharacters) { Assert-True (-not $content.Contains([string]$character)) "Possible mojibake in: $path" }
}

$node = Get-Command node -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1
if (-not $node) { $node = "C:\Users\win\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" }
Assert-True (Test-Path -LiteralPath $node -PathType Leaf) "Node.js was not found"
& $node --check $codePath; Assert-True ($LASTEXITCODE -eq 0) "code.js syntax check failed"

$repoRoot = Split-Path -Parent $PluginRoot
& git -C $repoRoot diff --check; Assert-True ($LASTEXITCODE -eq 0) "git diff --check failed"
Write-Host "QR Figma Development Plugin static validation passed"
Write-Host "- Managed page count: $($expectedPages.Count)"
Write-Host "- Legacy QR page cleanup targets: $($legacyPages.Count)"
Write-Host "- Non-QR page protection: passed"
Write-Host "- JavaScript syntax: passed"
Write-Host "- PNG format and SHA256: passed"
Write-Host "- Runtime screenshots embedded: 0"
Write-Host "- Runtime-aligned editable prototype dimensions: passed"
Write-Host "- UTF-8 and mojibake scan: passed"
Write-Host "- git diff --check: passed"
