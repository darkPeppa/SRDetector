#include "G4RunManager.hh"
#include "G4NistManager.hh"
#include "G4Box.hh"
#include "G4Cons.hh"
#include "G4LogicalVolume.hh"
#include "G4PVPlacement.hh"
#include "G4SystemOfUnits.hh"
#include "G4Tubs.hh"
#include "G4String.hh"
#include "G4ExtrudedSolid.hh"
#include "G4SDManager.hh"
#include "DetectorConstruction.hh"
#include "SensitiveDetector.hh"
#include "G4UserLimits.hh"
#include "G4Orb.hh"
#include "G4Sphere.hh"
#include "G4Trd.hh"
#include "G4OpticalSurface.hh"
#include "G4LogicalSkinSurface.hh"


DetectorConstruction::DetectorConstruction()
    : G4VUserDetectorConstruction()
{
}

DetectorConstruction::~DetectorConstruction()
{
}

/*G4VPhysicalVolume *DetectorConstruction::Construct()
{
    G4bool checkOverlaps = true;

    G4NistManager *nist = G4NistManager::Instance();

    G4Element *cs = nist->FindOrBuildElement("Cs");
    G4Element *i = nist->FindOrBuildElement("I");
    G4Material *shape1_mat = new G4Material("katenka", 4.51 * g / cm3, 2);
    shape1_mat->AddElement(cs, 1);
    shape1_mat->AddElement(i, 1);

    G4Element *al = nist->FindOrBuildElement("Al");
    G4Material *shape2_mat = new G4Material("mals", 2.7 * g / cm3, 1);
    shape2_mat->AddElement(al, 1);

    ///////////////////O(0.55*2+0.3+0.092++0.038+0.02*3) = 1.59
    G4Element *si = nist->FindOrBuildElement("Si");
    G4Element *pb = nist->FindOrBuildElement("Pb");
    G4Element *k = nist->FindOrBuildElement("K");
    G4Element *na = nist->FindOrBuildElement("Na");
    G4Element *o = nist->FindOrBuildElement("O");
    G4Material *shape3_mat = new G4Material("fred", 2.29 * g / cm3, 6);
    shape3_mat->AddElement(si, 0.55 / (1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04));
    shape3_mat->AddElement(pb, 0.3 / (1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04));
    shape3_mat->AddElement(k, 0.092 / (1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04));
    shape3_mat->AddElement(na, 0.038 / (1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04));
    shape3_mat->AddElement(al, 0.04 / (1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04));
    shape3_mat->AddElement(o, 1.59 / (1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04));

    G4double env_sizeXY = 10 * cm;
    G4double env_sizeZ = 10 * cm;
    G4double world_sizeXY = 1.2 * env_sizeXY;
    G4double world_sizeZ = 1.2 * env_sizeZ;
    G4Material *world_mat = nist->FindOrBuildMaterial("G4_AIR");
    G4Box *solidWorld =
        new G4Box("World",
                  0.5 * world_sizeXY, 0.5 * world_sizeXY, 0.5 * world_sizeZ);
    G4LogicalVolume *logicWorld =
        new G4LogicalVolume(solidWorld,
                            world_mat,
                            "World");
    G4VPhysicalVolume *physWorld =
        new G4PVPlacement(0,
                          G4ThreeVector(),
                          logicWorld,
                          "World",
                          0,
                          false,
                          0,
                          checkOverlaps);

    G4Box *solidEnv =
        new G4Box("Envelope",
                  0.5 * env_sizeXY, 0.5 * env_sizeXY, 0.5 * env_sizeZ);
    G4LogicalVolume *logicEnv =
        new G4LogicalVolume(solidEnv,
                            world_mat,
                            "Envelope");
    new G4PVPlacement(0,
                      G4ThreeVector(),
                      logicEnv,
                      "Envelope",
                      logicWorld,
                      false,
                      0,
                      checkOverlaps);

    G4int nsect = 6;
    G4double ang = 2 * 3.14 / nsect;
    G4int j = 0;
    G4double dtubemin = 0.8 * cm;
    G4double dtubemax = 1.1 * cm;
    G4double shape1_rmina = 0.01 * cm, shape1_rmaxa = 0.013 * cm;
    // G4double shape1_rminb = 0. * cm, shape1_rmaxb = 4. * cm;
    G4double shape1_hz = 3. * cm;
    G4double shape1_phimin = 0. * deg, shape1_phimax = 360. * deg;

    std::vector<G4TwoVector> polygon(nsect);
    for (G4int m = 0; m < nsect; m++)
    {
        G4double phi = m * ang;
        polygon[m].set(1.4 * shape1_rmaxa * std::cos(phi), 1.4 * shape1_rmaxa * std::sin(phi));
    }

    G4double scaleA = 1, scaleB = 1;

    G4ThreeVector pos1 = G4ThreeVector();
    G4Tubs *outtertube =
        new G4Tubs("headtube",
                   dtubemin, dtubemax, shape1_hz / 2,
                   shape1_phimin, shape1_phimax);

    G4LogicalVolume *outtertubelog =
        new G4LogicalVolume(outtertube,
                            shape3_mat,
                            "headtube");

    new G4PVPlacement(0,
                      pos1,
                      outtertubelog,
                      "headtube",
                      logicEnv,
                      false,
                      0,
                      checkOverlaps);
    G4int size = int(dtubemin * dtubemin / shape1_rmaxa / shape1_rmaxa);
    std::vector<G4Tubs *> tubes = std::vector<G4Tubs *>(size);
    std::vector<G4LogicalVolume *> logvol = std::vector<G4LogicalVolume *>(size);
    std::vector<G4LogicalVolume *> logvolp = std::vector<G4LogicalVolume *>(size);
    auto itertubes = tubes.begin();
    auto iterlogvol = logvol.begin();
    auto iterlogvolp = logvolp.begin();
    std::vector<G4Tubs *> tubesinner = std::vector<G4Tubs *>(size);
    std::vector<G4LogicalVolume *> logvoltubesinner = std::vector<G4LogicalVolume *>(size);
    auto itertubesinner = tubesinner.begin();
    auto itertubeslogvol = logvoltubesinner.begin();
    std::vector<G4VSolid *> prisms = std::vector<G4VSolid *>(size);
    auto iterprisms = prisms.begin();
    G4int p = 0;

    while (j <= dtubemin / 2 / shape1_rmaxa)
    {
        G4int k = 0;
        while (k < 2 * 3.14 * (shape1_rmaxa / 4 + j * shape1_rmaxa / 4) / shape1_rmaxa * 4)
        {
            std::string name = std::to_string(p);
            G4ThreeVector pos1 = G4ThreeVector(((shape1_rmaxa / 4 + j * shape1_rmaxa / 4) * (std::cos(2 * 3.14 * k / (2 * 3.14 * (shape1_rmaxa / 4 + j * shape1_rmaxa / 4)) * (shape1_rmaxa / 4)))) * cm,
                                               ((shape1_rmaxa / 4 + j * shape1_rmaxa / 4) * (std::sin(2 * 3.14 * k / (2 * 3.14 * (shape1_rmaxa / 4 + j * shape1_rmaxa / 4)) * (shape1_rmaxa / 4)))) * cm,
                                               0);
            *iterprisms = new G4ExtrudedSolid(name + "k", polygon, shape1_hz / 2, (0, 0), scaleA, (0, 0), scaleB);
            *itertubes =
                new G4Tubs(name,
                           shape1_rmina, shape1_rmaxa, shape1_hz / 2,
                           shape1_phimin, shape1_phimax);
            *itertubesinner =
                new G4Tubs(name + "t",
                           0, shape1_rmina - 0.01, shape1_hz / 2,
                           shape1_phimin, shape1_phimax);
            *iterlogvol =
                new G4LogicalVolume(*itertubes,
                                    shape2_mat,
                                    name);
            *itertubeslogvol =
                new G4LogicalVolume(*itertubesinner,
                                    shape1_mat,
                                    name + "t");
            *iterlogvolp =
                new G4LogicalVolume(*iterprisms,
                                    shape3_mat,
                                    name + "k");
            new G4PVPlacement(0,
                              pos1,
                              *iterlogvolp,
                              name + "k",
                              logicEnv,
                              false,
                              p,
                              checkOverlaps);
            new G4PVPlacement(0,
                              G4ThreeVector(),
                              *iterlogvol,
                              name,
                              *iterlogvolp,
                              false,
                              p,
                              checkOverlaps);
            new G4PVPlacement(0,
                              G4ThreeVector(),
                              *itertubeslogvol,
                              name + "t",
                              *iterlogvol,
                              false,
                              p,
                              checkOverlaps);
            p++;
            k++;
            ++itertubes;
            ++iterlogvol;
            ++iterprisms;
            ++iterlogvolp;
            ++itertubesinner;
            ++itertubeslogvol;
        }
        j++;
    }

    G4double maxStep = 0.0001 * cm;
    fStepLimit = new G4UserLimits(maxStep);
    logicEnv->SetUserLimits(fStepLimit);

    return physWorld;
}*/


