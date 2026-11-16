"""Rule-pack data with sources and bases (iteration 4: docs/purpose-loop.md §2, applying
`reports/Rule pack engineering data.md`; iteration 3 placeholders were NOTES DECISIONS #58).

Every value says **what it is**, not only how big it is (the report's conclusion).  Each entry
(`_v`) carries:

* `value`, `lo`, `hi`, `unit`: the nominal and the range used for worst-case propagation.  `lo`
  and `hi` are the minimum and maximum of *published means* where the sources are means; they
  are **not** 5th percentiles (the anchor data publish no scatter), so a worst case computed
  from them is not a characteristic value.
* `basis`: e.g. "mean ultimate", "short-term mean, in-layer", "as-made bias", "design rule".
* `source_sf`: the factor the *source* had already applied to the numbers it published (Cobra
  "safe" loads are ultimate ÷ 2; Sure Wall is ultimate ÷ 4; NDS is about ultimate ÷ 5.5).  The
  pack stores the ultimate and records the source's factor, so a check never divides twice.
* `status`: `sourced` (cited well enough to drop the placeholder flag, per the report's table),
  `provisional` (sourced but resting on inference, rules of thumb or secondhand equations: shown
  as a visible, unreviewed default) or `placeholder` (no data behind it).
* `placeholder`: True unless `status == "sourced"` (the report's "placeholder: false?" column).
* `confidence`, `conditions`, `sources` (keys into `SOURCES`) and a `note` citing them.

**Safety factors** (`SAFETY_FACTORS`) are applied by the checks, per the quantity they protect:
4 on the mean ultimate of drywall anchors, 5 on the mean ultimate of wood screws (the NDS basis),
4 on short-term printed-plastic strength under sustained load, 2 under short-term load.  Creep
is covered by the SF 4, so `sustained_derate` is stored as reference data and **never applied on
top of SF 4** (no double counting: 50 × 0.3 × 0.3 / 2 would double-penalise PLA).

The one source of truth rule (tolerance-uncertainty.md §4.2) holds: the same process entry gives
the checks their tolerances *and* the GUI its layer pitch, extrusion width and detail flags
(`appearance()`), so the render cannot disagree with the checks.

Not pack data, and not placeholders: standard gravity (SI), numbered-screw major diameters
(ASME B1.1), the ID-1 card (ISO/IEC 7810).
"""
from __future__ import annotations

PLACEHOLDER_NOTE = ("placeholder value, not from a cited source (src/dipm/packs.py); "
                    "replace with sourced pack data before relying on it")

G_STANDARD = 9.80665        # m/s², standard gravity (SI definition; not a placeholder)

