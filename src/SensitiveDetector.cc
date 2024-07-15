#include "G4HCofThisEvent.hh"
#include "G4Step.hh"
#include "G4ThreeVector.hh"
#include "G4SDManager.hh"
#include "G4ios.hh"

#include "SensitiveDetector.hh"

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
