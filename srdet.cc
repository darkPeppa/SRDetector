#include <G4EmStandardPhysics.hh>
#include "DetectorConstruction.hh"
#include "ActionInitialization.hh"
#include "G4RunManagerFactory.hh"
#include "G4SteppingVerbose.hh"
#include "G4UImanager.hh"
#include "FTFP_BERT.hh"
#include "Randomize.hh"
#include "G4VisExecutive.hh"
#include "G4UIExecutive.hh"
#include "G4StepLimiterPhysics.hh"
#include "G4OpticalPhysics.hh"
#include "G4OpticalParameters.hh"
#include "G4AnalysisManager.hh"



int main(int argc, char** argv)
{
    G4int precision = 4;
    G4SteppingVerbose::UseBestUnit(precision);
    G4RunManager* runManager = new G4RunManager;
    runManager->SetUserInitialization(new DetectorConstruction());
    auto physicsList = new FTFP_BERT;
    physicsList->RegisterPhysics(new G4StepLimiterPhysics());
    G4OpticalPhysics* opticalPhysics = new G4OpticalPhysics();
    
    auto opticalParams = G4OpticalParameters::Instance();
    opticalParams->SetBoundaryVerboseLevel(3);
    opticalParams->SetProcessActivation("Cerenkov", true);
    opticalParams->SetProcessActivation("Scintillation", true);
    opticalParams->SetProcessActivation("OpAbsorption", true);
    opticalParams->SetProcessActivation("OpRayleigh", true);
    opticalParams->SetProcessActivation("OpMieHG", true); // diffraction-like optical scattering
    opticalParams->SetProcessActivation("OpBoundary", true);
    opticalParams->SetCerenkovTrackSecondariesFirst(true);
    opticalParams->SetScintTrackSecondariesFirst(true);
    opticalParams->SetScintFiniteRiseTime(false);

    opticalPhysics->SetVerboseLevel(1);
    G4AnalysisManager::Instance()->SetVerboseLevel(1);
    
  physicsList-> RegisterPhysics(opticalPhysics);
    runManager->SetUserInitialization(physicsList);
    
    
    runManager->SetUserInitialization(new ActionInitialization());
    runManager->Initialize();
    G4VisManager* visManager = new G4VisExecutive;
    visManager->Initialize();
    G4UImanager* UImanager = G4UImanager::GetUIpointer();

    if (argc != 1) 
    {
        G4String command = "/control/execute ";
        G4String fileName = argv[1];
        UImanager->ApplyCommand(command + fileName);
    }
    else 
    {
        G4UIExecutive* ui = new G4UIExecutive(argc, argv);
        UImanager->ApplyCommand("/control/execute init_vis.mac");
        UImanager->ApplyCommand("/control/execute init.mac");
        ui->SessionStart();
        delete ui;
    }

    delete visManager;
    delete runManager;

    return 0;
}

