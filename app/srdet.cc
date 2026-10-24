// srdet-sim: Geant4 simulation of a cylindrical honeycomb micro-channel scintillation detector.
//
//   srdet-sim [macro] [-t threads] [-i]
//     macro   batch macro (geometry, physics, beam and /run/beamOn; see macros/)
//     -t N    worker threads (0 = sequential run manager)
//     -i      open an interactive terminal session after the macro
//   Without a macro an interactive session starts (macros/vis/interactive.mac is a good start).
//
// Nothing is initialised here: /run/initialize is part of the macro, so geometry and physics
// can be configured with /srdet/... commands first.

#include "Actions.hh"
#include "DetectorConstruction.hh"
#include "PhysicsList.hh"

#include "G4RunManagerFactory.hh"
#include "G4SteppingVerbose.hh"
#include "G4UIExecutive.hh"
#include "G4UImanager.hh"
#include "G4VisExecutive.hh"

#include <cstdlib>
#include <string>

int main(int argc, char** argv)
{
    G4String macro;
    G4int threads = -1;
    G4bool interactive = false;
    for (G4int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "-t" && i + 1 < argc) threads = std::atoi(argv[++i]);
        else if (a == "-i") interactive = true;
        else if (a == "-h" || a == "--help") {
            G4cout << "usage: srdet-sim [macro] [-t threads] [-i]" << G4endl;
            return 0;
        } else macro = a;
    }

    G4UIExecutive* ui = nullptr;
    if (macro.empty() || interactive) ui = new G4UIExecutive(argc, argv, "tcsh");

    G4SteppingVerbose::UseBestUnit(4);
    auto* runManager = G4RunManagerFactory::CreateRunManager(threads == 0 ? G4RunManagerType::SerialOnly
                                                                          : G4RunManagerType::Default);
    if (threads > 0) runManager->SetNumberOfThreads(threads);

    runManager->SetUserInitialization(new DetectorConstruction());
    runManager->SetUserInitialization(new PhysicsList());
    runManager->SetUserInitialization(new ActionInitialization());

    auto* vis = new G4VisExecutive("quiet");
    vis->Initialize();

    auto* uim = G4UImanager::GetUIpointer();
    G4int rc = 0;
    if (!macro.empty()) rc = uim->ApplyCommand("/control/execute " + macro);
    if (ui) {
        ui->SessionStart();
        delete ui;
    }

    delete vis;
    delete runManager;
    return rc == 0 ? 0 : 1;
}
