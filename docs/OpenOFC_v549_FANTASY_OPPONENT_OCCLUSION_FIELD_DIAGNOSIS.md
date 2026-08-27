# OpenOFC v5.4.9 — Fantasy opponent-occlusion field diagnosis

Date: 2026-08-23 (user-local field session)

## Scope

This note records the root cause exposed by the live KKPoker Fantasy session in:

- `oh_1(20260824-025132).log`
- replay frame `frame000000(6).bmp` captured at 21:42:58

The supplied files are field evidence; they are not committed to this repository by this patch.

## What the field session proved

Fantasy entry itself was detected repeatedly. Representative log evidence:

```text
[OpenOFC FANTASY ENTRY] static=1 previous=0 dynamic=1 dynamic_count=15 detail="current_bitmap_14_17" route=TRY_FANTASY
```

Thus the current TableMap marker and the generic current-bitmap probe both had positive Fantasy evidence, including a complete 15-card current-screen count.

The full Fantasy scrape nevertheless failed before Hero's native Fantasy policy/executor path. Immediately after the positive entry proof, the old implementation read the opponent through ordinary `ofc_p0_*` row TableMap regions. On the live Fantasy presentation those regions intersect Fantasy UI artwork and produced examples such as `BACK`, false standard cards and false Joker identities. The old Fantasy scraper treated any opponent `BACK` or rejected slot as terminal for the frame and returned false.

Later frames showed the same general geometry problem when strict normal scraping was used during weak/static-negative Fantasy frames: Fantasy artwork could also be interpreted as Hero row card-backs, producing `Unexpected hidden Hero cardback in row source slots`. That path remained fail-closed, but it reinforces that normal row geometry is not authoritative on a Fantasy presentation.

## Screenshot evidence

The replay frame shows a 450x830 KKPoker Fantasy screen with Hero's 15-card fan at the bottom and a large Fantasy presentation overlay in the opponent/board area. Therefore the prior source comment/assumption that the opponent board geometry remained safely readable during Hero Fantasy was false for the live client.

## Root cause

Pre-v5.4.9 `ScrapeOFCFantasyVisualObservation` performed this ordering:

1. detect/enter Fantasy;
2. reset a Fantasy observation;
3. scrape the opponent board through normal TableMap row regions;
4. reject the Fantasy observation if any opponent row is `BACK` or cannot be classified;
5. only then run Hero Fantasy arrangement/loose-card recognition.

This makes a non-authoritative UI overlay a prerequisite for Hero Fantasy play.

## v5.4.9 repair

During a pre-Confirm Hero Fantasy decision, the normal opponent-board regions are now explicitly treated as **unobservable**. The whole opponent visual board is reset and excluded from physical-card uniqueness/policy inputs for that Fantasy observation. The implementation does not keep a partially accepted opponent board because overlay pixels can form plausible false rank/suit/Joker identities as well as obvious `BACK` values.

Hero Fantasy recognition remains strict and unchanged:

- current arrangement-slot native recognition remains required;
- current loose-object native recognition remains required;
- 14..17 current-screen physical-card cardinality remains required;
- physical-card uniqueness remains required;
- dealer metadata, Fantasy actor authority and Confirm handling retain their existing contracts;
- normal-game row scraping is unchanged.

This follows the project architecture rule: a perception limitation in a screen region that is not authoritative must not become a restriction on otherwise valid Hero strategy/execution.

## Expected next field milestone

A v5.4.9 field build should progress beyond the old opponent-row failure and emit:

```text
[OpenOFC FANTASY OPPONENT] visibility=OCCLUDED ... action=IGNORE_OPPONENT_BOARD ...
[OpenOFC FANTASY] raw_valid=1 ...
[DeepOFC POLICY] ...
[DeepOFC PLAN] ...
```

followed by row clear/build, fresh-scrape verification and Fantasy Confirm.

CI can prove materialization, source contracts, regressions and Win32 build. Only a new live KKPoker session can certify the complete field path.