# Citation keys used by the entries below (reports/Rule pack engineering data.md, with the
# research notes under research_notes/Rule pack engineering data/).
SOURCES = {
    "toggler_hwa": "Toggler HWA technical bulletin: https://toggler.co.uk/wp-content/uploads/2021/09/Metric-Technical_HWA.pdf",
    "toggler_snap": "Toggler SnapToggle bulletin: https://toggler.co.uk/wp-content/uploads/2021/09/Metric-Technical_SNAPTOGGLE.pdf",
    "cobra_triplegrip": "Cobra TripleGrip sheet: https://cdn.rona.ca/documents/TRIPLEGRIP-COBRA%20-TechnicalSheet.pdf",
    "cobra_walldriller": "Cobra WallDriller Plus sheet: https://cdn.rona.ca/documents/COBRA%20-%20WallDriller%20Plus%20-%20Technical%20Sheet.pdf",
    "cobra_fliptoggle": "Cobra FlipToggle sheet: https://cdn.rona.ca/documents/FLIPTOGGLE-COBRA-Technicalsheet.pdf",
    "itw_ezancor": "ITW E-Z Ancor data: https://www.buildsite.com/pdf/itwbuildex/E-Z-ANCOR-Self-Drilling-Drywall-Anchors-Product-Data-2964390.pdf",
    "wood_handbook": "Wood Handbook ch. 8 (via CED): https://www.cedengineering.com/userfiles/S03-019%20-%20Wood%20as%20An%20Engineering%20Material%20-%20Fastenings%20-%20US.pdf",
    "engineers_edge": "Engineers Edge wood screw withdrawal: https://engineersedge.com/calculators/wood_screw_pullout_withdraw_resistance_15385.htm",
    "iapmo_er0262": "IAPMO ER-0262 (NDS withdrawal): https://forms.iapmo.org/ues_reports/reports/ER_0262.pdf",
    "prusa_pla": "Prusament PLA TDS: https://www.matterhackers.com/r/xFvGl8",
    "prusa_petg": "Prusament PETG TDS: https://www.3dprintergear.com.au/assets/files/technical-data-sheet%20(1).pdf",
    "polymaker_pla": "Polymaker PolyLite PLA TDS: https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/pla/polylite-tm-pla",
    "polymaker_petg": "Polymaker PolyLite PETG TDS V5.4/V5.2: https://polymaker.com/wp-content/uploads/lana-downloads/PolyLite_PETG_TDS_EN_V5.4.pdf",
    "polymaker_abs": "Polymaker PolyLite ABS TDS V5.6: https://polymaker.com/wp-content/uploads/lana-downloads/TDS_Polymaker_PolyLite-ABS_V5.6_2025-12-30_EN.pdf",
    "eryildiz2021": "Eryildiz 2021 (PLA build orientation): https://dergipark.org.tr/en/download/article-file/1580962",
    "ahn2002": "Ahn et al. 2002 (FDM ABS anisotropy): https://iss.mech.utah.edu/wp-content/uploads/sites/103/2012/10/Ahn-Anisotropic_material-2002.pdf",
    "protolabs": "Protolabs thermoplastic selection (long-term stress 20–40 %): https://www.protolabs.com/resources/guides-and-trend-reports/thermoplastic-material-selection-for-injection-molding/",
    "plastics_sf": "Design criteria and safety factors for plastic components: https://www.researchgate.net/publication/240421046",
    "byczuk2026": "Byczuk et al., euspen 2026 (X1C CMM study): https://www.euspen.eu/knowledge-base/ICE26126.pdf",
    "gebre2026": "Gebre et al. 2026 (X1C precision and accuracy), IRIS UniTN",
    "popescu2023": "Popescu et al. 2023 (hole accuracy): https://mdpi-res.com/d_attachment/applsci/applsci-13-00041/article_deploy/applsci-13-00041.pdf",
    "prusa_kb_width": "Prusa KB, extrusion width: https://help.prusa3d.com/article/creating-profiles-for-different-nozzles_127540",
    "orca_wiki": "OrcaSlicer wiki, line width: https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_line_width.html",
    "prusa_kb_foot": "Prusa KB, elephant foot compensation: https://help.prusa3d.com/article/elephant-foot-compensation_114487",
    "hubs": "Hubs FDM design guide: https://www.hubs.com/knowledge-base/how-design-parts-fdm-3d-printing/",
    "jiang2018": "Jiang et al. 2018 (overhang threshold): https://researchspace.auckland.ac.nz/handle/2292/44788",
    "qidi": "QIDI bridging guide: https://qidi3d.com/blogs/news/3d-printing-bridging-techniques-guide",
    "ansur2": "ANSUR II public CSVs (OpenLab), computed pooled P5/P50/P95: https://www.openlab.psu.edu/ansur2/",
    "faa_hfds": "FAA HFDS App. B Tech Ops anthropometrics: https://hf.tc.faa.gov/hfds/download-hfds/hfds_pdfs/App_B_Tech_Ops_Anthropometrics.pdf",
    "report": "reports/Rule pack engineering data.md (dipm deep research, 2026-11-16)",
}


def _v(value, lo=None, hi=None, unit="", note: str = PLACEHOLDER_NOTE, placeholder: bool | None = None, *,
       status: str = "placeholder", basis: str = "", source_sf: float | None = None, conditions: str = "",
       confidence: str = "", sources: tuple = (), **extra) -> dict:
    """A pack value with a range [lo, hi] (worst-case propagation, tolerance §2) and what it is."""
    if status not in ("sourced", "provisional", "placeholder"):
        raise ValueError(status)
    ph = (status != "sourced") if placeholder is None else placeholder
    return {"value": value, "lo": value if lo is None else lo, "hi": value if hi is None else hi,
            "unit": unit, "placeholder": ph, "status": status, "basis": basis, "source_sf": source_sf,
            "conditions": conditions, "confidence": confidence, "sources": list(sources), "note": note, **extra}


# ---------------------------------------------------------------- processes

