#pragma once
// Photodetector catalogue. A sensor = optional entrance window + thin Si active layer.
// The active layer carries a skin surface (dielectric_metal, R = 0) whose EFFICIENCY
// is QE(lambda) * fill factor, so every photon reaching it is either Detected or Absorbed.
//
// QE curves are representative shapes digitised from typical public data sheets of each
// technology (not of one vendor part) - see docs/physics.md, "Photodetectors". Cost is a
// relative figure per unit sensitive area (aSi flat panel = 1), used only for the
// price/performance figure of merit computed in the Python analysis.

#include "globals.hh"

#include <string>
#include <utility>
#include <vector>

struct SensorSpec
{
    G4String name;
    G4String description;
    std::vector<std::pair<G4double, G4double>> qe;  // (wavelength nm, QE)
    G4double fillFactor;
    G4double pixelPitch;      // Geant4 length units
    G4double readNoise;       // electrons rms per pixel and frame
    G4double darkRate;        // e-/pixel/s (typical, room temperature)
    G4double relativeCost;    // per cm2, aSi flat panel = 1
    G4String windowMaterial;  // empty -> no window
    G4double windowThickness;
};

namespace Sensors
{
const SensorSpec& Get(const G4String& name);
std::vector<G4String> Names();
// Efficiency (QE * fill factor) on Materials::EnergyGrid()
std::vector<G4double> Efficiency(const SensorSpec& s);
}  // namespace Sensors
