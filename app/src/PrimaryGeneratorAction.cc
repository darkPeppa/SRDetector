#include "PrimaryGeneratorAction.hh"

#include "Config.hh"
#include "DetectorConstruction.hh"
#include "Materials.hh"

#include "G4Event.hh"
#include "G4GeneralParticleSource.hh"
#include "G4GenericMessenger.hh"
#include "G4Material.hh"
#include "G4MaterialPropertiesTable.hh"
#include "G4OpticalPhoton.hh"
#include "G4PhysicalConstants.hh"
#include "G4PrimaryParticle.hh"
#include "G4PrimaryVertex.hh"
#include "G4SystemOfUnits.hh"
#include "Randomize.hh"

#include <algorithm>
#include <cmath>

PrimaryGeneratorAction::PrimaryGeneratorAction() : fGPS(new G4GeneralParticleSource())
{
    fMessenger = new G4GenericMessenger(this, "/srdet/gun/", "Primary source");
    fMessenger->DeclareProperty("mode", fMode, "gps | optical").SetCandidates("gps optical");
    // G4GenericMessenger matches properties by the last path element, so sub-directories
    // need their own messenger
    fOptMessenger = new G4GenericMessenger(this, "/srdet/gun/opt/", "Optical photon gun");
    fOptMessenger->DeclareProperty("n", fNPhotons, "optical photons per event");
    fOptMessenger->DeclarePropertyWithUnit("energy", "eV", fEnergy, "photon energy, 0 = emission spectrum");
    fOptMessenger->DeclarePropertyWithUnit("z", "mm", fZ, "emission depth (0 = channel centre)");
    fOptMessenger->DeclareProperty("zUniform", fZUniform, "uniform emission along the channel");
    fOptMessenger->DeclareProperty("rUniform", fRUniform, "uniform over the core cross-section");
    fOptMessenger->DeclarePropertyWithUnit("theta", "deg", fTheta, "fixed polar angle to +z, < 0 isotropic");
    fOptMessenger->DeclareProperty("absolute", fAbsolute, "use opt/pos and opt/dir");
    fOptMessenger->DeclarePropertyWithUnit("pos", "mm", fPos, "absolute start position");
    fOptMessenger->DeclareProperty("dir", fDir, "absolute direction");
}

PrimaryGeneratorAction::~PrimaryGeneratorAction()
{
    delete fGPS;
    delete fMessenger;
    delete fOptMessenger;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event)
{
    if (fMode == "optical") GenerateOptical(event);
    else fGPS->GeneratePrimaryVertex(event);
}

G4double PrimaryGeneratorAction::SampleEmission()
{
    if (fCdf.empty()) {
        const auto& cfg = SRDetConfig::Instance();
        auto* mat = G4Material::GetMaterial(cfg.mode == "slab" ? cfg.slabMaterial : cfg.coreMaterial, false);
        auto* mpt = mat ? mat->GetMaterialPropertiesTable() : nullptr;
        auto* pv = mpt ? mpt->GetProperty("SCINTILLATIONCOMPONENT1") : nullptr;
        if (!pv) {
            G4Exception("PrimaryGeneratorAction", "SRDet060", FatalException,
                        "optical gun: core material has no emission spectrum, set /srdet/gun/opt/energy");
        }
        G4double acc = 0.;
        for (std::size_t i = 0; i < pv->GetVectorLength(); ++i) {
            if (i > 0) acc += 0.5 * ((*pv)[i] + (*pv)[i - 1]) * (pv->Energy(i) - pv->Energy(i - 1));
            fCdfE.push_back(pv->Energy(i));
            fCdf.push_back(acc);
        }
        for (auto& c : fCdf) c /= acc;
    }
    const G4double u = G4UniformRand();
    auto it = std::lower_bound(fCdf.begin(), fCdf.end(), u);
    const std::size_t i = std::clamp<std::size_t>(it - fCdf.begin(), 1, fCdf.size() - 1);
    const G4double f = (u - fCdf[i - 1]) / std::max(1e-12, fCdf[i] - fCdf[i - 1]);
    return fCdfE[i - 1] + f * (fCdfE[i] - fCdfE[i - 1]);
}

void PrimaryGeneratorAction::GenerateOptical(G4Event* event)
{
    const auto& geo = DetectorConstruction::Info();
    G4ThreeVector centre;
    if (geo.centralCell >= 0) {
        const auto& c = geo.cells[geo.centralCell];
        centre = G4ThreeVector(c.x, c.y, 0);
    }
    for (G4int i = 0; i < fNPhotons; ++i) {
        G4ThreeVector pos, dir;
        if (fAbsolute) {
            pos = fPos;
            dir = fDir.unit();
        } else {
            // position inside the core of the central cell
            G4double x = 0, y = 0;
            if (fRUniform) {
                // circle of radius r, or flat-top hexagon of apothem r (corners on +-x)
                const G4double r = geo.coreRadius * 0.999;
                const G4double rx = geo.hexChannel ? 2 * r / std::sqrt(3.) : r;
                auto inside = [&](G4double px, G4double py) {
                    if (!geo.hexChannel) return px * px + py * py <= r * r;
                    return std::abs(py) <= r && std::abs(px) * std::sqrt(3.) / 2 + std::abs(py) / 2 <= r;
                };
                do {
                    x = (2 * G4UniformRand() - 1) * rx;
                    y = (2 * G4UniformRand() - 1) * r;
                } while (!inside(x, y));
            }
            const G4double halfL = 0.5 * geo.length * 0.9999;
            const G4double z = fZUniform ? (2 * G4UniformRand() - 1) * halfL : std::clamp(fZ, -halfL, halfL);
            pos = centre + G4ThreeVector(x, y, z);
            const G4double phi = twopi * G4UniformRand();
            const G4double cost = fTheta >= 0 ? std::cos(fTheta) : 2 * G4UniformRand() - 1;
            const G4double sint = std::sqrt(std::max(0., 1 - cost * cost));
            dir = G4ThreeVector(sint * std::cos(phi), sint * std::sin(phi), cost);
        }
        const G4double e = fEnergy > 0 ? fEnergy : SampleEmission();

        auto* particle = new G4PrimaryParticle(G4OpticalPhoton::Definition());
        particle->SetKineticEnergy(e);
        particle->SetMomentumDirection(dir);
        // random linear polarisation perpendicular to the momentum
        const G4ThreeVector perp = dir.orthogonal().unit();
        const G4ThreeVector perp2 = dir.cross(perp).unit();
        const G4double a = twopi * G4UniformRand();
        particle->SetPolarization(std::cos(a) * perp + std::sin(a) * perp2);

        auto* vertex = new G4PrimaryVertex(pos, 0.);
        vertex->SetPrimary(particle);
        event->AddPrimaryVertex(vertex);
    }
}
