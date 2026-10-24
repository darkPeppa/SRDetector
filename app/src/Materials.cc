#include "Materials.hh"

#include "Config.hh"

#include "G4Element.hh"
#include "G4Material.hh"
#include "G4MaterialPropertiesTable.hh"
#include "G4NistManager.hh"
#include "G4SystemOfUnits.hh"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <functional>
#include <iomanip>
#include <map>
#include <sstream>

// -----------------------------------------------------------------------------
// Data sources (typical values; see docs/physics.md for the discussion of
// uncertainties). Refractive indices use a Cauchy form n = A + B/lambda^2
// (lambda in um) fitted to the quoted n at the emission peak, unless a
// Sellmeier fit is available (fused silica, Malitson 1965).
//
//  CsI(Tl): Saint-Gobain data sheet: 54 ph/keV, peak 550 nm, n(550)=1.79,
//           density 4.51 g/cm3; decay 0.68 us (64%) + 3.34 us (36%)
//           [Valentine et al., NIM A 325 (1993) 147]. Birks kB from Tretyak,
//           Astropart. Phys. 33 (2010) 40 (3.2e-3 g/MeV/cm2 -> 7.1e-3 mm/MeV).
//  CsI (pure): ~2 ph/keV at RT, 315 nm, 16 ns.
//  NaI(Tl): 38 ph/keV, 415 nm, n=1.85, 250 ns, 3.67 g/cm3.
//  LYSO(Ce): 33 ph/keV, 420 nm, n=1.82, 40 ns, 7.1 g/cm3 (Lu1.8Y0.2SiO5).
//  BGO:     8.2 ph/keV, 480 nm, n=2.15, 300 ns, 7.13 g/cm3.
//  GAGG(Ce): ~50 ph/keV, 530 nm, n=1.91, 90 ns, 6.63 g/cm3.
//  EJ-200 (PVT plastic): 10 ph/keV, 425 nm, n=1.58, 2.1 ns, kB = 0.126 mm/MeV.
//  LeadGlass_MCP: typical lead-silicate micro-channel-plate glass,
//           mass fractions PbO 51 %, SiO2 38 %, K2O 6 %, Na2O 2 %, BaO 2 %, Al2O3 1 %,
//           density 3.95 g/cm3, n(550) ~ 1.66 (approximate, class of Corning 8161).
//  Legacy_fred: exactly the composition of the old code (molar oxide numbers used
//           as mass fractions, 2.29 g/cm3, no RINDEX) - kept only for comparison.
// -----------------------------------------------------------------------------

