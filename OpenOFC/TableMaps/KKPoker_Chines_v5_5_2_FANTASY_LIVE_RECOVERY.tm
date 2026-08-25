.osdb2

// OpenScrape 14.1.0

// 32 bits per pixel

//
// sizes
//

z$clientsizemax    2000  2000
z$clientsizemin    100  100
z$targetsize       450  830

//
// strings
//

s$nchairs                   2
s$network                   kkpoker
s$ofc_drag_duration_ms      350
s$ofc_drag_retry_limit      1
s$ofc_drag_targets_calibrated 1
s$ofc_drag_verify_wait_cycles 8
s$ofc_executor_enabled      1
s$ofc_fantasy15_geometry_measured 1
s$ofc_fantasy_geometry_measured 1
s$ofc_fantasy_max_cards     17
s$ofc_fantasy_min_cards     14
s$ofc_fantasy_recognizer_calibrated 1
s$ofc_fantasy_select_gap_ms 250
s$ofc_hero_chair            1
s$ofc_joker_detector_calibrated 1
s$ofc_joker_rank_token      X
s$ofc_players               2
s$ofc_round_stabilize_ms    1000
s$ofc_tablemap_stage           openofc_v5_5_2_fantasy_live_recovery
s$ofc_variant               joker_ultimate
s$openofc_contract          5
s$openofc_exit_mode_leave_next_hand 1
s$openofc_fantasy_dynamic_sources 1
s$openofc_fantasy17_calibrated 0
s$openofc_fantasy_tablemap_text_by_count 1
s$openofc_fantasy_live_recovery 1
s$openofc_fantasy_row_batch_click 1
s$openofc_field_revision       552
s$openofc_hero_discard_scrape 0
s$openofc_history_schema    1
s$openofc_opponent_history  1
s$openofc_opponent_partial_progression 1
s$openofc_opponent_reveal_scrape 1
s$openofc_partial_slot_tolerance 1
s$openofc_phase_contract    1
s$openofc_result_debounce_frames 2
s$openofc_safe_exit_calibrated 0
s$openofc_stop_enabled      1
s$openofc_stop_local_hhmm   -1
s$openofc_tablemap_clean    1
s$openofc_turn_semantics    0
s$sitename                  kkpoker
s$t1type                    fuzzy
s$t2type                    0.10
s$t3type                    fuzzy
s$t4type                    0.1
s$t5type                    fuzzy
s$t6type                    fuzzy
s$t7type                    0.75
s$titletext                 OFC
s$ttlimits                  OFC ^y

//
// regions
//

r$IsFantasy15         55 737  55 737 ffb7b8b6   25 C 1   0 0   0 -1
r$ofc_confirm_button 296 689 405 727 ff000000    0 N 1   0 0   0 -1
r$ofc_confirm_visible 351 710 351 710 ff2faccd   50 C 1   0 0   0 -1
r$ofc_drop_bottom0   109 583 164 659 ff000000    0 N 1   0 0   0 -1
r$ofc_drop_bottom1   169 583 224 659 ff000000    0 N 1   0 0   0 -1
r$ofc_drop_bottom2   229 583 284 659 ff000000    0 N 1   0 0   0 -1
r$ofc_drop_bottom3   289 583 344 659 ff000000    0 N 1   0 0   0 -1
r$ofc_drop_bottom4   349 583 404 659 ff000000    0 N 1   0 0   0 -1
r$ofc_drop_middle0   109 504 164 579 ff000000    0 N 1   0 0   0 -1
r$ofc_drop_middle1   169 504 224 579 ff000000    0 N 1   0 0   0 -1
r$ofc_drop_middle2   229 504 284 579 ff000000    0 N 1   0 0   0 -1
r$ofc_drop_middle3   289 504 344 579 ff000000    0 N 1   0 0   0 -1
r$ofc_drop_middle4   349 504 404 579 ff000000    0 N 1   0 0   0 -1
r$ofc_drop_top0      109 425 164 500 ff000000    0 N 1   0 0   0 -1
r$ofc_drop_top1      169 425 224 500 ff000000    0 N 1   0 0   0 -1
r$ofc_drop_top2      229 425 284 500 ff000000    0 N 1   0 0   0 -1
//
// OpenOFC v5.5.0 counted Fantasy text regions
// 06..16: field-measured fan centers; T7 boxes inherit the verified
// Fantasy-15 rotation envelope. 17 is interpolated and fail-closed.
//

// loose count 06
r$ofc_fantasy06_00rank 121 655 137 675 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy06_00suit 125 678 140 692 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy06_01rank 151 654 168 674 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy06_01suit 155 676 170 691 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy06_02rank 185 651 201 672 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy06_02suit 187 673 202 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy06_03rank 218 649 234 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy06_03suit 217 672 231 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy06_04rank 251 652 266 671 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy06_04suit 248 673 263 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy06_05rank 286 654 301 673 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy06_05suit 280 675 294 689 ffffffff -260 T7 1   0 0   0 -1

// loose count 07
r$ofc_fantasy07_00rank 105 659 121 679 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_00suit 109 682 124 696 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_01rank 136 655 153 675 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_01suit 140 677 155 692 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_02rank 169 651 184 673 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_02suit 171 673 186 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_03rank 202 650 217 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_03suit 201 672 217 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_04rank 235 649 251 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_04suit 233 672 248 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_05rank 268 652 283 672 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_05suit 264 674 278 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_06rank 302 656 317 675 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy07_06suit 296 677 310 691 ffffffff -260 T7 1   0 0   0 -1

// loose count 08
r$ofc_fantasy08_00rank  89 662 105 682 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_00suit  93 685 108 699 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_01rank 120 657 136 677 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_01suit 124 679 139 694 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_02rank 153 652 169 674 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_02suit 155 675 169 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_03rank 185 651 202 672 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_03suit 187 673 202 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_04rank 218 649 234 669 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_04suit 218 672 232 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_05rank 251 651 267 671 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_05suit 249 673 265 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_06rank 286 653 301 673 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_06suit 281 675 295 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_07rank 317 659 332 678 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy08_07suit 311 680 325 694 ffffffff -260 T7 1   0 0   0 -1

// loose count 09
r$ofc_fantasy09_00rank  73 666  89 686 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_00suit  77 689  92 703 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_01rank 104 659 120 679 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_01suit 108 681 123 696 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_02rank 136 655 153 676 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_02suit 139 678 154 692 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_03rank 168 651 183 673 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_03suit 170 673 186 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_04rank 202 650 217 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_04suit 201 672 217 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_05rank 235 649 251 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_05suit 233 672 247 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_06rank 267 652 283 672 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_06suit 265 674 280 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_07rank 300 655 315 675 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_07suit 295 677 309 691 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_08rank 334 662 349 681 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy09_08suit 328 683 342 697 ffffffff -260 T7 1   0 0   0 -1

// loose count 11
r$ofc_fantasy11_00rank  42 674  58 694 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_00suit  46 697  61 711 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_01rank  72 666  88 686 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_01suit  76 688  91 703 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_02rank 103 661 120 681 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_02suit 107 683 122 698 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_03rank 137 654 153 676 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_03suit 139 677 153 691 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_04rank 168 651 184 672 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_04suit 170 673 186 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_05rank 202 650 217 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_05suit 201 672 217 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_06rank 235 649 251 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_06suit 234 672 248 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_07rank 266 652 282 672 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_07suit 264 674 280 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_08rank 300 656 315 675 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_08suit 297 677 312 692 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_09rank 332 661 347 681 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_09suit 327 683 342 697 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_10rank 367 669 382 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy11_10suit 361 690 375 704 ffffffff -260 T7 1   0 0   0 -1

// loose count 12
r$ofc_fantasy12_00rank  27 679  43 699 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_00suit  31 702  46 716 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_01rank  57 670  73 690 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_01suit  61 692  76 707 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_02rank  88 663 104 683 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_02suit  92 685 107 700 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_03rank 120 656 137 678 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_03suit 123 679 137 693 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_04rank 152 653 168 675 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_04suit 154 675 170 691 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_05rank 185 650 201 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_05suit 186 672 201 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_06rank 218 649 233 669 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_06suit 217 672 232 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_07rank 252 650 268 671 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_07suit 250 673 264 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_08rank 282 653 298 673 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_08suit 280 675 296 690 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_09rank 317 659 332 678 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_09suit 313 680 328 695 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_10rank 348 664 363 685 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_10suit 343 686 358 701 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_11rank 382 673 397 692 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy12_11suit 376 694 390 708 ffffffff -260 T7 1   0 0   0 -1

// loose count 13
r$ofc_fantasy13_00rank  21 681  37 701 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_00suit  25 704  40 718 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_01rank  51 672  67 692 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_01suit  55 694  70 709 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_02rank  79 665  95 685 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_02suit  83 687  98 702 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_03rank 110 659 126 680 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_03suit 113 682 127 696 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_04rank 141 656 157 678 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_04suit 143 678 159 693 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_05rank 170 652 187 673 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_05suit 172 674 187 690 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_06rank 202 650 217 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_06suit 201 672 217 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_07rank 233 649 249 669 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_07suit 232 672 246 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_08rank 264 652 280 672 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_08suit 262 674 276 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_09rank 293 655 309 674 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_09suit 291 676 306 691 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_10rank 326 659 342 679 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_10suit 322 681 337 695 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_11rank 354 666 369 686 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_11suit 349 688 365 702 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_12rank 388 674 403 693 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy13_12suit 382 695 396 709 ffffffff -260 T7 1   0 0   0 -1

// loose count 14
r$ofc_fantasy14_00rank  21 681  37 701 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_00suit  25 704  40 718 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_01rank  47 673  63 693 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_01suit  51 695  66 710 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_02rank  74 666  91 686 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_02suit  78 688  93 703 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_03rank 102 661 119 681 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_03suit 105 683 120 698 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_04rank 130 654 146 676 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_04suit 132 677 147 692 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_05rank 159 652 175 674 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_05suit 161 674 176 690 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_06rank 187 651 203 671 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_06suit 188 673 203 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_07rank 216 649 231 669 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_07suit 215 672 230 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_08rank 245 650 261 671 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_08suit 244 673 258 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_09rank 273 652 289 672 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_09suit 271 674 287 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_10rank 299 659 315 678 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_10suit 297 680 312 695 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_11rank 330 660 345 680 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_11suit 326 682 340 696 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_12rank 358 666 373 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_12suit 353 688 369 703 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_13rank 388 674 403 693 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy14_13suit 382 695 396 709 ffffffff -260 T7 1   0 0   0 -1

// loose count 15
r$ofc_fantasy15_00rank  21 681  37 701 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_00suit  25 704  40 718 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_01rank  46 674  62 694 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_01suit  50 696  65 711 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_02rank  71 667  87 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_02suit  75 689  90 704 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_03rank  96 662 113 682 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_03suit 100 684 115 699 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_04rank 123 656 139 678 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_04suit 125 679 139 693 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_05rank 148 653 163 675 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_05suit 150 675 166 691 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_06rank 174 651 191 672 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_06suit 176 673 191 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_07rank 202 650 217 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_07suit 201 672 217 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_08rank 228 649 244 669 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_08suit 228 672 242 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_09rank 256 650 272 671 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_09suit 254 673 268 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_10rank 281 653 297 673 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_10suit 279 675 295 690 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_11rank 307 657 323 676 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_11suit 305 678 320 693 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_12rank 335 661 350 681 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_12suit 330 683 344 697 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_13rank 360 666 375 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_13suit 355 688 371 703 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_14rank 386 674 401 693 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_14suit 380 695 394 709 ffffffff -260 T7 1   0 0   0 -1

