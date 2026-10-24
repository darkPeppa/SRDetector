#include "Actions.hh"

#include "DetectorConstruction.hh"
#include "EventAction.hh"
#include "PrimaryGeneratorAction.hh"
#include "RunAction.hh"

#include "G4AnalysisManager.hh"
#include "G4Gamma.hh"
#include "G4PhysicalConstants.hh"
#include "G4Positron.hh"
#include "G4OpBoundaryProcess.hh"
#include "G4OpticalPhoton.hh"
#include "G4ProcessManager.hh"
#include "G4Step.hh"
#include "G4SystemOfUnits.hh"
#include "G4Track.hh"
#include "G4VProcess.hh"
#include "G4VTouchable.hh"

#include <cstring>

// ============================================================ initialisation
void ActionInitialization::BuildForMaster() const { SetUserAction(new RunAction()); }

void ActionInitialization::Build() const
{
    auto* run = new RunAction();
    auto* ev = new EventAction(run);
    SetUserAction(new PrimaryGeneratorAction());
    SetUserAction(run);
    SetUserAction(ev);
    SetUserAction(new StackingAction(ev));
    SetUserAction(new SteppingAction(ev));
}

// ============================================================ helpers
G4int CellOf(const G4StepPoint* point, G4int kind)
{
    const auto* t = point->GetTouchable();
    if (kind == kWall) return t->GetCopyNumber(0);
    if (kind == kCore || kind == kCoating) return t->GetCopyNumber(1);
    return -1;
}

G4bool IsFluorescenceCreator(const G4String& p)
{
    // Secondary gammas of these processes come only from atomic de-excitation
    // (the scattered photon of compt is the primary itself, not a secondary).
    return p == "phot" || p == "compt" || p == "eIoni" || p == "hIoni" || p == "ionIoni" || p == "muIoni" ||
           p == "Rayl";
}

namespace
{
G4int ProcIndex(const G4String& name)
{
    for (G4int i = 0; i < 8; ++i)
        if (name == kProcNames[i]) return i;
    return -1;
}

G4int FirstProcCode(const G4String& name)
{
    if (name == "phot") return kPhot;
    if (name == "compt") return kCompt;
    if (name == "Rayl") return kRayl;
    if (name == "conv") return kConv;
    return kOtherProc;
}

// -1: not a boundary interaction
G4int Classify(G4OpBoundaryProcessStatus s)
{
    switch (s) {
        case Undefined:
        case NotAtBoundary:
        case SameMaterial:
        case StepTooSmall:
            return -1;
        case FresnelReflection: return kOpFresnelRefl;
        case TotalInternalReflection: return kOpTIR;
        case LambertianReflection: return kOpLambertian;
        case LobeReflection:
        case SpikeReflection:
        case BackScattering: return kOpSpikeLobe;
        case FresnelRefraction:
        case Transmission:
        case Dichroic:
        case CoatedDielectricRefraction:
        case CoatedDielectricFrustratedTransmission: return kOpRefraction;
        case Absorption: return kOpSurfAbsorption;
        case Detection: return kOpDetection;
        case NoRINDEX: return kOpNoRindex;
        default: return kOpLUTRefl;  // LUT / LUTDAVIS / coated reflections
    }
}

G4bool IsReflection(G4int cls)
{
    return cls == kOpFresnelRefl || cls == kOpTIR || cls == kOpLambertian || cls == kOpSpikeLobe || cls == kOpLUTRefl;
}
}  // namespace

// ============================================================ stacking
G4ClassificationOfNewTrack StackingAction::ClassifyNewTrack(const G4Track* track)
{
    if (track->GetParentID() == 0) return fUrgent;
    auto& d = fEvent->Data();
    const auto* creator = track->GetCreatorProcess();
    if (!creator) return fUrgent;
    const G4String& cname = creator->GetProcessName();
    auto* am = G4AnalysisManager::Instance();
    if (track->GetDefinition() == G4OpticalPhoton::Definition()) {
        if (cname == "Scintillation") {
            ++d.nScint;
            am->FillH1(RunAction::kH_LambdaScint, 1239.84193 / (track->GetKineticEnergy() / eV));
        } else if (cname == "Cerenkov") {
            ++d.nCher;
            if (track->GetParentID() == 1) ++d.nCherPrimary;
        }
    } else if (track->GetDefinition() == G4Gamma::Definition() && IsFluorescenceCreator(cname)) {
        ++d.nFluo;
        am->FillH1(RunAction::kH_FluoEnergy, track->GetKineticEnergy());
    }
    return fUrgent;
}

// ============================================================ stepping
G4OpBoundaryProcess* SteppingAction::Boundary()
{
    if (!fBoundary) {
        auto* pv = G4OpticalPhoton::Definition()->GetProcessManager()->GetProcessList();
        for (std::size_t i = 0; i < pv->size(); ++i)
            if ((*pv)[i]->GetProcessName() == "OpBoundary") fBoundary = dynamic_cast<G4OpBoundaryProcess*>((*pv)[i]);
    }
    return fBoundary;
}

