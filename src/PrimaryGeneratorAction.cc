#include <G4INCLRandom.hh>
#include "G4LogicalVolumeStore.hh"
#include "G4LogicalVolume.hh"
#include "G4Box.hh"
#include "G4RunManager.hh"
#include "G4ParticleGun.hh"
#include "G4ParticleTable.hh"
#include "G4ParticleDefinition.hh"
#include "G4SystemOfUnits.hh"
#include "Randomize.hh"
#include "PrimaryGeneratorAction.hh"
#include "G4SystemOfUnits.hh"

PrimaryGeneratorAction* PrimaryGeneratorAction::fgInstance = 0;

const PrimaryGeneratorAction* PrimaryGeneratorAction::Instance()
{
  return fgInstance;
}      

PrimaryGeneratorAction::PrimaryGeneratorAction()
 : G4VUserPrimaryGeneratorAction(),
  fParticleGun(0)
{
 G4int n_particle = 1;
  fParticleGun  = new G4ParticleGun(n_particle);

  G4ParticleTable* particleTable = G4ParticleTable::GetParticleTable();
  G4String particleName;
  G4ParticleDefinition* particle
      = particleTable->FindParticle("gamma");
  fParticleGun->SetParticleDefinition(particle);
  fParticleGun->SetParticleMomentumDirection(G4ThreeVector(0.,0.,1.));
  fParticleGun->SetParticleEnergy(0.05*MeV);
  fgInstance = this;
}

PrimaryGeneratorAction::~PrimaryGeneratorAction()
{
  delete fParticleGun;
  fgInstance = 0;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* anEvent)
{
  G4double envSizeXY = 0;
  G4double envSizeZ = 0;
  G4LogicalVolume* envLV = G4LogicalVolumeStore::GetInstance()->GetVolume("Envelope");
  G4Box* envBox = NULL;
  if (envLV) envBox = dynamic_cast<G4Box*>(envLV->GetSolid());
  if ( envBox ) {
    envSizeXY = envBox->GetXHalfLength()*2.;
    envSizeZ = envBox->GetZHalfLength()*2.;
  }  
  else  {
    G4cerr << "Envelope volume of box shape not found." << G4endl;
    G4cerr << "Perhaps you have changed geometry." << G4endl;
    G4cerr << "The gun will be place in the center." << G4endl;
  }
  G4double size = 0.8; 
  G4double x0 = size * envSizeXY * (G4UniformRand()-0.5);
  G4double y0 = size * envSizeXY * (G4UniformRand()-0.5);
  G4double z0 = -0.5 * envSizeZ;
  std::vector<G4double> x = std::vector<G4double>(10);    
  fParticleGun->SetParticlePosition(G4ThreeVector(G4INCL::Random::gauss(), G4INCL::Random::gauss(), -5.5) * cm);
  fParticleGun->GeneratePrimaryVertex(anEvent); 
}