FDM = {
    "pack": "fdm_printing",
    "version": "0.1-sourced",
    # tolerance-uncertainty §4.2 default context: PLA on a standard FDM printer
    "defaults": {"process": "fdm_printing", "material": "PLA", "nozzle": "0.4 mm", "layer_height": "0.2 mm"},
    "printer_class": "well-tuned enclosed printer (Bambu X1C class), 0.4 mm nozzle, 0.2 mm layers, no calibration",
    # relative position of two printed features: ±(value + scale × distance)
    "position_tolerance": _v(0.1, 0.05, 0.2, "mm", status="provisional", basis="process scatter, uncompensated",
                             scale=0.0015, scale_lo=0.0, scale_hi=0.003, confidence="low–medium",
                             conditions="X1C-class printer; centre-to-centre has no modern CMM study",
                             sources=("byczuk2026",),
                             note="±0.1 mm + 0.15 % of distance: contour shrink cancels between two features, so the "
                                  "residual is axis scale (≈0.1–0.15 %, Byczuk 2026) plus scatter; an inference, not a "
                                  "measurement (report: entry-by-entry table)"),
    # a printed wall / thickness: as-made = nominal + bias ± band
    "dimension_tolerance": _v(0.1, 0.1, 0.3, "mm", status="sourced", basis="as-made, uncompensated: bias + band",
                              bias=-0.10, symmetric_fallback=0.2, confidence="medium",
                              conditions="XY, X1C-class printer, PLA, 0.4 mm nozzle, 0.2 mm layers, uncompensated; "
                                         "±0.1 after per-printer calibration, ±0.3 on a poorly tuned printer",
                              sources=("byczuk2026", "gebre2026"),
                              note="XY dimensions print ≈0.12 mm undersize with σ ≈ 0.03–0.04 mm (Byczuk 2026); "
                                   "absolute deviation roughly constant across sizes (Gebre 2026).  Stored as a bias "
                                   "of −0.10 mm and a band of ±0.10 mm (value = band); a symmetric model needs ±0.2"),
    "z_tolerance": _v(0.1, 0.05, 0.2, "mm", status="provisional", basis="as-made: bias + band + ½ layer",
                      bias=0.05, quantization="half a layer", confidence="medium-low",
                      sources=("byczuk2026", "gebre2026"),
                      note="Z prints ≈ +0.05 mm long (Byczuk 2026) and is the only plate-position-sensitive axis "
                           "(Gebre 2026); band ±0.1 plus half-layer quantization"),
    "extrusion_width_factor": _v(1.125, 1.0, 1.2, status="sourced", basis="slicer convention", confidence="high",
                                 conditions="PrusaSlicer automatic width; Cura 1.0, Bambu 1.05, Orca walls 1.05–1.2",
                                 sources=("prusa_kb_width", "orca_wiki"),
                                 note="extrusion width = 1.125 × nozzle (PrusaSlicer); a convention keyed to the slicer"),
    "overhang_max_deg": _v(45.0, 40.0, 60.0, "deg", status="sourced", basis="design rule (nominal)",
                           confidence="medium (nominal), low (60°)", sources=("hubs", "jiang2018"),
                           note="45° rule (Hubs); the printable threshold varies with fan, speed and temperature "
                                "(Jiang 2018), so only the nominal is sourced"),
    # a true bridge (unsupported span between two supports)
    "bridge_max_mm": _v(10.0, 5.0, 20.0, "mm", status="provisional", basis="design rule", confidence="low–medium",
                        sources=("hubs", "qidi"),
                        note="Hubs: some sag 'unless the bridge is less than 5mm'; vendor guides cite ≈20 mm clean spans"),
    # horizontal round holes up to this Ø print without support (crown chord ≈ 7 mm at Ø10)
    "horizontal_hole_max_d": _v(10.0, 6.0, 20.0, "mm", status="provisional", basis="geometric inference",
                                confidence="low–medium", sources=("hubs", "qidi"),
                                note="the unsupported crown of a horizontal Ø10 hole is a ≈7 mm chord, between Hubs' 5 mm "
                                     "and the ≈20 mm vendor span: geometric inference (report)"),
    "vertical_hole_undersize": _v(-0.15, -0.30, -0.05, "mm", status="sourced", basis="as-made, absolute, on Ø",
                                  confidence="medium-high", sources=("popescu2023", "gebre2026"),
                                  note="vertical Ø6–10 holes at 0.2 mm layers printed 0.12–0.24 mm undersize, flat across "
                                       "sizes and five sites (Popescu 2023); X1C −0.134 mm (Gebre 2026)"),
    "horizontal_hole_undersize": _v(-0.15, -0.40, -0.10, "mm", status="provisional", basis="as-made, on Ø",
                                    small_hole_value=-0.25, small_hole_below_mm=3.0, confidence="medium",
                                    sources=("gebre2026", "popescu2023"),
                                    note="−0.15 for Ø ≥ 5, −0.25 for Ø < 3 (a near-horizontal Ø2.3 printed ≈Ø2.05, "
                                         "Popescu 2023; X1C −0.108, Gebre 2026)"),
    "elephant_foot_per_side": _v(0.15, 0.05, 0.3, "mm", status="provisional", basis="as-made, first 1–3 layers",
                                 compensated_value=0.0, confidence="low–medium", sources=("prusa_kb_foot",),
                                 note="+0.15 per side uncompensated; 0 with compensation (on in Prusa profiles); no "
                                      "peer-reviewed measurement of the flare"),
    "thin_wall_delta": _v(-0.03, -0.05, -0.02, "mm", status="sourced", basis="as-made", confidence="medium",
                          sources=("byczuk2026",), note="0.8 mm walls printed at 0.75–0.78 mm (Byczuk 2026)"),
    "across_layer_strength_ratio": _v(0.5, 0.3, 0.8, status="sourced", basis="ratio of short-term means",
                                      confidence="medium", sources=("prusa_pla", "eryildiz2021", "polymaker_pla"),
                                      note="Prusa interlayer 17/51 = 0.33 (PLA), 0.38 (PETG); Eryildiz upright PLA 0.64; "
                                           "Polymaker Z 0.73–0.89.  Default PLA with the fan on sits near the low end"),
    # minimum printable wall: two perimeters (a design rule; not researched)
    "min_wall_perimeters": _v(2.0, unit="perimeters", status="placeholder", basis="design rule",
                              note="two perimeters × extrusion width; a common design rule, not researched"),
    # print-orientation scoring (3E.10): cost = overhang mm² + w_support × support mm³ − w_bed × bed mm²
    "orientation": {"candidates": 6, "w_support": 0.02, "w_bed": 0.1, "placeholder": True, "status": "placeholder",
                    "note": "policy weights, not researched"},
    # process appearance (3E.7): shading only (normal/roughness), never colour
    "appearance": {"top_line_angle_deg": 45.0,
                   "flags": {"layer_lines": True, "top_lines": True, "z_seam": False, "elephant_foot": False,
                             "support_scars": False}},
}