void SteppingAction::UserSteppingAction(const G4Step* step)
{
    const auto* pre = step->GetPreStepPoint();
    const G4int preKind = DetectorConstruction::KindOf(pre->GetTouchable()->GetVolume()->GetLogicalVolume());
    auto* track = step->GetTrack();
    if (track->GetDefinition() == G4OpticalPhoton::Definition()) {
        OpticalStep(step, preKind);
        return;
    }

    auto& d = fEvent->Data();
    const auto* post = step->GetPostStepPoint();
    const G4double edep = step->GetTotalEnergyDeposit();
    if (edep > 0) {
        d.edep[preKind] += edep;
        if (preKind == kCore) d.cellEdep[CellOf(pre, kCore)] += edep;
    }

    const auto* proc = post->GetProcessDefinedStep();
    if (proc) {
        const G4String& pname = proc->GetProcessName();
        const G4int idx = ProcIndex(pname);
        if (idx >= 0) ++d.proc[idx];
        if (track->GetTrackID() == 1 && d.firstProc == kNoInteraction && pname != "Transportation" &&
            pname != "CoupledTransportation" && pname != "msc" && pname != "UserLimit" && pname != "StepLimiter") {
            d.firstProc = FirstProcCode(pname);
            d.firstZ = post->GetPosition().z();
            d.firstKind = preKind;
            d.firstCell = CellOf(pre, preKind);
            G4AnalysisManager::Instance()->FillH1(RunAction::kH_FirstZ, d.firstZ);
            G4AnalysisManager::Instance()->FillH2(RunAction::kH2_FirstXY, post->GetPosition().x(),
                                                  post->GetPosition().y());
        }
    }

    if (post->GetStepStatus() == fWorldBoundary) {
        d.eEscape += post->GetKineticEnergy();
        // an escaping positron also carries away the 2 m_e c^2 it would release by annihilation
        if (track->GetDefinition() == G4Positron::Definition()) d.eEscape += 2 * electron_mass_c2;
        if (track->GetDefinition() == G4Gamma::Definition() && track->GetCreatorProcess() &&
            IsFluorescenceCreator(track->GetCreatorProcess()->GetProcessName()))
            ++d.nFluoEscape;
    }
}

void SteppingAction::OpticalStep(const G4Step* step, G4int preKind)
{
    auto& d = fEvent->Data();
    auto* track = step->GetTrack();
    const auto* pre = step->GetPreStepPoint();
    const auto* post = step->GetPostStepPoint();

    auto* info = static_cast<PhotonInfo*>(track->GetUserInformation());
    if (!info) {
        info = new PhotonInfo();
        info->birthCell = CellOf(pre, preKind);
        info->birthZ = track->GetVertexPosition().z();
        track->SetUserInformation(info);
    }

    const auto* proc = post->GetProcessDefinedStep();
    const G4bool bulkAbs = proc && proc->GetProcessName() == "OpAbsorption";
    if (proc && proc->GetProcessName() == "OpRayleigh") ++d.nOpRayleigh;

    G4OpBoundaryProcessStatus status = Undefined;
    G4int cls = -1;
    if (post->GetStepStatus() == fGeomBoundary && Boundary()) {
        status = fBoundary->GetStatus();
        cls = Classify(status);
        if (cls >= 0) {
            ++d.opClass[cls];
            if (IsReflection(cls)) ++info->nRefl;
            if (track->GetTrackID() == 1 && d.firstBoundaryStatus == -2) d.firstBoundaryStatus = status;
            const auto* postPV = post->GetPhysicalVolume();
            const G4int postKind = postPV ? DetectorConstruction::KindOf(postPV->GetLogicalVolume()) : -1;
            if (preKind == kCore && (postKind == kCoating || postKind == kWall)) {
                if (IsReflection(cls)) {
                    ++d.coatRefl;
                    ++info->nCoatRefl;
                }
                else if (cls == kOpSurfAbsorption) ++d.coatAbs;
                else if (cls == kOpRefraction) ++d.coatTrans;
            }
            if (preKind == kCore &&
                (postKind == kCoupling || postKind == kSensorWindow || postKind == kSensorActive) &&
                (cls == kOpRefraction || cls == kOpDetection || cls == kOpSurfAbsorption)) {
                info->exitCell = CellOf(pre, kCore);
                ++d.nExit;
            }
        }
    }
    if (bulkAbs && track->GetTrackID() == 1 && d.firstBoundaryStatus == -2) d.firstBoundaryStatus = -1;

    if (track->GetTrackStatus() != fStopAndKill) return;

    if (cls == kOpDetection) {
        ++d.fate[kFateDetected];
        if (info->exitCell >= 0 && info->exitCell == info->birthCell) ++d.detSameCell;
        else ++d.detOtherCell;
        fEvent->RunRef()->FillPhoton(*track, post, info);
    } else if (bulkAbs) {
        ++d.fate[kFateAbsBulk];
        ++d.absBulkByKind[preKind];
    } else if (cls == kOpSurfAbsorption) {
        ++d.fate[kFateAbsSurface];
    } else if (cls == kOpNoRindex) {
        ++d.fate[kFateNoRindex];
    } else if (post->GetStepStatus() == fWorldBoundary) {
        ++d.fate[kFateEscaped];
    } else {
        ++d.fate[kFateOther];
    }
}
