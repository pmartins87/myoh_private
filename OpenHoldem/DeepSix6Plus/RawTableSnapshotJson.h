#pragma once

#include <string>

#include "RawTableSnapshot.h"

namespace deepsix6plus {

// Deterministic audit JSON for raw scraper evidence. Raw money is encoded as
// strings using max_digits10 so no hidden decimal/locale rounding enters the
// transport layer. This is NOT the integer strategic money representation.
std::string RawTableSnapshotAuditJson(const RawTableSnapshot& snapshot);

}  // namespace deepsix6plus
