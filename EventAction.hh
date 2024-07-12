#include "G4UserEventAction.hh"
#include "globals.hh"
#pragma once;
class EventAction : public G4UserEventAction
{
public:
    EventAction() = default;
    ~EventAction() override = default;

    void  BeginOfEventAction(const G4Event*) override;
    void    EndOfEventAction(const G4Event*) override;
};

    