// loose count 16
r$ofc_fantasy16_00rank  21 681  37 701 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_00suit  25 704  40 718 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_01rank  45 674  61 694 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_01suit  49 696  64 711 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_02rank  67 667  83 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_02suit  71 689  86 704 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_03rank  91 663 108 683 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_03suit  95 685 110 700 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_04rank 116 658 132 679 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_04suit 118 680 133 695 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_05rank 140 654 155 676 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_05suit 142 677 157 692 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_06rank 164 652 180 673 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_06suit 166 674 181 690 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_07rank 189 651 204 671 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_07suit 189 673 204 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_08rank 214 650 229 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_08suit 213 672 228 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_09rank 239 649 255 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_09suit 238 672 252 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_10rank 263 652 279 672 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_10suit 261 674 275 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_11rank 287 654 303 674 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_11suit 285 676 301 691 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_12rank 313 658 328 677 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_12suit 310 679 325 694 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_13rank 339 661 354 681 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_13suit 334 683 348 697 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_14rank 360 667 375 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_14suit 355 689 371 704 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_15rank 388 674 403 693 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy16_15suit 382 695 396 709 ffffffff -260 T7 1   0 0   0 -1

// loose count 17
r$ofc_fantasy17_00rank  21 681  37 701 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_00suit  25 704  40 718 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_01rank  43 674  59 694 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_01suit  47 696  62 711 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_02rank  64 668  80 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_02suit  68 690  83 705 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_03rank  87 663 103 683 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_03suit  91 685 106 700 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_04rank 110 659 126 680 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_04suit 113 682 127 696 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_05rank 132 655 148 677 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_05suit 134 678 149 692 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_06rank 155 653 170 674 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_06suit 157 675 172 691 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_07rank 177 651 194 672 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_07suit 179 673 194 689 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_08rank 202 650 217 670 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_08suit 201 672 217 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_09rank 225 649 240 669 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_09suit 224 672 239 687 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_10rank 248 650 264 671 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_10suit 247 673 261 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_11rank 270 652 286 673 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_11suit 268 675 283 690 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_12rank 293 655 309 675 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_12suit 291 677 307 692 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_13rank 318 658 333 678 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_13suit 314 680 329 694 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_14rank 341 662 356 682 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_14suit 336 684 351 698 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_15rank 362 668 377 688 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_15suit 357 689 372 704 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_16rank 388 674 403 693 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy17_16suit 382 695 396 709 ffffffff -260 T7 1   0 0   0 -1
r$ofc_fantasy15_arrange_bottom0 112 561 160 627 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_arrange_bottom1 167 561 216 627 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_arrange_bottom2 223 561 271 627 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_arrange_bottom3 278 561 326 627 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_arrange_bottom4 333 561 381 627 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_arrange_middle0 112 488 160 554 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_arrange_middle1 167 488 216 554 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_arrange_middle2 223 488 271 554 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_arrange_middle3 278 488 326 554 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_arrange_middle4 333 488 381 554 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_arrange_top0 112 414 160 480 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_arrange_top1 167 415 216 481 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_arrange_top2 223 415 271 481 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_confirm_button 319 662 433 704 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy15_confirm_visible 350 684 350 684 ff32b2d2   30 C 1   0 0   0 -1
r$ofc_fantasy_active 225 760 225 760 ff004c87   32 C 1   0 0   0 -1
r$ofc_fantasy_arrange_bottom0 112 561 160 627 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_arrange_bottom1 167 561 216 627 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_arrange_bottom2 223 561 271 627 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_arrange_bottom3 278 561 326 627 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_arrange_bottom4 333 561 381 627 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_arrange_middle0 112 488 160 554 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_arrange_middle1 167 488 216 554 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_arrange_middle2 223 488 271 554 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_arrange_middle3 278 488 326 554 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_arrange_middle4 333 488 381 554 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_arrange_top0 112 414 160 480 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_arrange_top1 167 415 216 481 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_arrange_top2 223 415 271 481 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_confirm_button 319 662 433 704 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_confirm_visible 350 684 350 684 ff32b2d2   30 C 1   0 0   0 -1
r$ofc_fantasy_row_action_bottom 397 573 431 606 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_row_action_middle 397 500 431 533 ff000000    0 N 1   0 0   0 -1
r$ofc_fantasy_row_action_top 397 428 431 461 ff000000    0 N 1   0 0   0 -1
r$ofc_hero_in0back   136 707 136 707 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_hero_in0drag   111 673 161 741 ff000000    0 N 1   0 0   0 -1
r$ofc_hero_in0empty  136 707 136 707 ff4e7426   32 C 1   0 0   0 -1
r$ofc_hero_in0rank   113 675 128 696 ffffffff -120 T3 1   0 0   0 -1
r$ofc_hero_in0suit   112 698 128 712 ffffffff -120 T3 1   0 0   0 -1
r$ofc_hero_in1back   191 707 191 707 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_hero_in1drag   166 673 216 741 ff000000    0 N 1   0 0   0 -1
r$ofc_hero_in1empty  191 707 191 707 ff4e7426   32 C 1   0 0   0 -1
r$ofc_hero_in1rank   168 675 184 696 ffffffff -120 T3 1   0 0   0 -1
r$ofc_hero_in1suit   168 698 184 712 ffffffff -120 T3 1   0 0   0 -1
r$ofc_hero_in2back   246 707 246 707 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_hero_in2drag   221 673 271 741 ff000000    0 N 1   0 0   0 -1
r$ofc_hero_in2empty  246 707 246 707 ff4e7426   32 C 1   0 0   0 -1
r$ofc_hero_in2rank   223 675 239 696 ffffffff -120 T3 1   0 0   0 -1
r$ofc_hero_in2suit   223 698 239 712 ffffffff -120 T3 1   0 0   0 -1
r$ofc_leave_next_hand_menu_item  17 268 232 286 ff000000    0 N 1   0 0   0 -1
r$ofc_menu_button     19  61  41  82 ff000000    0 N 1   0 0   0 -1
r$ofc_p0_bottom0back 110 270 110 270 ff4eb0d6   50 C 1   0 0   0 -1
r$ofc_p0_bottom0empty 110 270 110 270 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_bottom0rank  89 242 103 260 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_bottom0suit  89 262 103 271 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_bottom1back 161 270 161 270 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_bottom1empty 161 270 161 270 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_bottom1rank 140 242 154 260 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_bottom1suit 140 262 154 271 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_bottom2back 212 270 212 270 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_bottom2empty 212 270 212 270 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_bottom2rank 191 242 205 260 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_bottom2suit 191 262 205 271 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_bottom3back 263 270 263 270 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_bottom3empty 263 270 263 270 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_bottom3rank 242 242 256 260 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_bottom3suit 242 262 256 271 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_bottom4back 314 270 314 270 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_bottom4empty 314 270 314 270 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_bottom4rank 293 242 307 260 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_bottom4suit 293 262 307 271 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_dealer      403 320 403 320 ffcfcfcf   20 C 1   0 0   0 -1
r$ofc_p0_discard0back 103 333 103 333 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_discard0empty 103 333 103 333 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_discard0rank  88 313 100 326 ffffffff -120 T4 1   0 0   0 -1
r$ofc_p0_discard0suit  89 328  98 337 ffffffff -120 T4 1   0 0   0 -1
r$ofc_p0_discard1back 138 333 138 333 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_discard1empty 138 333 138 333 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_discard1rank 123 313 135 326 ffffffff -120 T4 1   0 0   0 -1
r$ofc_p0_discard1suit 124 328 133 337 ffffffff -120 T4 1   0 0   0 -1
r$ofc_p0_discard2back 173 333 173 333 ff4eb0d6   50 C 1   0 0   0 -1
r$ofc_p0_discard2empty 173 333 173 333 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_discard2rank 158 313 170 326 ffffffff -120 T4 1   0 0   0 -1
r$ofc_p0_discard2suit 159 328 168 337 ffffffff -120 T4 1   0 0   0 -1
r$ofc_p0_discard3back 208 333 208 333 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_discard3empty 208 333 208 333 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_discard3rank 193 313 205 326 ffffffff -120 T4 1   0 0   0 -1
r$ofc_p0_discard3suit 194 328 203 337 ffffffff -120 T4 1   0 0   0 -1
r$ofc_p0_middle0back 110 203 110 203 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_middle0empty 110 203 110 203 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_middle0rank  89 174 103 192 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_middle0suit  89 194 103 204 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_middle1back 161 203 161 203 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_middle1empty 161 203 161 203 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_middle1rank 140 174 154 192 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_middle1suit 140 194 154 204 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_middle2back 212 203 212 203 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_middle2empty 212 203 212 203 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_middle2rank 191 174 205 192 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_middle2suit 191 194 205 204 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_middle3back 263 203 263 203 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_middle3empty 263 203 263 203 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_middle3rank 242 174 256 192 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_middle3suit 242 194 256 204 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_middle4back 314 203 314 203 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_middle4empty 314 203 314 203 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_middle4rank 293 174 307 192 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_middle4suit 293 194 307 204 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_name        351 272 411 282   696969   50 A0 1 125 0  40 3
r$ofc_p0_result_fantasy0 160 220 160 220 ffcfa649   45 C 1   0 0   0 -1
r$ofc_p0_result_fantasy1 225 219 225 219 ffe8ba5e   45 C 1   0 0   0 -1
r$ofc_p0_result_fantasy2 265 220 265 220 ffd0a455   45 C 1   0 0   0 -1
r$ofc_p0_timer_active 382 211 382 211 ff71ffff  100 C 1   0 0   0 -1
r$ofc_p0_top0back    110 136 110 136 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_top0empty   110 136 110 136 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_top0rank     89 107 103 125 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_top0suit     89 127 103 137 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_top1back    161 136 161 136 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_top1empty   161 136 161 136 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_top1rank    140 107 154 125 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_top1suit    140 127 154 137 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_top2back    212 136 212 136 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p0_top2empty   212 136 212 136 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p0_top2rank    191 107 205 125 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p0_top2suit    191 127 205 137 ffffffff -120 T5 1   0 0   0 -1
r$ofc_p1_bottom0back 136 621 136 621 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_bottom0empty 136 621 136 621 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_bottom0rank 112 587 128 609 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_bottom0suit 112 611 128 624 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_bottom1back 196 621 196 621 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_bottom1empty 196 621 196 621 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_bottom1rank 172 588 188 609 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_bottom1suit 172 611 188 624 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_bottom2back 256 621 256 621 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_bottom2empty 256 621 256 621 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_bottom2rank 232 588 248 609 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_bottom2suit 232 611 248 624 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_bottom3back 316 621 316 621 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_bottom3empty 316 621 316 621 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_bottom3rank 292 588 308 609 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_bottom3suit 292 611 308 624 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_bottom4back 376 621 376 621 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_bottom4empty 376 621 376 621 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_bottom4rank 352 588 368 609 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_bottom4suit 352 611 368 624 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_dealer      393 482 393 482 ffcfcfcf   20 C 1   0 0   0 -1
r$ofc_p1_middle0back 136 541 136 541 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_middle0empty 136 541 136 541 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_middle0rank 112 508 128 530 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_middle0suit 112 532 128 545 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_middle1back 196 541 196 541 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_middle1empty 196 541 196 541 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_middle1rank 172 508 188 530 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_middle1suit 172 532 188 545 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_middle2back 256 541 256 541 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_middle2empty 256 541 256 541 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_middle2rank 232 508 248 530 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_middle2suit 232 532 248 545 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_middle3back 316 541 316 541 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_middle3empty 316 541 316 541 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_middle3rank 292 508 308 530 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_middle3suit 292 532 308 545 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_middle4back 376 541 376 541 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_middle4empty 376 541 376 541 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_middle4rank 352 508 368 530 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_middle4suit 352 532 368 545 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_name        312 470 371 480 ff201b16   50 A0 1 125 0  40 3
r$ofc_p1_result_fantasy0 192 555 192 555 ffe3a853   38 C 1   0 0   0 -1
r$ofc_p1_result_fantasy1 240 555 240 555 ffe5b557   38 C 1   0 0   0 -1
r$ofc_p1_result_fantasy2 294 555 294 555 ffe5b557   38 C 1   0 0   0 -1
r$ofc_p1_timer_active 345 409 345 409 ff0beceb  100 C 1   0 0   0 -1
r$ofc_p1_top0back    136 462 136 462 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_top0empty   136 462 136 462 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_top0rank    112 429 128 451 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_top0suit    111 452 128 465 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_top1back    196 462 196 462 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_top1empty   196 462 196 462 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_top1rank    172 429 188 451 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_top1suit    172 452 188 465 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_top2back    256 462 256 462 ff4eb0d6   46 C 1   0 0   0 -1
r$ofc_p1_top2empty   256 462 256 462 ff4e7426   32 C 1   0 0   0 -1
r$ofc_p1_top2rank    232 429 248 451 ffffffff -120 T1 1   0 0   0 -1
r$ofc_p1_top2suit    232 452 248 465 ffffffff -120 T1 1   0 0   0 -1

