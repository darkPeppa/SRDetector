#include "G4UserSteppingAction.hh"
#include "globals.hh"
#pragma once;

class G4Step;
class EventAction;

class SteppingAction : public G4UserSteppingAction
{
public:
    explicit SteppingAction(EventAction *eventAction);
    ~SteppingAction() override = default;

    void UserSteppingAction(const G4Step *step) override;

private:
    EventAction *fEventAction = nullptr;
};
