#include "G4VSensitiveDetector.hh"
#include "SDHits.hh"
#include <vector>
#pragma once;
class G4Step;
class G4HCofThisEvent;


class SDet : public G4VSensitiveDetector
    {
    public:
        SDet (const G4String& name, const G4String& hitsCollectionName);
        ~SDet() override = default;

        void   Initialize(G4HCofThisEvent* hitCollection) override;
        G4bool ProcessHits(G4Step* step, G4TouchableHistory* history) override;
        void   EndOfEvent(G4HCofThisEvent* hitCollection) override;

    private:
        HitsCollection* fHitsCollection = nullptr;
    };
