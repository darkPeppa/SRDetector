"""Names and key numbers of the C++ catalogues (app/src/*.cc), used for validation,
`srdet catalog` and automatic histogram ranges. tests/test_catalog_sync.py checks that
these lists match the C++ sources."""

# scintillator: (photons / MeV, slowest decay time ns, emission peak nm)
SCINTILLATORS = {
    "CsI_Tl": (54000, 3340, 550),
    "CsI_pure": (2000, 16, 315),
    "NaI_Tl": (38000, 250, 415),
    "LYSO": (33000, 40, 420),
    "BGO": (8200, 300, 480),
    "GAGG": (50000, 90, 530),
    "EJ200": (10000, 2.1, 425),
}
GLASSES = ["LeadGlass_MCP", "LeadGlass_NIST", "Borosilicate", "FusedSilica", "Legacy_fred"]
OTHER_MATERIALS = ["Air", "Vacuum", "OpticalGrease", "Epoxy", "CarbonFiber"]

COATINGS = {
    "none": "bare channel: Fresnel/TIR on the core-wall interface",
    "air_gap": "air layer between core and wall (TIR at n_core/1.0)",
    "MgF2_film": "thin MgF2 film, coherent thin-film model (G4 'coated')",
    "ideal": "perfect specular mirror R = 1 (reference)",
    "black": "perfect absorber R = 0 (reference)",
    "mirror": "specular mirror, R = optics.coating_reflectivity",
    "diffuse": "Lambertian reflector, R = optics.coating_reflectivity",
    "Al": "aluminium, complex n+ik (Rakic 1998)",
    "Ag": "silver, complex n+ik (Johnson & Christy 1972)",
    "Au": "gold, complex n+ik (Johnson & Christy 1972)",
    "Al_simple": "aluminium, legacy REFLECTIVITY(E) without angular dependence",
    "TiO2": "TiO2 white paint, Lambertian",
    "BaSO4": "BaSO4 white paint, Lambertian",
    "Teflon": "PTFE, Lambertian",
    "ESR_LUT": "3M ESR, measured LUT (LUTDAVIS)",
    "Teflon_LUT": "Teflon tape, measured LUT (LUTDAVIS)",
    "ESR_LUT_BGO": "VM2000/ESR in air, measured LUT (BGO)",
    "Tyvek_LUT": "Tyvek in air, measured LUT (BGO)",
    "TiO2_LUT": "TiO2 paint in air, measured LUT (BGO)",
}

# sensor: (description, fill factor, pixel pitch mm, read noise e-, relative cost per cm2)
SENSORS = {
    "ideal": ("QE = 1", 1.0, 0.1, 0.0, 0.0),
    "aSi_FPD": ("a-Si photodiode flat panel", 0.70, 0.139, 1500.0, 1.0),
    "CMOS_FSI": ("front-illuminated CMOS", 0.90, 0.050, 5.0, 3.0),
    "sCMOS_BSI": ("back-illuminated sCMOS", 1.00, 0.0065, 1.5, 30.0),
    "SiPM": ("SiPM array (S13360 class)", 1.00, 3.0, 0.0, 50.0),
    "PMT_bialkali": ("multi-anode PMT, bialkali", 0.87, 6.0, 0.0, 80.0),
    "EMCCD": ("back-illuminated EMCCD", 1.00, 0.016, 0.1, 60.0),
}
