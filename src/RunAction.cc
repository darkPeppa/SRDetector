#include "RunAction.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include <fstream>

RunAction::RunAction()
{
	G4RunManager::GetRunManager()->SetPrintProgress(1000);
}

void RunAction::BeginOfRunAction(const G4Run *)
{
	G4RunManager::GetRunManager()->SetRandomNumberStore(false);

    if (IsMaster())
    {
        std::ofstream hitsFile("hits_immediate.csv", std::ios::trunc);
        hitsFile << "EventID,TrackID,ChannelCopyNo,Particle,Edep,PosX_mm,PosY_mm,PosZ_mm,Process\n";

        std::ofstream opticalFile("optical_photons.csv", std::ios::trunc);
        opticalFile << "EventID,Produced,ProducedByScintillation,ProducedByCerenkov,ProducedByOther,"
                    << "Step_OpBoundary,Step_OpRayleigh,Step_Diffraction,Step_OpAbsorption,Step_Transportation,Step_Other,"
                    << "Detected,Absorbed,Escaped,TerminatedOther\n";
    }
}

void RunAction::EndOfRunAction(const G4Run *)
{
}
