#include "SteppingAction.hh"
#include "EventAction.hh"
#include "G4Step.hh"
#include "G4Track.hh"
#include "G4VProcess.hh"
#include "G4OpticalPhoton.hh"
#include "G4OpBoundaryProcess.hh"

SteppingAction::SteppingAction(EventAction *eventAction)
    : G4UserSteppingAction(),
      fEventAction(eventAction)
{
}

void SteppingAction::UserSteppingAction(const G4Step *step)
{
    if (!step || !fEventAction)
    {
        return;
    }

    const auto *track = step->GetTrack();
    if (!track || track->GetDefinition() != G4OpticalPhoton::OpticalPhotonDefinition())
    {
        return;
    }

    if (track->GetCurrentStepNumber() == 1)
    {
        fEventAction->CountOpticalProduced();
        const auto *creatorProcess = track->GetCreatorProcess();
        const G4String creatorName = creatorProcess ? creatorProcess->GetProcessName() : "Primary";
        if (creatorName == "Scintillation")
        {
            fEventAction->CountOpticalProducedByScintillation();
        }
        else if (creatorName == "Cerenkov")
        {
            fEventAction->CountOpticalProducedByCerenkov();
        }
        else
        {
            fEventAction->CountOpticalProducedByOther();
        }
    }

    const auto *postStepPoint = step->GetPostStepPoint();
    const auto *process = postStepPoint ? postStepPoint->GetProcessDefinedStep() : nullptr;
    const G4String processName = process ? process->GetProcessName() : "Undefined";
    if (processName == "OpBoundary")
    {
        fEventAction->CountStepOpBoundary();
    }
    else if (processName == "OpRayleigh")
    {
        fEventAction->CountStepOpRayleigh();
    }
    else if (processName == "OpMieHG")
    {
        fEventAction->CountStepDiffraction();
    }
    else if (processName == "OpAbsorption")
    {
        fEventAction->CountStepOpAbsorption();
    }
    else if (processName == "Transportation")
    {
        fEventAction->CountStepTransportation();
    }
    else
    {
        fEventAction->CountStepOtherProcess();
    }

    const auto trackStatus = track->GetTrackStatus();
    const bool isTerminated =
        (trackStatus == fStopAndKill || trackStatus == fKillTrackAndSecondaries);
    if (!isTerminated)
    {
        return;
    }

    const auto *postVolume = postStepPoint ? postStepPoint->GetPhysicalVolume() : nullptr;

    if (processName == "OpAbsorption")
    {
        fEventAction->CountOpticalAbsorbed();
        return;
    }

    if (processName == "OpBoundary")
    {
        const auto *boundaryProcess = dynamic_cast<const G4OpBoundaryProcess *>(process);
        if (boundaryProcess && boundaryProcess->GetStatus() == Detection)
        {
            fEventAction->CountOpticalDetected();
            return;
        }
        if (boundaryProcess && boundaryProcess->GetStatus() == Absorption)
        {
            fEventAction->CountOpticalAbsorbed();
            return;
        }
    }

    if (!postVolume)
    {
        fEventAction->CountOpticalEscaped();
        return;
    }

    fEventAction->CountOpticalTerminatedOther();
}
