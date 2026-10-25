#pragma once
// Run-time configuration of the detector. Every field is settable from macros
// via /srdet/... commands (ConfigMessenger); nothing about the geometry is hard-coded.
// Values are filled on the master thread before /run/initialize and only read afterwards.

#include "globals.hh"
#include "G4SystemOfUnits.hh"

#include <string>
#include <vector>

struct MaterialOverride
{
    G4String material;
    G4String action;   // setConst | setAbsLength | loadProperty | birks | noRindex | density
    G4String key;
    G4double value = 0.;
    G4String file;
};

struct SRDetConfig
{
    static SRDetConfig& Instance();

    // ---- geometry mode: full | cluster7 | unit | slab
    G4String mode = "full";

    // ---- honeycomb matrix (cylindrical detector)
    G4double detectorRadius = 11. * mm;     // radius of the honeycomb matrix
    G4double length = 30. * mm;             // channel (matrix) length along z
    G4double pitch = 0.208 * mm;            // hex cell flat-to-flat == centre-to-centre distance
    G4double channelDiameter = 0.200 * mm;  // scintillator core diameter (circle) or flat-to-flat (hex)
    G4String channelShape = "circle";       // circle | hex
    G4String wallMaterial = "LeadGlass_MCP";
    G4String matrixMaterial = "";           // rim between lattice and cylinder; empty -> wallMaterial
    G4String coreMaterial = "CsI_Tl";

    // ---- channel reflective coating
    G4String coating = "Al";                // see OpticalSurfaces.hh for the catalogue
    G4double coatingThickness = 0.002 * mm; // physical layer (EM); 0 -> optical surface only
    G4String coatingMaterial = "";          // EM material of the layer; empty -> coating default
    G4double coatingReflectivity = 0.90;    // for coating "mirror" / "diffuse"
    G4double coatingSigmaAlpha = 0. * deg;  // micro-facet roughness; > 0 switches finish to ground
    G4double filmThickness = 0.5 * um;      // for thin-film coatings (MgF2_film)

    // ---- surroundings
    G4String worldMaterial = "Air";
    G4String housingMaterial = "G4_Al";
    G4double housingThickness = 1. * mm;    // 0 -> no housing
    G4String windowMaterial = "G4_Be";
    G4double windowThickness = 0.5 * mm;    // entrance window, 0 -> none
    G4String entranceCoating = "Al";        // optical surface on the window face (reflects light back)

    // ---- read-out
    G4String couplingMaterial = "OpticalGrease";
    G4double couplingThickness = 0.05 * mm; // 0 -> direct contact
    G4String sensor = "aSi_FPD";            // see Sensors.hh
    G4double sensorWindowThickness = -1.;   // < 0 -> catalogue value
    G4double sensorActiveThickness = 0.02 * mm;

    // ---- slab mode (validation: plain block of material)
    G4String slabMaterial = "CsI_Tl";
    G4double slabThickness = 1. * mm;
    G4double slabHalfXY = 50. * mm;

    // ---- misc
    G4double worldMargin = 50. * mm;        // free space around the detector (sources live there)
    G4bool checkOverlaps = false;
    G4double yieldScale = 1.0;              // multiplies SCINTILLATIONYIELD of every scintillator
    std::vector<MaterialOverride> materialOverrides;

    // ---- output
    G4String outDir = ".";
    G4double photonFraction = 0.0;          // fraction of detected photons written to the 'photons' ntuple
    G4bool writeCellHits = false;           // per-event per-cell energy deposits ('cells' ntuple)
    G4double cellEdepThreshold = 0.5 * keV; // a cell counts as "hit" above this deposit
    G4bool writeGDML = false;
    // histogram ranges (z and x-y ranges follow the geometry)
    G4double histEmax = 1000. * keV;
    G4double histNScintMax = 60000.;
    G4double histNDetMax = 20000.;
    G4double histTmax = 20000. * ns;
    // trajectories for the 3D viewer of the web UI (tracks.jsonl); needs /tracking/storeTrajectory 1
    G4int tracksEvents = 0;          // number of events whose trajectories are written
    G4int tracksOpticalEvery = 50;   // keep every N-th optical photon trajectory (there are thousands)

  private:
    SRDetConfig() = default;
};

class G4GenericMessenger;
class G4UImessenger;

class ConfigMessenger
{
  public:
    ConfigMessenger();
    ~ConfigMessenger();

  private:
    G4GenericMessenger* fGeom = nullptr;
    G4GenericMessenger* fOptics = nullptr;
    G4GenericMessenger* fMat = nullptr;
    G4GenericMessenger* fOut = nullptr;
    G4UImessenger* fMatCmds = nullptr;  // multi-argument /srdet/mat/... commands
};
