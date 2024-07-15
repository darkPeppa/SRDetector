#include "SDHits.hh"
#include "G4UnitsTable.hh"
#include "G4VVisManager.hh"
#include "G4Circle.hh"
#include "G4Colour.hh"
#include "G4VisAttributes.hh"
#include <iomanip>



G4ThreadLocal G4Allocator<SDHits>* hitsAllocator = nullptr;

G4bool SDHits::operator==(const SDHits& right) const
{
    return (this == &right) ? true : false;
}

void SDHits::Draw()
{
    G4VVisManager* pVVisManager = G4VVisManager::GetConcreteInstance();
    if (pVVisManager)
    {
        G4Circle circle(fPos);
        circle.SetScreenSize(4.);
        circle.SetFillStyle(G4Circle::filled);
        G4VisAttributes attribs(G4Colour::Red());
        circle.SetVisAttributes(attribs);
        pVVisManager->Draw(circle);
    }
}

void SDHits::Print()
{
    G4cout
        << "  trackID: " << fTrackID << " chamberNb: " << fElementNb
        << "Edep: "
        << std::setw(7) << G4BestUnit(fEdep, "Energy")
        << " Position: "
        << std::setw(7) << G4BestUnit(fPos, "Length")
        << G4endl;
}