G4VPhysicalVolume* DetectorConstruction::Construct() {
    
        G4NistManager* nist = G4NistManager::Instance();
        G4Material* world_mat = nist->FindOrBuildMaterial("G4_AIR");
        G4Material* envelope_mat = nist->FindOrBuildMaterial("G4_AIR");
        
        
        G4Material* shell_mat = nist->FindOrBuildMaterial("G4_Al");
        G4Material* core_mat = nist->FindOrBuildMaterial("G4_CESIUM_IODIDE");


G4MaterialPropertiesTable* csiMPT = new G4MaterialPropertiesTable();

const G4int NUM = 2;
G4double pp[NUM] = {2.48*eV, 3.1*eV};
G4double scintil[NUM] = {1.0, 1.0};  
csiMPT->AddProperty("SCINTILLATIONCOMPONENT1", pp, scintil, NUM);

csiMPT->AddConstProperty("SCINTILLATIONTIMECONSTANT1", 1.0*ns); 
csiMPT->AddConstProperty("SCINTILLATIONYIELD", 50000/MeV);     

G4double rindex[NUM] = {1.78, 1.78}; 
csiMPT->AddProperty("RINDEX", pp, rindex, NUM);

G4double absorption[NUM] = {5.0*m, 5.0*m};
csiMPT->AddProperty("ABSLENGTH", pp, absorption, NUM);
csiMPT->AddConstProperty("RESOLUTIONSCALE", 0.04);

core_mat->SetMaterialPropertiesTable(csiMPT);


G4OpticalSurface* opSurface = new G4OpticalSurface("MicrochannelSurface");
opSurface->SetType(dielectric_dielectric);
opSurface->SetFinish(polished);
opSurface->SetModel(unified);


G4MaterialPropertiesTable* alMPT = new G4MaterialPropertiesTable();
const G4int num = 5;

G4double ePhoton[num] = {1.0*eV, 2.26*eV, 3.54*eV, 4.96*eV, 6.20*eV}; 
G4double reflectivity[num] = {0.92, 0.90, 0.88, 0.85, 0.82}; 

alMPT->AddProperty("REFLECTIVITY", ePhoton, reflectivity, num);
shell_mat->SetMaterialPropertiesTable(alMPT);


G4OpticalSurface* alSurface = new G4OpticalSurface("AlSurface");
alSurface->SetType(dielectric_metal); 
alSurface->SetFinish(polished);       
alSurface->SetModel(unified);         


G4MaterialPropertiesTable* surfaceMPT = new G4MaterialPropertiesTable();
surfaceMPT->AddProperty("REFLECTIVITY", ePhoton, reflectivity, num);
G4double absorption2[num] = {0.1*um, 0.1*um, 0.1*um, 0.1*um, 0.1*um};
surfaceMPT->AddProperty("ABSORPTION", ePhoton, absorption2, num, true);
surfaceMPT->AddConstProperty("SPECULARLOBECONSTANT", 0.3, true);
surfaceMPT->AddConstProperty("SPECULARSPIKECONSTANT", 0.2, true);
surfaceMPT->AddConstProperty("BACKSCATTERCONSTANT", 0.1, true);


alSurface->SetMaterialPropertiesTable(surfaceMPT);






        
        G4Element *si = nist->FindOrBuildElement("Si");
    G4Element *pb = nist->FindOrBuildElement("Pb");
    G4Element *k = nist->FindOrBuildElement("K");
    G4Element *na = nist->FindOrBuildElement("Na");
    G4Element *o = nist->FindOrBuildElement("O");
    G4Element *al = nist->FindOrBuildElement("Al");
    G4Material *tube_mat = new G4Material("fred", 2.29 * g / cm3, 6);
    tube_mat->AddElement(si, 0.55 / (1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04));
    tube_mat->AddElement(pb, 0.3 / (1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04));
    tube_mat->AddElement(k, 0.092 / (1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04));
    tube_mat->AddElement(na, 0.038 / (1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04));
    tube_mat->AddElement(al, 0.04 / (1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04));
    tube_mat->AddElement(o, 1.59 / (1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04));





        G4Box* solidWorld = new G4Box("World", 6*cm, 6*cm, 6*cm);
        G4LogicalVolume* logicWorld = new G4LogicalVolume(solidWorld, world_mat, "World");
        G4PVPlacement* physWorld = new G4PVPlacement(0, G4ThreeVector(), logicWorld, "World", 0, false, 0);

        
        G4Box* solidEnvelope = new G4Box("Envelope", 5*cm, 5*cm, 5*cm);
        G4LogicalVolume* logicEnvelope = new G4LogicalVolume(solidEnvelope, envelope_mat, "Envelope");
        new G4PVPlacement(0, G4ThreeVector(), logicEnvelope, "Envelope", logicWorld, false, 0);

        
        G4double tube_radius = 1.1*cm;
        G4double tube_height = 3*cm;
        G4Tubs* solidTube = new G4Tubs("MainTube", 0, tube_radius, tube_height/2, 0, 360*deg);
        G4LogicalVolume* logicTube = new G4LogicalVolume(solidTube, tube_mat, "MainTube");
        G4PVPlacement* physTube = new G4PVPlacement(0, G4ThreeVector(0,0,0), logicTube, "MainTube", logicEnvelope, false, 0);

        G4double outer_radius = 0.012*cm; 
        G4double inner_radius = 0.01*cm;  
        G4double spacing = 2*outer_radius;

        
        std::vector<G4ThreeVector> positions;
        positions.push_back(G4ThreeVector(0,0,0));

        int rings = static_cast<int>((tube_radius - outer_radius)/spacing) + 1;
        for (int ring = 1; ring <= rings; ++ring) {
            int channels_in_ring = 6*ring;
            for (int i = 0; i < channels_in_ring; ++i) {
                G4double angle = 2*3.14 * i/channels_in_ring;
                G4double distance = ring*spacing;
                G4double x = distance * std::cos(angle);
                G4double y = distance * std::sin(angle);
                positions.push_back(G4ThreeVector(x,y,0));
            }
        }

     
        G4Tubs* solidShell = new G4Tubs("MicroShell", 0, outer_radius, tube_height/2, 0, 360*deg);
        
        G4Tubs* solidCore = new G4Tubs("MicroCore", 0, inner_radius, tube_height/2, 0, 360*deg);

        G4LogicalVolume* logicShell = new G4LogicalVolume(solidShell, shell_mat, "MicroShell");
        G4LogicalVolume* logicCore = new G4LogicalVolume(solidCore, core_mat, "MicroCore");
        new G4LogicalSkinSurface("AlSurface", logicShell, alSurface);
       
        for (size_t i = 0; i < positions.size(); ++i) {
           
            if (positions[i].perp() + outer_radius <= tube_radius) {
                new G4PVPlacement(0, positions[i], logicShell, "MicroShell", logicTube, false, i);
                new G4PVPlacement(0, G4ThreeVector(0,0,0), logicCore, "MicroCore", logicShell, false, i);
            }
        }

        return physWorld;
    
};



