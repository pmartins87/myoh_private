$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)

$reconPath = 'OpenHoldem/COFCReconstructor.cpp'
$recon = Get-Content -Raw -Encoding UTF8 $reconPath
$eol = if ($recon.Contains("`r`n")) { "`r`n" } else { "`n" }

# Persistent visual Joker identity is now source-backed. Do not normalize/swap
# JK1/JK2 based on historical occurrence heuristics.
$oldNormalize = '  NormalizeJokerOccurrenceLabels(&observation, previous);'
if ($recon.Contains($oldNormalize)) {
  $recon = $recon.Replace(
    $oldNormalize,
    '  // JK1/JK2 are persistent visual identities; never swap occurrence labels.'
  )
}

# Replace the old Fantasy same-hand block. A new 14..17 incoming set is an
# unambiguous new/re-Fantasy hand. Within the same set, tentative row placement
# may be freely rearranged before Confirm, so prior pending rows are not sticky.
$start = $recon.IndexOf('  bool same_fantasy_decision = false;')
$endMarker = '  out->schema_version = kOFCStateSchemaVersion;'
$finish = $recon.IndexOf($endMarker, $start)
if ($start -lt 0 -or $finish -lt 0) {
  throw 'Could not locate ReconstructFantasyDecision same-hand block'
}
$newBlock = @(
  '  bool same_fantasy_decision = false;',
  '  if (previous != NULL && previous->valid',
  '      && previous->hero_chair >= 0',
  '      && previous->hero_chair < previous->player_count',
  '      && previous->players[previous->hero_chair].fantasy',
  '      && previous->round_index == -1) {',
  '    set<int> old_incoming = CardArraySet(',
  '      previous->hero_incoming, previous->hero_incoming_count);',
  '    if (old_incoming == current_incoming) {',
  '      same_fantasy_decision = true;',
  '      if (previous->player_count != observation.player_count',
  '          || previous->hero_chair != observation.hero_chair',
  '          || previous->dealer_chair != observation.dealer_chair) {',
  '        return Fail(out, error, "Fantasy hand metadata changed during arrangement");',
  '      }',
  '      // Do NOT require previous pending cards to stay in the same row.',
  '      // KKPoker Fantasy is a pre-Confirm arrangement and the player may',
  '      // move/rearrange cards freely until the final 13-card board is committed.',
  '    }',
  '  }',
  ''
) -join $eol
$recon = $recon.Substring(0, $start) + $newBlock + $recon.Substring($finish)

# An actionable Fantasy Confirm must correspond exactly to 13 tentative cards
# and 1..4 unused loose cards. Detection alone is never authority to click.
$needle = '  if (!ValidateCanonicalKnownCardUniqueness(*out, &validation_error)) {'
$pos = $recon.IndexOf($needle, $start)
if ($pos -lt 0) { throw 'Could not locate Fantasy canonical uniqueness gate' }
$guard = @(
  '  if (out->hero_can_confirm) {',
  '    if (pending.size() != 13) {',
  '      return Fail(out, error,',
  '        "actionable Fantasy Confirm requires exactly 13 tentative placements");',
  '    }',
  '    const int unused = out->hero_incoming_count - static_cast<int>(pending.size());',
  '    if (unused < 1 || unused > 4) {',
  '      return Fail(out, error,',
  '        "actionable Fantasy Confirm requires exactly 1..4 unused loose cards");',
  '    }',
  '  }',
  '',
  $needle
) -join $eol
$recon = $recon.Substring(0, $pos) + $guard + $recon.Substring($pos + $needle.Length)

[System.IO.File]::WriteAllText((Resolve-Path $reconPath), $recon, $utf8)

$selfPath = 'OpenHoldem/COFCReconstructorSelftest.cpp'
$self = Get-Content -Raw -Encoding UTF8 $selfPath
$eol2 = if ($self.Contains("`r`n")) { "`r`n" } else { "`n" }

# Replace obsolete exchangeable-Joker test with the now-correct invariant:
# persistent JK1->JK2 identity drift in the same normal round must fail closed.
$oldStartText = '  // Joker occurrence labels are visual occurrences, not persistent identities.'
$oldStart = $self.IndexOf($oldStartText)
$oldEndMarker = '  return true;'
$oldEnd = $self.IndexOf($oldEndMarker, $oldStart)
if ($oldStart -lt 0 -or $oldEnd -lt 0) {
  throw 'Could not locate obsolete Joker normalization self-test block'
}
$newTest = @(
  '  // JK1/JK2 are persistent physical visual identities. A same-round raw',
  '  // identity flip must be rejected rather than silently normalized.',
  '  COFCVisualObservation joker_raw;',
  '  joker_raw.Reset();',
  '  joker_raw.valid = true;',
  '  joker_raw.player_count = 2;',
  '  joker_raw.hero_chair = 1;',
  '  joker_raw.dealer_chair = 1;',
  '  joker_raw.acting_chair = 0;',
  '  joker_raw.round_index = 0;',
  '  joker_raw.hero_can_prepare = true;',
  '  joker_raw.confirm_visible = true;',
  '  joker_raw.players[0].occupied = true;',
  '  joker_raw.players[0].source_chair = 0;',
  '  joker_raw.players[0].hidden_incoming_count = 5;',
  '  joker_raw.players[1].occupied = true;',
  '  joker_raw.players[1].source_chair = 1;',
  '  const int values[5] = {kOFCCardJoker1, 0, 1, 2, 3};',
  '  joker_raw.hero_loose_count = 5;',
  '  for (int i = 0; i < 5; ++i) joker_raw.hero_loose_cards[i].value = values[i];',
  '',
  '  COFCState joker_first;',
  '  error.clear();',
  '  if (!COFCReconstructor::Reconstruct(joker_raw, NULL, &joker_first, &error)) {',
  '    cerr << "PERSISTENT JOKER TEST SETUP FAIL: " << error << endl;',
  '    return false;',
  '  }',
  '  COFCVisualObservation flipped = joker_raw;',
  '  flipped.hero_loose_cards[0].value = kOFCCardJoker2;',
  '  COFCState joker_second;',
  '  error.clear();',
  '  if (COFCReconstructor::Reconstruct(flipped, &joker_first, &joker_second, &error)) {',
  '    cerr << "PERSISTENT JOKER TEST FAIL: same-round JK1->JK2 drift was accepted" << endl;',
  '    return false;',
  '  }',
  '',
  '  return true;'
) -join $eol2
$self = $self.Substring(0, $oldStart) + $newTest + $self.Substring($oldEnd + $oldEndMarker.Length)
[System.IO.File]::WriteAllText((Resolve-Path $selfPath), $self, $utf8)

Write-Host 'DeepOFC native Fantasy/persistent-Joker semantic patch applied.'
Select-String -Path $reconPath -Pattern 'persistent visual identities|actionable Fantasy Confirm|same_fantasy_decision'
Select-String -Path $selfPath -Pattern 'PERSISTENT JOKER TEST'
