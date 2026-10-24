#pragma once
// Two source modes (/srdet/gun/mode):
//   gps     - G4GeneralParticleSource, every beam (pencil, parallel, gaussian, divergent,
//             isotropic, spectra, radioactive ions) is defined with /gps/... in macros/beams/
//   optical - N optical photons inside the core of the central cell: isotropic or at a fixed
//             polar angle to the channel axis, random linear polarisation perpendicular to the
//             momentum, energy fixed or sampled from the core emission spectrum. Isolates the
//             light transport from the EM shower (unit studies U1-U6).
//             With /srdet/gun/opt/absolute true the photon starts at /srdet/gun/opt/pos with
//             direction /srdet/gun/opt/dir (validation tests in slab mode).

#include "G4ThreeVector.hh"
#include "G4VUserPrimaryGeneratorAction.hh"
#include "globals.hh"

#include <vector>

class G4GeneralParticleSource;
class G4GenericMessenger;
class G4Event;

class PrimaryGeneratorAction : public G4VUserPrimaryGeneratorAction
{
  public:
    PrimaryGeneratorAction();
    ~PrimaryGeneratorAction() override;
    void GeneratePrimaries(G4Event* event) override;

  private:
    void GenerateOptical(G4Event* event);
    G4double SampleEmission();

    G4GeneralParticleSource* fGPS = nullptr;
    G4GenericMessenger* fMessenger = nullptr;
    G4GenericMessenger* fOptMessenger = nullptr;

    G4String fMode = "gps";
    G4int fNPhotons = 1;
    G4double fEnergy = 0.;          // 0 -> sample core emission spectrum
    G4double fZ = 0.;               // position along the channel (detector frame)
    G4bool fZUniform = true;
    G4bool fRUniform = true;        // uniform in the core cross-section (else on axis)
    G4double fTheta = -1.;          // < 0 -> isotropic, else fixed polar angle to +z
    G4bool fAbsolute = false;
    G4ThreeVector fPos;
    G4ThreeVector fDir = G4ThreeVector(0, 0, 1);

    std::vector<G4double> fCdfE, fCdf;
};