namespace
{
using Vec = std::vector<G4double>;

G4NistManager* Nist() { return G4NistManager::Instance(); }

G4double LambdaNm(G4double e) { return Materials::hc_eVnm() / (e / eV); }

Vec Fill(const std::function<G4double(G4double)>& f)
{
    Vec v;
    for (auto e : Materials::EnergyGrid()) v.push_back(f(e));
    return v;
}

std::function<G4double(G4double)> Cauchy(G4double A, G4double B)
{
    return [A, B](G4double e) {
        const G4double l = LambdaNm(e) / 1000.;
        return A + B / (l * l);
    };
}

G4double SellmeierSilica(G4double e)
{
    const G4double l2 = std::pow(LambdaNm(e) / 1000., 2);
    const G4double n2 = 1. + 0.6961663 * l2 / (l2 - 0.0684043 * 0.0684043) +
                        0.4079426 * l2 / (l2 - 0.1162414 * 0.1162414) +
                        0.8974794 * l2 / (l2 - 9.896161 * 9.896161);
    return std::sqrt(n2);
}

// Gaussian emission band in wavelength, converted to a density in photon energy
// (dN/dE = dN/dlambda * lambda^2 / hc), which is what G4Scintillation samples.
Vec Emission(G4double peakNm, G4double fwhmNm)
{
    const G4double s = fwhmNm / 2.3548;
    Vec v = Fill([&](G4double e) {
        const G4double l = LambdaNm(e);
        const G4double w = std::exp(-0.5 * std::pow((l - peakNm) / s, 2)) * l * l;
        return w < 1e-12 ? 0. : w;
    });
    const G4double vmax = *std::max_element(v.begin(), v.end());
    for (auto& x : v) x /= vmax;
    return v;
}

void AddVec(G4MaterialPropertiesTable* mpt, const G4String& key, const Vec& v)
{
    auto e = Materials::EnergyGrid();
    mpt->AddProperty(key, e, v);
}

// Compound from oxide mass fractions; converts to element mass fractions.
G4Material* FromOxides(const G4String& name, G4double density,
                       const std::vector<std::pair<std::map<G4String, G4int>, G4double>>& oxides)
{
    std::map<G4String, G4double> el;
    G4double total = 0.;
    for (const auto& [formula, w] : oxides) {
        G4double M = 0.;
        for (const auto& [sym, n] : formula) M += n * Nist()->FindOrBuildElement(sym)->GetA();
        for (const auto& [sym, n] : formula)
            el[sym] += w * n * Nist()->FindOrBuildElement(sym)->GetA() / M;
        total += w;
    }
    auto* mat = new G4Material(name, density, static_cast<G4int>(el.size()));
    for (const auto& [sym, w] : el) mat->AddElement(Nist()->FindOrBuildElement(sym), w / total);
    return mat;
}

G4Material* FromAtoms(const G4String& name, G4double density, const std::map<G4String, G4double>& atoms)
{
    auto* mat = new G4Material(name, density, static_cast<G4int>(atoms.size()));
    // fractional stoichiometry -> mass fractions
    G4double M = 0.;
    for (const auto& [sym, n] : atoms) M += n * Nist()->FindOrBuildElement(sym)->GetA();
    for (const auto& [sym, n] : atoms)
        mat->AddElement(Nist()->FindOrBuildElement(sym), n * Nist()->FindOrBuildElement(sym)->GetA() / M);
    return mat;
}

G4double DensityOverride(const G4String& name, G4double def)
{
    for (const auto& o : SRDetConfig::Instance().materialOverrides)
        if (o.material == name && o.action == "density") return o.value;
    return def;
}

G4Material* Clone(const G4String& name, const G4String& nist, G4double density = -1.)
{
    auto* base = Nist()->FindOrBuildMaterial(nist);
    const G4double rho = DensityOverride(name, density > 0 ? density : base->GetDensity());
    return Nist()->BuildMaterialWithNewDensity(name, nist, rho);
}

struct Scint
{
    G4double yield;   // photons / MeV
    G4double peakNm, fwhmNm;
    G4double tau1, tau2, frac1;
    G4double cauchyA, cauchyB;
    G4double absLength;
    G4double birks;   // mm/MeV
};

void MakeScintillator(G4Material* m, const Scint& s)
{
    auto* mpt = new G4MaterialPropertiesTable();
    AddVec(mpt, "RINDEX", Fill(Cauchy(s.cauchyA, s.cauchyB)));
    AddVec(mpt, "ABSLENGTH", Vec(Materials::EnergyGrid().size(), s.absLength));
    const auto em = Emission(s.peakNm, s.fwhmNm);
    AddVec(mpt, "SCINTILLATIONCOMPONENT1", em);
    mpt->AddConstProperty("SCINTILLATIONYIELD", s.yield);
    mpt->AddConstProperty("RESOLUTIONSCALE", 1.0);
    mpt->AddConstProperty("SCINTILLATIONTIMECONSTANT1", s.tau1);
    mpt->AddConstProperty("SCINTILLATIONYIELD1", s.frac1);
    if (s.frac1 < 1.) {
        AddVec(mpt, "SCINTILLATIONCOMPONENT2", em);
        mpt->AddConstProperty("SCINTILLATIONTIMECONSTANT2", s.tau2);
        mpt->AddConstProperty("SCINTILLATIONYIELD2", 1. - s.frac1);
    }
    m->SetMaterialPropertiesTable(mpt);
    m->GetIonisation()->SetBirksConstant(s.birks);
}

void MakeDielectric(G4Material* m, const std::function<G4double(G4double)>& n, G4double absLength)
{
    auto* mpt = new G4MaterialPropertiesTable();
    AddVec(mpt, "RINDEX", Fill(n));
    if (absLength > 0) AddVec(mpt, "ABSLENGTH", Vec(Materials::EnergyGrid().size(), absLength));
    m->SetMaterialPropertiesTable(mpt);
}

using Builder = std::function<G4Material*(const G4String&)>;

const std::map<G4String, Builder>& Catalogue()
{
    static const std::map<G4String, Builder> cat = {
        // ---------------- scintillators
        {"CsI_Tl",
         [](const G4String& n) {
             auto* m = Clone(n, "G4_CESIUM_IODIDE", 4.51 * g / cm3);
             MakeScintillator(m, {54000. / MeV, 550, 130, 680 * ns, 3340 * ns, 0.64, 1.7536, 0.0109, 40 * cm,
                                  7.1e-3 * mm / MeV});
             return m;
         }},
        {"CsI_pure",
         [](const G4String& n) {
             auto* m = Clone(n, "G4_CESIUM_IODIDE", 4.51 * g / cm3);
             MakeScintillator(m, {2000. / MeV, 315, 40, 16 * ns, 0, 1., 1.7536, 0.0109, 40 * cm, 0.});
             return m;
         }},
        {"NaI_Tl",
         [](const G4String& n) {
             auto* m = Clone(n, "G4_SODIUM_IODIDE", 3.67 * g / cm3);
             MakeScintillator(m, {38000. / MeV, 415, 80, 250 * ns, 0, 1., 1.81, 0.0069, 40 * cm, 0.});
             return m;
         }},
        {"LYSO",
         [](const G4String& n) {
             auto* m = FromAtoms(n, DensityOverride(n, 7.1 * g / cm3), {{"Lu", 1.8}, {"Y", 0.2}, {"Si", 1}, {"O", 5}});
             MakeScintillator(m, {33000. / MeV, 420, 70, 40 * ns, 0, 1., 1.79, 0.0057, 40 * cm, 0.});
             return m;
         }},
        {"BGO",
         [](const G4String& n) {
             auto* m = Clone(n, "G4_BGO", 7.13 * g / cm3);
             MakeScintillator(m, {8200. / MeV, 480, 110, 300 * ns, 0, 1., 2.09, 0.0138, 40 * cm, 0.});
             return m;
         }},
        {"GAGG",
         [](const G4String& n) {
             auto* m = FromAtoms(n, DensityOverride(n, 6.63 * g / cm3), {{"Gd", 3}, {"Al", 2}, {"Ga", 3}, {"O", 12}});
             MakeScintillator(m, {50000. / MeV, 530, 110, 90 * ns, 0, 1., 1.87, 0.0108, 40 * cm, 0.});
             return m;
         }},
        {"EJ200",
         [](const G4String& n) {
             auto* m = Clone(n, "G4_PLASTIC_SC_VINYLTOLUENE", 1.023 * g / cm3);
             MakeScintillator(m, {10000. / MeV, 425, 50, 2.1 * ns, 0, 1., 1.565, 0.0027, 380 * cm, 0.126 * mm / MeV});
             return m;
         }},
        // ---------------- glasses (honeycomb walls)
        {"LeadGlass_MCP",
         [](const G4String& n) {
             auto* m = FromOxides(n, DensityOverride(n, 3.95 * g / cm3),
                                  {{{{"Pb", 1}, {"O", 1}}, 0.51},
                                   {{{"Si", 1}, {"O", 2}}, 0.38},
                                   {{{"K", 2}, {"O", 1}}, 0.06},
                                   {{{"Na", 2}, {"O", 1}}, 0.02},
                                   {{{"Ba", 1}, {"O", 1}}, 0.02},
                                   {{{"Al", 2}, {"O", 3}}, 0.01}});
             MakeDielectric(m, Cauchy(1.637, 0.0075), 50 * cm);
             return m;
         }},
        {"LeadGlass_NIST",
         [](const G4String& n) {
             auto* m = Clone(n, "G4_GLASS_LEAD");
             MakeDielectric(m, Cauchy(1.81, 0.012), 50 * cm);
             return m;
         }},
        {"Borosilicate",
         [](const G4String& n) {
             auto* m = Clone(n, "G4_Pyrex_Glass");
             MakeDielectric(m, Cauchy(1.462, 0.0042), 100 * cm);
             return m;
         }},
        {"FusedSilica",
         [](const G4String& n) {
             auto* m = Clone(n, "G4_SILICON_DIOXIDE", 2.20 * g / cm3);
             MakeDielectric(m, SellmeierSilica, 100 * cm);
             return m;
         }},
        {"Legacy_fred",
         [](const G4String& n) {
             // reproduces the old code exactly (no RINDEX -> optically opaque)
             const G4double s = 1.59 + 0.55 + 0.3 + 0.092 + 0.038 + 0.04;
             auto* m = new G4Material(n, DensityOverride(n, 2.29 * g / cm3), 6);
             m->AddElement(Nist()->FindOrBuildElement("Si"), 0.55 / s);
             m->AddElement(Nist()->FindOrBuildElement("Pb"), 0.3 / s);
             m->AddElement(Nist()->FindOrBuildElement("K"), 0.092 / s);
             m->AddElement(Nist()->FindOrBuildElement("Na"), 0.038 / s);
             m->AddElement(Nist()->FindOrBuildElement("Al"), 0.04 / s);
             m->AddElement(Nist()->FindOrBuildElement("O"), 1.59 / s);
             return m;
         }},
        // ---------------- optical media
        {"Air",
         [](const G4String& n) {
             auto* m = Clone(n, "G4_AIR");
             MakeDielectric(m, [](G4double) { return 1.0003; }, -1);
             return m;
         }},
        {"Vacuum",
         [](const G4String& n) {
             auto* m = Clone(n, "G4_Galactic");
             MakeDielectric(m, [](G4double) { return 1.0; }, -1);
             return m;
         }},
        {"OpticalGrease",
         [](const G4String& n) {
             // silicone (PDMS) grease, e.g. EJ-550 / BC-630: n = 1.465
             auto* m = FromAtoms(n, DensityOverride(n, 1.06 * g / cm3), {{"C", 2}, {"H", 6}, {"O", 1}, {"Si", 1}});
             MakeDielectric(m, Cauchy(1.455, 0.0030), 50 * cm);
             return m;
         }},
        {"Epoxy",
         [](const G4String& n) {
             auto* m = FromAtoms(n, DensityOverride(n, 1.18 * g / cm3), {{"C", 21}, {"H", 25}, {"Cl", 1}, {"O", 5}});
             MakeDielectric(m, Cauchy(1.545, 0.0055), 50 * cm);
             return m;
         }},
        {"CarbonFiber",
         [](const G4String& n) { return Clone(n, "G4_C", 1.6 * g / cm3); }},
    };
    return cat;
}

std::map<G4String, G4double>& BaseYields()
{
    static std::map<G4String, G4double> y;
    return y;
}

Vec ReadTable(const G4String& file, const G4String& key, Vec& energies)
{
    std::ifstream in(file);
    if (!in) {
        G4ExceptionDescription ed;
        ed << "cannot open property file " << file;
        G4Exception("Materials", "SRDet010", FatalException, ed);
    }
    G4bool inNm = true;
    std::vector<std::pair<G4double, G4double>> rows;
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        if (line[0] == '#') {
            if (line.find("eV") != std::string::npos) inNm = false;
            continue;
        }
        std::replace(line.begin(), line.end(), ',', ' ');
        std::istringstream is(line);
        G4double x, y;
        if (!(is >> x >> y)) continue;
        const G4double e = inNm ? Materials::hc_eVnm() / x * eV : x * eV;
        if (key == "ABSLENGTH" || key == "RAYLEIGH" || key == "WLSABSLENGTH") y *= mm;
        rows.emplace_back(e, y);
    }
    std::sort(rows.begin(), rows.end());
    Vec v;
    energies.clear();
    for (auto& [e, y] : rows) {
        energies.push_back(e);
        v.push_back(y);
    }
    return v;
}
}  // namespace

