#include "DetectorConstruction.hh"

#include "Config.hh"
#include "Materials.hh"
#include "OpticalSurfaces.hh"
#include "Sensors.hh"

#include "G4Box.hh"
#include "G4GeometryManager.hh"
#include "G4LogicalBorderSurface.hh"
#include "G4LogicalSkinSurface.hh"
#include "G4LogicalVolume.hh"
#include "G4LogicalVolumeStore.hh"
#include "G4Material.hh"
#include "G4OpticalSurface.hh"
#include "G4PVPlacement.hh"
#include "G4PhysicalConstants.hh"
#include "G4PhysicalVolumeStore.hh"
#include "G4Polyhedra.hh"
#include "G4Region.hh"
#include "G4RegionStore.hh"
#include "G4SolidStore.hh"
#include "G4SystemOfUnits.hh"
#include "G4Tubs.hh"
#include "G4VisAttributes.hh"

#ifdef G4LIB_USE_GDML
#include "G4GDMLParser.hh"
#endif

#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <set>

std::unordered_map<const G4LogicalVolume*, G4int> DetectorConstruction::fKinds;
GeometryInfo DetectorConstruction::fInfo;

namespace
{
constexpr G4double kTouchGap = 1. * nm;  // keeps touching volumes from being flagged as overlaps

void Fatal(const G4String& msg)
{
    G4Exception("DetectorConstruction", "SRDet040", FatalErrorInArgument, msg);
}
}  // namespace

DetectorConstruction::DetectorConstruction() : fMessenger(new ConfigMessenger()) {}

DetectorConstruction::~DetectorConstruction() { delete fMessenger; }

void DetectorConstruction::Cleanup()
{
    if (auto* region = G4RegionStore::GetInstance()->GetRegion("Detector", false)) {
        std::vector<G4LogicalVolume*> roots;
        auto it = region->GetRootLogicalVolumeIterator();
        for (std::size_t i = 0; i < region->GetNumberOfRootVolumes(); ++i, ++it) roots.push_back(*it);
        for (auto* lv : roots) region->RemoveRootLogicalVolume(lv, false);
    }
    G4GeometryManager::GetInstance()->OpenGeometry();
    G4PhysicalVolumeStore::GetInstance()->Clean();
    G4LogicalVolumeStore::GetInstance()->Clean();
    G4SolidStore::GetInstance()->Clean();
    G4LogicalSkinSurface::CleanSurfaceTable();
    G4LogicalBorderSurface::CleanSurfaceTable();
    fKinds.clear();
    fInfo = GeometryInfo();
}

G4VPhysicalVolume* DetectorConstruction::Construct()
{
    Cleanup();
    auto& cfg = SRDetConfig::Instance();
    G4VPhysicalVolume* world = (cfg.mode == "slab") ? BuildSlab() : BuildHoneycomb();
    Materials::ApplyOverrides();
    ExportGeometry(world);
    return world;
}

// A hexagonal prism (or hexagonal ring) with corners on the ±x axis.
G4VSolid* DetectorConstruction::Hex(const G4String& name, G4double aIn, G4double aOut, G4double halfZ)
{
    auto make = [&](G4double phi0) {
        const G4double z[2] = {-halfZ, halfZ};
        const G4double rin[2] = {aIn, aIn};
        const G4double rout[2] = {aOut, aOut};
        return new G4Polyhedra(name, phi0, twopi, 6, 2, z, rin, rout);
    };
    if (!fHexPhiChecked) {
        // G4Polyhedra radii are apothems; verify (once) that phiStart = 0 puts a corner on +x,
        // otherwise rotate by 30 deg. A point at 0.99 * circumradius on +x is inside only if
        // a corner points along +x.
        auto* probe = make(0.);
        const G4double rc = aOut / std::cos(pi / 6);
        fHexPhi0 = (probe->Inside(G4ThreeVector(0.99 * rc, 0, 0)) == kOutside) ? pi / 6 : 0.;
        delete probe;
        fHexPhiChecked = true;
        G4cout << "[srdet] G4Polyhedra phiStart for flat-top hexagons: " << fHexPhi0 / deg << " deg" << G4endl;
    }
    return make(fHexPhi0);
}

