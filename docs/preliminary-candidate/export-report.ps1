param(
    [string]$DocumentPath = (Join-Path $PSScriptRoot 'credproof-manuscript-candidate.docx'),
    [string]$PdfPath = (Join-Path $PSScriptRoot 'credproof-manuscript-candidate.pdf')
)
$ErrorActionPreference = 'Stop'
$resolvedDoc = [System.IO.Path]::GetFullPath($DocumentPath)
$resolvedPdf = [System.IO.Path]::GetFullPath($PdfPath)
if (-not (Test-Path -LiteralPath $resolvedDoc -PathType Leaf)) { throw 'Candidate DOCX missing' }
$wpsReportApp = $null
$wpsReportDoc = $null
try {
    $wpsReportApp = New-Object -ComObject kwps.Application
    $wpsReportApp.Visible = $false
    $wpsReportApp.DisplayAlerts = 0
    try { $wpsReportApp.AutomationSecurity = 3 } catch {}
    $wpsReportDoc = $wpsReportApp.Documents.Open($resolvedDoc, $false, $false)
    $wpsReportDoc.Fields.Update() | Out-Null
    foreach ($contents in $wpsReportDoc.TablesOfContents) { $contents.Update() | Out-Null }
    $wpsReportDoc.Repaginate()
    foreach ($section in $wpsReportDoc.Sections) {
        foreach ($footer in $section.Footers) { $footer.Range.Fields.Update() | Out-Null }
    }
    $wpsReportDoc.Save()
    $wpsReportDoc.ExportAsFixedFormat($resolvedPdf, 17)
    Write-Output ('Exported: ' + $resolvedPdf)
} finally {
    if ($null -ne $wpsReportDoc) {
        $wpsReportDoc.Close(0)
        [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wpsReportDoc) | Out-Null
    }
    if ($null -ne $wpsReportApp) {
        $wpsReportApp.Quit()
        [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wpsReportApp) | Out-Null
    }
}
