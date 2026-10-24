#include "RunAction.hh"

#include "Actions.hh"
#include "Config.hh"
#include "DetectorConstruction.hh"
#include "EventAction.hh"

#include "G4AccumulableManager.hh"
#include "G4AnalysisManager.hh"
#include "G4Event.hh"
#include "G4EventManager.hh"
#include "G4PrimaryParticle.hh"
#include "G4PrimaryVertex.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4StepPoint.hh"
#include "G4SystemOfUnits.hh"
#include "G4Track.hh"
#include "G4UnitsTable.hh"
#include "Randomize.hh"

#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>

namespace
{
std::chrono::steady_clock::time_point gStart;

struct HistDef
{
    const char *name, *title, *xtitle, *ytitle, *unit;
};
// Titles are re-applied after every range change: SetH1/SetH2 reset the axis titles.
const HistDef kH1Defs[] = {
    {"edep_total", "Total energy deposit in the detector", "E_{dep} [keV]", "events", "keV"},
    {"edep_core", "Energy deposit in the scintillator cores", "E_{dep} [keV]", "events", "keV"},
    {"n_scint", "Scintillation photons produced per event (scaled yield)", "N_{scint}", "events", "none"},
    {"n_det", "Detected photons per event (scaled yield)", "N_{det} [photo-electrons]", "events", "none"},
    {"t_det", "Arrival time of detected photons", "t [ns]", "photons", "ns"},
    {"lambda_det", "Wavelength of detected photons", "#lambda [nm]", "photons", "none"},
    {"nrefl_det", "Reflections before detection", "N_{refl}", "photons", "none"},
    {"first_z", "Depth of the primary's first interaction", "z [mm]", "events", "mm"},
    {"fluo_energy", "Fluorescence X-ray energies", "E_{#gamma} [keV]", "photons", "keV"},
    {"n_cells_hit", "Cells with core deposit above threshold", "N_{cells}", "events", "none"},
    {"lambda_scint", "Wavelength of produced scintillation photons", "#lambda [nm]", "photons", "none"},
    {"birthz_det", "Emission depth of detected photons", "z_{emission} [mm]", "photons", "mm"},
};
const HistDef kH2Defs[] = {
    {"det_xy", "Detected photon positions on the sensor", "x [mm]", "y [mm]", "mm"},
    {"first_xy", "Position of the primary's first interaction", "x [mm]", "y [mm]", "mm"},
};

G4double U(const char* unit) { return std::string(unit) == "none" ? 1. : G4UnitDefinition::GetValueOf(unit); }

// lo / hi in internal units
void RangeH1(G4int id, G4int n, G4double lo, G4double hi)
{
    auto* am = G4AnalysisManager::Instance();
    const auto& d = kH1Defs[id];
    am->SetH1(id, n, lo, hi, d.unit);
    am->SetH1Title(id, d.title);
    am->SetH1XAxisTitle(id, d.xtitle);
    am->SetH1YAxisTitle(id, d.ytitle);
}

void RangeH2(G4int id, G4int n, G4double lo, G4double hi)
{
    auto* am = G4AnalysisManager::Instance();
    const auto& d = kH2Defs[id];
    am->SetH2(id, n, lo, hi, n, lo, hi, d.unit, d.unit);
    am->SetH2Title(id, d.title);
    am->SetH2XAxisTitle(id, d.xtitle);
    am->SetH2YAxisTitle(id, d.ytitle);
}
}  // namespace