G4VPhysicalVolume* DetectorConstruction::BuildSlab()
{
    const auto& cfg = SRDetConfig::Instance();
    auto* worldMat = Materials::Get(cfg.worldMaterial);
    const G4double hz = cfg.slabThickness / 2 + cfg.worldMargin;
    const G4double hxy = cfg.slabHalfXY + cfg.worldMargin;
    auto* worldLV = new G4LogicalVolume(new G4Box("World", hxy, hxy, hz), worldMat, "World");
    auto* worldPV = new G4PVPlacement(nullptr, {}, worldLV, "World", nullptr, false, 0);
    auto* slabLV = new G4LogicalVolume(new G4Box("Slab", cfg.slabHalfXY, cfg.slabHalfXY, cfg.slabThickness / 2),
                                       Materials::Get(cfg.slabMaterial), "Slab");
    new G4PVPlacement(nullptr, {}, slabLV, "Slab", worldLV, false, 0, cfg.checkOverlaps);
    Register(worldLV, kWorld);
    Register(slabLV, kSlab);
    worldLV->SetVisAttributes(G4VisAttributes::GetInvisible());

    auto* region = G4RegionStore::GetInstance()->FindOrCreateRegion("Detector");
    region->AddRootLogicalVolume(slabLV);

    fInfo.length = cfg.slabThickness;
    fInfo.zFront = -cfg.slabThickness / 2;
    fInfo.zBack = cfg.slabThickness / 2;
    fInfo.matrixRadius = cfg.slabHalfXY;
    return worldPV;
}