void DetectorConstruction::SetMaxStep(G4double maxStep)
{
    if ((fStepLimit) && (maxStep > 0.))
        fStepLimit->SetMaxAllowedStep(maxStep);
}

/*void DetectorConstruction::ConstructSD()
{
    G4double dtubemin = 0.8 * cm;
    G4double dtubemax = 1.1 * cm;
    G4double shape1_rmina = 0.01 * cm, shape1_rmaxa = 0.013 * cm;
    G4int j = 0;
    G4int kas = 0;
    G4int size = int(dtubemin * dtubemin / shape1_rmaxa / shape1_rmaxa);
    std::vector<SDet *> sds = std::vector<SDet *>(size);
    auto sdsiter = sds.begin();
    G4SDManager *man = G4SDManager::GetSDMpointer();
    while (j <= dtubemin / 2 / shape1_rmaxa)
    {
        G4int k = 0;
        while (k < 2 * 3.14 * (shape1_rmaxa / 4 + j * shape1_rmaxa / 4) / shape1_rmaxa * 4)
        {
            std::string name = std::to_string(kas);
            *sdsiter = new SDet("/microchan" + name + "t", "HitsCollection");
            man->AddNewDetector(*sdsiter);
            SetSensitiveDetector(name + "t", *sdsiter, true);
            ++sdsiter;
            k++;
            kas++;
        }
        j++;
    }
}*/

void DetectorConstruction::ConstructSD() {
   
    G4SDManager* sdManager = G4SDManager::GetSDMpointer();


       SDet* microchannelSD = new SDet("/MicrochannelSD", "HitsCollection");
        sdManager->AddNewDetector(microchannelSD);
    
    SetSensitiveDetector("MicroCore", microchannelSD, true);
}
