#include "EventAction.hh"
#include "G4Event.hh"
#include "G4AutoLock.hh"
#include "G4ios.hh"
#include <fstream>

namespace
{
G4Mutex opticalCsvMutex = G4MUTEX_INITIALIZER;
}

void EventAction::CountOpticalProduced()
{
    ++fOptProduced;
}

void EventAction::CountOpticalProducedByScintillation()
{
    ++fOptProducedByScintillation;
}

void EventAction::CountOpticalProducedByCerenkov()
{
    ++fOptProducedByCerenkov;
}

void EventAction::CountOpticalProducedByOther()
{
    ++fOptProducedByOther;
}

void EventAction::CountStepOpBoundary()
{
    ++fStepOpBoundary;
}

void EventAction::CountStepOpRayleigh()
{
    ++fStepOpRayleigh;
}

void EventAction::CountStepDiffraction()
{
    ++fStepDiffraction;
}

void EventAction::CountStepOpAbsorption()
{
    ++fStepOpAbsorption;
}

void EventAction::CountStepTransportation()
{
    ++fStepTransportation;
}

void EventAction::CountStepOtherProcess()
{
    ++fStepOtherProcess;
}

void EventAction::CountOpticalDetected()
{
    ++fOptDetected;
}

void EventAction::CountOpticalAbsorbed()
{
    ++fOptAbsorbed;
}

void EventAction::CountOpticalEscaped()
{
    ++fOptEscaped;
}

void EventAction::CountOpticalTerminatedOther()
{
    ++fOptTerminatedOther;
}

void EventAction::BeginOfEventAction(const G4Event *)
{
    fOptProduced = 0;
    fOptProducedByScintillation = 0;
    fOptProducedByCerenkov = 0;
    fOptProducedByOther = 0;
    fStepOpBoundary = 0;
    fStepOpRayleigh = 0;
    fStepDiffraction = 0;
    fStepOpAbsorption = 0;
    fStepTransportation = 0;
    fStepOtherProcess = 0;
    fOptDetected = 0;
    fOptAbsorbed = 0;
    fOptEscaped = 0;
    fOptTerminatedOther = 0;
}

void EventAction::EndOfEventAction(const G4Event *event)
{
    G4AutoLock lock(&opticalCsvMutex);
    std::ofstream outputFile("optical_photons.csv", std::ios::app);
    outputFile << event->GetEventID() << ","
               << fOptProduced << ","
               << fOptProducedByScintillation << ","
               << fOptProducedByCerenkov << ","
               << fOptProducedByOther << ","
               << fStepOpBoundary << ","
               << fStepOpRayleigh << ","
               << fStepDiffraction << ","
               << fStepOpAbsorption << ","
               << fStepTransportation << ","
               << fStepOtherProcess << ","
               << fOptDetected << ","
               << fOptAbsorbed << ","
               << fOptEscaped << ","
               << fOptTerminatedOther << "\n";
}