G4VPhysicalVolume* DetectorConstruction::BuildHoneycomb()
{
    const auto& cfg = SRDetConfig::Instance();
    const G4bool checkOv = cfg.checkOverlaps;
    const CoatingSpec& coat = OpticalSurfaces::Spec(cfg.coating);
    const SensorSpec& sensor = Sensors::Get(cfg.sensor);

    // ---------------- derived cell dimensions
    const G4double L = cfg.length;
    const G4double apothem = cfg.pitch / 2 - kTouchGap;
    const G4double rc = cfg.pitch / std::sqrt(3.);  // hex circumradius
    const G4double rCore = cfg.channelDiameter / 2;
    const G4bool hexChannel = (cfg.channelShape == "hex");
    const G4bool coatVolume = coat.needsVolume && cfg.coatingThickness > 0;
    const G4double tCoat = coatVolume ? cfg.coatingThickness : 0.;
    const G4double wallMin = cfg.pitch - cfg.channelDiameter - 2 * tCoat;
    if (cfg.coating == "air_gap" && !coatVolume) Fatal("coating air_gap needs coatingThickness > 0");
    if (wallMin <= 2 * kTouchGap) {
        G4ExceptionDescription ed;
        ed << "Cell does not fit: pitch " << cfg.pitch / um << " um < channel " << cfg.channelDiameter / um
           << " um + 2 x coating " << tCoat / um << " um";
        Fatal(ed.str());
    }

    G4double rMatrix = cfg.detectorRadius;
    G4bool withHousing = cfg.housingThickness > 0;
    if (cfg.mode == "unit") {
        rMatrix = rc + 1. * um;
        withHousing = false;
    } else if (cfg.mode == "cluster7") {
        rMatrix = cfg.pitch + rc + 1. * um;
        withHousing = false;
    } else if (cfg.mode != "full") {
        Fatal("unknown geometry mode " + cfg.mode);
    }
    const G4double tHous = withHousing ? cfg.housingThickness : 0.;

    // ---------------- z stack
    const G4double tWin = cfg.windowThickness;
    const G4double tCpl = cfg.couplingThickness;
    const G4double tSW = (cfg.sensorWindowThickness >= 0 ? cfg.sensorWindowThickness : sensor.windowThickness) *
                         (sensor.windowMaterial.empty() && cfg.sensorWindowThickness < 0 ? 0. : 1.);
    const G4String swMatName = sensor.windowMaterial.empty() ? G4String("Borosilicate") : sensor.windowMaterial;
    const G4double tAct = cfg.sensorActiveThickness;
    const G4double zFront = -L / 2 - tWin;
    const G4double zCpl0 = L / 2, zSW0 = zCpl0 + tCpl, zAct0 = zSW0 + tSW, zBack = zAct0 + tAct;

    // ---------------- materials
    auto* worldMat = Materials::Get(cfg.worldMaterial);
    auto* wallMat = Materials::Get(cfg.wallMaterial);
    auto* rimMat = Materials::Get(cfg.matrixMaterial.empty() ? cfg.wallMaterial : cfg.matrixMaterial);
    auto* coreMat = Materials::Get(cfg.coreMaterial);
    G4Material* coatMat = coatVolume ? Materials::Get(cfg.coatingMaterial.empty() ? coat.defaultMaterial
                                                                                  : cfg.coatingMaterial)
                                     : nullptr;

    // ---------------- world + housing
    const G4double hz = std::max(std::abs(zFront), zBack + tHous) + cfg.worldMargin;
    const G4double hxy = rMatrix + tHous + cfg.worldMargin;
    auto* worldLV = new G4LogicalVolume(new G4Box("World", hxy, hxy, hz), worldMat, "World");
    auto* worldPV = new G4PVPlacement(nullptr, {}, worldLV, "World", nullptr, false, 0);
    worldLV->SetVisAttributes(G4VisAttributes::GetInvisible());
    Register(worldLV, kWorld);

    auto* region = G4RegionStore::GetInstance()->FindOrCreateRegion("Detector");

    G4LogicalVolume* motherLV = worldLV;
    G4VPhysicalVolume* motherPV = worldPV;
    G4double zOff = 0.;  // offset of the detector frame inside the mother
    if (withHousing) {
        const G4double hzH = (zBack + tHous - zFront) / 2;
        const G4double zc = (zBack + tHous + zFront) / 2;
        auto* housLV = new G4LogicalVolume(new G4Tubs("Housing", 0, rMatrix + tHous, hzH, 0, twopi),
                                           Materials::Get(cfg.housingMaterial), "Housing");
        motherPV = new G4PVPlacement(nullptr, {0, 0, zc}, housLV, "Housing", worldLV, false, 0, checkOv);
        housLV->SetVisAttributes(G4VisAttributes(G4Colour(0.6, 0.6, 0.6, 0.15)));
        Register(housLV, kHousing);
        region->AddRootLogicalVolume(housLV);
        motherLV = housLV;
        zOff = -zc;
    }

    auto placeDisc = [&](const G4String& name, G4Material* mat, G4double z0, G4double t, G4int kind,
                         const G4Colour& col) -> std::pair<G4LogicalVolume*, G4VPhysicalVolume*> {
        if (t <= 0) return {nullptr, nullptr};
        auto* lv = new G4LogicalVolume(new G4Tubs(name, 0, rMatrix, t / 2, 0, twopi), mat, name);
        auto* pv = new G4PVPlacement(nullptr, {0, 0, z0 + t / 2 + zOff}, lv, name, motherLV, false, 0, checkOv);
        lv->SetVisAttributes(G4VisAttributes(col));
        Register(lv, kind);
        if (!withHousing) region->AddRootLogicalVolume(lv);
        return {lv, pv};
    };

    [[maybe_unused]] auto [winLV, winPV] = placeDisc("Window", Materials::Get(cfg.windowMaterial), zFront, tWin, kWindow,
                                    G4Colour(0.8, 0.8, 1.0, 0.3));
    [[maybe_unused]] auto [matLV, matPV] = placeDisc("Matrix", rimMat, -L / 2, L, kMatrix, G4Colour(0.3, 0.8, 0.3, 0.1));
    [[maybe_unused]] auto [cplLV, cplPV] = placeDisc("Coupling", Materials::Get(cfg.couplingMaterial), zCpl0, tCpl, kCoupling,
                                    G4Colour(1, 1, 0, 0.3));
    [[maybe_unused]] auto [swLV, swPV] = placeDisc("SensorWindow", Materials::Get(swMatName), zSW0, tSW, kSensorWindow,
                                  G4Colour(0.7, 0.7, 1, 0.3));
    [[maybe_unused]] auto [actLV, actPV] = placeDisc("SensorActive", Materials::Get("G4_Si"), zAct0, tAct, kSensorActive,
                                    G4Colour(0.2, 0.2, 0.8, 0.8));
    if (!actLV) Fatal("sensorActiveThickness must be > 0");

    // ---------------- one honeycomb cell (logical volume shared by all copies)
    auto* cellLV = new G4LogicalVolume(Hex("Cell", 0., apothem, L / 2), wallMat, "Cell");
    cellLV->SetVisAttributes(G4VisAttributes(G4Colour(0.5, 0.5, 0.5, 0.3)));
    Register(cellLV, kWall);

    G4VSolid* coreSolid = hexChannel ? Hex("Core", 0., rCore, L / 2)
                                     : static_cast<G4VSolid*>(new G4Tubs("Core", 0., rCore, L / 2, 0, twopi));
    auto* coreLV = new G4LogicalVolume(coreSolid, coreMat, "Core");
    coreLV->SetVisAttributes(G4VisAttributes(G4Colour(0.1, 0.9, 0.1, 0.6)));
    Register(coreLV, kCore);
    auto* corePV = new G4PVPlacement(nullptr, {}, coreLV, "Core", cellLV, false, 0, checkOv);

    G4VPhysicalVolume* coatPV = nullptr;
    if (coatVolume) {
        const G4double r0 = rCore, r1 = rCore + tCoat;  // coating touches the core: no gap
        G4VSolid* s = hexChannel ? Hex("Coating", r0, r1, L / 2)
                                 : static_cast<G4VSolid*>(new G4Tubs("Coating", r0, r1, L / 2, 0, twopi));
        auto* coatLV = new G4LogicalVolume(s, coatMat, "Coating");
        coatLV->SetVisAttributes(G4VisAttributes(G4Colour(0.9, 0.9, 0.2, 0.8)));
        Register(coatLV, kCoating);
        coatPV = new G4PVPlacement(nullptr, {}, coatLV, "Coating", cellLV, false, 0, checkOv);
    }

    // ---------------- lattice
    std::vector<std::pair<G4int, G4int>> qr;
    if (cfg.mode == "unit") {
        qr = {{0, 0}};
    } else if (cfg.mode == "cluster7") {
        qr = {{0, 0}, {1, 0}, {0, 1}, {-1, 1}, {-1, 0}, {0, -1}, {1, -1}};
    } else {
        const G4int n = static_cast<G4int>(2. * rMatrix / cfg.pitch) + 2;  // covers |r| <= 1.58 R/pitch
        for (G4int q = -n; q <= n; ++q)
            for (G4int r = -n; r <= n; ++r) qr.emplace_back(q, r);
    }
    std::vector<G4VPhysicalVolume*> cellPVs;
    for (auto [q, r] : qr) {
        const G4double x = std::sqrt(3.) / 2 * cfg.pitch * q;
        const G4double y = cfg.pitch * (r + 0.5 * q);
        if (std::hypot(x, y) + rc > rMatrix - 0.5 * um) continue;
        const G4int copy = static_cast<G4int>(fInfo.cells.size());
        if (q == 0 && r == 0) fInfo.centralCell = copy;
        fInfo.cells.push_back({q, r, x, y});
        cellPVs.push_back(new G4PVPlacement(nullptr, {x, y, 0}, cellLV, "Cell", matLV, false, copy, checkOv));
    }
    if (cellPVs.empty()) Fatal("no honeycomb cell fits into the matrix radius");
    if (cellPVs.size() > 2000000)
        G4cout << "[srdet] WARNING: " << cellPVs.size() << " cells - memory hungry geometry" << G4endl;

    // ---------------- optical surfaces
    if (coat.surfaceOnCore) {
        auto* surf = OpticalSurfaces::Make(cfg.coating, "Coating_" + cfg.coating);
        if (surf) {
            if (coatPV) {
                new G4LogicalBorderSurface("CoreToCoating", corePV, coatPV, surf);
            } else {
                // surface-only coating: one border surface per cell (all share the same core PV)
                for (auto* cpv : cellPVs) new G4LogicalBorderSurface("CoreToWall", corePV, cpv, surf);
            }
        }
    }
    if (cfg.entranceCoating != "none") {
        auto* surf = OpticalSurfaces::Make(cfg.entranceCoating, "Entrance_" + cfg.entranceCoating);
        if (surf) {
            if (winLV) new G4LogicalSkinSurface("EntranceReflector", winLV, surf);
            else new G4LogicalBorderSurface("EntranceReflector", corePV, motherPV, surf);
        }
    }
    new G4LogicalSkinSurface("SensorSurface", actLV, OpticalSurfaces::MakeSensor(Sensors::Efficiency(sensor)));

    // ---------------- bookkeeping for actions / output
    fInfo.matrixRadius = rMatrix;
    fInfo.length = L;
    fInfo.pitch = cfg.pitch;
    fInfo.coreRadius = rCore;
    fInfo.hexChannel = hexChannel;
    fInfo.zFront = zFront;
    fInfo.zBack = zBack;
    fInfo.zSensor = zAct0;

    G4cout << "[srdet] honeycomb: mode=" << cfg.mode << " cells=" << cellPVs.size() << " pitch=" << cfg.pitch / um
           << " um core D=" << cfg.channelDiameter / um << " um coating=" << cfg.coating << " (" << tCoat / um
           << " um) min wall=" << wallMin / um << " um" << G4endl;
    return worldPV;
}