RunAction::RunAction()
{
    G4RunManager::GetRunManager()->SetPrintProgress(0);
    auto* am = G4AnalysisManager::Instance();
    am->SetDefaultFileType("root");
    am->SetVerboseLevel(0);
    am->SetNtupleMerging(true);
    am->SetFileName("srdet");
    am->SetFirstHistoId(0);
    am->SetFirstNtupleId(0);
    am->SetFirstNtupleColumnId(0);

    // ---------------- histograms (ranges are set at the start of each run, see SetRanges)
    for (const auto& d : kH1Defs) am->CreateH1(d.name, d.title, 100, 0., 1. * U(d.unit), d.unit);
    for (const auto& d : kH2Defs) am->CreateH2(d.name, d.title, 10, -U(d.unit), U(d.unit), 10, -U(d.unit), U(d.unit), d.unit, d.unit);

    // ---------------- ntuples
    am->CreateNtuple("events", "One row per event");
    am->CreateNtupleIColumn("evt");
    am->CreateNtupleDColumn("e0_keV");
    am->CreateNtupleIColumn("pdg");
    for (auto n : {"x0_mm", "y0_mm"}) am->CreateNtupleDColumn(n);
    am->CreateNtupleIColumn("first_proc");
    am->CreateNtupleDColumn("first_z_mm");
    for (auto n : {"first_kind", "first_cell"}) am->CreateNtupleIColumn(n);
    for (auto n : {"edep_total_keV", "edep_core_keV", "edep_wall_keV", "edep_coating_keV", "edep_matrix_keV",
                   "edep_window_keV", "edep_housing_keV", "edep_coupling_keV", "edep_sensor_keV", "edep_slab_keV",
                   "edep_world_keV", "e_escape_keV"})
        am->CreateNtupleDColumn(n);
    am->CreateNtupleIColumn("n_cells_hit");
    for (auto n : {"edep_first_cell_keV", "edep_max_cell_keV"}) am->CreateNtupleDColumn(n);
    for (auto n : {"n_phot", "n_compt", "n_rayl", "n_conv", "n_eioni", "n_ebrem", "n_annihil", "n_msc", "n_fluo",
                   "n_fluo_escape", "n_scint", "n_cher", "n_cher_primary", "op_fresnel_refl", "op_tir",
                   "op_lambert", "op_spike_lobe", "op_lut_refl", "op_refraction", "op_surf_abs", "op_detection",
                   "op_norindex", "n_det", "n_abs_bulk", "n_abs_surface", "n_norindex", "n_escaped", "n_lost_other",
                   "abs_bulk_core", "abs_bulk_wall", "abs_bulk_coupling", "abs_bulk_other", "coat_refl", "coat_abs",
                   "coat_trans", "n_exit", "det_same_cell", "det_other_cell", "n_op_rayleigh",
                   "first_boundary_status"})
        am->CreateNtupleIColumn(n);
    am->FinishNtuple();

    am->CreateNtuple("photons", "Detected optical photons (sampled)");
    am->CreateNtupleIColumn("evt");
    for (auto n : {"x_mm", "y_mm", "t_ns", "lambda_nm"}) am->CreateNtupleDColumn(n);
    for (auto n : {"n_refl", "birth_cell", "exit_cell"}) am->CreateNtupleIColumn(n);
    am->CreateNtupleDColumn("birth_z_mm");
    am->CreateNtupleIColumn("n_coat_refl");
    am->FinishNtuple();

    am->CreateNtuple("cells", "Per-cell core energy deposits");
    am->CreateNtupleIColumn("evt");
    am->CreateNtupleIColumn("cell");
    am->CreateNtupleDColumn("edep_keV");
    am->FinishNtuple();

    auto* acc = G4AccumulableManager::Instance();
    for (auto* a : {&fN, &fSumEdep, &fSumScint, &fSumDet, &fSumDet2, &fSumExit, &fNInteracting, &fSumFluoEsc})
        acc->Register(*a);
}

void RunAction::SetRanges()
{
    const auto& cfg = SRDetConfig::Instance();
    const auto& geo = DetectorConstruction::Info();
    const G4double z0 = geo.zFront - 2 * mm, z1 = geo.zBack + 2 * mm;
    const G4double r = 1.05 * geo.matrixRadius;
    RangeH1(kH_EdepTotal, 1000, 0., cfg.histEmax);
    RangeH1(kH_EdepCore, 1000, 0., cfg.histEmax);
    RangeH1(kH_NScint, 500, 0., cfg.histNScintMax);
    RangeH1(kH_NDet, 500, 0., cfg.histNDetMax);
    RangeH1(kH_TDet, 500, 0., cfg.histTmax);
    RangeH1(kH_LambdaDet, 300, 250., 850.);
    RangeH1(kH_NReflDet, 500, 0., 2000.);
    RangeH1(kH_FirstZ, 600, z0, z1);
    RangeH1(kH_FluoEnergy, 4000, 0., std::max(100. * keV, cfg.histEmax));
    RangeH1(kH_NCellsHit, 200, 0., 200.);
    RangeH1(kH_LambdaScint, 300, 250., 850.);
    RangeH1(kH_BirthZDet, 600, z0, z1);
    RangeH2(kH2_DetXY, 300, -r, r);
    RangeH2(kH2_FirstXY, 300, -r, r);
}

