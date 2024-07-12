#include "G4VUserDetectorConstruction.hh"
#include "globals.hh"
#include "SensitiveDetector.hh"

#pragma once;


class G4VPhysicalVolume;

class DetectorConstruction : public G4VUserDetectorConstruction
{
  public:
    DetectorConstruction();
    virtual ~DetectorConstruction();
    virtual G4VPhysicalVolume* Construct();
    virtual void ConstructSD();
    void SetMaxStep(G4double);
    G4UserLimits* fStepLimit = nullptr;
};