//
// fonts
//

t1$d 100 380 380 7c0 1fe0 3ff8 fffe 3ffff fffe 7ff8 1ff0 fe0 7c0 380 100
t1$5 10 1ffc3c 1ffc3e 1ffc1e 1c380f 1c380f 1c380f 1c3e1e 1c3ffe 1c1ffc 7f0
t1$d 10 30 78 fc 1fe 3ff fff 3fff 1fff 7ff 1ff fc 78 38 10
t1$s 10 7c 1fe 3fe 7fe ffe 1fff 3fff 1fff ffe 7fe 3fe fe 7c
t1$2 18006 3c01f 7c03f f807f f00ff e03f7 e07e7 f1f87 fff0f 7fe1f 3f81f
t1$3 18 1e003e 1e001e 1e100f 1e780f 1efc0f 1ffc0f 1ffe1f 1f9ffe 1f0ffc 7f8
t1$8 1c1f0 7fffc ffffe 1f7fbe 1c1e0f 1c1e0f 1c1e0f 1e3f1f 1ffffe ffffc 3f3f8
t1$4 1e0 7e0 1fe0 7fe3 1fce7 7f0e7 fffff fffff 7ffff ff e7 66
t1$J 1f8 1fe 1fe 1f 1c0007 1c000f 1fffff 1ffffe 1ffffe 1ffff8 1c0000 c0000
t1$6 1fe0 fff8 3fffe 7fffe f9e0f f1c0f e1c0f 1c1e1f 1c1ffe 1c0ffc 3f8
t1$h 300 1fe0 3ff0 3ff8 3ffe 3fff 3fff 1fff fff 1fff 3fff 3fff 3ffe 3ffc 3ff0 1fe0 f80
t1$Q 380 fff0 3fffc 7fffe fffff f03cf e01e7 e01f7 f00ff fffff 7fffe 3ffff f 7
t1$X 382 38fe3 3cc73 d832 3fd833 3f8e73 2007e2 380
t1$c 3c0 7f0 ff8 ff8 77f8 fff9 fff3 1ffff 1ffff 1fff7 fff9 fff8 77fc 7fc 7f8 3f0 1c0
t1$s 40 1f0 7f8 ff8 1ff8 3ff9 7fff ffff 7fff 3ff9 1ff8 ff8 3f8 1f0
t1$7 78000 f8000 f8000 e0003 e003f e01ff e1fff ffff0 fff00 ff000 70000
t1$T 78007 78007 fffff fffff fffff fffff 7 7 ffff 3fffc ffffe ff0ff 1e000f 1e0007 1e0007 1f001f fffff
t1$c 78 fe 1ff 1ff eff 1ffe 1ffe 3fff 3fff 3ffe 1fff 1fff eff ff ff 7e 18
t1$A 7 f 1ff 3fff fffff 1ffff7 1ff870 1ffff7 fffff 7fff 1ff f 7
t1$5 8 ffc1e ffe1e ffe0f e3c0f e3c07 e3c0f e3e1f e1ffe e0ffe 7f8
t1$h c00 7f80 ffc0 ffe0 fff8 fff8 fffe 7fff 3fff 7ffe fffe fffc fff8 fff0 ffc0 7f80 3e00
t1$K e0007 e0007 fffff fffff fffff e0fc7 c3f87 effc0 fffff fe3ff f80ff e001f e0007 e0007
t1$9 f000 7fc06 ffe07 1fbf07 1e0f0f 1c070e 1c071e 1f1f7c 1ffffc ffff0 3ffc0 3c00
t1$T f000e f000e 1f001e 1ffffe 1ffffe ffffe e e ffce 7fff8 ffffc 1fc0fe 3e001f 3c000f 3c000f 1e001e 1ffffe
t2$c 10 3c 7c 1fc 1fb 1fb 1fd bc 3c 18
t2$d 18 38 7e 1ff ff 7c 18 10
t2$s 18 3c 7c 1ff 1ff fd 7c 1c
t2$4 18 78 1fa 79b 7ff 7ff 1b
t2$9 1c0 7e3 e73 c37 7fe 7fc e0
t2$J 1e 7 c03 fff ffe c00
t2$6 1fc 7fe 6c3 ce3 c7e 3c
t2$Q 1fc 7fe e37 c1b 61f 7fe 3
t2$6 1fe 3ff 763 663 47f 3c
t2$T 203 603 7ff 7ff 3 3ff 7ff e03 c03 7ff 3fe
t2$2 203 70f e1f c3b 7f3 7c7
t2$h 20 f8 fc fe ff 7f fe fc f8 70
t2$T 2 c06 c06 1ffe 1ffe 6 7fe ffe 1c0f 1803 1c07 ffe 7fc
t2$2 307 60f c1f c73 7e7 3c7
t2$d 30 78 1fe 3ff fc 78 30
t2$Q 30 7fe 7fe c3b c1f 7fe 3fe 3
t2$A 3 7 ff ffb fea 3ff 1f 3
t2$9 380 7e3 c73 c36 ffe 7fc e0
t2$4 38 f8 3cb fff 7ff 1f 9
t2$4 38 f8 3db 79b 7ff 1b
t2$s 3c 7c fd 1ff ff 7c 3c 18
t2$8 3de 7ff 633 673 3ff 1de
t2$9 3e0 7f3 c33 e36 7fe 3f8
t2$8 3fe 7ff c63 c63 7ff 39e
t2$5 4 1fce 19c7 1983 19c6 18fe 78
t2$5 4 fc6 cc3 cc3 cee 47e
t2$7 600 600 41f 4fe 7e0 600
t2$7 600 600 607 67f 7f8 780
t2$T 603 6ff 7ff 3 73 3fe 70f c03 e07 7fe 1fc
t2$h 60 f8 fc ff 7f ff fe fc f8 20
t2$3 6 407 4c3 7c3 777 67e
t2$5 6 fe7 fc3 cc3 ce7 c7f 3c
t2$7 700 600 60f 6ff 7f0 300
t2$7 700 601 61f 7fe 7e0 200
t2$2 707 60f c3b e73 7e7 387
t2$8 73c ffe 18e7 18c3 1de7 ffe 73c
t2$9 780 fe3 1ce3 1866 1cee ffc 7f0
t2$3 804 180e 1987 1b87 1fc6 1cfe 38
t2$6 fc 3fe 763 663 677 43e
t3$T 1800e 3c00e 3800e 7fffe 7fffe 7fffe e e 7fee 1fffc 3fffe 7801e 7000f 70007 7800f 7f9fe
t3$Q 1c0 fffc 1fffe 3ffff 381c7 380e7 380f7 3807f 3ffff 1fffe 7fff 7
t3$X 1e3 e7f3 361a 8341b fe633 803f3 c0
t3$4 1f0 7f0 ff0 7f77 1fc77 3f877 3ffff 1ffff 77 77
t3$6 1ff0 7ffc 1fffe 3ef1f 3ce0f 78e07 70f0f 70ffe 707fc 1f8
t3$h 200 1f80 3fe0 3ff0 3ff8 3ffc 3ffe fff 1fff 3ffe 3ffc 3ff8 3ff0 3fe0 1f80 700
t3$K 30007 3ffff 3ffff 3ffff 387e7 31fc3 3ffe3 3ffff 3f0ff 3c03f 3800f 30007 3
t3$A 3 7 3f 7ff 1ffff 3fff7 3fc30 3fff7 ffff 7ff 3f 7 3
t3$7 3c000 3c000 38002 3803f 383ff 39ffe 3ffe0 3fe00 3e000
t3$c 3e0 7f0 7f8 7f8 7ff8 7ff2 7fef 7fff 7ff7 7ff8 3ff8 3f8 3f8 3f0 1e0
t3$d 40 e0 1f0 3f8 ffc 1fff 7fff 3fff ffc 3f8 1f0 e0 c0
t3$2 6007 1e00f 3e03f 3c07f 380ff 383e7 387c7 3ff8f 1ff0f fc0f
t3$4 60 1f0 7f0 1ff0 7e77 1f877 3ffff 3ffff 1ffff 77 77
t3$3 7001c 7001e 7080e 73c0f 77c07 7fe0f 7ef1e 7cffe 787fc 1e0
t3$5 8 7fe1c 7fe1e 7fe0f 71c07 71c0f 71e1e 70ffe 707fc 3f8
t3$3 c 3801e 3800f 39e07 3be07 3fe07 3ff0f 3efff 3c7fe 1f8
t3$s e0 1f0 7f8 ff8 1ff8 3fff 7fff 3ff7 1ffb ff8 7f8 3f0 e0
t3$h f00 1fc0 3fe0 3ff8 3ffc 3ffe 1fff fff 1fff 3ffe 3ffc 3ff8 3ff0 3fc0 1f80
t3$8 f0f8 3fffc 7fffe 79f0f 70f0f 70f07 79f8f 7fffe 3fffc f1f8
t3$J fc ff ff 7 30007 3800f 3ffff 3fffe 3fff8 30000
t3$9 fe00 3ff07 3ff87 78387 703cf 7839f 3cffe 3fffc 1fff0 3fc0
t3$J fe ff 7f 30007 30007 3ffff 3ffff 3fffe 38000 30000
t4$d 10 30 78 1fe 3ff 1fe 78 30
t4$A 1 7 ff fff fcc fff 7f 3 1
t4$3 180e 1806 1983 1fc7 1efe 1cfe
t4$3 180e 1806 1987 1fc7 1eee 1cfe 38
t4$4 18 78 1eb 78b fff 7ff b
t4$c 18 7c 7c 1fc 1fb 1ff 1fd 1fe 3e 3c
t4$s 1c 3c fe 1fd 1ff fd 7e 3c
t4$s 1c 7c fc 1ff 1ff fc 7c 3c
t4$h 1e0 1f8 1fc 1fe 1ff 1ff 1fe 1fc 1f0 e0
t4$J 1e 1f 3 c03 fff ffe c00
t4$J 1f 7 c03 fff fff c00
t4$6 1fc 7fe ec7 cc3 18e7 18fe 38
t4$6 1fc 7ff 7e3 cc3 ce7 c7f 1c
t4$5 1fce 1fc6 1983 19c7 18fe 7c
t4$2 203 707 e0f c3f e73 7e7 387
t4$2 203 f07 c1f c3b ef3 7e7 383
t4$d 30 78 fc 3ff 3ff fc 78 30
t4$Q 30 7ff fff c1b c1f fff 7ff 3
t4$8 31c ffe ce7 c63 ce7 ffe 31c
t4$9 3800 ff03 1ff87 3c387 381c7 3838e 3c7be 1fffc fff0 3fc0
t4$4 38 f8 3cb f9f fff 1f b
t4$9 3c0 fe3 c73 c33 e7f ffe 3f8
t4$c 3c 7c 1fc 1fd 1ff 1ff 1fc be 3c 38
t4$5 4 1fce 19c7 1983 19c6 18fe 78
t4$T 6 c06 1ffe 1ffe 6 6 7fc 1ffe 1807 1803 1e1e ffe 1f0
t4$T 6 c06 c06 1ffe ffe 6 7fe ffe 1c07 1803 1c0f ffe 3f8
t4$5 6 fe7 fc3 cc3 ce7 c7f 3c
t4$2 703 e0f c1f c3b ff3 7e7
t4$8 73c ffe 18e7 18c3 1de7 ffe 73c
t4$9 780 fe3 1ce3 1866 1cee ffc 7f0
t4$s 8 3c 7e fd 1ff 1ff fe 7c 1c
t4$5 8 3ff1e 3ff1e 3fe07 38e07 38e07 38f1f 387fe 183fc f0
t4$h c0 1f0 1fc 1fe 1ff ff 1fe 1fc 1f8 1f0
t4$3 c06 c07 dc3 fc3 fe7 e7e 3c
t4$3 c07 c83 dc3 fc3 fff c7e
t4$7 e00 e00 c07 c7f ff8 f80
t4$9 fc2 1fe3 1867 1866 1ffe ff8 1e0
t4$9 fc3 1fe3 1867 186e 1ffc 7f8
t4$5 fc6 fe7 cc3 cc3 cff 7e
t4$5 fce 1fc6 1983 1987 18fe 8fe
t4$8 ffe 1ffe 18c3 18c7 1ffe fbc
t5$Q 1c0 fffc 1fffe 1e1ef 1c0e7 180f7 1c07f 1ffff fffe 7fff 7
t5$7 1e000 1e000 1e000 1c00f 1c0ff 1cfff 1fff0 1ff00 1f000
t5$c 1e 3f 3f 3f 1ff 3ff 7ff 7ff 7ff 3ff 3ff 3f 3f 3f 3f
t5$h 1f0 3f8 7fe 7ff 7ff 3ff 1ff 3ff 3ff 7ff 7ff 7fc 3f8 1f0
t5$c 1f 3f 3f 1ff 3ff 3ff 3ff 3ff 3ff 3ff 3f 3f 1f e
t5$s 1f 3f 7f ff 1ff 7ff 3ff 1ff ff 7f 1f e
t5$2 2006 f00f 1f01f 1c07f 1c0ff 1c1e7 1e7c7 1ff8f ff0f 380e
t5$X 31f1 3b19 21a09 3fb09 3e1f9 e0
t5$K 38007 38007 3ffff 3ffff 3ffff 38fc7 3bfc0 3ffff 3f9ff 3e03f 3800f 38007 6
t5$8 3878 fefe 1ffff 1c7c7 18383 18383 1e7c7 1ffff fefe 38
t5$9 3c00 ff83 1ffc3 1c3c3 181c7 1c1cf 1e3fe 1fffe fff8 1fe0
t5$5 4 1ff0e 1ff0f 1ff07 1c703 1c707 1c78f 1c7ff c3fe 78
t5$4 70 1f0 7f0 1ff3 7f33 fc33 1ffff ffff ffff 33
t5$J 78 7e 7f 7 18003 1c007 1ffff 1fffe 1fff8 18000
t5$8 78f8 1fdfc 3fffe 3cf8f 38707 38707 3cf8f 1fffe fdfc 3070
t5$6 7f0 3ffc fffe f78f 1c707 1c707 3878f 387fe 103fc 70
t5$A 7 f 1ff 3fff 3fff7 3fe32 3fff7 1ffff 7ff 3f 7 6
t5$5 8 3ff1e 3ff1e 3fe07 38e07 38e07 38f1f 387fe 183fc f0
t5$3 c 1c00e 1c00f 1c607 1df03 1ff07 1ff8f 1f3ff 1c1fe 70
t5$3 c 3801e 3800e 38e07 3be07 3fe07 3ff1f 3e7fe 3c3fc f0
t5$d c e 1f 7f ff 3ff 3ff ff 3f 1f e c
t5$T e006 1e006 1c006 3fffe 3fffe e 6 1fe6 fffc 1fffe 3e01f 38007 38007 3c00f 3fffe
t5$4 f0 3f0 ff0 3f77 fc77 1ffff 1ffff ffff 77 77
t7$d 100 180 3e0 3fc 7ff ffe 1ffc 3ff8 1ff0 3f0 e0 60 20
t7$5 1 1 30 78 83c f80e ff80e fb80e e381e e1c3c e1ff8 60ff0 70380 70000
t7$7 18000 3c000 3c000 38000 38007 3007f 307ff 3fff0 3fe00 3c000
t7$d 180 180 3c0 7f0 1ff8 7ffe 7fff 3ffc ff0 3e0 3c0 180
t7$3 18 3c 1e f 60007 61c07 73c07 77e0f 7fffe 7e7fc 3c3f0 38000
t7$2 18 3c 7c fc 300ee 701ce f03ce e0387 e071f e0f0e 73e00 7fc00 3f000
t7$T 1c000 1c003 38003 3fc03 3ffff 3ffff 3f 7 7 1ffe7 7fffc 7c1fe e001e e0007 e0007 70007
t7$s 1f0 3f8 ff8 1ff8 7ff8 3ff3 1fff 1ff6 ff2 7f0 3f0 1e0
t7$9 1fe00 3ff03 78f83 70383 60387 7038f 7879e 3fffc 1fff8 3fc0
t7$X 2000 10c0 e1230 e008 8 208 1f1 1
t7$X 200 1823c 17e46 c81 41 61 3e
t7$d 20 70 1f0 ff8 3ff8 1ffc ffe 7ff 3fe 3f0 1c0 180 100
t7$K 30000 70000 7e000 7ff03 7fff3 60fff ffe cff86 fff06 fe780 e03e0 1801fe 8007c 3c 1c 1c
t7$9 3e000 ff800 1ffc0c 1c1e0c 180e0c 180e1c 1c0e3c ffcf8 7fff0 3ffc1 1001
t7$c 3e0 7f0 ff0 7f0 7f3 3fe7 7ff7 7ff0 7ffc 7ffc 3ffe 3cfe 1fc f8 20
t7$8 4000 3f8e0 7fffc 71ffe e0f0e e0e06 e0e07 71f07 7ff9e 1fffe 1fc 20
t7$J 60 7c 6007e 6000f 60007 7f807 fffff c7ffe c03fc
t7$A 70000 ffe83 fffff ffffe 3f0fe 7ce6 3fc2 fc8 3fc fc 38 19 19 1
t7$Q 70c0 1ffc0 3fff8 301fe 300ff 300c7 30063 3c073 1fc33 7fff 3fe 1c e 6
t7$7 78000 78000 70000 7001f 700ff 707fc 73fe0 7fe00 7f000 30000
t7$6 7f0 3ffc fffe 1ff0f 3ce07 38e07 30e07 30fff 707fe 701f8
t7$5 8 1c c1e 3fe07 7fc07 71c07 71c07 70e0f 70ffe 307fc 301e0
t7$c e0 1f8 1fc 3dfc 7ffc 7ff8 7ff0 7fc1 7fdf 7fe6 7f2 7f0 ff0 7f0 3e0
t7$4 e0 3e0 fe0 1e67 7c73 1f077 3e3ff 3ffff 3fff3 73
t7$s e0 3f0 7f0 ff0 ff2 1fff 3fff 7ff9 3ff8 ff8 7f8 3f8 f0
t7$5 e 3fe0f 3fe07 30e03 30e03 30e03 30f0f 307ff 303fc f0
t7$8 f1f8 3fffc 7ff9e 70f0e 60e07 60e07 70f0e 7fffe 3fffc 1f0f0
t7$h f80 1fc0 1fe0 3ff0 1ff8 1ff8 ffc 3ffc 3ffe 3fff 3ffe 3ff8 3ff0 3fc0 1e00
t7$c f8 1fc 1dfe 3efe 3ffc 3ffc 3ff0 3fe3 3fe7 3f3 7f1 7f8 7f8 3f0