void RunAction::BeginOfRunAction(const G4Run*)
{
    G4AccumulableManager::Instance()->Reset();
    SetRanges();
    auto* am = G4AnalysisManager::Instance();
    if (IsMaster()) {
        gStart = std::chrono::steady_clock::now();
        std::filesystem::create_directories(std::string(SRDetConfig::Instance().outDir));
    }
    am->OpenFile();
}

void RunAction::FillEvent(G4int eventID, const EventData& d)
{
    auto* am = G4AnalysisManager::Instance();
    const auto& cfg = SRDetConfig::Instance();
    G4double eTot = 0.;
    for (G4int k = 0; k < kNKinds; ++k) eTot += d.edep[k];
    G4int nHit = 0;
    G4double eMax = 0., eFirst = 0.;
    for (const auto& [cell, e] : d.cellEdep) {
        if (e > cfg.cellEdepThreshold) ++nHit;
        eMax = std::max(eMax, e);
        if (cell == d.firstCell) eFirst = e;
    }

    G4int c = 0;
    auto I = [&](G4int v) { am->FillNtupleIColumn(kNtEvents, c++, v); };
    auto D = [&](G4double v) { am->FillNtupleDColumn(kNtEvents, c++, v); };
    I(eventID);
    D(d.e0 / keV);
    I(d.pdg);
    D(d.x0 / mm);
    D(d.y0 / mm);
    I(d.firstProc);
    D(d.firstZ / mm);
    I(d.firstKind);
    I(d.firstCell);
    D(eTot / keV);
    for (G4int k : {kCore, kWall, kCoating, kMatrix, kWindow, kHousing, kCoupling}) D(d.edep[k] / keV);
    D((d.edep[kSensorWindow] + d.edep[kSensorActive]) / keV);
    D(d.edep[kSlab] / keV);
    D(d.edep[kWorld] / keV);
    D(d.eEscape / keV);
    I(nHit);
    D(eFirst / keV);
    D(eMax / keV);
    for (G4int i = 0; i < 8; ++i) I(d.proc[i]);
    I(d.nFluo);
    I(d.nFluoEscape);
    I(d.nScint);
    I(d.nCher);
    I(d.nCherPrimary);
    for (G4int i = 0; i < kOpNClasses; ++i) I(d.opClass[i]);
    for (G4int i = 0; i < kNFates; ++i) I(d.fate[i]);
    I(d.absBulkByKind[kCore]);
    I(d.absBulkByKind[kWall]);
    I(d.absBulkByKind[kCoupling]);
    G4int other = 0;
    for (G4int k = 0; k < kNKinds; ++k)
        if (k != kCore && k != kWall && k != kCoupling) other += d.absBulkByKind[k];
    I(other);
    I(d.coatRefl);
    I(d.coatAbs);
    I(d.coatTrans);
    I(d.nExit);
    I(d.detSameCell);
    I(d.detOtherCell);
    I(d.nOpRayleigh);
    I(d.firstBoundaryStatus);
    am->AddNtupleRow(kNtEvents);

    if (cfg.writeCellHits) {
        for (const auto& [cell, e] : d.cellEdep) {
            am->FillNtupleIColumn(kNtCells, 0, eventID);
            am->FillNtupleIColumn(kNtCells, 1, cell);
            am->FillNtupleDColumn(kNtCells, 2, e / keV);
            am->AddNtupleRow(kNtCells);
        }
    }

    am->FillH1(kH_EdepTotal, eTot);
    am->FillH1(kH_EdepCore, d.edep[kCore]);
    am->FillH1(kH_NScint, d.nScint);
    am->FillH1(kH_NDet, d.fate[kFateDetected]);
    am->FillH1(kH_NCellsHit, nHit);

    fN += 1.;
    fSumEdep += d.edep[kCore];
    fSumScint += d.nScint;
    fSumDet += d.fate[kFateDetected];
    fSumDet2 += std::pow(d.fate[kFateDetected], 2);
    fSumExit += d.nExit;
    fSumFluoEsc += d.nFluoEscape;
    if (d.firstProc != kNoInteraction) fNInteracting += 1.;
}

