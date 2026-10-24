#include "EventAction.hh"

#include "RunAction.hh"

#include "G4Event.hh"
#include "G4PrimaryParticle.hh"
#include "G4PrimaryVertex.hh"

void EventAction::BeginOfEventAction(const G4Event* event)
{
    fData = EventData();
    if (const auto* v = event->GetPrimaryVertex(0)) {
        fData.x0 = v->GetX0();
        fData.y0 = v->GetY0();
        if (const auto* p = v->GetPrimary(0)) {
            fData.e0 = p->GetKineticEnergy();
            fData.pdg = p->GetPDGcode();
        }
    }
}

void EventAction::EndOfEventAction(const G4Event* event) { fRun->FillEvent(event->GetEventID(), fData); }