// BEGIN OPENOFC_V550_STABLE_REPLAY_T7
// Exact stable-replay glyphs; global T7 tolerance remains 0.75.
t7$2 8 3c 3c 7e fe 380fe 781ef f83ef f07cf f0f9f f1f0f fff08 7fe00 3fc00 1f000
t7$2 1e 1e 1803f 3c07f 7c0ff f81ff f03ef f07cf f1f9f fff0f 7fe0e 3fc00 f000
t7$2 1e 3e 1807e 7c0ff 7c1ff f83ff f03ef e0fcf f1f9f fff1f 7fe0c 3fc00 e000
t7$2 38 79 fd fd 701fd f03fc 1f07de 1e0f9e 1e0f3e 1e3f3e 1ffe1c 1ffc00 ff800 3e000
t7$2 38 7c fc 201fc 701fc f03fe 1f07de 1e079e 1e0f3e 1e3f3f 1ffe1c ffc00 7f800 3e000
t7$2 3c 3c 7e fe 380fe 781ef f83ef f07cf f079f f1f0f fff08 7fe00 3fc00 1f000
t7$2 3c 3c 3007e 780fe f81fe f03fe e07ce e0f8f e1f1f fff1f ffe18 7f800 3e000
t7$2 3c 7c fc 100fe 781fe f83fe f03cf f07df e0f9f f1f1f fff00 ffe00 7fc00 1f000
t7$2 3c 7c fc 700fe f81fe f03fe 1e07de 1e0f9e 1e1f1f 1fbf1f ffe18 7f800 3f000
t7$2 3c 7e fe 380fe 781ef f83ef f07cf f079f f1f0f fff08 7fe00 3fc00 1f000
t7$2 3c 7e fe 380fe 781ef f83ef f07cf f0f9f f1f0f fff08 7fe00 3fc00 1f000
t7$2 3d 3c 7e 380fe f81fe f83fe f03ce e078f e0f9f fbf1f ffe1c 7fc00 3f000
t7$2 3d 7d fc 300fe 781fe f83fe f03cf e079f e0f9f f3f1e ffe00 ffc00 7f800 1e000
t7$2 7d fc 300fe 781fe f83fe f03de e078f e0f9f f3f1f ffe18 ffc00 7f800 e000
t7$2 c007 3e01f 3e03f 7c07f f80ff f03f7 f07e7 fdfc7 7ff8f 3fe0f 1fc0f
t7$2 1c000 7c00e fc01f f807f f01ff e03ff 1f0fee fffce fff1e 7fe3e 1f03e 3e
t7$2 100000 3c 7c fc 300fe 781fe f83fe f03ce 1e0f8f 1e0f9f f3f1f ffe18 ffc00 3f000 4000
t7$2 1f8000 180000 38 7c fc 701fc f01fc f03fe 1f07de 1e0f9e 1e1f3e 1e3e1f 1ffe18 ffc00 7f000 1c000
t7$2 3f8000 380000 78 f8 1f8 601fc f03fd 1f07fc 1e07bc 3c0f1e 3c1f3e 3e7e3e 1ffc30 1ff800 ff000 1c000
t7$3 10 7c 7e 3e f 1e180f 1e3c0f e7c1f ffe3e ffffe 7fffc 7e7f0 7c000 78000
t7$3 1c 3e 3f 1f f0007 f1e07 f3e0f 77e1f 7ffff 7fffe 7e7fc 3c1f0 3c000
t7$3 1c 3e 3f e000f f1c07 f3e07 f7e0f 7ff1f 7ffff 7effe 7c7fc 78060
t7$3 1c 3e 6001f f000f f1c07 f3e07 77e0f 7ff9f 7ffff 7e7fe 7c3f8 78000
t7$3 30 78 7c 3e 4001e 1c180e 1e7c1f 1e7c1e eff7e ffffc ffff8 fc7e0 78000 70000
t7$3 30 78 7d 3e 4001e 1c380e 1e7c1f 1e7c1e eff7e ffffc ffff8 fc7e0 78000 70000
t7$3 38 3c 3e e001f e000f e3c0f e7c0f efe1f ffffe ffffc 7cff8 781e0 70000
t7$3 38 7c 7e 1f 2000f e1c0f e3c0f f7e1f ffffe 7fffc 7eff8 7e3e0 7c000 38000
t7$3 3c 3e 3e e001f 1e180f e3c0f e7c1f fff3e ffffe 7effc 7c7f0 78000 70000
t7$3 3c 3e 3f 6000f e000f f1c07 f3e0f f7e1f 7fffe 7fffe 7e7fc 7c1e0 78000
t7$3 3c 3e 3f e000f e1c0f e3c0f f7e0f fff3f 7fffe 7effc 7c7f0 78000 30000
t7$3 3c 3e 3f e000f e1c0f f3c07 f7e0f 7ff1f 7fffe 7effe 7e7f8 78040 20000
t7$3 3c 3e 3f e001f e1c0f e3c0f f7c0f fff3f ffffe 7effc 7c7f8 78000
t7$3 3c 3e e003f e000f e3c0f e7c0f ffc1f fff7f ffffe fcffc 783f0
t7$3 3c 3e e003f e080f e3c0f e7c0f ffc1f fff7f ffffe fcffc 783f0
t7$3 78 7c 7e c001e 1c101e 1e780f 1e7c1e efe3e ffffc ffffc fcff0 f8000 70000
t7$3 40000 70000 7000c f001e f3c1e ffc0f ffc0f ffc0f fde1f f1fff ffe 7fc 1f0
t7$3 ff000 c0000 0 0 0 e1 fb fb 8007f 8f03f 9f03d bf079 ffcf8 ffff8 f3ff0 e1fc0 c0000
t7$4 40 3e0 7e0 1fe6 3fef feef 1f8ff 3ffff 7ffff 7ffff 7fff7 38076
t7$4 80 1c0 7e0 fe6 3fef 7eef fcff 3f3ff 7ffff 7ffff 7fff7 7f072
t7$4 c0 3c0 7e0 1fe6 7fee fcef 3f8ff 7ffff fffff 7ffff 7fef7 200e4
t7$4 180 7c0 fc0 1fce 3fde fdee 1f8ff 3efff 7ffff fffff 7fff7 7e060
t7$4 181 7c0 fc0 1fce 3fde fdde 1f9fe 3efff 7ffff fffff ffef7 7e0e0
t7$4 1c0 3c0 fc0 3fee 7fee 1fdee 3f1fe fffff fffff fffff 7ffef e6
t7$4 1c0 3e0 fe0 3fee 7fee 1fcef 7f0ff fffff fffff fffff 7f0ef e4
t7$4 1c0 3e0 fe2 1fef 7eef fcef 3f9ff 7ffff 7ffff 7fff7 7f877 60
t7$4 1c0 7c0 1fc0 3fee ffee 3f9fe 7f1fe ffffe fffff fffff 7e0ef e4
t7$4 1e0 7e0 fe0 3fef 7eef 1fcef 3f3ff 7ffff 7ffff 7ffff 3e077 40
t7$4 1e0 7e0 1fe0 3fee feef 3f8ef 7ffff fffff fffff 7ffff ef c0
t7$4 3c0 fc0 1fc0 7fce fdde 3f9fe 7effe ffffe ffffe fffff 780ee 80
t7$4 f0000 0 c0 3e0 7e0 fe7 3fef 7eef fcff 3f7ff 7ffff 7ffff 7fff7 3e072
t7$4 ff000 c0000 0 0 f00 3f00 7f30 1ff78 3f779 7e7f9 f9ff8 ffff8 ffffc fffbc f0390
t7$4 1c0000 0 0 1c0 7c0 fc0 3fee 7fee 1f8ee 3f1ff 7ffff fffff fffff 7f8f7 60
t7$4 1f0000 0 40 1e0 7e0 fe2 3fef 7eef 1fcef 3f7ff 7ffff 7ffff 7fff7 7e077
t7$5 1 21 79 7c 787e 7fc1e 1ffc0e 1ffc0f 1f3c1e e3f7e e1ffc f1ff8 f0fe0 70000 70000
t7$5 8 3c 7fe3e ffe1f ffe0f ffc0f f1c0f f1e1f f1fff f0ffe 70ff8 201e0
t7$5 8 3c1c ffe1e ffe1f ffe0f f1c0f f1e0f f1f1f f1fff f0ffe 707f8 c0
t7$5 c 3fe1f 7ff1f 7ff0f 7fe07 78e07 78e07 78f9f 78fff 787fe 303fc
t7$5 1c 43e fe1f ffe0f ffe07 ffe07 71e0f 71f9f 70ffe 78ffe 783f8 70000
t7$5 1c 43e 3fe1f ffe0f ffe07 fde07 71e0f 71f9f 71fff 70ffe 783f8 30000
t7$5 1c 7c3e ffe3e ffe1f ffc0f e3c0f f1c1f f1f7f f1ffe f0ffc 703f0
t7$5 1c 7fe1e ffe1f ffe0f fde07 f1c07 f1e0f 71fff 70ffe 70ffc 3e0
t7$5 3c ffc3e ffe3e ffe0f ffc0f e3c0f e3e1f f1ffe f1ffe f0ffc 603e0
t7$6 40 3ff8 1fffc 3fffe 7fe1f 79c0f f1c0f f1e3f e1ffe e0ffc e07f8 c0
t7$6 60 7ff8 1fffc 3fffe 7ff1f 79e0f f1c0f f1f3f e1ffe e0ffc e07f8 e0
t7$6 e0 3ff8 fffe 1fffe 3ff1f 7de0f 79e0f f1f1f f1ffe f0ffc f07f8 40040
t7$6 e0 3ffc fffe 1ffff 3ff1f 7de0f 79e0f f1f1f f0fff f0ffe 603f8 60
t7$6 1f0 1ffc 7ffe ffff 1ff0f 3fe0f 7de0f 79fbf 70ffe 70ffc 707f0 70000 20000
t7$6 7f8 3ffe fffe 1ffff 3ff0f 3de07 79e0f 78fff 70ffe 707fc 701f0
t7$6 ff0 3ffe ffff 1ffff 3ff87 3cf07 78f07 78f9f 787ff 707fe 1fc
t7$6 ff8 7ffe ffff 1ffff 3ff07 7ce07 78f0f 78fff 70fff 707fc 701f0
t7$6 1fe0 7ffc 1fffe 3fffe 7ff1f 79e0f f1e0f f1f1f e0ffe e0ffc 3f8
t7$6 1fe0 7ffc 1fffe 3ffff 7ff0f 79e0f f1e0f f1f3f f0ffe e0ffc 3f8
t7$6 3ff8 7ffc 1fffe 3ffff 7fe0f 79e0f f1e1f f1fff f0ffe f07fc 601e0
t7$6 3ff8 fffc 1fffe 3ffff 7de0f f9e0f f1e0f f1fff f0ffe 607fc 1f0
t7$6 3ff8 fffc 3fffe 3ffff 7de0f f9e0f f1f0f f1fff f0ffe 607fc 1f0
t7$6 3ff8 fffc 3fffe 7ffbe 7de0f f9c0f f1e1f f1ffe e1ffc e0ff8 601e0
t7$6 7f00 1fff0 3fffc 7fffe f9ffe f1e1e 1e1c0f 1e1e0f 41ffe ffe 7fc 1f8
t7$6 7ff0 1fffc 3fffe 7fffe f9e1f f1c0f f1e1f e1ffe e1ffe c07fc 3f0
t7$7 3e000 3e000 3e000 38000 78000 78000 7142a 7ffff fffff 7ffff
t7$7 78000 f8000 f8000 f001f f00ff f07ff f7ffe fffe0 ffe00 7f000 70000
t7$7 78000 f8007 f801f f007f 703ff 71ffc 77fe0 7ff80 7fc00 7e000 38000
t7$7 78006 f801f f807f f01ff 707fc 71ff0 77fc0 7fe00 7f800 7e000 30000
t7$7 7c000 7c000 7c000 70003 7007f 707ff 77fff 7fffc 7ff80 7e000
t7$7 7c000 7c000 7c000 f0000 f007f f07ff fffff ffffc fff80 ff000 70000
t7$7 f8000 f8000 f8000 f001f f01ff f0fff ffffe fffe0 ffe00 fc000
t7$7 f8000 fc007 f801f 701ff 707ff 71ffc 7ffc0 7fe00 7f800 7c000
t7$7 fc000 fc000 f8007 f007f 701ff 71fff 7fff0 7ff80 7f800 7e000
t7$7 1f0000 1f0000 1f0000 3c0000 3c0018 3c07fc 3cfffc 3ffff8 3fff80 3ff000 180001 1 1 1
t7$8 10 e3fc 3fffe 7ffff fff8f f1f0f e0f0f e1f1f fbfff ffffe 7fffc 3f860
t7$8 f0 3fbfc 7fffe 7ffff f9f0f f0f0f e0f0f f1f9f ffffe 7fffe 3f9f8
t7$8 f8 1fdfe 3ffff 7ffff f8f87 70787 70787 79fcf 7ffff 3ffff 1fcfc
t7$8 6000 3f9f8 7fffe ffffe f1fdf e0f0f f0f0f fbf0f 7ffff 7fffe 1fbfc f8
t7$8 70f8 1fffe 3ffff 7ffff f8f87 f0707 f0787 fdfcf 7ffff 3fffe 1f8fc
t7$8 e000 3fbf8 7fffe ffffe f1f1f e0e0f e1f0f fbf9f ffffe 7fffc 1f3f8 e0
t7$8 f9fe 3ffff 3ffff 7ffc7 78787 70787 78f8f 7ffff 3ffff 3fdfe f830
t7$8 1e080 7f3f8 ffffc 1ffffe 1e1f1f 1c1e0f 1e1e0f 1f7f1f ffffe ffffc 3f3f8 c0
t7$8 1f000 7fdf8 ffffc ffffe e1fdf e0f0f 1f1e0f fff0f 7ffff 3fffe e3fc f8
t7$8 1f9f8 3fffe 7fffe fffdf f0f0f e0f0f f1f0f fffff 7fffe 3fbfc e0f8
t7$8 3e000 ffbf0 1ffffc 1ffffc 1e3fbe 1c1e1e 3e3e1e 1ffe1e ffffe 7fffc 1e7f9 1f1 1
t7$8 3f0f0 7fffc 7fffe fbffe e1f1f e0e0f f1f0f fff9f 7fffe 3fffc 63f8
t7$8 3f9fc 7fffe fffff fffdf f0f0f e0f0f f1f0f fffff 7fffe 3fbfc e0f0
t7$9 e000 3fc00 7ff00 fff87 f0f87 e078f f078f f8fbe ffffe 7fffc 1fff8 7fc0
t7$9 f000 7fc00 fff07 fff07 1f0f8f 1e078f 1e079e 1f9ffe ffffc 7fff8 1ffe0 7f00
t7$9 f800 3fe00 7ff07 fff87 f0787 e038f f079f fdffe 7fffe 3fff8 1fff0 700
t7$9 f800 3fe00 7ff07 fff87 f0787 e038f f079f fdffe 7fffe 3fffc 1fff0 700
t7$9 f800 3fe07 7ff07 fff87 1f0f8f 1e079e 1e07be 1f9ffe ffffc 7fff8 1ffe0 3c00
t7$9 10000 ff800 1ffc00 3ffe0e 3e3e0e 3c0f1e 3c0f3e 3f1f7c 1ffff8 ffff9 7ffe1 1ff81 1
t7$9 18000 ff800 1ffc00 3ffe1c 3c1e1c 381e1c 3c1e3d 3e3efd 1ffff8 1ffff0 7ffe0 1ff00
t7$9 1e000 ff800 1ffe0e 1ffe0e 3e1f1e 3c0f3f 3c0f3d 3f3ffd 1ffff8 ffff0 3ffc0 fe00
t7$9 1f800 7fe00 fff02 fff87 f0787 e078f f079f fffbe 7fffe 3fffc fff0 f00
t7$9 1f800 7fe00 fff07 1fff07 1e0f8f 1e079f 1f0fbe ffffe ffffc 7fff8 1ffe0 700
t7$9 1fc00 7fe07 fff07 fdf87 f078f e079f f0fbe ffffe 7fffc 3fff0 ffc0
t7$9 1fc00 7fe07 fff07 fff87 f078f e079f f0fbe ffffe 7fffc 3fff0 ffc0
t7$9 1fe03 3ff83 7ffc3 f87c7 703c7 703df 7cfff 7fffe 3fffc 1fff0 3f80
t7$9 3f000 ffc00 1ffe00 1fff0f 1e0f0f 1e070e 1e0f1e 1fff7e ffffc 7fff8 1fff0 1f80
t7$9 3f800 7fc00 fff00 1fff07 1e0f8f 1e078f 1e0f9f fff7e ffffc 7fff8 fff0 e80
t7$9 3f800 7fe00 fff07 1fff07 1e078f 1e079f 1f0fbe ffffe ffffc 3fff0 ffc0
t7$9 3fc00 7fe0f fff0f 1fff0f 1e0f8f 1e079e 1f0f7e ffffc ffff8 3ffe0 1ff80
t7$9 7f000 ffc0c 1ffe0e 3e3e1e 3c0f1e 3c0f3f 3e1f7c 1ffff8 ffff8 7ffe0 1ff80
t7$9 7f000 1ffc00 1ffe0e 3e3e0e 3c0f1e 3c0f1e 3e1f7d 1ffffc ffff8 7fff0 1ffc0
t7$9 1fc000 7ff000 7ff839 78f83b 703c7b 703cff 7c7df7 7ffff7 3fffe7 1fffc3 7ff01
t7$A 1 3 4dff 7ffff 7ffff 7ffff 7fe7f 1ffff 7fff fff 1ff 3f f f 2
t7$A 1 3 3ffff 7ffff 7ffff 7ffff 3ff7b fffb 1fff 7ff 1ff 3f f f 6
t7$A 1 3fc01 7ffff 7ffff 7ffff 3fe7f 7fff 1ff7 fff 3ff 7f 1f e e
t7$A 2 40003 fffff fffff fffff ffd7f 3fff7 ffee 1ffe 3fe fe 3e 1c 1c
t7$A 2 40003 fffff fffff fffff ffdff 3ffff ffee 1ffe 7fe fe 3e 1e 1c
t7$A 3 dff 7ffff 7ffff 7ffff 7fe7f 1fff3 3fff fff 1ff 3f f f 2
t7$A 3 7fda3 7ffff 7ffff fffff 3fe77 fff7 1ff7 7ff 1ff 7e 1e e e
t7$A 3 7ff03 fffff fffff fffff 3fe77 fff7 3ffe ffe 3fe fe 1e 1c 1c
t7$A 3 7ffa3 7ffff fffff fffff 3fe77 fff7 1ff7 7ff 3ff 7e 1e 1e e
t7$A 3 7fff7 7ffff 7ffff fffff 7fe77 fff7 1ff7 7ff 1ff 7e e e e
t7$A 3 7fff7 7ffff 7ffff fffff 7fe77 fff7 1fff 7ff 1ff 7e 1e e e
t7$A 1c 1e 3e fe 7fe 3ffe ffee 3fff7 fffff fffff fffff fffff 7 2
t7$A 1c 3c ffc 1ffffc 3ffffc 3fffdc 3ff9dc 3fffdc 3fffc 7ffd 7fd 7d 3d 18
t7$A 3e001 7fffd 7ffff 7ffff 3ffff ff7f 3ff7 ff7 3ff ff 7e 1e 1e c
t7$A 40003 fffef fffff fffff fffff 3fcff ffee 3fee 7fe 3fe fc 3c 3c 1c
t7$A 7f801 7ffff 7ffff 7ffff 3feff ff77 3ff7 fff 3ff fe 3e 1e 1c c
t7$A 7f801 7ffff 7ffff 7ffff 3ffff ff77 3ff7 fff 3ff fe 3e 1e 1c c
t7$J 3 0 0 0 3f0 3fc 3fc 1c00fe 1c001e 1f801e 1ffffe 1ffffc 1ffff8 1c07f0 80000
t7$J c0 fc fe f00ff e000f f0007 fff0f fffff ffffe 1e1ffc 40000
t7$J f0 1fe 1fe 1ff f e000f e003f fffff ffffe ffffc fff00 f0000 60000
t7$J f0 c00fc f00fe e007f f800f ffc07 1fffff 1fffff c1ffe 1fc
t7$J fc fe 700ff f003f f8007 ffe0f fffff fffff e3ffe f8
t7$J fc 3fe 3ff 1cf 7 1f 7f 707fe 77ffc 7fff0 7ff00 7f000 38000 38000
t7$J 1f0 1fc 1fe ff e000f e0007 fff3f fffff ffffe ffff8 e0000
t7$J 1f8 1fc c01fe e007f e000f 1ff00e 1ffffe 1ffffe 1ffffc 1c03f8
t7$J 1f8 1fc e01fe e003f e000f ff80f 1fffff 1ffffe 1efffe c01f8
t7$J 1fc 1ff 1ff e000f e0007 f001f fffff ffffe ffffc e0000 60000
t7$J 3e0 7f8 7fc 3803fc 3c003c 3c001c 3ffffc 3ffffc 3ffff8 38fff1 380001 1 1
t7$K 1c000 1c000 1fe01 3fffd 3ffff 3ffff 187ff 3bff1 3fff1 3fffb 7f0ff 7807f 7801f 7 3 3
t7$K 1c000 1c000 1fe01 3fffd 3ffff 3ffff 18fff 3bff1 3fff1 3fffb 7f0ff 7807f 7801f 7 3 3
t7$K 1e380 7fff0 7fffc ffffe f03fe e03cf f01ef f01ff ffffe 7fffe 1fffe 3fe 1e 6
t7$K 20000 38000 78000 7fe03 7fffb 7ffff 71fff 63fff 7ffc7 fffe3 ffff7 fc1ff e00ff e003f 1f f e
t7$K 38000 38000 3e000 7fe00 7fff3 7ffff 30fff 77fff fffe7 fffc7 ff7f6 f01ff 1e00ff 7f 1e e e
t7$K 38000 38000 7e000 7fe03 7fff3 7ffff 30fff f7fff fffc7 fffc7 ff7e6 f03ff 1e00ff 7e 1e e e
t7$K 38000 3c000 3ff01 7fffb 7ffff 70fff 73fff 7ffe3 fffe3 ff3f7 f81ff e00ff 6003f 1f f e
t7$K 38000 78000 7f000 7ff02 7fff3 f7fff e1fff fffff fff8f 1fffc7 1fc7ec 1c03fe 1c01fe 7e 3e 1c 1c
t7$K 70000 70000 78000 7fc02 fffe7 fffff 61fff e7fff fffcf 1fff8f 1fefec 1f03fe 1c01fe c00fe 3e 1c 1c
t7$K 70000 70000 78000 7fe03 ffff7 fffff e1fff e7fff fff87 1fffc7 1fe7ee 1f03fe 1c01fe c007e 3e 1e 1c
t7$K 70000 70000 7f807 ffff7 fffff fffff 61fff effc7 fffc7 fffee 1fc3ff 1e01fe 1e007e 1e e e
t7$K 78000 70000 7f800 fff83 fffff e7fff e3fff fffff 1fff8f 1fffc7 1f87fe 1c03fe 1c00fe 7e 3c 1c 1c
t7$K e0000 f0000 f8007 fffe7 fffff fffff e1fff e7fcf 1fff8f 1fffee 1fe7fe 1f01fe 1c00fe 1c003e e e
t7$K f0000 e0000 fe004 fff87 fffff 1effff 103ffe 1fff9e 1fff0e 1fffc8 1f8ffe 1c03fe 1c00fc 7c 1c 1c c
t7$Q 1 0 600 7ff80 ffff0 1ffffc 1e0ffc 1c07be 1e079e 1e03de 1fe1fe ffffc 7fffc 7ff9 1f9 3d d 1
t7$Q 3 0 0 700 7ffc0 ffff8 1ffffc 1e07fe 1c079e 1c03de 1e03fe 1ff1fe ffffc 7fffc 7ffc 3c 1c
t7$Q 180 1ffe0 3fffc 7ffff 783ff 701ef 781e7 780f7 7f87f 3ffff 1ffff 1ffe 7e f 2
t7$Q 200 7ff80 7ffe0 ffffc f0ffe 1e03fe 1e03de f03ce fe1fe 7fffe 3fffe 7ffc 1fc 3d 1d
t7$Q 380 3ffe0 7fffc ffffe f03ff e03cf e01ef f01ff ff8ff 7fffe 3fffe 3ffe 1e e
t7$Q 380 3fffc 7fffe 7ffff f83df f01ef f01f7 f00ff 7ffff 7fffe 3fffe 7fff f
t7$Q e00 3ff00 ffff0 1ffff8 3ffffc 3c07bc 3c079c 3c07dc 3e03fc 1ffffc ffff9 7fff9 3d 3d
t7$Q f00 7ff00 1ffff0 1ffff8 3e0ffc 3c073c 3c079c 3c03dc 1fc3fd 1ffffc ffff8 1fff8 3c 3c
t7$Q 8000 3ffc0 7ffc0 ffffc f0ffc e03fe 1e03df f03ce fe1ee 7fffe 3fffe 7ffc 3fc 3c 3c
t7$Q 1e380 7ffe0 7fffc ffffe f03fe e03cf f01ef f81ff ffefe 7fffe 1fffe 7fc 1e 1e
t7$Q 1fbc0 7ffe0 7fffc f9ffe f03ff f01cf f01ef fc1ff 7ffff 3ffff fffe 3fe 1e e
t7$Q 3c700 fffe0 ffff8 1ffffc 1e07fc 1c079e 1e03de 1f03fe 1ffffc ffffc 3fffc 7fd 3d d
t7$Q 3e780 fffc0 1ffff8 1f7ffc 1e07fe 1c079e 1e03de 1f03fe ffffe 7fffc 3fffc 7f9 3d 3d 1
t7$Q 3fbc0 7ffc0 ffffc f0ffe f03fe f03df f01ef fe1ef 7feff 3fffe 7ffe 3fc 3c 1c
t7$Q 3ff80 ffff0 ffffc 1f3ffc 1e07be 1e039e 1e03ce 1f81fe ffffe 7fffc 1fffc 1fc 3d 5
t7$T 3c007 7c007 7f80f fffcf 7ffff 3fff ff 1600e fff9e ffffe 1ffffe 1e07fc 1c007e 1e003e 1f001e 1fe03e ffffc 3fffc
t7$T 3c007 7c00f 7ffef fffff 7ffff 1ff f 1ff8f 7ffff ffffe ffffe 1f003f 1e000f 1f000f fc01f fffff 7fffe
t7$T 3fe01 1ffc3 3ffb 7ff 7f 7fc0f fff87 fffe7 1fbfff 1e03ff 1e007e 1f003e fe01e 7f81e 3fffe fffe 3ffc
t7$T 7800c f001e f001e 1fff1e 1ffffe 1ffffc ffc 1c 3fc3d ffffd 1ffffd 3ffff9 3c01fd 38003c 3c003c 3f003c
t7$T 7800f fc00e fffce ffffe fffe 1fe 1e 7ff1e 1ffffe 3ffffc 3f3ffc 3c007c 3c003e 3e001c 1fc03c 1ffffc 7fffc
t7$T f001c f001c 1f001c 1ffffc 1ffffc 1ffffc 1c 3c 3ffbd ffffd 1ffffd 3ffffc 3e003e 3c001e 3c001e 3fc07e 1ffffc
t7$T f001e f001e 1ff81e 1ffffe 1ffffc 1fffc 1c c01c 7fffc 1ffffd 1ffffd 3f03fc 3c003e 3c001e 3e003e 1fe3fc
t7$X 63860 78df8 7fbfc fb0c 30c 3ec 1fd 71 1
t7$X 63ce0 78df8 7fbfc fb0c 30c 3fc 1fd 71 1
t7$X 87080 c3bf0 ffff9 ff619 e61d 799 3fb 1f3 3
t7$c 40 7f0 ff0 ff8 ff8 ffb 1ff7 1fff 1fff 1ffb 1ffc 1ffc 1ffc 1bfe 3fc
t7$c 80 3f0 3f8 77fc fffc fffc fff8 fff3 ffff ffff ffee 2ff6 ff6 1ff0 ff0 ff0
t7$c 80 3f0 7f8 7fc 7ffc 7ffc 7ff9 7ff3 7fff 7fff 7ff7 7ffb ff8 ff8 ff8 7f0
t7$c 1e0 3f0 7f8 7f8 7f9 3ff9 7ff7 7fff 7fff 7ffb 7ffd 7ffe 3ffe 13fe
t7$c 1e0 3f8 7f8 7fc 7fc 3ff9 7fff 7fff 7ff7 7ffd 7ffe 7ffe 3ffe 1fe 1fc
t7$c 1e0 3f8 33fc 7ffc 7ffc 7ffc 7ffc 7ff3 7fff 7fff 7ffe ff6 1ff6 1ff0 ff0 3e0
t7$c 1e0 7f0 7f8 7f8 7ff8 fff9 fffb ffff ffff fff7 fffb 7ff9 7f8 7f8 7f8 3f0
t7$c 1e0 7f0 7f8 27f8 7ffc fff8 fffb ffef ffff ffff fff6 7ffa ff8 ff8 ff8 7f0
t7$c 1f0 3f8 3fc 3bfc 3ffc 7ffc 7ff9 7fff 7fff 7ff7 7ffb 3ffd 7fc 7fc 3f8
t7$c 1f8 3fc 3fc 3ffc 7ffc 7ffd 7ffb 7fff 7fff 7fff 3ffd 3fc 3fc 3fc 1f8
t7$c 1f8 3fc 33fc 7ffc 7ffc fffc fff9 ffff ffff ffff 3fff ffa ff8 ff0 7f0 e0
t7$c 1f8 3fc 3bfc 7ffc 7ffc 7ffc 7ff9 7fff 7fff 7fff 3ff7 ffa ff8 ff0 7f0 1e0
t7$c 3c0 7f0 ff0 1ff2 ff2 1ff7 7fff 7fff 7ffb 7ffc 7ffc 7ffe 7ffe 3dfe 1fc 1f0
t7$c 3c0 fe0 1ff0 1ff2 1ff6 1fee 7fff 7fff 7ffb 7ffc 7ffe 7ffe 7ffe 3dfc 1f8
t7$c 3e0 7f0 ff8 ff8 ff9 7ff3 ffff ffff ffff fffb fffc fffc 7bfc 3fc 3f8 1f0
t7$c 3e0 7f0 ff8 ff8 7ff8 fffb ffff ffff ffff fff7 fffb 7ff8 7f8 7f8 7f8 3e0
t7$c 3e0 7f8 ff8 ff8 7ff9 7ff3 fff7 ffff ffff fffb fffd 7ffc 3ffc 7fc 3f8
t7$c 3f0 3f8 3fc 7ffc 7ffc 7ffc 7ffb 7fff 7fff 7ff7 7fff 7fa ff8 ff8 7f0 1c0
t7$c 3f0 7f8 7f8 7f8 7f9 3ffb 7fff 7fff 7fff 7ffc 7ffe 7ffe 3ffe 1fe
t7$c 3f0 7f8 37fc 7ffc fff8 fff8 fff3 ffff fffe fffe 7ff6 ff2 ff0 ff0 ff0 180
t7$c 3f8 3fc 7ffc fffc fffc fff8 fff3 ffff fffe 7ffe ff6 1ff2 1ff0 ff0 3e0
t7$c 3f8 7f8 7fc 3ffc 7ffc fff9 fff7 ffff ffff ffff 7ffb 37fc 7fc 7f8 7f8 60
t7$c 3f8 7fc 7fc 3ffc 7ff9 7ff7 7fff 7fff 7ffb 7ff9 7ffc 7fc 7fc 3f8 1f0
t7$c 3f8 7fc 7fc 7ffc 7ffc 7ffb 7fff ffff fff7 7ffb 7ffd 7fc 7fc 7fc 3f0
t7$c 3f8 7fc 27fc 3ffc 3ffc 3ffb 3fff 3fff 3ff7 3ffb 3ffd 7fc 7f8 7f8 3f0
t7$c 3f8 33fc 7ffc 7ffc fffc fff9 fff7 ffff ffff 7ff6 ffa ffa ff0 7f0 1e0
t7$c 7c0 fe0 1ff0 1ff0 1ff6 1fee fffe ffff fff3 fffc fffc fffc fffc 7bfc 3f8 1e0
t7$c 7c0 ff0 1ff0 ff0 ff6 fff6 fffe ffff fff7 fffb fffc fffc 7ffc 7f8 3f8 1e0
t7$c 7e0 ff0 ff0 ff2 1ff2 7fff ffff ffff fffb fffc fffc 7ffc 3bfc 3fc 3f8 80
t7$c 7e0 ff0 ff8 ff0 ffb 3ff7 7fff 7fff 7ffb 7ffc 7ffe 7ffe 3ffe 11fe 1f8
t7$c 7e0 ff0 ff8 ff2 ffb 3ff7 7fff 7fff 7ffb 7ffc 7ffe 7ffe 3ffe 11fe 1f8
t7$c 7e0 ff0 ff8 ff2 ffb 7ff7 7fff 7fff 7ffb 7ffc 7ffe 7ffe 3ffe 11fe 1f8
t7$c 7e0 ff0 ff8 ff8 7ff8 fff7 ffef ffff ffff ffff fff8 fff8 7f8 7f8
t7$c 7e0 ff0 ff8 ff8 7ffa fff7 ffff ffff ffff fffb fff8 7ffc 7fc 7f8 7f0
t7$c 7e0 ff0 1ff0 ff2 ff6 7fee ffff ffff fff3 fffd fffc fffc 7bfc 3fc 3f8 c0
t7$c 7f0 7f8 ff8 7f8 7ffb 7ff7 7fff 7fff 7fff 7ff9 7ffc 7ffc 3fc 3fc 3f8
t7$c 7f0 ff0 ff8 ff0 7ff2 ffff ffff ffff fff7 fffb fffc 7ffc 7fc 7f8 3f0
t7$d 20 30 f8 1f8 7fc 7ffe 7fff 3fff fff 7ff 3fe 1f8 1f0 c0 c0
t7$d 20 60 e0 3f0 7f8 7ff8 fffe 7fff 3fff fff fff 7f8 3e0 1c0 180
t7$d 20 60 e0 3f0 ff8 fff8 fffc 7ffe 3fff 1fff fff 7f8 3e0 3c0 300
t7$d 20 70 70 1f8 3fc 1ffe 7fff 7fff 1fff fff 3fe 3f8 1f0 e0 c0
t7$d 20 70 f0 3f8 1ff8 7ffc 7ffe 3fff 1fff 7ff 7fe 3f0 1e0 1c0 100
t7$d 20 70 f0 7f0 7ff8 7ffc 7ffc 3ffe 1fff fff 7ff 7f8 3c0 380 200
t7$d 20 70 f8 1f8 7fc 7ffe 7fff 3fff fff 7ff 3fe 1f8 1f0 c0 c0
t7$d 20 70 f8 3f8 ffc 3ffe 7fff 3fff fff 7ff 3fe 1f8 1e0 e0
t7$d 20 70 f8 3f8 ffc 3ffe 7fff 3fff 1fff 7ff 3fe 1f8 1e0 e0
t7$d 30 f8 1f8 7fc 7ffe 7fff 3fff fff 7ff 3fe 1f8 1f0 c0 c0
t7$d 38 7c fe 7fe 3fff 3fff fff 7ff 3ff 1fe fc 78 70 20
t7$d 40 c0 1e0 3e0 ff0 3ff8 fffc fffe 7fff 3fff ffe ff0 7e0 380 300
t7$d 40 e0 f0 1fc 3fe 7ff fff 3fff 7fff 1ffe 7fc 1fc 78
t7$d 40 e0 f0 1fc 3fe 7ff fff 3fff 7fff 1ffe 7fc 1fc 78 30
t7$d 60 e0 1f0 3f8 1ff8 fffe ffff 3fff 1fff fff 7f8 3f0 1e0 1c0 80
t7$d 60 e0 1f0 7f0 3ff8 fffc 7ffe 3fff 1fff fff 7fc 3f0 3c0 380 100
t7$d 60 e0 3f0 1ff0 fff8 fff8 7ffc 3ffe 1fff fff 7f8 7c0 380 300
t7$d 80 c0 1e0 1f8 3fe 7ff fff 1fff 3fff 7ffe ffc 1f8 f8 70 30
t7$d 80 c0 1f0 1f8 3ff 7ff fff 1fff 3fff 7ffe ffc 1fc 78 38 10
t7$d 80 1c0 1f0 3fc 7ff 7ff fff 3fff 7ffe 7ffc 7fc 1f8 70 30
t7$d 80 1c0 3c0 7e0 ff0 3ff8 fffe ffff 7fff 3ffe ff8 7e0 3c0 380 100
t7$d 80 1c0 3c0 7e0 ff0 3ff8 1fffe 1ffff 7fff 3ffe ff8 7e0 3c0 380 100
t7$d 80 1c0 3e0 3f0 7fc 1fff 3fff 7fff fffe 1ffc 7f8 3f0 e0 60 40
t7$d c0 c0 1e0 3f0 ff8 3ffc ffff ffff 3fff 1ffe 7f8 3f0 3e0 1c0 80
t7$d c0 c0 1e0 7f0 1ff8 7ffc fffe 7fff 3fff 1ffe ff8 7e0 3c0 180 100
t7$d c0 e0 1f0 1fc 3ff 7ff 1fff 3fff 7fff 1ffe 7fc 1f8 78
t7$d c0 1e0 3e0 ff0 3ff8 fffe 1ffff 7fff 1fff ffc 7f0 3e0 3c0 180
t7$d e0 e0 3f0 7f8 3ffc fffe ffff 3fff 1fff 7fc 7f0 3e0 1c0 180
t7$d 100 180 3c0 3e0 ff8 1ffe 3fff ffff ffff 7ffc 1ff8 7f0 3e0 1c0 c0
t7$d 100 1c0 1c0 3f0 7f8 ffe 3fff 7fff ffff 7ffc 1ff8 7f0 1e0 e0 40
t7$d 100 3c0 3e0 3fc 7ff fff 1fff 3ffe 7ffc 7ffc 3ff8 3f8 70 30
t7$d 180 1c0 3e0 3f8 7fe fff 3fff 7fff fffe 3ffc ff8 3f0 f0 60 20
t7$d 180 380 7c0 fe0 1ff0 7ff8 1fffe 1ffff 7ffe 3ff8 ff0 7e0 3c0 380 100
t7$d 180 380 7c0 fe0 1ff0 7ff8 1fffe 1ffff fffe 3ff8 1ff0 7e0 7c0 380 100
t7$d 180 380 7c0 fe0 3ff0 7ff8 1fffe 1ffff 7ffe 3ff8 1ff0 7c0 780 380 100
t7$d 180 3c0 3e0 7e0 1ff8 7ffe 1ffff 1ffff 7ffe 3ff8 ff0 7e0 3c0 180 100
t7$d 200 700 780 fc0 ff0 1ffe 7fff 7ffe 7ffc 7ff8 7ff0 1fe0 7c0 1c0
t7$d 300 380 3e0 7f8 7ff fff 1fff 3ffe 7ffc fff8 1ff8 3f0 f0 60 20
t7$d 300 380 7c0 7f0 fff 1fff 3fff 7ffe fffc fff8 3ff0 7f0 1e0 60
t7$d 300 3c0 3e0 7f8 fff 1fff 3fff 7ffe fffc 7ff8 ff0 3f0 e0 60
t7$d 3c0 3e0 3fc 7ff fff 1fff 3ffe 7ffc 7ffc 3ff8 3f8 70 30
t7$d 8000 0 30 f0 3f8 1ffc 7ffc 7ffe 1fff fff fff 7ff 3f8 1e0 1c0 180
t7$h e00 3f80 7fc0 7fe0 7ff0 7ff8 7ffc 3ffe 3fff 7fff fffe fffc fff8 fff0 ffc0 7f80 1e00
t7$h 1800 7f00 ffc0 ffe0 fff0 fffc fffe ffff 7ffe 3ffc 7ffc fff8 fff0 ffe0 7fc0 7f80 1f00
t7$h 1c00 3f80 7fc0 7ff0 7ff8 7ffc 7fff 7fff 3fff 3ffe 7ffc 7ff8 7ff8 7ff0 7fe0
t7$h 1c00 7f00 ffc0 ffe0 fff8 fffc fffe 7fff 3fff 7ffe fffc fff8 fff0 ffe0 7fc0
t7$h 1e00 3f80 7fe0 7ff0 7ff8 7ffc 7ffe 3fff 3fff 7ffe 7ffc 7ff8 7ff0 7fe0 7fc0
t7$h 1e00 3f80 7fe0 7ff0 7ff8 7ffc 7ffe 3fff 3fff 7fff 7ffc 7ff8 7ff8 7fe0 7fc0 3f00
t7$h 1e00 7f80 ffc0 ffe0 fff8 fff8 7ffc 7ffe 3fff 7fff fffe fff8 fff0 ffe0 ffc0 7f00
t7$h 1e00 7f80 ffc0 fff0 fff0 fff8 fffe 7fff 3fff fffe fffc fff8 fff0 ffe0 7fc0 3f00
t7$h 1e00 7f80 ffc0 fff0 fff0 fff8 fffe 7fff 3fff fffe fffc fff8 fff0 ffe0 ffc0 3f00
t7$h 1f00 3fe0 7ff0 7ffc 7ffe 7fff 7fff 3fff 1fff 3ffe 3ffc 3ffc 3ff8
t7$h 1f00 7fc0 7fe0 7ff8 7ffc 7ffe 7fff 3fff 1fff 7ffe 7ffc 7ff8 7ff0 7fe0
t7$h 1f00 7fc0 7fe0 7ff8 7ffc 7ffe 7fff 3fff 1fff 7ffe 7ffc 7ff8 7ff0 7fe0 3fc0
t7$h 1f00 7fc0 7fe0 7ff8 7ffc 7ffe 7fff 3fff 1fff 7ffe 7ffc 7ff8 7ff0 7fe0 3fc0 1f80
t7$h 1f80 3fc0 3fe0 3ff0 3ff8 3ffc 3ffe 1fff 3fff 3fff 3fff 3ffc 3ff8 3ff0 3fc0 3f00
t7$h 1fc0 3fe0 3ff0 3ff8 3ff8 1ffc 1ffe 3ffe 3fff 3fff 3fff 3ffe 3ff8 3fe0 3f80 400
t7$h 1fc0 3fe0 3ff0 3ff8 7ffc 3ffc 3ffe 1fff 7fff 7fff 7ffe 7ffc 7ff8 7ff0 3fc0
t7$h 1fc0 7fe0 7ff0 7ff8 7ffc 3ffe 3fff 3fff 7fff 7ffe 7ffc 7ff8 7ff0 7fe0 3f80
t7$h 1ff8 1ffc 3ffe 1ffe 1fff fff 3fff 3fff 3fff 7ffe 7ffc 3ff0 1fe0 f80
t7$h 3800 7f00 7fe0 7ff0 7ffc 7fff 7fff 7ffe 7ffc 3ffc 7ff8 7ff8 7ff0 7fe0
t7$h 3800 7f80 ffc0 fff0 fffc fffe ffff fffe 7ffe 3ffc 7ffc 7ff8 7ff0 7fe0 7fc0 3f80
t7$h 3c00 7f80 ffc0 ffe0 fff0 fff8 fffc 7fff 3fff fffc fffc fff8 fff0 ffe0 ff80
t7$h 3e00 3fc0 3ff0 3ffc 3fff 3fff 3fff 3ffe 3ffe 1ffc 3ffc 3ff8 3ff0 3ff0 3fe0
t7$h 3e00 3fc0 7ff0 7ff8 7ffe 7fff 7fff 7fff 3ffe 1ffc 3ffc 3ff8 3ff8 3ff0 3fe0 1fc0
t7$h 3e00 7f00 ffc0 ffe0 fff8 fffc fffc 7fff 3ffe fffc fff8 fff8 fff0 ffc0 ff80
t7$h 3e00 7f80 ffc0 ffe0 fff8 fffc fffc 7fff 3ffe fffc fff8 fff8 fff0 ffc0
t7$h 3e00 7f80 ffc0 ffe0 fff8 fffc fffc 7fff 3ffe fffc fff8 fff8 fff0 ffc0 ff80
t7$h 3e00 7f80 ffc0 ffe0 fff8 fffc fffe 7fff 3ffe fffc fff8 fff0 fff0 ffe0 7f80
t7$h 3e00 7f80 ffc0 ffe0 fff8 fffc fffe 7fff 3ffe fffc fff8 fff8 fff0 ffc0 ff80
t7$h 3e00 7f80 ffc0 fff0 fff8 fffc fffe 7fff 3ffe 7ffe fffc fff8 fff0 ffe0
t7$h 3e00 7f80 ffc0 fff0 fff8 fffc fffe 7fff 3ffe 7ffe fffc fff8 fff0 ffe0 7f80
t7$h 3e00 ff80 ffe0 fff0 fff8 fffc ffff 7fff 3ffe 7ffc fff8 fff0 ffe0 ffc0 7f80
t7$h 3f00 7fc0 7fe0 7ff0 7ff8 7ffc 7ffc 7ffe 7fff 7ffe 7ffc 7ff0 7fe0 7fc0 7f00 1c00
t7$h 3f00 7fc0 7ff0 7ff8 7ffe 7fff 7fff 7ffe 1ffe 3ffc 7ff8 7ff8 7ff0 7fe0
t7$h 3f80 3fe0 3ff8 3ffe 3fff 3fff 3fff 3ffe 1ffe 3ffc 3ffc 3ff8 3ff0 3fe0 1fc0
t7$h 3f80 7fc0 7fe0 7ff0 7ff8 7ffc 3ffe 7ffe 7fff 7fff 7ffc 7ff8 7ff0 7fc0 7f00 c00
t7$h 3f80 7fc0 7fe0 7ff0 7ff8 7ffc 7ffe 7fff 7fff 7ffc 7ff8 7ff0 7fe0 7fc0 7f00 c00
t7$h 3f80 7fc0 7fe0 7ff0 7ffc 7ffc 3ffe 3fff 7fff fffe fffc fff8 fff0 7fc0 3f80 1e00
t7$h 3fc0 3fe0 3ff0 7ff8 3ffc 3ffc 1ffe 7fff 7fff 7fff 7ffe 7ff8 7ff0 7fc0 3f00
t7$h 3fc0 7fc0 7ff0 7ff8 7ffc 7ffe 3fff 3fff 7fff fffe fffc fff8 ffe0 7fc0 3f80
t7$h 3fe0 3ff0 7ff8 7ffc 3ffc 1ffe 7fff 7fff 7fff 7ffe 7ffc 7ff0 7fc0 3f80
t7$h 7f80 7fc0 7fe0 7ff0 7ff8 7ffc 3ffc 7ffe 7fff 7ffe 7ff8 7ff0 7fe0 7f80 7f00
t7$h 7f80 7fe0 7ff8 7ffe 7fff 7ffe 7ffe 7ffc 3ffc 3ff8 7ff8 7ff0 3fe0 3fc0 1f80
t7$s 20 1f8 7fc ffc 3ffc 7ffc 7ffb 3fff 1fff 1fff ffb 7fa 3f0 1e0
t7$s 20 1f8 7fc 1ffc 7ffe 7ffc 7ffd 3fff 1fff 1fff ff6 7fa 7f0 3e0
t7$s 30 1fc 3fc ffe 1ffe 7ffc 7fff 3fff 1fff 1ffb ffd 7fc 3f8 1f0
t7$s 40 1f0 7f0 ff8 ffa 1fff 3fff 7fff 7ffb 7ffd 3ffc ffc 7f8 1f8
t7$s 40 1f0 7f0 ff8 ffa 1fff 3fff 7fff fffb 7ffd 3ffc ffc 7f8 1f8
t7$s 60 1f0 3f8 7fc ffd 1ffb 3fff 7fff 7fff 3ffd 1ffe 7fc 3fc
t7$s 70 1f8 3fc 7fc 1ffc 3ffd 7fff 7fff 3fff 1ffb ffd 7fc 3f8 f0
t7$s 70 1f8 7fc ffc 1ffc 7ffd 7fff 3fff 1fff 1ffb ffd 7fc 3f8 f0
t7$s 70 1f8 7fc ffc 1ffd 3fff 7fff 7fff 3fff 1ffd ffc 7fc 3f8 f0
t7$s 70 3f8 7fc 3ffc 7ffc 7ffc 3ffb 3fff 1fff fff ffa 7fa 3f0 e0
t7$s 78 3fc 7fe 1ffe 3ffe 7ffd 3fff 1fff 1fff ffb 7fd 3f8 1f8 20
t7$s c0 3e0 7f0 ff8 1ffa 3ff6 7ffe ffff ffff 7ffb 3ffc ff8 7f8 1f0
t7$s e0 1f8 7f8 ffc 1ffd 3ffb ffff 7fff 3fff 3ffb 1ff9 7f8 3f8 1f0
t7$s e0 3f8 7f8 ff8 1ff9 3fff ffff ffff 7fff 3ffb 1ff8 7f8 3f8 1e0
t7$s e0 3f8 7f8 ff8 1ff9 7fff ffff ffff 7fff 3ffb 1ff8 7f8 3f8 1e0
t7$s e0 3f8 7f8 1ffc 3ffd 7ffb ffff 7fff 3fff 1ffb ff8 7f8 3f0 1e0
t7$s f0 3f8 7f8 ffd 1ffb 3fff 3fff 7fff 7fff 3ffc ffc 7fc 1f8
t7$s f0 3f8 7fc 1ffc 3ffd 7ffb 7fff 3fff 1fff fff ffc 3f8 1f0 20
t7$s f0 3f8 7fc 1ffc 7ffc 7ffd 7fff 3fff 1fff 1fff ffa 7f8 3f0 e0
t7$s f0 3f8 ffc 1ffc 7ffc 7ffb 7fff 3fff 1fff 1fff ffa 7f8 3f0 60
t7$s f0 7f8 ffc 3ffc fffc fffd 7fff 3fff 3ffe 1ff6 ff6 7f0 3e0 c0
t7$s f8 3fc ffe 3ffe 7ffe 3ffc 3fff 1fff 1fff fff 7fa 7f8 3f0
t7$s 1c0 3f0 7f0 ff8 1ffa 3fff 7fff ffff ffff 7ffb 1ffc ff8 7f8 1f0
t7$s 1c0 3f0 7f8 ff8 ffb 1fff 3fff 7fff fffb 3ffd 1ffc ffc 3f8 1f0
t7$s 1e0 3f0 7f8 ffb fff 1fff 3fff 7fff 7ffc 7ffc 1ffc 7fc 1f8 60
t7$s 1f0 3f8 7f8 ff9 1fff 1fff 3fff 7fff 7ffd 3ffc ffc 7fc 1f8 40
t7$s 1f0 3f8 ff8 ff9 1ffb 3fff 7fff ffff 7ffb 3ffd ffc 7f8 1f8
t7$s 1f0 7f8 ff8 1ff8 3ffb 7fff ffff ffff 7ffb 3ff9 ff8 7f8 3f0
t7$s 1f0 7f8 ffc 3ffc fffc fffb 7fff 3fff 3ffe 1ff6 ffa 7f0 3e0 40
t7$s 1f8 3fc 7fc 1ffe 7ffe 7fff 3fff 1fff ffb ffd 7fc 3f8 1f0
t7$s 1f8 ffc 1ffc 7ffc 7ffc 7ffd 3fff 3fff 1ffe ff6 ff6 7f0 3e0
t7$s 3c0 7e0 ff0 ff6 1ffe 3ffe 3fff 7ffb fffd fffc 3ffc ffc 3f8 60
t7$s 3e0 3f0 7f2 ffe 1ff6 1fff 3fff 3ffb 7ffc 7ffc 3ffc ffc 3f8 60
t7$s 3e0 7f0 ff8 1ffa 3ff6 7ffe fffe ffff 7ffb 3ff8 1ff8 7f8 3f0
t7$s 4000 0 1e0 3f0 7fa ffa 1fff 1fff 3fff 7fff 7ffc 7ffc 1ffc 7fc 3f8 60
t7$s 6000 0 c0 3f0 7f0 ffa ffe 1fff 3fff 3fff 7ff9 7ffc 3ffc ffc 7fc f8
t7$s 7800 0 0 1f0 3f0 7f8 ffb 1fff 1fff 3fff 7fff 7ffc 3ffc 1ffc 7fc
t7$s 7800 0 0 3e0 7e0 ff2 ff6 1ffe 3ffe 3fff 7ffb 7ffd 7ffc 3ffc ff8 3f8 40
t7$s 7800 0 0 3e0 7f0 7fa ffe 1fff 1fff 3fff 7ffb 7ffc 7ffc 1ffc 7fc 1f8 40
t7$s 7e00 0 0 f0 1f8 3fc 7fd ffd 1fff 1fff 3fff 7ffc 3ffe ffe 7fe
// END OPENOFC_V550_STABLE_REPLAY_T7

//
// points
//


//
// hash
//


//
// images
//


//
// templates
//


