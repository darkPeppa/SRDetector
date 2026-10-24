#include "OpticalSurfaces.hh"

#include "Config.hh"
#include "Materials.hh"

#include "G4MaterialPropertiesTable.hh"
#include "G4OpticalSurface.hh"
#include "G4SystemOfUnits.hh"

#include <map>

namespace
{
using Table = std::vector<std::pair<G4double, G4double>>;  // (lambda nm, value)

// Linear interpolation of a wavelength table on the common energy grid.
std::vector<G4double> OnGrid(const Table& t)
{
    std::vector<G4double> out;
    for (auto e : Materials::EnergyGrid()) {
        const G4double l = Materials::hc_eVnm() / (e / eV);
        G4double v = t.front().second;
        if (l >= t.back().first) v = t.back().second;
        else
            for (std::size_t i = 1; i < t.size(); ++i)
                if (l <= t[i].first) {
                    const G4double f = std::max(0., (l - t[i - 1].first) / (t[i].first - t[i - 1].first));
                    v = t[i - 1].second + f * (t[i].second - t[i - 1].second);
                    break;
                }
        out.push_back(v);
    }
    return out;
}

std::vector<G4double> Const(G4double v) { return std::vector<G4double>(Materials::EnergyGrid().size(), v); }

// Complex refractive indices (n, k), approximate values:
//   Al: Rakic, Appl. Opt. 37 (1998) 5271;  Ag, Au: Johnson & Christy, PRB 6 (1972) 4370.
const Table kAl_n = {{300, 0.276}, {350, 0.37}, {400, 0.49}, {450, 0.62}, {500, 0.77}, {550, 0.96},
                     {600, 1.20}, {650, 1.47}, {700, 1.83}, {750, 2.40}, {800, 2.80}};
const Table kAl_k = {{300, 3.61}, {350, 4.25}, {400, 4.86}, {450, 5.47}, {500, 6.08}, {550, 6.69},
                     {600, 7.26}, {650, 7.79}, {700, 8.31}, {750, 8.62}, {800, 8.45}};
const Table kAg_n = {{300, 1.35}, {330, 0.80}, {350, 0.20}, {400, 0.05}, {450, 0.04}, {500, 0.05},
                     {550, 0.055}, {600, 0.06}, {650, 0.05}, {700, 0.04}, {800, 0.04}};
const Table kAg_k = {{300, 0.80}, {330, 0.45}, {350, 1.30}, {400, 2.10}, {450, 2.65}, {500, 3.09},
                     {550, 3.59}, {600, 4.00}, {650, 4.45}, {700, 4.84}, {800, 5.50}};
const Table kAu_n = {{300, 1.62}, {350, 1.63}, {400, 1.47}, {450, 1.38}, {500, 0.97}, {550, 0.43},
                     {600, 0.25}, {650, 0.17}, {700, 0.16}, {800, 0.16}};
const Table kAu_k = {{300, 1.90}, {350, 1.90}, {400, 1.95}, {450, 1.85}, {500, 1.87}, {550, 2.45},
                     {600, 3.00}, {650, 3.50}, {700, 3.95}, {800, 4.80}};

// Diffuse reflectance of thick white reflectors (typical literature values).
const Table kTiO2_R = {{350, 0.06}, {380, 0.10}, {400, 0.40}, {420, 0.80}, {450, 0.92}, {500, 0.94}, {800, 0.95}};
const Table kBaSO4_R = {{300, 0.92}, {350, 0.95}, {400, 0.97}, {800, 0.98}};
const Table kTeflon_R = {{300, 0.90}, {400, 0.96}, {500, 0.98}, {800, 0.98}};
// The REFLECTIVITY of the old code (1.0 .. 6.2 eV)
const Table kAlSimple_R = {{200, 0.82}, {250, 0.85}, {350, 0.88}, {549, 0.90}, {1240, 0.92}};

const std::map<G4String, CoatingSpec>& Catalogue()
{
    static const std::map<G4String, CoatingSpec> cat = {
        {"none", {"none", "bare channel, Fresnel/TIR on core-wall interface", false, false, ""}},
        {"air_gap", {"air_gap", "air layer between core and wall (TIR at n_core/1.0)", true, false, "Air"}},
        {"MgF2_film", {"MgF2_film", "thin MgF2 film (n=1.38) on the wall, coherent thin-film model", false, true, ""}},
        {"ideal", {"ideal", "perfect specular mirror R=1", true, true, "G4_Al"}},
        {"black", {"black", "perfect absorber R=0", true, true, "G4_C"}},
        {"mirror", {"mirror", "specular mirror, R = coatingReflectivity", true, true, "G4_Al"}},
        {"diffuse", {"diffuse", "Lambertian reflector, R = coatingReflectivity", true, true, "G4_TITANIUM_DIOXIDE"}},
        {"Al", {"Al", "aluminium, complex index (Rakic 1998)", true, true, "G4_Al"}},
        {"Ag", {"Ag", "silver, complex index (Johnson & Christy 1972)", true, true, "G4_Ag"}},
        {"Au", {"Au", "gold, complex index (Johnson & Christy 1972)", true, true, "G4_Au"}},
        {"Al_simple", {"Al_simple", "aluminium, legacy REFLECTIVITY(E), no angular dependence", true, true, "G4_Al"}},
        {"TiO2", {"TiO2", "TiO2 white paint (Lambertian, UV cut-off ~400 nm)", true, true, "G4_TITANIUM_DIOXIDE"}},
        {"BaSO4", {"BaSO4", "BaSO4 white paint (Lambertian)", true, true, "G4_BARIUM_SULFATE"}},
        {"Teflon", {"Teflon", "PTFE wrapping (Lambertian)", true, true, "G4_TEFLON"}},
        {"ESR_LUT", {"ESR_LUT", "3M ESR (Vikuiti), measured LUT, LUTDAVIS model", true, true, "G4_MYLAR"}},
        {"Teflon_LUT", {"Teflon_LUT", "Teflon tape, measured LUT, LUTDAVIS model", true, true, "G4_TEFLON"}},
        {"ESR_LUT_BGO", {"ESR_LUT_BGO", "VM2000/ESR in air, measured LUT (BGO crystal)", true, true, "G4_MYLAR"}},
        {"Tyvek_LUT", {"Tyvek_LUT", "Tyvek in air, measured LUT (BGO crystal)", true, true, "G4_POLYETHYLENE"}},
        {"TiO2_LUT", {"TiO2_LUT", "TiO2 paint in air, measured LUT (BGO crystal)", true, true, "G4_TITANIUM_DIOXIDE"}},
    };
    return cat;
}

void ApplyRoughness(G4OpticalSurface* s, G4MaterialPropertiesTable* mpt)
{
    const G4double sa = SRDetConfig::Instance().coatingSigmaAlpha;
    if (sa <= 0.) return;
    s->SetFinish(ground);
    s->SetSigmaAlpha(sa);
    // pure micro-facet (lobe) reflection, otherwise unified defaults to Lambertian
    mpt->AddProperty("SPECULARLOBECONSTANT", Materials::EnergyGrid(), Const(1.));
    mpt->AddProperty("SPECULARSPIKECONSTANT", Materials::EnergyGrid(), Const(0.));
    mpt->AddProperty("BACKSCATTERCONSTANT", Materials::EnergyGrid(), Const(0.));
}

G4OpticalSurface* Metal(const G4String& label, const std::vector<G4double>* refl, const Table* n, const Table* k)
{
    auto* s = new G4OpticalSurface(label, unified, polished, dielectric_metal);
    auto* mpt = new G4MaterialPropertiesTable();
    if (refl) mpt->AddProperty("REFLECTIVITY", Materials::EnergyGrid(), *refl);
    if (n && k) {
        mpt->AddProperty("REALRINDEX", Materials::EnergyGrid(), OnGrid(*n));
        mpt->AddProperty("IMAGINARYRINDEX", Materials::EnergyGrid(), OnGrid(*k));
    }
    mpt->AddProperty("EFFICIENCY", Materials::EnergyGrid(), Const(0.));
    ApplyRoughness(s, mpt);
    s->SetMaterialPropertiesTable(mpt);
    return s;
}

G4OpticalSurface* Paint(const G4String& label, const std::vector<G4double>& refl)
{
    auto* s = new G4OpticalSurface(label, unified, groundfrontpainted, dielectric_dielectric);
    auto* mpt = new G4MaterialPropertiesTable();
    mpt->AddProperty("REFLECTIVITY", Materials::EnergyGrid(), refl);
    s->SetMaterialPropertiesTable(mpt);
    return s;
}

G4OpticalSurface* Lut(const G4String& label, G4OpticalSurfaceModel model, G4SurfaceType type,
                      G4OpticalSurfaceFinish finish)
{
    // model must be set before the finish: SetFinish() loads the LUT file
    auto* s = new G4OpticalSurface(label);
    s->SetModel(model);
    s->SetType(type);
    s->SetFinish(finish);
    return s;
}
}  // namespace

