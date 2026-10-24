#pragma once
// User actions: initialisation, stacking (photon production bookkeeping),
// stepping (energy deposits, process counts, optical boundary outcomes).

#include "G4UserStackingAction.hh"
#include "G4UserSteppingAction.hh"
#include "G4VUserActionInitialization.hh"
#include "G4VUserTrackInformation.hh"
#include "globals.hh"

class EventAction;
class G4OpBoundaryProcess;
class G4Step;
class G4StepPoint;

class ActionInitialization : public G4VUserActionInitialization
{
  public:
    void BuildForMaster() const override;
    void Build() const override;
};

// Attached to every optical photon on its first step.
class PhotonInfo : public G4VUserTrackInformation
{
  public:
    G4int birthCell = -1;
    G4int exitCell = -1;
    G4int nRefl = 0;
    G4int nCoatRefl = 0;  // reflections on the channel wall / coating
    G4double birthZ = 0.;
};

class StackingAction : public G4UserStackingAction
{
  public:
    explicit StackingAction(EventAction* ev) : fEvent(ev) {}
    G4ClassificationOfNewTrack ClassifyNewTrack(const G4Track* track) override;

  private:
    EventAction* fEvent;
};

class SteppingAction : public G4UserSteppingAction
{
  public:
    explicit SteppingAction(EventAction* ev) : fEvent(ev) {}
    void UserSteppingAction(const G4Step* step) override;

  private:
    void OpticalStep(const G4Step* step, G4int preKind);
    G4OpBoundaryProcess* Boundary();

    EventAction* fEvent;
    G4OpBoundaryProcess* fBoundary = nullptr;
};

// helpers shared with the analysis
G4int CellOf(const G4StepPoint* point, G4int kind);
G4bool IsFluorescenceCreator(const G4String& creatorProcess);
