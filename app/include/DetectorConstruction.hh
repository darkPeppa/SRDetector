#pragma once
// Geometry (all lengths from SRDetConfig):
//
//   World (Air)
//   └─ Housing (cylinder, side wall + back plate)          [full mode]
//      ├─ Window (entrance, -z)  ← skin surface: entrance reflector
//      ├─ Matrix (cylinder radius R, length L, rim material)
//      │   └─ Cell × N   (hexagonal prism, wall material, flat-to-flat = pitch)
//      │       ├─ Coating (annulus / hex ring, thickness t)   [if the coating has a layer]
//      │       └─ Core    (scintillator, diameter D)          ← border surface Core→Coating
//      ├─ Coupling (optical grease)
//      ├─ SensorWindow
//      └─ SensorActive (Si)  ← skin surface: EFFICIENCY = QE × fill factor
//
// Hexagons are "flat-top" (corners on ±x). Axial lattice coordinates (q, r):
//   x = √3/2 · pitch · q,   y = pitch · (r + q/2),   neighbour distance = pitch.
// Modes: full (all cells inside R), cluster7 (centre + 6 neighbours), unit (one cell),
//        slab (plain block of slabMaterial, for validation).

#include "G4VUserDetectorConstruction.hh"
#include "globals.hh"

#include <unordered_map>
#include <vector>

class G4LogicalVolume;
class G4VPhysicalVolume;
class G4VSolid;
class ConfigMessenger;

enum VKind : G4int
{
    kWorld = 0,
    kHousing,
    kWindow,
    kMatrix,
    kWall,
    kCoating,
    kCore,
    kCoupling,
    kSensorWindow,
    kSensorActive,
    kSlab,
    kNKinds
};

inline const char* VKindName(G4int k)
{
    static const char* names[] = {"world", "housing", "window", "matrix", "wall", "coating",
                                  "core", "coupling", "sensor_window", "sensor_active", "slab"};
    return (k >= 0 && k < kNKinds) ? names[k] : "unknown";
}

struct CellInfo
{
    G4int q, r;
    G4double x, y;
};

struct GeometryInfo
{
    G4double matrixRadius = 0., length = 0., pitch = 0., coreRadius = 0.;
    G4double zFront = 0., zBack = 0., zSensor = 0.;
    G4bool hexChannel = false;
    std::vector<CellInfo> cells;
    G4int centralCell = -1;
};

class DetectorConstruction : public G4VUserDetectorConstruction
{
  public:
    DetectorConstruction();
    ~DetectorConstruction() override;

    G4VPhysicalVolume* Construct() override;

    static G4int KindOf(const G4LogicalVolume* lv)
    {
        auto it = fKinds.find(lv);
        return it == fKinds.end() ? kWorld : it->second;
    }
    static const GeometryInfo& Info() { return fInfo; }

  private:
    void Cleanup();
    G4VPhysicalVolume* BuildSlab();
    G4VPhysicalVolume* BuildHoneycomb();
    G4VSolid* Hex(const G4String& name, G4double apothemIn, G4double apothemOut, G4double halfZ);
    void Register(G4LogicalVolume* lv, G4int kind) { fKinds[lv] = kind; }
    void ExportGeometry(G4VPhysicalVolume* world);

    ConfigMessenger* fMessenger = nullptr;
    G4double fHexPhi0 = 0.;
    G4bool fHexPhiChecked = false;

    static std::unordered_map<const G4LogicalVolume*, G4int> fKinds;
    static GeometryInfo fInfo;
};
