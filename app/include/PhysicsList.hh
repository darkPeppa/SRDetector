#pragma once
// Modular physics list for keV-MeV photons / electrons in a scintillating honeycomb:
//   EM:      G4EmLivermorePhysics (default) | option4 | penelope | standard | option3
//   decay:   G4DecayPhysics (+ G4RadioactiveDecayPhysics on request, for ion sources)
//   optical: G4OpticalPhysics (process switches via /process/optical/... in macros)
// Hadronic physics is left out on purpose: photo-nuclear cross sections are < 1e-3 of
// the total below ~10 MeV (see docs/physics.md).
//
// Commands (PreInit): /srdet/phys/em <name>, /srdet/phys/radioactive <bool>

#include "G4VModularPhysicsList.hh"

class G4GenericMessenger;

class PhysicsList : public G4VModularPhysicsList
{
  public:
    PhysicsList();
    ~PhysicsList() override;

    void SetEm(const G4String& name);
    void SetRadioactive(G4bool on);
    void SetCuts() override;

  private:
    G4String fEmName;
    G4bool fRadioactive = false;
    G4GenericMessenger* fMessenger = nullptr;
};
