// Evidence rows for the sheet (screen 9). Hurrell 1999 is verified in ProjectDefinition.md;
// the others are marked "to extract" until Person A fills engine_rule_evidence.csv.
export interface EvidenceRow {
  id: string;
  short: string;
  title: string;
  authors: string;
  year: number;
  journal: string;
  value_used: string;
  location: string;
  note: string;
  url?: string;
  verified: boolean;
}

const HURRELL: Omit<EvidenceRow, "id"> = {
  short: "Hurrell et al., 1999",
  title: "Inhibition of non-haem iron absorption in man by polyphenolic-containing beverages",
  authors: "Hurrell RF, Reddy M, Cook JD",
  year: 1999,
  journal: "British Journal of Nutrition",
  value_used: "Black tea reduced non-haem iron absorption by 79 to 94%",
  location: "Table 1",
  note: "Single-meal radioisotope studies in adults. Effect measured with the drink taken alongside the meal.",
  url: "https://doc.rero.ch/record/294784/files/S0007114599000537.pdf",
  verified: true,
};
const HALLBERG_89: Omit<EvidenceRow, "id"> = {
  short: "Hallberg et al., 1989",
  title: "Iron absorption in man: ascorbic acid and dose-dependent inhibition by phytate",
  authors: "Hallberg L, Brune M, Rossander L",
  year: 1989,
  journal: "American Journal of Clinical Nutrition",
  value_used: "Dose-dependent inhibition by phytate, counteracted by vitamin C (value to extract)",
  location: "To extract",
  note: "Mock value until the data team verifies it against the paper.",
  verified: false,
};
const HALLBERG_91: Omit<EvidenceRow, "id"> = {
  short: "Hallberg et al., 1991",
  title: "Calcium: effect of different amounts on nonheme- and heme-iron absorption in humans",
  authors: "Hallberg L, et al.",
  year: 1991,
  journal: "American Journal of Clinical Nutrition",
  value_used: "Reduction at different calcium doses (value to extract)",
  location: "To extract",
  note: "Mock value until the data team verifies it against the paper.",
  verified: false,
};
const MONSEN: Omit<EvidenceRow, "id"> = {
  short: "Monsen et al., 1978",
  title: "Estimation of available dietary iron",
  authors: "Monsen ER, et al.",
  year: 1978,
  journal: "American Journal of Clinical Nutrition",
  value_used: "Haem iron 23% absorbed. Non-haem 3%, 5% or 8% by enhancer units",
  location: "To extract",
  note: "Sets the base absorption before inhibitors are applied.",
  verified: false,
};

export const EVIDENCE: Record<string, EvidenceRow> = Object.fromEntries(
  (
    [
      ["EVID_LINK_IRON_010", HURRELL],
      ["ABS_MOD_IRON_010", HURRELL],
      ["EVID_LINK_IRON_030", HALLBERG_89],
      ["ABS_MOD_IRON_020", HALLBERG_89],
      ["EVID_LINK_IRON_020", HALLBERG_91],
      ["ABS_MOD_IRON_030", HALLBERG_91],
      ["ABS_BASE_MONSEN", MONSEN],
    ] as const
  ).map(([id, row]) => [id, { id, ...row }]),
);

// MOCK validation rows for screen 8. Clearly not real study results.
export const VALIDATION = {
  mae_pp: 2.1,
  rows: [
    { meal: "Bread meal, water", study: "Mock study A", measured: 10.2, predicted: 8.0 },
    { meal: "Bread meal, black tea", study: "Mock study A", measured: 1.6, predicted: 1.8 },
    { meal: "Bread meal, cocoa", study: "Mock study A", measured: 3.1, predicted: 3.9 },
    { meal: "Rice meal", study: "Mock study B", measured: 4.5, predicted: 5.0 },
    { meal: "Rice meal + vitamin C", study: "Mock study B", measured: 9.8, predicted: 8.0 },
    { meal: "Phytate-rich roll", study: "Mock study C", measured: 2.2, predicted: 3.1 },
    { meal: "Roll + 300 mg calcium", study: "Mock study C", measured: 3.0, predicted: 3.6 },
    { meal: "Supplement with coffee", study: "Mock study D", measured: 6.1, predicted: 4.4 },
  ],
  // "Avail" side is computed live from the engine (see EvidenceView); only the published side is fixed.
  relative: [
    { label: "Black tea", food_code: "MOCK_BLACK_TEA", published: "Hurrell 1999 measured 79 to 94%" },
    { label: "Peppermint tea", food_code: "MOCK_PEPPERMINT_TEA", published: "Hurrell 1999 measured 84%" },
    { label: "Camomile tea", food_code: "MOCK_CAMOMILE_TEA", published: "Hurrell 1999 measured 47%" },
    { label: "Cocoa", food_code: "MOCK_COCOA", published: "Hurrell 1999 measured 71%" },
  ],
};
