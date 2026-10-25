#include "EventAction.hh"

#include "Config.hh"
#include "RunAction.hh"

#include "G4AutoLock.hh"
#include "G4Event.hh"
#include "G4PrimaryParticle.hh"
#include "G4PrimaryVertex.hh"
#include "G4SystemOfUnits.hh"
#include "G4TrajectoryContainer.hh"
#include "G4VTrajectory.hh"
#include "G4VTrajectoryPoint.hh"

#include <algorithm>
#include <atomic>
#include <cstdio>
#include <fstream>
#include <sstream>

namespace
{
G4Mutex gTrackMutex = G4MUTEX_INITIALIZER;
std::atomic<G4int> gTrackEvents{0};

// One JSON line per event: {"evt":..,"e0_keV":..,"tracks":[{"id","parent","pdg","name","pts":[[x,y,z],..]}]}
void WriteTracks(const G4Event* event, const EventData& d)
{
    const auto& cfg = SRDetConfig::Instance();
    if (cfg.tracksEvents <= 0 || gTrackEvents >= cfg.tracksEvents) return;
    auto* tc = event->GetTrajectoryContainer();
    if (!tc) return;
    std::ostringstream js;
    js << "{\"evt\":" << event->GetEventID() << ",\"e0_keV\":" << d.e0 / keV << ",\"tracks\":[";
    G4bool first = true;
    G4int optical = 0;
    char buf[64];
    for (std::size_t i = 0; i < tc->entries(); ++i) {
        auto* t = (*tc)[i];
        if (t->GetParticleName() == "opticalphoton" && (optical++ % std::max(1, cfg.tracksOpticalEvery)) != 0) continue;
        js << (first ? "" : ",") << "{\"id\":" << t->GetTrackID() << ",\"parent\":" << t->GetParentID()
           << ",\"pdg\":" << t->GetPDGEncoding() << ",\"name\":\"" << t->GetParticleName() << "\",\"pts\":[";
        for (G4int j = 0; j < t->GetPointEntries(); ++j) {
            const auto& p = t->GetPoint(j)->GetPosition();
            std::snprintf(buf, sizeof(buf), "%s[%.4g,%.4g,%.4g]", j ? "," : "", p.x() / mm, p.y() / mm, p.z() / mm);
            js << buf;
        }
        js << "]}";
        first = false;
    }
    js << "]}\n";
    G4AutoLock lock(&gTrackMutex);
    if (gTrackEvents >= cfg.tracksEvents) return;  // another thread filled the quota meanwhile
    ++gTrackEvents;
    std::ofstream(std::string(cfg.outDir) + "/tracks.jsonl", std::ios::app) << js.str();
}
}  // namespace

void EventAction::BeginOfEventAction(const G4Event* event)
{
    fData = EventData();
    if (const auto* v = event->GetPrimaryVertex(0)) {
        fData.x0 = v->GetX0();
        fData.y0 = v->GetY0();
        if (const auto* p = v->GetPrimary(0)) {
            fData.e0 = p->GetKineticEnergy();
            fData.pdg = p->GetPDGcode();
        }
    }
}

void EventAction::EndOfEventAction(const G4Event* event)
{
    fRun->FillEvent(event->GetEventID(), fData);
    WriteTracks(event, fData);
}