PROCESSES = {"fdm_printing": FDM}
LAYER_HEIGHTS = ("0.1 mm", "0.15 mm", "0.2 mm", "0.28 mm")
NOZZLES = ("0.25 mm", "0.4 mm", "0.6 mm")

# ---------------------------------------------------------------- materials

_TENSILE_BASIS = "short-term mean, in-layer, ISO 527, 100 % infill"
MATERIALS = {
    # in-layer tensile strength of printed parts (MPa) and surface roughness for the renderer (0..1)
    "PLA": {"tensile_mpa": _v(50.0, 40.0, 58.0, "MPa", status="sourced", basis=_TENSILE_BASIS, confidence="medium-high",
                              sources=("prusa_pla", "polymaker_pla", "eryildiz2021"),
                              note="Prusament PLA 51 ± 3, Polymaker 52.3, Eryildiz flat 55.5 MPa"),
            "flexural_mpa": _v(83.0, unit="MPa", status="sourced", basis="short-term mean, ISO 178 (reference only)",
                               governing=False, sources=("prusa_pla",),
                               note="non-governing: bending checks compare σ = 6M/(bh²) with the tensile value"),
            "sustained_derate": _v(0.3, 0.2, 0.4, status="provisional", basis="long-term / short-term strength",
                                   confidence="low", sources=("protolabs",),
                                   note="moulded-thermoplastic rule (20–40 %), lower near HDT; no printed creep-rupture "
                                        "data (longest ≈2 h).  Reference only: SF 4 already covers creep"),
            "hdt_c": _v(55.0, unit="°C", status="sourced", basis="datasheet", sources=("prusa_pla",), note="HDT"),
            "roughness": 0.62, "label": "PLA"},
    "PETG": {"tensile_mpa": _v(45.0, 32.0, 52.0, "MPa", status="sourced", basis=_TENSILE_BASIS, confidence="medium",
                               sources=("prusa_petg", "polymaker_petg"),
                               note="Prusament PETG 47 ± 2, Polymaker V5.4 50.8; V5.2 listed 31.9 MPa unexplained (lo)"),
             "flexural_mpa": _v(66.0, unit="MPa", status="sourced", basis="short-term mean, ISO 178 (reference only)",
                                governing=False, sources=("prusa_petg",), note="non-governing reference value"),
             "sustained_derate": _v(0.4, 0.3, 0.5, status="provisional", basis="long-term / short-term strength",
                                    confidence="low", sources=("protolabs",),
                                    note="reference only: SF 4 already covers creep"),
             "hdt_c": _v(68.0, unit="°C", status="sourced", basis="datasheet", sources=("prusa_petg",), note="HDT"),
             "roughness": 0.38, "label": "PETG"},
    "ABS": {"tensile_mpa": _v(33.0, 25.0, 40.0, "MPa", status="sourced", basis=_TENSILE_BASIS, confidence="medium-low",
                              sources=("polymaker_abs", "ahn2002"),
                              note="Polymaker ABS 33.4 MPa (fan off); raster direction swings ABS 10–73 % of moulded "
                                   "(Ahn 2002)"),
            "flexural_mpa": _v(56.0, unit="MPa", status="sourced", basis="short-term mean, ISO 178 (reference only)",
                               governing=False, sources=("polymaker_abs",), note="non-governing reference value"),
            "sustained_derate": _v(0.4, 0.3, 0.5, status="provisional", basis="long-term / short-term strength",
                                   confidence="low", sources=("protolabs",),
                                   note="reference only: SF 4 already covers creep"),
            "hdt_c": _v(98.0, unit="°C", status="sourced", basis="datasheet", sources=("polymaker_abs",), note="HDT"),
            "roughness": 0.55, "label": "ABS"},
}

