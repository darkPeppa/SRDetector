#include "Config.hh"

#include "G4GenericMessenger.hh"
#include "G4UIcommand.hh"
#include "G4UImessenger.hh"
#include "G4UIparameter.hh"
#include "G4UnitsTable.hh"

#include <functional>
#include <map>
#include <sstream>

SRDetConfig& SRDetConfig::Instance()
{
    static SRDetConfig instance;
    return instance;
}

namespace
{
std::vector<std::string> Split(const G4String& s)
{
    std::istringstream is(s);
    std::vector<std::string> out;
    std::string tok;
    while (is >> tok) out.push_back(tok);
    return out;
}

void Bad(const G4String& cmd, const G4String& args, const G4String& usage)
{
    G4ExceptionDescription ed;
    ed << cmd << ": cannot parse '" << args << "'. Usage: " << cmd << " " << usage;
    G4Exception("ConfigMessenger", "SRDet001", FatalErrorInArgument, ed);
}

template <typename T>
void Local(G4GenericMessenger::Command& c, T)
{
    // detector configuration lives on the master only
    c.SetToBeBroadcasted(false);
    c.SetStates(G4State_PreInit, G4State_Idle);
}
}  // namespace

namespace
{
void MatSetConst(const G4String& args)
{
    auto t = Split(args);
    if (t.size() != 3) Bad("/srdet/mat/setConst", args, "<material> <KEY> <value>");
    SRDetConfig::Instance().materialOverrides.push_back({t[0], "setConst", t[1], std::stod(t[2]), ""});
}

void MatSetAbsLength(const G4String& args)
{
    auto t = Split(args);
    if (t.size() != 3) Bad("/srdet/mat/setAbsLength", args, "<material> <value> <unit>");
    const G4double v = std::stod(t[1]) * G4UIcommand::ValueOf(t[2].c_str());
    SRDetConfig::Instance().materialOverrides.push_back({t[0], "setAbsLength", "ABSLENGTH", v, ""});
}

void MatLoadProperty(const G4String& args)
{
    auto t = Split(args);
    if (t.size() != 3) Bad("/srdet/mat/loadProperty", args, "<material> <KEY> <file>");
    SRDetConfig::Instance().materialOverrides.push_back({t[0], "loadProperty", t[1], 0., t[2]});
}

void MatBirks(const G4String& args)
{
    auto t = Split(args);
    if (t.size() != 2) Bad("/srdet/mat/birks", args, "<material> <kB in mm/MeV>");
    const G4double v = std::stod(t[1]) * mm / MeV;
    SRDetConfig::Instance().materialOverrides.push_back({t[0], "birks", "", v, ""});
}

void MatNoRindex(const G4String& args)
{
    auto t = Split(args);
    if (t.size() != 1) Bad("/srdet/mat/noRindex", args, "<material>");
    SRDetConfig::Instance().materialOverrides.push_back({t[0], "noRindex", "", 0., ""});
}

void MatDensity(const G4String& args)
{
    auto t = Split(args);
    if (t.size() != 3) Bad("/srdet/mat/density", args, "<material> <value> <unit>");
    const G4double v = std::stod(t[1]) * G4UIcommand::ValueOf(t[2].c_str());
    SRDetConfig::Instance().materialOverrides.push_back({t[0], "density", "", v, ""});
}

// G4GenericMessenger methods only receive the first token, so the multi-argument
// material commands are plain G4UIcommands with explicit parameters.
class MaterialCommands : public G4UImessenger
{
  public:
    MaterialCommands()
    {
        Add("setConst", "Set a constant material property", {{"material", 's'}, {"key", 's'}, {"value", 'd'}},
            MatSetConst);
        Add("setAbsLength", "Constant absorption length", {{"material", 's'}, {"value", 'd'}, {"unit", 's'}},
            MatSetAbsLength);
        Add("loadProperty", "Load a property table: two columns, '# unit: nm' (default) or '# unit: eV'",
            {{"material", 's'}, {"key", 's'}, {"file", 's'}}, MatLoadProperty);
        Add("birks", "Birks constant in mm/MeV", {{"material", 's'}, {"kB", 'd'}}, MatBirks);
        Add("noRindex", "Remove RINDEX (optically opaque material)", {{"material", 's'}}, MatNoRindex);
        Add("density", "Override the density (applied when the material is built)",
            {{"material", 's'}, {"value", 'd'}, {"unit", 's'}}, MatDensity);
    }
    ~MaterialCommands() override
    {
        for (auto& [c, _] : fCmds) delete c;
    }
    void SetNewValue(G4UIcommand* cmd, G4String value) override { fCmds.at(cmd)(value); }

  private:
    void Add(const char* name, const char* guidance, std::vector<std::pair<const char*, char>> params,
             std::function<void(const G4String&)> fn)
    {
        auto* c = new G4UIcommand((G4String("/srdet/mat/") + name).c_str(), this);
        c->SetGuidance(guidance);
        for (auto [pname, type] : params) c->SetParameter(new G4UIparameter(pname, type, false));
        c->AvailableForStates(G4State_PreInit, G4State_Idle);
        c->SetToBeBroadcasted(false);
        fCmds[c] = std::move(fn);
    }
    std::map<G4UIcommand*, std::function<void(const G4String&)>> fCmds;
};
}  // namespace

