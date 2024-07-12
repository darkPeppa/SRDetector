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


    void EventAction::BeginOfEventAction(const G4Event*)
    {
    
    }

    void EventAction::EndOfEventAction(const G4Event* event)
    {
        G4TrajectoryContainer* trajectoryContainer = event->GetTrajectoryContainer();
        std::size_t n_trajectories = 0;
        if (trajectoryContainer) n_trajectories = trajectoryContainer->entries();
        std::cout << n_trajectories << G4endl;
        G4int eventID = event->GetEventID();
        if (eventID < 100 || eventID % 100 == 0) {
            G4cout << ">>> Event: " << eventID << G4endl;
            if (trajectoryContainer) {
                G4cout << "    " << n_trajectories
                    << " trajectories stored in this event." << G4endl;
                G4int n = event->GetHCofThisEvent()->GetNumberOfCollections();
                G4cout << n << G4endl;
            }
            /*G4VHitsCollection* hc = event->GetHCofThisEvent()->GetHC(0);
            if (hc) {
                G4cout << "    "
               << hc->GetName() << " hits stored in this event" << G4endl;
            }*/
            
            //std::cout << hc << G4endl;
            //if (hc) {
                //G4cout << "    "
                  // << hc << " hits stored in this event" << G4endl;
           // }


        }
    }