# ---------------------------------------------------------------- safety factors (applied by checks)

SAFETY_FACTORS = {
    "drywall anchor": _v(4.0, status="sourced", basis="on mean ultimate tension/shear",
                         sources=("toggler_hwa", "cobra_walldriller"),
                         note="'Industry standards recommend ¼ of ultimate test load' (Toggler); Wall Twister, LH Dottie "
                              "and Confast name 4:1"),
    "wood screw": _v(5.0, status="sourced", basis="on mean ultimate withdrawal (≈ NDS basis)",
                     sources=("wood_handbook", "iapmo_er0262"),
                     note="NDS reference withdrawal ≈ 1/5.5 of the Wood Handbook ultimate (secondhand; NDS text not "
                          "checked)"),
    "printed sustained": _v(4.0, status="sourced", basis="on short-term strength, long-term static load",
                            sources=("plastics_sf",),
                            note="plastics design literature: ≈2 short-term, ≈4 long-term static; creep is covered "
                                 "here and not derated again"),
    "printed short-term": _v(2.0, status="sourced", basis="on short-term strength, short-term static load",
                             sources=("plastics_sf",), note="≈2 for short-term static load"),
}

# ---------------------------------------------------------------- wall anchors (context `install`)

ANCHORS = {
    # mean ultimate capacity of one wall fixing in 1/2" (12.5 mm) gypsum board, per direction
    "drywall with anchors": {
        "label": "plastic plug / self-drilling drywall anchor", "fits": "#8/#10 wood screw", "safety": "drywall anchor",
        "tension_n": _v(250.0, 130.0, 450.0, "N", status="sourced", basis="mean ultimate", source_sf=2.0,
                        confidence="medium", conditions='1/2" gypsum board; items flush to the wall',
                        sources=("cobra_triplegrip", "itw_ezancor", "cobra_walldriller"),
                        note="TripleGrip safe ×2 = 190–260 N; E-Z Ancor 130–220 N; WallDriller Plus 310–445 N.  Cobra "
                             "values 'will vary with items hung away from the wall'.  Default install class "
                             "(plastic plug)"),
        "shear_n": _v(600.0, 310.0, 1050.0, "N", status="sourced", basis="mean ultimate", source_sf=2.0,
                      confidence="medium", sources=("cobra_triplegrip", "cobra_walldriller"),
                      note="TripleGrip 310–410 N, WallDriller Plus 760–1,050 N (safe ×2)")},
    "drywall, plastic toggle": {
        "label": "plastic folding toggle (drywall)", "fits": "#8/#10 wood screw", "safety": "drywall anchor",
        "tension_n": _v(640.0, 450.0, 700.0, "N", status="sourced", basis="mean ultimate", source_sf=1.0,
                        confidence="medium", sources=("toggler_hwa",), note="Toggler TB ultimate"),
        "shear_n": _v(745.0, 600.0, 800.0, "N", status="sourced", basis="mean ultimate", source_sf=1.0,
                      confidence="medium", sources=("toggler_hwa",), note="Toggler TB ultimate")},
    "drywall, metal strap toggle": {
        "label": "metal strap toggle (drywall; machine bolt only)", "fits": "M5/M6 machine bolt", "safety": "drywall anchor",
        "tension_n": _v(1000.0, 600.0, 1180.0, "N", status="sourced", basis="mean ultimate", source_sf=1.0,
                        confidence="medium", sources=("toggler_snap", "cobra_fliptoggle"),
                        note="SnapToggle BM5 1,059 N at onset of gouging; FlipToggle safe ×2"),
        "shear_n": _v(1000.0, 940.0, 1100.0, "N", status="sourced", basis="mean ultimate", source_sf=1.0,
                      confidence="medium", sources=("toggler_snap", "cobra_fliptoggle"), note="SnapToggle 1,098 N")},
    "wood stud": {
        "label": "wood screw in a stud (#8/#10, 25–40 mm thread)", "fits": "#8/#10 wood screw", "safety": "wood screw",
        "tension_n": _v(2500.0, 1800.0, 5200.0, "N", status="provisional", basis="mean ultimate (≈ 5.5 × NDS reference)",
                        source_sf=1.0, confidence="medium-low (secondhand equations)",
                        conditions="side grain, threaded penetration only, pilot ≈70 % of root Ø",
                        sources=("wood_handbook", "engineers_edge", "iapmo_er0262"),
                        note="#8 in SPF with ≈32 mm thread: ≈2,500 N mean ultimate (Wood Handbook 15,700·G²·D per in); "
                             "provisional until the NDS text is checked"),
        "shear_n": _v(2500.0, 1800.0, 5200.0, "N", status="placeholder", basis="not researched",
                      note="lateral capacity not researched; the tension value is reused as a stand-in")},
}
DEFAULT_INSTALL = "drywall with anchors"
INTERACTION_RULE = ("linear N/N_u + V/V_u ≤ 1/SF (a design choice: no anchor maker publishes an interaction rule; "
                    "report, 'Combined tension and shear')")


