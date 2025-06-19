#include "EventAction.hh"
#include "G4Event.hh"
#include "G4EventManager.hh"
#include "G4TrajectoryContainer.hh"
#include "G4Trajectory.hh"
#include "G4ios.hh"
#include "FTFP_BERT.hh"
#include "G4EmStandardPhysics.hh"
#include "G4StepLimiterPhysics.hh"
#include "SensitiveDetector.hh"
#include "G4AnalysisManager.hh"
#include "G4VHitsCollection.hh"

void EventAction::BeginOfEventAction(const G4Event *)
{
    
        
}

void EventAction::EndOfEventAction(const G4Event *event)
{//auto analysisManager = G4AnalysisManager::Instance();
    std::ofstream outputFile;
    G4TrajectoryContainer *trajectoryContainer = event->GetTrajectoryContainer();
    std::size_t n_trajectories = 0;
    if (trajectoryContainer)
        n_trajectories = trajectoryContainer->entries();
    std::cout << n_trajectories << G4endl;
    G4int eventID = event->GetEventID();
    outputFile.open("hits_immediate.csv", std::ios::app);
    outputFile<<eventID<<G4endl;
    //analysisManager->FillNtupleIColumn(0,eventID);
    //analysisManager->AddNtupleRow();
    if (eventID < 100 || eventID % 100 == 0)
    {
        G4cout << ">>> Event: " << eventID << G4endl;
        if (trajectoryContainer)
        {
            G4cout << "    " << n_trajectories
                   << " trajectories stored in this event." << G4endl;
            G4int n = event->GetHCofThisEvent()->GetNumberOfCollections();
            G4cout << n << G4endl;
        }

    }
}
