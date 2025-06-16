#include "G4HCofThisEvent.hh"
#include "G4Step.hh"
#include "G4ThreeVector.hh"
#include "G4SDManager.hh"
#include "G4ios.hh"
#include "G4VProcess.hh" 
#include "SensitiveDetector.hh"
#include "G4AnalysisManager.hh"

SDet::SDet(const G4String &name,
           const G4String &hitsCollectionName) : G4VSensitiveDetector(name)
{
    collectionName.insert(hitsCollectionName);
}

void SDet::Initialize(G4HCofThisEvent *hce)
{
    fHitsCollection = new HitsCollection(SensitiveDetectorName, collectionName[0]);

    G4int hcID = G4SDManager::GetSDMpointer()->GetCollectionID(collectionName[0]);
    hce->AddHitsCollection(hcID, fHitsCollection);
}

G4bool SDet::ProcessHits(G4Step *aStep, G4TouchableHistory *)
{
    G4double edep = aStep->GetTotalEnergyDeposit();
    if (edep == 0.)
        return false;
    auto newHit = new SDHits();
    newHit->SetTrackID(aStep->GetTrack()->GetTrackID());
    newHit->SetElementNb(aStep->GetPreStepPoint()->GetTouchableHandle()->GetCopyNumber());
    newHit->SetEdep(edep);
    newHit->SetPos(aStep->GetPostStepPoint()->GetPosition());
    fHitsCollection->insert(newHit);
    auto analysisManager = G4AnalysisManager::Instance();
        //analysisManager->FillNtupleIColumn(0,aStep->GetTrack()->GetTrackID());
        analysisManager->FillNtupleIColumn(1,aStep->GetTrack()->GetTrackID());
        analysisManager->FillNtupleSColumn(2,aStep->GetTrack()->GetParticleDefinition()->GetParticleName());
        analysisManager->FillNtupleDColumn(3,edep);
        analysisManager->FillNtupleDColumn(4,aStep->GetPostStepPoint()->GetPosition().getX());
        analysisManager->FillNtupleDColumn(5,aStep->GetPostStepPoint()->GetPosition().getY());
        analysisManager->FillNtupleDColumn(6,aStep->GetPostStepPoint()->GetPosition().getZ());
        analysisManager->FillNtupleSColumn(7,aStep->GetPostStepPoint()->GetProcessDefinedStep()->GetProcessName());
        
        analysisManager->AddNtupleRow();
        analysisManager->Write();
    return true;
}

void SDet::EndOfEvent(G4HCofThisEvent *)
{
    
    if (verboseLevel > 1)
    {
        std::size_t nofHits = fHitsCollection->entries();
        G4cout << G4endl
               << "-------->Hits Collection: in this event they are " << nofHits
               << " hits: " << G4endl;
        for (std::size_t i = 0; i < nofHits; i++)
            (*fHitsCollection)[i]->Print();
    }
}
