//******************************************************************************
// OpenOFC PLAYABLE P3 Normal/Normal policy bridge (shadow-only).
//******************************************************************************

#ifndef INC_COFCP3POLICY_H
#define INC_COFCP3POLICY_H

#include <string>
#include <vector>

#include "COFCTurnPlan.h"

struct COFCP3PublicPlacement {
  int card_value;
  EOFCRow row;

  COFCP3PublicPlacement()
      : card_value(kOFCCardNoCard), row(kOFCRowUndefined) {}
  COFCP3PublicPlacement(int value, EOFCRow target)
      : card_value(value), row(target) {}
};

struct COFCP3PublicActionEvent {
  int round_index;
  int player_role;
  std::vector<COFCP3PublicPlacement> placements;

  COFCP3PublicActionEvent() : round_index(-1), player_role(-1) {}
};

// Reconstructs the exact ordered public placement history from monotone
// committed-board deltas.  It never guesses a missing event or a moved card.
class COFCP3PublicHistory {
 public:
  COFCP3PublicHistory();

  bool ResetForKnownNewHand(const COFCState &state, std::string *error);
  bool Observe(const COFCState &state, std::string *error);
  bool ValidateForDecision(const COFCState &state, std::string *error) const;
  void Invalidate();

  bool valid() const { return valid_; }
  int button_identity() const { return button_identity_; }
  int RoleForChair(int chair) const;
  int ChairForRole(int role) const;
  const std::vector<COFCP3PublicActionEvent> &events() const {
    return events_;
  }

 private:
  bool ValidateStableHand(const COFCState &state, std::string *error) const;

 private:
  bool valid_;
  int hero_chair_;
  int button_identity_;
  int role_chairs_[2];
  COFCPlayerBoard observed_boards_[2];
  std::vector<COFCP3PublicActionEvent> events_;
};

struct COFCP3PolicyReceipt {
  bool valid;
  bool physical_execution_authorized;
  int button_identity;
  int actor_role;
  std::string authority;
  std::string native_manifest_sha256;
  std::string p2_manifest_sha256;
  std::string p2_source_commit;
  std::string route_sha256;
  std::string model_sha256;
  std::string canonical_information_key;
  std::string canonical_information_key_sha256;
  std::string canonical_action_key;
  double selected_probability;

  COFCP3PolicyReceipt() { Reset(); }
  void Reset();
};

class COFCP3Policy {
 public:
  COFCP3Policy();

  // The directory must contain the exact manifest and B0/B1 binary files
  // exported by DeepOFC.  Every file/header identity is checked before use.
  bool LoadDirectory(const std::string &directory, std::string *error);
  bool LoadFiles(
      const std::string &manifest_path,
      const std::string &b0_path,
      const std::string &b1_path,
      std::string *error);
  bool loaded() const { return loaded_; }

  bool Choose(
      const COFCState &state,
      const COFCP3PublicHistory &history,
      COFCStrategyAction *action,
      COFCP3PolicyReceipt *receipt,
      std::string *error) const;

  static const char *Authority();
  static const char *NativeManifestSha256();
  static const char *P2ManifestSha256();
  static const char *P2SourceCommit();

 public:
  // Public only so the translation-unit loader can fill an independently
  // validated temporary route before atomically replacing live policy state.
  struct RouteWeights {
    int button;
    std::vector<double> values;
    std::string route_sha256;
    std::string snapshot_sha256;
    std::string model_sha256;
    std::string file_sha256;

    RouteWeights() : button(-1) {}
  };

 private:
  bool loaded_;
  RouteWeights routes_[2];
};

#endif  // INC_COFCP3POLICY_H
