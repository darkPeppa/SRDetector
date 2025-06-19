#include "RunAction.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4AnalysisManager.hh"
std::ofstream outputFile;
RunAction::RunAction()
{
	G4RunManager::GetRunManager()->SetPrintProgress(1000);
	auto analysisManager = G4AnalysisManager::Instance();
    outputFile.open("hits_immediate.csv", std::ios::app);
    
    analysisManager->SetFileName("optical_hits.csv");
   analysisManager->SetNtupleMerging(true);
    
   
    analysisManager->CreateNtuple("Hits", "hits data");
	
    analysisManager->CreateNtupleIColumn("EventID"); 
	analysisManager->CreateNtupleIColumn("TrackID");   
	analysisManager->CreateNtupleDColumn("Partical");
	analysisManager->CreateNtupleDColumn("Energy");
    analysisManager->CreateNtupleDColumn("PosX_mm");  
    analysisManager->CreateNtupleDColumn("PosY_mm");   
    analysisManager->CreateNtupleDColumn("PosZ_mm");
    analysisManager->CreateNtupleSColumn("Process"); 
    analysisManager->FinishNtuple();

	outputFile << "{"
           << "\"event\":" <<"," << "\"track\":" <<"," << "\"particle\":" <<"," << "\"energy\":" <<","
           << "\"x\":"  << ","
           << "\"y\":"  << ","
           << "\"z\":" << "\"process\":" <<","
           << "}\n";
}
void RunAction::BeginOfRunAction(const G4Run *)
{
	G4RunManager::GetRunManager()->SetRandomNumberStore(false);
	 auto analysisManager = G4AnalysisManager::Instance();
    analysisManager->OpenFile("optical_hits.csv");
	if(!analysisManager->OpenFile()) {
        G4Exception("RunAction", "FileOpenError", FatalException,
                  "Cannot open output file!");
    }
}
void RunAction::EndOfRunAction(const G4Run *)
{auto analysisManager = G4AnalysisManager::Instance();
    analysisManager->Write();
    analysisManager->CloseFile();
}
