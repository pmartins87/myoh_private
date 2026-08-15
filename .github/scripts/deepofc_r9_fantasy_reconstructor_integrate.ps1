$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)

# ---------------------------------------------------------------------------
# 1) Native self-test: protocol v2 adds one explicit synthetic Fantasy contract
# fixture after the seven original screenshot-backed normal frames.
# ---------------------------------------------------------------------------
$selftestPath = 'OpenHoldem/COFCReconstructorSelftest.cpp'
$selftest = Get-Content -Raw -Encoding UTF8 $selftestPath
$oldHeader = 'if (!getline(in, line) || line != "DEEPOFC_OPENHOLDEM_REPLAY_REFERENCE|1") {'
$newHeader = 'if (!getline(in, line) || (line != "DEEPOFC_OPENHOLDEM_REPLAY_REFERENCE|1" && line != "DEEPOFC_OPENHOLDEM_REPLAY_REFERENCE|2")) {'
if ($selftest.Contains($oldHeader)) {
  $selftest = $selftest.Replace($oldHeader, $newHeader)
} elseif (-not $selftest.Contains($newHeader)) {
  throw 'Could not find replay-reference protocol header check'
}
[System.IO.File]::WriteAllText((Resolve-Path $selftestPath), $selftest, $utf8)

# ---------------------------------------------------------------------------
# 2) Reconstructor: add a deliberately narrow pre-Confirm Fantasy decision
# path. It does not guess post-Confirm/reveal semantics; those remain fail-closed.
# ---------------------------------------------------------------------------
$path = 'OpenHoldem/COFCReconstructor.cpp'
$text = Get-Content -Raw -Encoding UTF8 $path
$eol = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }

