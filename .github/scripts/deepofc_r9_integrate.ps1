$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)

# 1) Project entries. COFCReconstructor deliberately does not use the project
# PCH because the same translation unit is also compiled by the standalone
# cross-language replay test. This avoids MSVC losing a preprocessor guard at
# the /Yu boundary and reporting C1020 on the matching #endif.
$projectPath = 'OpenHoldem/OpenHoldem.vcxproj'
$text = Get-Content -Raw -Encoding UTF8 $projectPath
$eol = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }

if ($text -notmatch 'ClCompile Include="COFCScraper\.cpp"') {
  $needle = '    <ClCompile Include="CScraper.cpp" />'
  if (-not $text.Contains($needle)) { throw 'Could not find CScraper.cpp project entry' }
  $text = $text.Replace($needle, $needle + $eol + '    <ClCompile Include="COFCScraper.cpp" />')
}

$reconBlock = @(
  '    <ClCompile Include="COFCReconstructor.cpp">',
  '      <PrecompiledHeader>NotUsing</PrecompiledHeader>',
  '    </ClCompile>'
) -join $eol

if ($text -match '<ClCompile Include="COFCReconstructor\.cpp"\s*/>') {
  $text = [regex]::Replace(
    $text,
    '    <ClCompile Include="COFCReconstructor\.cpp"\s*/>',
    [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $reconBlock },
    1)
} elseif ($text -notmatch 'ClCompile Include="COFCReconstructor\.cpp"') {
  $needle = '    <ClCompile Include="COFCScraper.cpp" />'
  if (-not $text.Contains($needle)) { throw 'Could not find COFCScraper.cpp project entry' }
  $text = $text.Replace($needle, $needle + $eol + $reconBlock)
} elseif ($text -notmatch 'COFCReconstructor\.cpp">\s*<PrecompiledHeader>NotUsing</PrecompiledHeader>') {
  throw 'COFCReconstructor.cpp entry exists in unexpected non-PCH-safe form'
}
[System.IO.File]::WriteAllText((Resolve-Path $projectPath), $text, $utf8)

# 2) Reconstructor preamble + temporary-set fix.
$reconPath = 'OpenHoldem/COFCReconstructor.cpp'
$recon = Get-Content -Raw -Encoding UTF8 $reconPath
$reconEol = if ($recon.Contains("`r`n")) { "`r`n" } else { "`n" }
if ($recon -notmatch 'DEEPOFC_RECONSTRUCTOR_STANDALONE') {
  $needle = '#include "StdAfx.h"' + $reconEol + '#include "COFCReconstructor.h"'
  if (-not $recon.Contains($needle)) { throw 'Could not find reconstructor include preamble' }
  $replacement = @(
    '#ifndef DEEPOFC_RECONSTRUCTOR_STANDALONE',
    '#include "StdAfx.h"',
    '#endif',
    '#include "COFCReconstructor.h"'
  ) -join $reconEol
  $recon = $recon.Replace($needle, $replacement)
}
$old = '  if (KnownBoardSet(visual).find(value) != KnownBoardSet(visual).end()) return true;'
$new = '  set<int> visual_cards = KnownBoardSet(visual);' + $reconEol + '  if (visual_cards.find(value) != visual_cards.end()) return true;'
if ($recon.Contains($old)) { $recon = $recon.Replace($old, $new) }
[System.IO.File]::WriteAllText((Resolve-Path $reconPath), $recon, $utf8)

# 3) Wire stateful canonical reconstruction into the isolated OFC heartbeat.
$lazyPath = 'OpenHoldem/CLazyScraper.cpp'
$lazy = Get-Content -Raw -Encoding UTF8 $lazyPath
$eol = if ($lazy.Contains("`r`n")) { "`r`n" } else { "`n" }
if ($lazy -notmatch '#include "COFCReconstructor\.h"') {
  $needle = '#include "CScraper.h"' + $eol
  if (-not $lazy.Contains($needle)) { throw 'Could not find CScraper include' }
  $lazy = $lazy.Replace($needle, '#include "COFCReconstructor.h"' + $eol + $needle)
}
if ($lazy -notmatch 'DeepOFC R9 canonical reconstruction path') {
  $pattern = '(?s)  // DeepOFC R9 read-only scrape path:.*?  if \(p_tablemap->SupportsOFCJokerUltimate\(\)\) \{.*?\r?\n  \}\r?\n\tp_scraper->ScrapeLimits\(\);'
  $replacementLines = @(
    '  // DeepOFC R9 canonical reconstruction path. Joker Ultimate never falls',
    '  // through to legacy Hold''em hole/community/betting semantics.',
    '  if (p_tablemap->SupportsOFCJokerUltimate()) {',
    '    COFCState previous_state = *p_table_state->OFCState();',
    '    if (!p_scraper->ScrapeOFCVisualObservation()) {',
    '      p_table_state->OFCState()->Reset();',
    '      write_log(k_always_log_errors,',
    '        "[DeepOFC] R9 raw OFC scrape rejected; canonical state invalid\n");',
    '      return;',
    '    }',
    '',
    '    const COFCVisualObservation *raw = p_table_state->OFCVisualObservation();',
    '    // Backwards transition to round 0 is an unambiguous new normal hand.',
    '    // Fantasy gets a deliberately separate reconstruction path later.',
    '    const COFCState *previous = previous_state.valid ? &previous_state : NULL;',
    '    if (raw->round_index == 0 && previous_state.valid && previous_state.round_index > 0) {',
    '      previous = NULL;',
    '    }',
    '',
    '    COFCState rebuilt;',
    '    std::string reconstruction_error;',
    '    if (!COFCReconstructor::Reconstruct(',
    '          *raw, previous, &rebuilt, &reconstruction_error)) {',
    '      p_table_state->OFCState()->Reset();',
    '      write_log(k_always_log_errors,',
    '        "[DeepOFC] canonical reconstruction rejected: %s\n",',
    '        reconstruction_error.c_str());',
    '      return;',
    '    }',
    '',
    '    *p_table_state->OFCState() = rebuilt;',
    '    std::string snapshot = COFCReconstructor::DiagnosticSnapshot(rebuilt);',
    '    write_log(true, "[DeepOFC SNAPSHOT v1] %s\n", snapshot.c_str());',
    '    return;',
    '  }',
    "`tp_scraper->ScrapeLimits();"
  )
  $replacement = $replacementLines -join $eol
  $newLazy = [regex]::Replace($lazy, $pattern, $replacement, 1)
  if ($newLazy -eq $lazy) { throw 'Could not replace existing DeepOFC heartbeat block' }
  $lazy = $newLazy
}
[System.IO.File]::WriteAllText((Resolve-Path $lazyPath), $lazy, $utf8)

Write-Host 'DeepOFC R9 integration patch applied.'
Select-String -Path $projectPath -Pattern 'COFC(Scraper|Reconstructor)\.cpp|PrecompiledHeader>NotUsing'
Select-String -Path $lazyPath -Pattern 'DeepOFC R9 canonical reconstruction path|DeepOFC SNAPSHOT v1'
