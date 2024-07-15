#include "RunAction.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"

	
RunAction::RunAction()
	{
		G4RunManager::GetRunManager()->SetPrintProgress(1000);
	}
void RunAction::BeginOfRunAction(const G4Run*)
	{
		G4RunManager::GetRunManager()->SetRandomNumberStore(false);
	}
void RunAction::EndOfRunAction(const G4Run*)
	{}




