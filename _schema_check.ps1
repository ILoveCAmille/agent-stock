$schema = openclaw config schema 2>&1 | Out-String
$lines = $schema -split "`n"
$inSearchProvider = $false
$braceDepth = 0
for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    if ($line -match '"search"' -and $line -match '"properties"') {
        $inSearchProvider = $true
    }
    if ($inSearchProvider) {
        if ($line -match '"provider"') {
            for ($j = $i; $j -lt [Math]::Min($i + 20, $lines.Count); $j++) {
                Write-Output $lines[$j]
            }
            break
        }
    }
}