if ($text -notmatch 'ReconstructFantasyDecision') {
  $marker = '}  // namespace' + $eol + $eol + 'bool COFCReconstructor::Reconstruct('
  $idx = $text.IndexOf($marker)
  if ($idx -lt 0) { throw 'Could not find anonymous-namespace end before Reconstruct' }

  $helperLines = @(
    'bool ReconstructFantasyDecision(',
    '    const COFCVisualObservation &observation,',
    '    const COFCState *previous,',
    '    COFCState *out,',
    '    string *error) {',
    '  if (observation.round_index != -1) {',
    '    return Fail(out, error, "Hero Fantasy observation requires round_index=-1");',
    '  }',
    '  if (observation.hero_discard_tracker_count != 0) {',
    '    return Fail(out, error,',
    '      "Fantasy pre-Confirm discard-tracker semantics are not calibrated; expected zero");',
    '  }',
    '',
    '  const COFCPlayerBoard &hero_visual =',
    '    observation.players[observation.hero_chair].visual_board;',
    '  set<int> pending_cards = KnownBoardSet(hero_visual);',
    '  set<int> loose = CardArraySet(observation.hero_loose_cards, observation.hero_loose_count);',
    '  for (set<int>::const_iterator it = pending_cards.begin(); it != pending_cards.end(); ++it) {',
    '    if (loose.find(*it) != loose.end()) {',
    '      return Fail(out, error,',
    '        "same Hero Fantasy card is both loose and tentatively placed");',
    '    }',
    '  }',
    '  set<int> current_incoming = pending_cards;',
    '  current_incoming.insert(loose.begin(), loose.end());',
    '  if (current_incoming.size() < 14 || current_incoming.size() > 17) {',
    '    ostringstream oss;',
    '    oss << "Fantasy decision requires 14..17 visible Hero physical cards; got "',
    '        << current_incoming.size();',
    '    return Fail(out, error, oss.str());',
    '  }',
    '  if (pending_cards.size() > 13) {',
    '    return Fail(out, error, "Fantasy tentative board exceeds 13 cards");',
    '  }',
    '',
    '  bool same_fantasy_decision = false;',
    '  if (previous != NULL && previous->valid',
    '      && previous->hero_chair >= 0',
    '      && previous->hero_chair < previous->player_count',
    '      && previous->players[previous->hero_chair].fantasy',
    '      && previous->round_index == -1) {',
    '    same_fantasy_decision = true;',
    '    if (previous->player_count != observation.player_count',
    '        || previous->hero_chair != observation.hero_chair',
    '        || previous->dealer_chair != observation.dealer_chair) {',
    '      return Fail(out, error, "Fantasy hand metadata changed during arrangement");',
    '    }',
    '    set<int> old_incoming = CardArraySet(',
    '      previous->hero_incoming, previous->hero_incoming_count);',
    '    if (old_incoming != current_incoming) {',
    '      return Fail(out, error,',
    '        "Hero Fantasy incoming identities changed during the same arrangement");',
    '    }',
    '    for (int i = 0; i < kOFCMaxIncomingCards; ++i) {',
    '      if (!previous->pending[i].active) continue;',
    '      int old_index = previous->pending[i].incoming_index;',
    '      if (old_index < 0 || old_index >= previous->hero_incoming_count) {',
    '        return Fail(out, error, "previous Fantasy pending index is invalid");',
    '      }',
    '      int value = previous->hero_incoming[old_index].value;',
    '      if (!ContainsInRow(hero_visual, previous->pending[i].row, value)) {',
    '        return Fail(out, error,',
    '          "previous Fantasy tentative placement moved/disappeared before Confirm");',
    '      }',
    '    }',
    '  }',
    '',
    '  out->schema_version = kOFCStateSchemaVersion;',
    '  out->player_count = observation.player_count;',
    '  out->hero_chair = observation.hero_chair;',
    '  out->dealer_chair = observation.dealer_chair;',
    '  out->acting_chair = observation.acting_chair;',
    '  out->round_index = -1;',
    '  out->hero_can_prepare = observation.hero_can_prepare;',
    '  out->hero_can_confirm = observation.confirm_visible',
    '    && observation.acting_chair == observation.hero_chair;',
    '  out->action_required = out->hero_can_confirm;',
    '',
    '  string validation_error;',
    '  for (int p = 0; p < observation.player_count; ++p) {',
    '    out->players[p].occupied = observation.players[p].occupied;',
    '    out->players[p].source_chair = observation.players[p].source_chair;',
    '    out->players[p].fantasy = observation.players[p].fantasy;',
    '    out->players[p].sitting_out = observation.players[p].sitting_out;',
    '    out->players[p].hidden_incoming_count = observation.players[p].hidden_incoming_count;',
    '    out->players[p].hidden_discard_count = observation.players[p].hidden_discard_count;',
    '    if (p == observation.hero_chair) {',
    '      // During a pre-Confirm Fantasy decision every visible Hero row card',
    '      // is tentative; the committed canonical Hero board is still empty.',
    '      out->players[p].board.Reset();',
    '    } else {',
    '      COFCPlayerBoard normalized;',
    '      if (!NormalizeBoard(observation.players[p].visual_board, &normalized, &validation_error)) {',
    '        return Fail(out, error, validation_error);',
    '      }',
    '      if (same_fantasy_decision) {',
    '        if (!EnsureCommittedStillVisible(',
    '              previous->players[p].board, normalized, "opponent", &validation_error)) {',
    '          return Fail(out, error, validation_error);',
    '        }',
    '      }',
    '      out->players[p].board = normalized;',
    '    }',
    '  }',
    '',
    '  CopySortedValuesToCards(',
    '    current_incoming, out->hero_incoming, kOFCMaxIncomingCards, &out->hero_incoming_count);',
    '  out->hero_discard_count = 0;',
    '',
    '  vector<pair<int, EOFCRow> > pending;',
    '  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {',
    '    EOFCRow row = static_cast<EOFCRow>(r);',
    '    vector<int> values = KnownRowValues(hero_visual, row);',
    '    for (size_t i = 0; i < values.size(); ++i) {',
    '      pending.push_back(make_pair(values[i], row));',
    '    }',
    '  }',
    '  sort(pending.begin(), pending.end());',
    '  for (size_t i = 0; i < pending.size(); ++i) {',
    '    int incoming_index = -1;',
    '    for (int j = 0; j < out->hero_incoming_count; ++j) {',
    '      if (out->hero_incoming[j].value == pending[i].first) {',
    '        incoming_index = j;',
    '        break;',
    '      }',
    '    }',
    '    if (incoming_index < 0 || i >= static_cast<size_t>(kOFCMaxIncomingCards)) {',
    '      return Fail(out, error, "Fantasy pending card cannot map to incoming set");',
    '    }',
    '    out->pending[i].active = true;',
    '    out->pending[i].incoming_index = incoming_index;',
    '    out->pending[i].row = pending[i].second;',
    '  }',
    '',
    '  if (!ValidateCanonicalKnownCardUniqueness(*out, &validation_error)) {',
    '    return Fail(out, error, validation_error);',
    '  }',
    '  out->valid = true;',
    '  return true;',
    '}',
    ''
  )
  $helper = ($helperLines -join $eol) + $eol
  $text = $text.Substring(0, $idx) + $helper + $text.Substring($idx)
}