def anchor(install: str | None) -> dict:
    return ANCHORS.get(str(install or DEFAULT_INSTALL)) or ANCHORS[DEFAULT_INSTALL]


def safety_factor(name: str) -> float:
    return float(SAFETY_FACTORS[name]["value"])

# ---------------------------------------------------------------- screws (reference objects)

SCREW_MAJOR_MM = {   # not placeholders: ASME B1.1 numbered sizes (inch × 25.4), ISO nominal M sizes
    "#6": 3.505, "#8": 4.166, "#10": 4.826, "M3": 3.0, "M4": 4.0, "M5": 5.0,
}
SCREW_REFERENCE_LENGTH_MM = _v(25.0, unit="mm", note="length of the ghosted reference screw; not researched")

# ---------------------------------------------------------------- human scale (reference objects)

# ID-1 card: ISO/IEC 7810 (85.60 × 53.98 mm, 3.18 mm corner radius); not a placeholder
ID1_CARD_MM = {"width": 85.60, "height": 53.98, "corner_radius": 3.18, "thickness": 0.76, "placeholder": False,
               "status": "sourced", "note": "ISO/IEC 7810 ID-1"}
# Fingertip: ANSUR II has no finger measurements; breadth from the FAA index-finger PIP breadth
FINGERTIP_MM = {"breadth": 18.0, "breadth_lo": 16.0, "breadth_hi": 21.0, "length": 25.0, "placeholder": True,
                "status": "provisional", "sources": ["faa_hfds"],
                "note": "breadth 18 mm (16–21): FAA HFDS index-finger PIP breadth medians 21 (men) / 18 (women), the "
                        "fingertip is narrower (provisional); length 25 mm has no source (placeholder)"}
