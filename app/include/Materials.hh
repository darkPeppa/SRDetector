#pragma once
// Material catalogue: scintillators, glasses, couplings, optical air.
// Each entry carries its optical properties (RINDEX, ABSLENGTH, scintillation)
// with the data source noted in Materials.cc. Unknown names fall back to the
// Geant4 NIST database (G4_*). Overrides from /srdet/mat/... are applied after build.

#include "globals.hh"

#include <string>
#include <vector>

class G4Material;

namespace Materials
{
// Build (once) and return a material by catalogue or NIST name. Fatal if unknown.
G4Material* Get(const G4String& name);

// True if the material has a scintillation yield.
G4bool IsScintillator(const G4Material* mat);

// Apply SRDetConfig::materialOverrides and yieldScale to already built materials.
void ApplyOverrides();

// Common optical photon energy grid (1.55 - 4.43 eV, i.e. 800 - 280 nm).
const std::vector<G4double>& EnergyGrid();

// Names available in the custom catalogue (for documentation / validation).
std::vector<G4String> CatalogueNames();

// Dump composition and optical tables of the given materials as JSON.
void ExportJson(const G4String& path, const std::vector<G4Material*>& mats);

// Photon energy <-> wavelength
inline G4double hc_eVnm() { return 1239.84193; }
}  // namespace Materials