$oldMeta = @(
'  if ((observation.player_count != 2 && observation.player_count != 3)',
'      || observation.hero_chair < 0',
'      || observation.hero_chair >= observation.player_count',
'      || observation.dealer_chair < 0',
'      || observation.dealer_chair >= observation.player_count',
'      || observation.acting_chair < 0',
'      || observation.acting_chair >= observation.player_count',
'      || observation.round_index < 0',
'      || observation.round_index > 4) {',
'    return Fail(out, error, "raw observation has invalid player/chair/round metadata");',
'  }'
) -join $eol
$newMeta = @(
'  if ((observation.player_count != 2 && observation.player_count != 3)',
'      || observation.hero_chair < 0',
'      || observation.hero_chair >= observation.player_count',
'      || observation.dealer_chair < 0',
'      || observation.dealer_chair >= observation.player_count',
'      || observation.acting_chair < 0',
'      || observation.acting_chair >= observation.player_count) {',
'    return Fail(out, error, "raw observation has invalid player/chair metadata");',
'  }'
) -join $eol
if ($text.Contains($oldMeta)) {
  $text = $text.Replace($oldMeta, $newMeta)
} elseif (-not $text.Contains($newMeta)) {
  throw 'Could not patch common metadata validation'
}

if ($text -notmatch 'Hero Fantasy observation requires round_index=-1.*ReconstructFantasyDecision' -and $text -notmatch 'return ReconstructFantasyDecision') {
  $oldUniq = @(
'  if (!ValidateObservationKnownCardUniqueness(observation, &validation_error)) {',
'    return Fail(out, error, validation_error);',
'  }',
'',
'  COFCPlayerBoard hero_committed;'
  ) -join $eol
  $newUniq = @(
'  if (!ValidateObservationKnownCardUniqueness(observation, &validation_error)) {',
'    return Fail(out, error, validation_error);',
'  }',
'',
'  if (observation.players[observation.hero_chair].fantasy) {',
'    if (observation.round_index != -1) {',
'      return Fail(out, error, "Hero Fantasy observation requires round_index=-1");',
'    }',
'    return ReconstructFantasyDecision(observation, previous, out, error);',
'  }',
'  if (observation.round_index < 0 || observation.round_index > 4) {',
'    return Fail(out, error, "normal OFC observation requires round_index=0..4");',
'  }',
'',
'  COFCPlayerBoard hero_committed;'
  ) -join $eol
  if (-not $text.Contains($oldUniq)) { throw 'Could not insert Fantasy branch after uniqueness gate' }
  $text = $text.Replace($oldUniq, $newUniq)
}

[System.IO.File]::WriteAllText((Resolve-Path $path), $text, $utf8)
Select-String -Path $path -Pattern 'ReconstructFantasyDecision|round_index=-1|normal OFC observation'

# ---------------------------------------------------------------------------
# 3) Heartbeat: transition from a Fantasy hand back to a new normal round 0 is
# also an unambiguous new hand. Never carry Fantasy pending state into it.
# ---------------------------------------------------------------------------
$lazyPath = 'OpenHoldem/CLazyScraper.cpp'
$lazy = Get-Content -Raw -Encoding UTF8 $lazyPath
$oldReset = @(
'    if (raw->round_index == 0 && previous_state.valid && previous_state.round_index > 0) {',
'      previous = NULL;',
'    }'
) -join $eol
$newReset = @(
'    if (raw->round_index == 0 && previous_state.valid &&',
'        (previous_state.round_index > 0 ||',
'         (previous_state.hero_chair >= 0 &&',
'          previous_state.hero_chair < previous_state.player_count &&',
'          previous_state.players[previous_state.hero_chair].fantasy))) {',
'      previous = NULL;',
'    }'
) -join $eol
if ($lazy.Contains($oldReset)) {
  $lazy = $lazy.Replace($oldReset, $newReset)
} elseif (-not $lazy.Contains($newReset)) {
  throw 'Could not patch Fantasy -> normal new-hand reset'
}
[System.IO.File]::WriteAllText((Resolve-Path $lazyPath), $lazy, $utf8)
Select-String -Path $lazyPath -Pattern 'previous_state.players\[previous_state.hero_chair\]\.fantasy'
