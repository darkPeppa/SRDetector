#include "Sensors.hh"

#include "Materials.hh"

#include "G4SystemOfUnits.hh"
#include "G4ios.hh"
#include "G4Exception.hh"

#include <algorithm>
#include <map>

namespace
{
const std::map<G4String, SensorSpec>& Catalogue()
{
    static const std::map<G4String, SensorSpec> cat = {
        {"ideal",
         {"ideal", "QE = 1 everywhere (upper bound of light collection)",
          {{250, 1.}, {850, 1.}}, 1.0, 0.1 * mm, 0., 0., 0., "", 0.}},
        {"aSi_FPD",
         {"aSi_FPD", "amorphous-Si photodiode flat panel (TFT array) - standard for CsI(Tl) X-ray imaging",
          {{350, 0.20}, {400, 0.45}, {450, 0.62}, {500, 0.72}, {550, 0.78}, {600, 0.78},
           {650, 0.70}, {700, 0.55}, {750, 0.35}, {800, 0.15}},
          0.70, 0.139 * mm, 1500., 1000., 1.0, "", 0.}},
        {"CMOS_FSI",
         {"CMOS_FSI", "front-illuminated CMOS image sensor with micro-lenses",
          {{350, 0.10}, {400, 0.30}, {450, 0.45}, {500, 0.55}, {550, 0.58}, {600, 0.55},
           {650, 0.48}, {700, 0.40}, {750, 0.30}, {800, 0.20}},
          0.90, 0.050 * mm, 5., 50., 3.0, "Borosilicate", 0.5 * mm}},
        {"sCMOS_BSI",
         {"sCMOS_BSI", "back-illuminated scientific CMOS",
          {{300, 0.30}, {350, 0.50}, {400, 0.75}, {450, 0.85}, {500, 0.92}, {550, 0.95},
           {600, 0.93}, {650, 0.88}, {700, 0.80}, {750, 0.70}, {800, 0.55}},
          1.00, 0.0065 * mm, 1.5, 1., 30.0, "FusedSilica", 0.5 * mm}},
        {"SiPM",
         {"SiPM", "SiPM array, 50 um cells (S13360-class); PDE already includes the cell fill factor",
          {{300, 0.10}, {350, 0.25}, {400, 0.36}, {450, 0.40}, {500, 0.37}, {550, 0.30},
           {600, 0.24}, {650, 0.18}, {700, 0.13}, {750, 0.09}, {800, 0.06}},
          1.00, 3.0 * mm, 0., 5.e5, 50.0, "Epoxy", 0.3 * mm}},
        {"PMT_bialkali",
         {"PMT_bialkali", "multi-anode PMT, bialkali photocathode (poor match to CsI(Tl) green light)",
          {{300, 0.20}, {350, 0.27}, {400, 0.28}, {450, 0.24}, {500, 0.15}, {550, 0.07},
           {600, 0.03}, {650, 0.008}, {700, 0.002}, {800, 0.0}},
          0.87, 6.0 * mm, 0., 10., 80.0, "Borosilicate", 1.5 * mm}},
        {"EMCCD",
         {"EMCCD", "back-illuminated electron-multiplying CCD",
          {{300, 0.35}, {350, 0.55}, {400, 0.80}, {450, 0.90}, {500, 0.95}, {550, 0.95},
           {600, 0.94}, {650, 0.90}, {700, 0.83}, {750, 0.72}, {800, 0.58}},
          1.00, 0.016 * mm, 0.1, 0.01, 60.0, "FusedSilica", 0.5 * mm}},
    };
    return cat;
}
}  // namespace

const SensorSpec& Sensors::Get(const G4String& name)
{
    const auto& cat = Catalogue();
    auto it = cat.find(name);
    if (it == cat.end()) {
        G4ExceptionDescription ed;
        ed << "Unknown sensor '" << name << "'. Available:";
        for (auto& n : Names()) ed << " " << n;
        G4Exception("Sensors::Get", "SRDet020", FatalErrorInArgument, ed);
    }
    return it->second;
}

std::vector<G4String> Sensors::Names()
{
    std::vector<G4String> v;
    for (const auto& [k, _] : Catalogue()) v.push_back(k);
    return v;
}

std::vector<G4double> Sensors::Efficiency(const SensorSpec& s)
{
    std::vector<G4double> out;
    for (auto e : Materials::EnergyGrid()) {
        const G4double l = Materials::hc_eVnm() / (e / eV);
        G4double qe = 0.;
        const auto& t = s.qe;
        if (l <= t.front().first) qe = t.front().second;
        else if (l >= t.back().first) qe = t.back().second;
        else {
            for (std::size_t i = 1; i < t.size(); ++i) {
                if (l <= t[i].first) {
                    const G4double f = (l - t[i - 1].first) / (t[i].first - t[i - 1].first);
                    qe = t[i - 1].second + f * (t[i].second - t[i - 1].second);
                    break;
                }
            }
        }
        out.push_back(std::clamp(qe * s.fillFactor, 0., 1.));
    }
    return out;
}
