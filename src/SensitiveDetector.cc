#include "G4HCofThisEvent.hh"
#include "G4Step.hh"
#include "G4ThreeVector.hh"
#include "G4SDManager.hh"
#include "G4ios.hh"
#include "G4VProcess.hh" 
#include "G4RunManager.hh"
#include "G4Event.hh"
#include "SensitiveDetector.hh"
#include <fstream>

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

G4bool SDet::ProcessHits(G4Step *aStep, G4TouchableHistory * history)
{
    if (!aStep || !fHitsCollection)
    {
        return false;
    }

    const auto *preStepPoint = aStep->GetPreStepPoint();
    if (!preStepPoint)
    {
        return false;
    }

    const auto &touchable = preStepPoint->GetTouchableHandle();
    const auto *volume = touchable->GetVolume();
    if (!volume || volume->GetName() != "MicroCore")
    {
        return false;
    }

    G4double edep = aStep->GetTotalEnergyDeposit();
    if (edep <= 0.)
    {
        return false;
    }
    
    auto newHit = new SDHits();
    newHit->SetTrackID(aStep->GetTrack()->GetTrackID());
    newHit->SetElementNb(touchable->GetCopyNumber());
    newHit->SetEdep(edep);
    newHit->SetPos(aStep->GetPostStepPoint()->GetPosition());
    fHitsCollection->insert(newHit);

    const auto *postStepPoint = aStep->GetPostStepPoint();
    const auto *process = postStepPoint ? postStepPoint->GetProcessDefinedStep() : nullptr;
    const G4String processName = process ? process->GetProcessName() : "UndefinedProcess";

    G4int eventID = -1;
    const auto *currentEvent = G4RunManager::GetRunManager()->GetCurrentEvent();
    if (currentEvent)
    {
        eventID = currentEvent->GetEventID();
    }

    std::ofstream outputFile("hits_immediate.csv", std::ios::app);
    outputFile << eventID << ","
               << aStep->GetTrack()->GetTrackID() << ","
               << touchable->GetCopyNumber() << ","
               << aStep->GetTrack()->GetParticleDefinition()->GetParticleName() << ","
               << edep << ","
               << postStepPoint->GetPosition().getX() << ","
               << postStepPoint->GetPosition().getY() << ","
               << postStepPoint->GetPosition().getZ() << ","
               << processName << "\n";
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
