#include "PhysicsList.hh"

#include "G4DecayPhysics.hh"
#include "G4EmLivermorePhysics.hh"
#include "G4EmPenelopePhysics.hh"
#include "G4EmStandardPhysics.hh"
#include "G4EmStandardPhysics_option3.hh"
#include "G4EmStandardPhysics_option4.hh"
#include "G4GenericMessenger.hh"
#include "G4OpticalPhysics.hh"
#include "G4ProductionCutsTable.hh"
#include "G4RadioactiveDecayPhysics.hh"
#include "G4SystemOfUnits.hh"

PhysicsList::PhysicsList()
{
    SetVerboseLevel(1);
    SetDefaultCutValue(10. * um);
    SetEm("livermore");
    RegisterPhysics(new G4DecayPhysics());
    RegisterPhysics(new G4OpticalPhysics());

    fMessenger = new G4GenericMessenger(this, "/srdet/phys/", "Physics list (PreInit only)");
    fMessenger->DeclareMethod("em", &PhysicsList::SetEm, "livermore | option4 | penelope | standard | option3")
        .SetCandidates("livermore option4 penelope standard option3")
        .SetStates(G4State_PreInit)
        .SetToBeBroadcasted(false);
    fMessenger->DeclareMethod("radioactive", &PhysicsList::SetRadioactive, "Add G4RadioactiveDecayPhysics")
        .SetStates(G4State_PreInit)
        .SetToBeBroadcasted(false);
}

PhysicsList::~PhysicsList() { delete fMessenger; }

void PhysicsList::SetEm(const G4String& name)
{
    if (name == fEmName) return;
    G4VPhysicsConstructor* em = nullptr;
    if (name == "livermore") em = new G4EmLivermorePhysics();
    else if (name == "option4") em = new G4EmStandardPhysics_option4();
    else if (name == "penelope") em = new G4EmPenelopePhysics();
    else if (name == "standard") em = new G4EmStandardPhysics();
    else if (name == "option3") em = new G4EmStandardPhysics_option3();
    else {
        G4Exception("PhysicsList::SetEm", "SRDet050", JustWarning, ("unknown EM option " + name).c_str());
        return;
    }
    if (fEmName.empty()) RegisterPhysics(em);
    else ReplacePhysics(em);
    fEmName = name;
    G4cout << "[srdet] EM physics: " << name << G4endl;
}

void PhysicsList::SetRadioactive(G4bool on)
{
    if (on && !fRadioactive) {
        RegisterPhysics(new G4RadioactiveDecayPhysics());
        fRadioactive = true;
    }
}

void PhysicsList::SetCuts()
{
    // Low edge of production thresholds: 250 eV (lowest value supported by Livermore/Penelope).
    G4ProductionCutsTable::GetProductionCutsTable()->SetEnergyRange(250. * eV, 100. * GeV);
    G4VUserPhysicsList::SetCuts();
}