ConfigMessenger::ConfigMessenger()
{
    auto& c = SRDetConfig::Instance();

    fGeom = new G4GenericMessenger(this, "/srdet/geom/", "Detector geometry (apply before /run/initialize)");
    auto L = [&](G4GenericMessenger::Command& cmd) { Local(cmd, 0); };

    L(fGeom->DeclareProperty("mode", c.mode, "full | cluster7 | unit | slab")
          .SetCandidates("full cluster7 unit slab"));
    L(fGeom->DeclarePropertyWithUnit("detectorRadius", "mm", c.detectorRadius, "Radius of the honeycomb matrix"));
    L(fGeom->DeclarePropertyWithUnit("length", "mm", c.length, "Channel length (z)"));
    L(fGeom->DeclarePropertyWithUnit("pitch", "mm", c.pitch, "Hex cell pitch (flat-to-flat)"));
    L(fGeom->DeclarePropertyWithUnit("channelDiameter", "mm", c.channelDiameter, "Scintillator core diameter"));
    L(fGeom->DeclareProperty("channelShape", c.channelShape, "circle | hex").SetCandidates("circle hex"));
    L(fGeom->DeclareProperty("wallMaterial", c.wallMaterial, "Honeycomb wall material"));
    L(fGeom->DeclareProperty("matrixMaterial", c.matrixMaterial, "Matrix rim material (default: wall)"));
    L(fGeom->DeclareProperty("coreMaterial", c.coreMaterial, "Scintillator in the channels"));
    L(fGeom->DeclarePropertyWithUnit("coatingThickness", "um", c.coatingThickness, "Coating layer thickness"));
    L(fGeom->DeclareProperty("coatingMaterial", c.coatingMaterial, "EM material of the coating layer"));
    L(fGeom->DeclareProperty("worldMaterial", c.worldMaterial, "World material"));
    L(fGeom->DeclareProperty("housingMaterial", c.housingMaterial, "Housing material"));
    L(fGeom->DeclarePropertyWithUnit("housingThickness", "mm", c.housingThickness, "Housing wall, 0 = none"));
    L(fGeom->DeclareProperty("windowMaterial", c.windowMaterial, "Entrance window material"));
    L(fGeom->DeclarePropertyWithUnit("windowThickness", "mm", c.windowThickness, "Entrance window, 0 = none"));
    L(fGeom->DeclareProperty("couplingMaterial", c.couplingMaterial, "Optical coupling to the sensor"));
    L(fGeom->DeclarePropertyWithUnit("couplingThickness", "mm", c.couplingThickness, "Coupling layer, 0 = none"));
    L(fGeom->DeclareProperty("sensor", c.sensor, "Photodetector type (see Sensors.hh)"));
    L(fGeom->DeclarePropertyWithUnit("sensorWindowThickness", "mm", c.sensorWindowThickness,
                                     "Sensor window, < 0 = catalogue value"));
    L(fGeom->DeclarePropertyWithUnit("sensorActiveThickness", "mm", c.sensorActiveThickness, "Sensor Si layer"));
    L(fGeom->DeclareProperty("slabMaterial", c.slabMaterial, "Slab mode: material"));
    L(fGeom->DeclarePropertyWithUnit("slabThickness", "mm", c.slabThickness, "Slab mode: thickness (z)"));
    L(fGeom->DeclarePropertyWithUnit("slabHalfXY", "mm", c.slabHalfXY, "Slab mode: half size in x,y"));
    L(fGeom->DeclarePropertyWithUnit("worldMargin", "mm", c.worldMargin, "Space around the detector"));
    L(fGeom->DeclareProperty("checkOverlaps", c.checkOverlaps, "Check overlaps at placement (slow for full)"));

    fOptics = new G4GenericMessenger(this, "/srdet/optics/", "Optical surfaces");
    L(fOptics->DeclareProperty("coating", c.coating, "Channel coating type (see OpticalSurfaces.hh)"));
    L(fOptics->DeclareProperty("coatingReflectivity", c.coatingReflectivity, "R for mirror/diffuse coatings (0..1)"));
    L(fOptics->DeclarePropertyWithUnit("coatingSigmaAlpha", "deg", c.coatingSigmaAlpha, "Micro-facet roughness"));
    L(fOptics->DeclarePropertyWithUnit("filmThickness", "um", c.filmThickness, "Thin-film coating thickness"));
    L(fOptics->DeclareProperty("entranceCoating", c.entranceCoating, "Optical surface on the entrance window"));

    fMat = new G4GenericMessenger(this, "/srdet/mat/", "Material property overrides");
    L(fMat->DeclareProperty("yieldScale", c.yieldScale, "Scale all scintillation yields (speed-up)"));

    fMatCmds = new MaterialCommands();

    fOut = new G4GenericMessenger(this, "/srdet/out/", "Output");
    L(fOut->DeclareProperty("dir", c.outDir, "Output directory (geometry.json, materials.json, summary)"));
    L(fOut->DeclareProperty("photonFraction", c.photonFraction, "Fraction of detected photons stored"));
    L(fOut->DeclareProperty("cellHits", c.writeCellHits, "Write per-cell deposits ntuple"));
    L(fOut->DeclarePropertyWithUnit("cellThreshold", "keV", c.cellEdepThreshold, "Hit threshold per cell"));
    L(fOut->DeclareProperty("gdml", c.writeGDML, "Export geometry.gdml"));
    L(fOut->DeclarePropertyWithUnit("histEmax", "keV", c.histEmax, "Upper edge of energy histograms"));
    L(fOut->DeclareProperty("histNScintMax", c.histNScintMax, "Upper edge of the N_scint histogram"));
    L(fOut->DeclareProperty("histNDetMax", c.histNDetMax, "Upper edge of the N_det histogram"));
    L(fOut->DeclarePropertyWithUnit("histTmax", "ns", c.histTmax, "Upper edge of the arrival time histogram"));
}

ConfigMessenger::~ConfigMessenger()
{
    delete fGeom;
    delete fOptics;
    delete fMat;
    delete fMatCmds;
    delete fOut;
}

