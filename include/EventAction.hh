#include "G4UserEventAction.hh"
#include "globals.hh"
#pragma once
class EventAction : public G4UserEventAction
{
public:
    EventAction() = default;
    ~EventAction() override = default;

    void BeginOfEventAction(const G4Event *) override;
    void EndOfEventAction(const G4Event *) override;

    void CountOpticalProduced();
    void CountOpticalProducedByScintillation();
    void CountOpticalProducedByCerenkov();
    void CountOpticalProducedByOther();

    void CountStepOpBoundary();
    void CountStepOpRayleigh();
    void CountStepDiffraction();
    void CountStepOpAbsorption();
    void CountStepTransportation();
    void CountStepOtherProcess();

    void CountOpticalDetected();
    void CountOpticalAbsorbed();
    void CountOpticalEscaped();
    void CountOpticalTerminatedOther();

private:
    G4int fOptProduced = 0;
    G4int fOptProducedByScintillation = 0;
    G4int fOptProducedByCerenkov = 0;
    G4int fOptProducedByOther = 0;
    G4int fStepOpBoundary = 0;
    G4int fStepOpRayleigh = 0;
    G4int fStepDiffraction = 0;
    G4int fStepOpAbsorption = 0;
    G4int fStepTransportation = 0;
    G4int fStepOtherProcess = 0;
    G4int fOptDetected = 0;
    G4int fOptAbsorbed = 0;
    G4int fOptEscaped = 0;
    G4int fOptTerminatedOther = 0;
};