void RunAction::FillPhoton(const G4Track& track, const G4StepPoint* post, const PhotonInfo* info)
{
    auto* am = G4AnalysisManager::Instance();
    const auto& pos = post->GetPosition();
    const G4double t = post->GetGlobalTime();
    const G4double lambda = 1239.84193 / (track.GetTotalEnergy() / eV);
    am->FillH1(kH_TDet, t);
    am->FillH1(kH_LambdaDet, lambda);
    am->FillH1(kH_NReflDet, info->nRefl);
    am->FillH1(kH_BirthZDet, info->birthZ);
    am->FillH2(kH2_DetXY, pos.x(), pos.y());
    const G4double f = SRDetConfig::Instance().photonFraction;
    if (f > 0 && (f >= 1 || G4UniformRand() < f)) {
        const auto* ev = G4EventManager::GetEventManager()->GetConstCurrentEvent();
        am->FillNtupleIColumn(kNtPhotons, 0, ev ? ev->GetEventID() : -1);
        am->FillNtupleDColumn(kNtPhotons, 1, pos.x() / mm);
        am->FillNtupleDColumn(kNtPhotons, 2, pos.y() / mm);
        am->FillNtupleDColumn(kNtPhotons, 3, t / ns);
        am->FillNtupleDColumn(kNtPhotons, 4, lambda);
        am->FillNtupleIColumn(kNtPhotons, 5, info->nRefl);
        am->FillNtupleIColumn(kNtPhotons, 6, info->birthCell);
        am->FillNtupleIColumn(kNtPhotons, 7, info->exitCell);
        am->FillNtupleDColumn(kNtPhotons, 8, info->birthZ / mm);
        am->FillNtupleIColumn(kNtPhotons, 9, info->nCoatRefl);
        am->AddNtupleRow(kNtPhotons);
    }
}

void RunAction::EndOfRunAction(const G4Run* run)
{
    G4AccumulableManager::Instance()->Merge();
    auto* am = G4AnalysisManager::Instance();
    am->Write();
    am->CloseFile();
    if (!IsMaster()) return;

    const G4double n = std::max(1., fN.GetValue());
    const G4double meanDet = fSumDet.GetValue() / n;
    const G4double varDet = std::max(0., fSumDet2.GetValue() / n - meanDet * meanDet);
    const G4double secs = std::chrono::duration<G4double>(std::chrono::steady_clock::now() - gStart).count();
    std::ostringstream js;
    js << std::setprecision(8) << "{\"run\": " << run->GetRunID() << ", \"events\": " << fN.GetValue()
       << ", \"interacting_fraction\": " << fNInteracting.GetValue() / n
       << ", \"mean_edep_core_keV\": " << fSumEdep.GetValue() / n / keV
       << ", \"mean_n_scint\": " << fSumScint.GetValue() / n << ", \"mean_n_exit\": " << fSumExit.GetValue() / n
       << ", \"mean_n_det\": " << meanDet << ", \"rms_n_det\": " << std::sqrt(varDet)
       << ", \"fluo_escape_per_event\": " << fSumFluoEsc.GetValue() / n << ", \"wall_time_s\": " << secs
       << ", \"yield_scale\": " << SRDetConfig::Instance().yieldScale << "}";
    G4cout << "[srdet] SUMMARY " << js.str() << G4endl;
    std::ofstream(std::string(SRDetConfig::Instance().outDir) + "/run_summary.json") << js.str() << "\n";
}
