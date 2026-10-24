#pragma once
// Per-event accumulators filled by SteppingAction / StackingAction and written to the
// 'events' ntuple at the end of the event. Column layout: see RunAction.cc (BookNtuples).

#include "G4UserEventAction.hh"
#include "globals.hh"

#include <array>
#include <map>

class RunAction;

// Primary first-interaction codes
enum FirstProc : G4int { kNoInteraction = 0, kPhot, kCompt, kRayl, kConv, kOtherProc };

// Optical boundary outcome classes (aggregated G4OpBoundaryProcessStatus)
enum OpClass : G4int
{
    kOpFresnelRefl = 0,
    kOpTIR,
    kOpLambertian,
    kOpSpikeLobe,       // spike, lobe, back-scattering
    kOpLUTRefl,         // reflections reported by LUT / LUTDAVIS / coated models
    kOpRefraction,      // FresnelRefraction / Transmission
    kOpSurfAbsorption,
    kOpDetection,
    kOpNoRindex,
    kOpNClasses
};

// Fate of an optical photon
enum OpFate : G4int { kFateDetected = 0, kFateAbsBulk, kFateAbsSurface, kFateNoRindex, kFateEscaped, kFateOther, kNFates };

// Counted EM processes (any particle): index in EventData::proc
inline const char* kProcNames[8] = {"phot", "compt", "Rayl", "conv", "eIoni", "eBrem", "annihil", "msc"};

struct EventData
{
    G4double e0 = 0.;
    G4int pdg = 0;
    G4double x0 = 0., y0 = 0.;
    G4int firstProc = kNoInteraction;
    G4double firstZ = 0.;
    G4int firstKind = -1;
    G4int firstCell = -1;
    std::array<G4double, 16> edep{};          // by volume kind
    std::map<G4int, G4double> cellEdep;       // core deposits per cell
    G4double eEscape = 0.;                    // kinetic energy leaving the world (non-optical)
    std::array<G4int, 8> proc{};              // EM process invocations, order: kProcNames
    G4int nFluo = 0, nFluoEscape = 0;
    G4int nScint = 0, nCher = 0, nCherPrimary = 0;
    std::array<G4int, kOpNClasses> opClass{};
    std::array<G4int, kNFates> fate{};
    std::array<G4int, 16> absBulkByKind{};
    G4int coatRefl = 0, coatAbs = 0, coatTrans = 0;
    G4int nExit = 0;                          // photons leaving a core towards the sensor
    G4int detSameCell = 0, detOtherCell = 0;
    G4int nOpRayleigh = 0;
    // first optical photon (gun photon, trackID 1) - validation tests
    G4int firstBoundaryStatus = -2;           // -2 none, -1 absorbed before boundary, else G4 status
};

class EventAction : public G4UserEventAction
{
  public:
    explicit EventAction(RunAction* run) : fRun(run) {}
    void BeginOfEventAction(const G4Event*) override;
    void EndOfEventAction(const G4Event*) override;

    EventData& Data() { return fData; }
    RunAction* RunRef() { return fRun; }

  private:
    RunAction* fRun;
    EventData fData;
};