const std::vector<G4double>& Materials::EnergyGrid()
{
    static const std::vector<G4double> grid = [] {
        std::vector<G4double> g;
        const G4int n = 73;
        for (G4int i = 0; i < n; ++i) g.push_back((1.55 + (4.43 - 1.55) * i / (n - 1)) * eV);
        return g;
    }();
    return grid;
}

std::vector<G4String> Materials::CatalogueNames()
{
    std::vector<G4String> v;
    for (const auto& [k, _] : Catalogue()) v.push_back(k);
    return v;
}

G4Material* Materials::Get(const G4String& name)
{
    if (auto* m = G4Material::GetMaterial(name, false)) return m;
    const auto& cat = Catalogue();
    auto it = cat.find(name);
    G4Material* m = nullptr;
    if (it != cat.end()) {
        m = it->second(name);
    } else {
        const G4double rho = DensityOverride(name, -1.);
        if (rho > 0) {
            Nist()->FindOrBuildMaterial(name);
            m = Nist()->BuildMaterialWithNewDensity(name + "_custom_density", name, rho);
        } else {
            m = Nist()->FindOrBuildMaterial(name, false, false);
        }
    }
    if (!m) {
        G4ExceptionDescription ed;
        ed << "Unknown material '" << name << "'. Catalogue:";
        for (auto& n : CatalogueNames()) ed << " " << n;
        ed << " or any NIST name (G4_*).";
        G4Exception("Materials::Get", "SRDet011", FatalErrorInArgument, ed);
    }
    if (IsScintillator(m)) BaseYields().emplace(m->GetName(), m->GetMaterialPropertiesTable()->GetConstProperty("SCINTILLATIONYIELD"));
    return m;
}

