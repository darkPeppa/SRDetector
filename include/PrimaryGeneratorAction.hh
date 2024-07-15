#include "G4VUserPrimaryGeneratorAction.hh"
#include "G4ParticleGun.hh"
#include "globals.hh"


#pragma once;

class G4ParticleGun;
class G4Event;
class DetectorConstruction;

class PrimaryGeneratorAction : public G4VUserPrimaryGeneratorAction
{
  public:
    PrimaryGeneratorAction();    
    virtual ~PrimaryGeneratorAction();
    static const PrimaryGeneratorAction* Instance();
    virtual void GeneratePrimaries(G4Event*);         
    const G4ParticleGun* GetParticleGun() const { return fParticleGun; }
  
  private:
    static PrimaryGeneratorAction* fgInstance;
    G4ParticleGun*  fParticleGun;
};

