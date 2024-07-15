#include "G4VHit.hh"
#include "G4THitsCollection.hh"
#include "G4Allocator.hh"
#include "G4ThreeVector.hh"
#include "tls.hh"

#pragma once;
class SDHits : public G4VHit
    {
    public:
        SDHits() = default;
        SDHits(const SDHits&) = default;
        ~SDHits() override = default;

       SDHits& operator=(const SDHits&) = default;
        G4bool operator==(const SDHits&) const;

        inline void* operator new(size_t);
        inline void  operator delete(void*);
        
        void Draw() override;
        void Print() override;

        void SetTrackID(G4int track) { fTrackID = track; };
        void SetElementNb(G4int el) { fElementNb = el; };
        void SetEdep(G4double de) { fEdep = de; };
        void SetPos(G4ThreeVector xyz) { fPos = xyz; };

        G4int GetTrackID() const { return fTrackID; };
        G4int GetElementNb() const { return fElementNb; };
        G4double GetEdep() const { return fEdep; };
        G4ThreeVector GetPos() const { return fPos; };

    private:
        G4int         fTrackID = -1;
        G4int         fElementNb = -1;
        G4double      fEdep = 0.;
        G4ThreeVector fPos;
    };

    using HitsCollection = G4THitsCollection<SDHits>;

    extern G4ThreadLocal G4Allocator<SDHits>* hitsAllocator;

    inline void* SDHits::operator new(size_t)
    {
        if (!hitsAllocator)
            hitsAllocator = new G4Allocator<SDHits>;
        return (void*)hitsAllocator->MallocSingle();
    }

    inline void SDHits::operator delete(void* hit)
    {
        hitsAllocator->FreeSingle((SDHits*)hit);
    }