G4bool Materials::IsScintillator(const G4Material* mat)
{
    auto* mpt = mat ? mat->GetMaterialPropertiesTable() : nullptr;
    return mpt && mpt->ConstPropertyExists("SCINTILLATIONYIELD");
}

void Materials::ApplyOverrides()
{
    const auto& cfg = SRDetConfig::Instance();
    for (const auto& [name, y0] : BaseYields()) {
        auto* m = G4Material::GetMaterial(name, false);
        if (m) m->GetMaterialPropertiesTable()->AddConstProperty("SCINTILLATIONYIELD", y0 * cfg.yieldScale);
    }
    for (const auto& o : cfg.materialOverrides) {
        if (o.action == "density") continue;  // applied at build time
        auto* m = G4Material::GetMaterial(o.material, false);
        if (!m) {
            G4cout << "[srdet] override for material '" << o.material << "' ignored: not used in geometry" << G4endl;
            continue;
        }
        auto* mpt = m->GetMaterialPropertiesTable();
        if (!mpt && o.action != "birks") {
            mpt = new G4MaterialPropertiesTable();
            m->SetMaterialPropertiesTable(mpt);
        }
        if (o.action == "setConst") {
            if (o.key == "SCINTILLATIONYIELD") {
                BaseYields()[m->GetName()] = o.value / MeV;
                mpt->AddConstProperty(o.key, o.value / MeV * cfg.yieldScale);
            } else {
                mpt->AddConstProperty(o.key, o.value);
            }
        } else if (o.action == "setAbsLength") {
            mpt->RemoveProperty("ABSLENGTH");
            AddVec(mpt, "ABSLENGTH", Vec(EnergyGrid().size(), o.value));
        } else if (o.action == "loadProperty") {
            Vec e;
            Vec v = ReadTable(o.file, o.key, e);
            mpt->RemoveProperty(o.key);
            mpt->AddProperty(o.key, e, v);
        } else if (o.action == "birks") {
            m->GetIonisation()->SetBirksConstant(o.value);
        } else if (o.action == "noRindex") {
            mpt->RemoveProperty("RINDEX");
        }
        G4cout << "[srdet] material override: " << o.material << " " << o.action << " " << o.key << G4endl;
    }
}

