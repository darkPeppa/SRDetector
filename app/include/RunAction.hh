#pragma once
// Books and writes the output (G4AnalysisManager, ROOT by default, merged over threads):
//   ntuple 'events'  - one row per event (energy deposits, process counts, photon fates)
//   ntuple 'photons' - detected optical photons (fraction /srdet/out/photonFraction)
//   ntuple 'cells'   - per-cell core deposits (/srdet/out/cellHits true)
//   H1/H2 with titles and axis labels (ranges adjustable with /analysis/h1/set)
// The master writes <outDir>/run_summary.json at the end of the run.

#include "G4Accumulable.hh"
#include "G4UserRunAction.hh"
#include "globals.hh"

class G4StepPoint;
class G4Track;
class PhotonInfo;
struct EventData;

class RunAction : public G4UserRunAction
{
  public:
    enum H1 : G4int
    {
        kH_EdepTotal = 0,
        kH_EdepCore,
        kH_NScint,
        kH_NDet,
        kH_TDet,
        kH_LambdaDet,
        kH_NReflDet,
        kH_FirstZ,
        kH_FluoEnergy,
        kH_NCellsHit,
        kH_LambdaScint,
        kH_BirthZDet,
    };
    enum H2 : G4int { kH2_DetXY = 0, kH2_FirstXY };
    enum Nt : G4int { kNtEvents = 0, kNtPhotons, kNtCells };

    RunAction();
    void BeginOfRunAction(const G4Run*) override;
    void EndOfRunAction(const G4Run*) override;

    void FillEvent(G4int eventID, const EventData& d);
    void FillPhoton(const G4Track& track, const G4StepPoint* post, const PhotonInfo* info);

  private:
    void SetRanges();
    G4int fEventID = -1;
    G4Accumulable<G4double> fN = 0., fSumEdep = 0., fSumScint = 0., fSumDet = 0., fSumDet2 = 0., fSumExit = 0.;
    G4Accumulable<G4double> fNInteracting = 0., fSumFluoEsc = 0.;
};
