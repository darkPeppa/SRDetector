#pragma once
// Catalogue of channel coatings / reflectors.
//
//  name         model                                          physical layer (EM)
//  ----------   --------------------------------------------   -------------------
//  none         bare channel: Fresnel + TIR core <-> wall       -
//  air_gap      air layer: TIR core <-> air, then glass         Air
//  MgF2_film    thin low-index film (G4 'coated', interference) -
//  ideal        dielectric_metal, R = 1 (reference)             G4_Al
//  black        dielectric_metal, R = 0 (reference)             G4_C
//  mirror       dielectric_metal, R = coatingReflectivity       G4_Al
//  diffuse      Lambertian paint, R = coatingReflectivity       G4_TITANIUM_DIOXIDE
//  Al, Ag, Au   dielectric_metal with complex index n + ik      G4_Al / G4_Ag / G4_Au
//               (angle and polarisation dependent Fresnel)
//  Al_simple    dielectric_metal with the old REFLECTIVITY(E)   G4_Al
//  TiO2, BaSO4, Teflon   Lambertian paint, R(lambda)            corresponding compound
//  ESR_LUT, Teflon_LUT   measured LUT (LUTDAVIS, LYSO crystal)  G4_MYLAR / G4_TEFLON
//  ESR_LUT_BGO, Tyvek_LUT, TiO2_LUT  measured LUT (BGO crystal) ...
//
// coatingSigmaAlpha > 0 makes metallic / mirror surfaces 'ground' (micro-facets).

#include "globals.hh"

#include <vector>

class G4OpticalSurface;

struct CoatingSpec
{
    G4String name;
    G4String description;
    G4bool needsVolume;       // place a physical coating layer
    G4bool surfaceOnCore;     // optical surface core -> next volume
    G4String defaultMaterial; // EM material of the layer
};

namespace OpticalSurfaces
{
const CoatingSpec& Spec(const G4String& name);
std::vector<G4String> Names();
// Build the optical surface for a coating (nullptr if the coating has none).
G4OpticalSurface* Make(const G4String& name, const G4String& label);
// Detector surface: perfect absorber with EFFICIENCY = QE * fill factor
G4OpticalSurface* MakeSensor(const std::vector<G4double>& efficiency);
}  // namespace OpticalSurfaces