HAND_MM = {"length": 190.0, "length_lo": 171.0, "length_hi": 208.0, "breadth": 85.0, "breadth_lo": 74.0,
           "breadth_hi": 94.0, "placeholder": False, "status": "sourced", "sources": ["ansur2"],
           "note": "pooled ANSUR II P50 190 × 86 mm (P5–P95 171–208 × 74–94), unweighted, computed from the public "
                   "CSVs (4,082 men, 1,986 women); 85 kept for the reference hand"}

# ---------------------------------------------------------------- components (starter set, placeholders)

# Off-the-shelf things a design must fit (docs/purpose-loop.md §3 step 4).  A hand-written
# starter set: every entry is a placeholder until a component pack with sources exists.
COMPONENTS = {
    "fishing_rod_blank": {
        "shape": "cylinder", "label": "fishing rod blank at the holder",
        "diameter": _v(10.0, 6.0, 14.0, "mm", note="blank Ø where a wall holder grips it (above the reel seat); "
                                                     "not from a cited source"),
        "length": _v(1800.0, 1500.0, 2400.0, "mm", note="rod length; not from a cited source"),
        "mass": _v(0.4, 0.2, 1.0, "kg", note="rod with reel; not from a cited source")},
    "spinning_reel": {
        "shape": "box", "label": "spinning reel envelope (hangs below the rod)",
        "size": {"along": _v(120.0, 90.0, 140.0, "mm"), "across": _v(75.0, 60.0, 90.0, "mm"),
                 "down": _v(110.0, 90.0, 130.0, "mm")},
        "note": "size 1000–4000 envelope estimated, not from a cited source"},
    "baitcasting_reel": {
        "shape": "box", "label": "baitcasting reel envelope (sits on top of the rod)",
        "size": {"along": _v(80.0, 70.0, 95.0, "mm"), "across": _v(110.0, 95.0, 125.0, "mm"),
                 "down": _v(-50.0, -60.0, -40.0, "mm")},
        "note": "estimated envelope, not from a cited source"},
}

# ---------------------------------------------------------------- margin states

THIN_FRACTION = 0.10   # a margin below 10 % of the limit is "thin" (placeholder policy, NOTES #59)


def mm(text) -> float:
    """'0.2 mm' -> 0.2 (context values are text in the intent file)."""
    s = str(text).strip().lower().replace("mm", "").strip()
    return float(s)


def process(name: str | None) -> dict | None:
    return PROCESSES.get(str(name or ""))


def material(name: str | None) -> dict | None:
    return MATERIALS.get(str(name or "").upper()) or MATERIALS.get(str(name or ""))


def entries() -> dict:
    """Flat `dotted name -> entry` for every pack value (tests, the vocabulary listing)."""
    out = {}
    for k, v in FDM.items():
        if isinstance(v, dict) and "value" in v:
            out[f"FDM.{k}"] = v
    for m, d in MATERIALS.items():
        for k, v in d.items():
            if isinstance(v, dict) and "value" in v:
                out[f"MATERIALS.{m}.{k}"] = v
    for a, d in ANCHORS.items():
        for k, v in d.items():
            if isinstance(v, dict) and "value" in v:
                out[f"ANCHORS[{a}].{k}"] = v
    for k, v in SAFETY_FACTORS.items():
        out[f"SAFETY_FACTORS.{k}"] = v
    out["SCREW_REFERENCE_LENGTH_MM"] = SCREW_REFERENCE_LENGTH_MM
    return out


def appearance(context: dict) -> dict | None:
    """What the renderer needs from the process pack (3E.7): layer pitch, extrusion width,
    detail flags and the material's roughness.  None for processes without appearance data."""
    p = process(context.get("process"))
    if p is None:
        return None
    try:
        layer = mm(context.get("layer_height", p["defaults"]["layer_height"]))
        nozzle = mm(context.get("nozzle", p["defaults"]["nozzle"]))
    except ValueError:
        layer, nozzle = mm(p["defaults"]["layer_height"]), mm(p["defaults"]["nozzle"])
    m = material(context.get("material")) or MATERIALS["PLA"]
    return {"process": p["pack"], "pack_version": p["version"], "layer_pitch": layer,
            "extrusion_width": round(nozzle * p["extrusion_width_factor"]["value"], 4), "nozzle": nozzle,
            "top_line_angle_deg": p["appearance"]["top_line_angle_deg"], "flags": dict(p["appearance"]["flags"]),
            "roughness": m["roughness"], "material": m["label"],
            "placeholder": bool(p["extrusion_width_factor"]["placeholder"])}