const CoatingSpec& OpticalSurfaces::Spec(const G4String& name)
{
    const auto& cat = Catalogue();
    auto it = cat.find(name);
    if (it == cat.end()) {
        G4ExceptionDescription ed;
        ed << "Unknown coating '" << name << "'. Available:";
        for (auto& n : Names()) ed << " " << n;
        G4Exception("OpticalSurfaces::Spec", "SRDet030", FatalErrorInArgument, ed);
    }
    return it->second;
}

std::vector<G4String> OpticalSurfaces::Names()
{
    std::vector<G4String> v;
    for (const auto& [k, _] : Catalogue()) v.push_back(k);
    return v;
}

G4OpticalSurface* OpticalSurfaces::Make(const G4String& name, const G4String& label)
{
    Spec(name);  // validates
    const auto& cfg = SRDetConfig::Instance();
    if (cfg.coatingReflectivity < 0 || cfg.coatingReflectivity > 1)
        G4Exception("OpticalSurfaces::Make", "SRDet031", FatalErrorInArgument, "coatingReflectivity must be in [0, 1]");
    if (name == "none" || name == "air_gap") return nullptr;
    if (name == "ideal") { auto r = Const(1.); return Metal(label, &r, nullptr, nullptr); }
    if (name == "black") { auto r = Const(0.); return Metal(label, &r, nullptr, nullptr); }
    if (name == "mirror") { auto r = Const(cfg.coatingReflectivity); return Metal(label, &r, nullptr, nullptr); }
    if (name == "Al_simple") { auto r = OnGrid(kAlSimple_R); return Metal(label, &r, nullptr, nullptr); }
    if (name == "Al") return Metal(label, nullptr, &kAl_n, &kAl_k);
    if (name == "Ag") return Metal(label, nullptr, &kAg_n, &kAg_k);
    if (name == "Au") return Metal(label, nullptr, &kAu_n, &kAu_k);
    if (name == "diffuse") return Paint(label, Const(cfg.coatingReflectivity));
    if (name == "TiO2") return Paint(label, OnGrid(kTiO2_R));
    if (name == "BaSO4") return Paint(label, OnGrid(kBaSO4_R));
    if (name == "Teflon") return Paint(label, OnGrid(kTeflon_R));
    if (name == "ESR_LUT") return Lut(label, DAVIS, dielectric_LUTDAVIS, PolishedESR_LUT);
    if (name == "Teflon_LUT") return Lut(label, DAVIS, dielectric_LUTDAVIS, PolishedTeflon_LUT);
    if (name == "ESR_LUT_BGO") return Lut(label, LUT, dielectric_LUT, polishedvm2000air);
    if (name == "Tyvek_LUT") return Lut(label, LUT, dielectric_LUT, polishedtyvekair);
    if (name == "TiO2_LUT") return Lut(label, LUT, dielectric_LUT, polishedtioair);
    if (name == "MgF2_film") {
        auto* s = new G4OpticalSurface(label, unified, polished, coated);
        auto* mpt = new G4MaterialPropertiesTable();
        mpt->AddProperty("COATEDRINDEX", Materials::EnergyGrid(), Const(1.38));
        mpt->AddConstProperty("COATEDTHICKNESS", cfg.filmThickness);
        mpt->AddConstProperty("COATEDFRUSTRATEDTRANSMISSION", 1);
        s->SetMaterialPropertiesTable(mpt);
        return s;
    }
    return nullptr;
}

G4OpticalSurface* OpticalSurfaces::MakeSensor(const std::vector<G4double>& efficiency)
{
    auto* s = new G4OpticalSurface("SensorSurface", unified, polished, dielectric_metal);
    auto* mpt = new G4MaterialPropertiesTable();
    mpt->AddProperty("REFLECTIVITY", Materials::EnergyGrid(), Const(0.));
    mpt->AddProperty("EFFICIENCY", Materials::EnergyGrid(), efficiency);
    s->SetMaterialPropertiesTable(mpt);
    return s;
}