void DetectorConstruction::ExportGeometry(G4VPhysicalVolume* world)
{
    const auto& cfg = SRDetConfig::Instance();
    std::filesystem::create_directories(std::string(cfg.outDir));
    const std::string dir = cfg.outDir;

    const G4double cellArea = std::sqrt(3.) / 2 * cfg.pitch * cfg.pitch;
    const G4double coreArea = (cfg.channelShape == "hex") ? std::sqrt(3.) / 2 * std::pow(cfg.channelDiameter, 2)
                                                          : pi * std::pow(cfg.channelDiameter / 2, 2);
    std::ofstream out(dir + "/geometry.json");
    out << std::setprecision(10) << "{\n"
        << "  \"mode\": \"" << cfg.mode << "\",\n"
        << "  \"length_mm\": " << fInfo.length / mm << ",\n"
        << "  \"matrix_radius_mm\": " << fInfo.matrixRadius / mm << ",\n"
        << "  \"pitch_mm\": " << cfg.pitch / mm << ",\n"
        << "  \"channel_diameter_mm\": " << cfg.channelDiameter / mm << ",\n"
        << "  \"channel_shape\": \"" << cfg.channelShape << "\",\n"
        << "  \"coating\": \"" << cfg.coating << "\",\n"
        << "  \"coating_thickness_um\": " << cfg.coatingThickness / um << ",\n"
        << "  \"wall_material\": \"" << cfg.wallMaterial << "\",\n"
        << "  \"core_material\": \"" << cfg.coreMaterial << "\",\n"
        << "  \"sensor\": \"" << cfg.sensor << "\",\n"
        << "  \"core_fill_factor\": " << (cfg.mode == "slab" ? 1. : coreArea / cellArea) << ",\n"
        << "  \"z_front_mm\": " << fInfo.zFront / mm << ",\n"
        << "  \"z_back_mm\": " << fInfo.zBack / mm << ",\n"
        << "  \"z_sensor_mm\": " << fInfo.zSensor / mm << ",\n"
        << "  \"central_cell\": " << fInfo.centralCell << ",\n";
    if (cfg.mode != "slab") {
        const auto eff = Sensors::Efficiency(Sensors::Get(cfg.sensor));
        const auto& grid = Materials::EnergyGrid();
        out << "  \"sensor_efficiency\": {\"energy_eV\": [";
        for (std::size_t i = 0; i < grid.size(); ++i) out << (i ? ", " : "") << grid[i] / eV;
        out << "], \"efficiency\": [";
        for (std::size_t i = 0; i < eff.size(); ++i) out << (i ? ", " : "") << eff[i];
        out << "]},\n";
    }
    out
        << "  \"n_cells\": " << fInfo.cells.size() << ",\n"
        << "  \"cells\": [";
    for (std::size_t i = 0; i < fInfo.cells.size(); ++i) {
        const auto& c = fInfo.cells[i];
        out << (i ? "," : "") << (i % 4 ? " " : "\n    ") << "[" << c.q << "," << c.r << "," << c.x / mm << ","
            << c.y / mm << "]";
    }
    out << "\n  ]\n}\n";

    std::set<G4Material*> used;
    for (auto* lv : *G4LogicalVolumeStore::GetInstance()) used.insert(lv->GetMaterial());
    Materials::ExportJson(dir + "/materials.json", std::vector<G4Material*>(used.begin(), used.end()));

#ifdef G4LIB_USE_GDML
    if (cfg.writeGDML) {
        std::filesystem::remove(dir + "/geometry.gdml");
        G4GDMLParser parser;
        parser.Write(dir + "/geometry.gdml", world, false);
    }
#else
    (void)world;
#endif
}