void Materials::ExportJson(const G4String& path, const std::vector<G4Material*>& mats)
{
    std::ofstream out(path);
    out << std::setprecision(8) << "{\n";
    G4bool firstMat = true;
    for (auto* m : mats) {
        if (!m) continue;
        if (!firstMat) out << ",\n";
        firstMat = false;
        out << "  \"" << m->GetName() << "\": {\n";
        out << "    \"density_g_cm3\": " << m->GetDensity() / (g / cm3) << ",\n";
        out << "    \"birks_mm_MeV\": " << m->GetIonisation()->GetBirksConstant() / (mm / MeV) << ",\n";
        out << "    \"composition\": {";
        for (std::size_t i = 0; i < m->GetNumberOfElements(); ++i) {
            out << (i ? ", " : "") << "\"" << m->GetElement(i)->GetSymbol() << "\": " << m->GetFractionVector()[i];
        }
        out << "},\n";
        out << "    \"const\": {";
        auto* mpt = m->GetMaterialPropertiesTable();
        if (mpt) {
            G4bool first = true;
            for (const auto& key : mpt->GetMaterialConstPropertyNames()) {
                if (!mpt->ConstPropertyExists(key)) continue;
                G4double v = mpt->GetConstProperty(key);
                if (key == "SCINTILLATIONYIELD") v *= MeV;
                if (key.find("TIMECONSTANT") != std::string::npos) v /= ns;
                out << (first ? "" : ", ") << "\"" << key << "\": " << v;
                first = false;
            }
        }
        out << "},\n    \"vectors\": {";
        if (mpt) {
            G4bool first = true;
            for (const auto& key : mpt->GetMaterialPropertyNames()) {
                auto* pv = mpt->GetProperty(key);
                if (!pv) continue;
                const G4double unit = (key == "ABSLENGTH" || key == "RAYLEIGH") ? mm : 1.;
                out << (first ? "" : ",") << "\n      \"" << key << "\": {\"energy_eV\": [";
                for (std::size_t i = 0; i < pv->GetVectorLength(); ++i)
                    out << (i ? ", " : "") << pv->Energy(i) / eV;
                out << "], \"value\": [";
                for (std::size_t i = 0; i < pv->GetVectorLength(); ++i) out << (i ? ", " : "") << (*pv)[i] / unit;
                out << "]}";
                first = false;
            }
        }
        out << "}\n  }";
    }
    out << "\n}\n";
}
