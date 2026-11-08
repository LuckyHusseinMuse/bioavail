"""Batch 002: phytate, calcium, cocoa, herbal tea and coffee timing.

Sources (abstracts checked 2026-11-07):
- Hallberg, Brune, Rossander 1989 (IRON_015): 2 / 25 / 250 mg phytate P -> 18 / 64 / 82% inhibition; ascorbic acid counteracts.
- Hallberg et al. 1991 (IRON_016): 165 mg Ca -> 50-60% inhibition of non-haem and also haem iron; dose related up to 300 mg; 300-600 mg -> 50-60%.
- Siegenberg et al. 1991 (IRON_022): inhibition from 10-58 mg phytate P (maize bran) overcome by 30 mg ascorbic acid.
- Hurrell et al. 1999 (IRON_013): cocoa 71%, peppermint 84%, camomile 47%.
- Morck, Lynch, Cook 1983 (IRON_023): coffee 1 h before a meal no effect; 1 h after same inhibition as with the meal.

Run once: python -m pipeline.batches.batch_002_phytate_calcium_coffee
"""
from pipeline.append_rows import append, common

C = common()

mod_base = {**C, "target_nutrient": "Iron", "applicable_nutrient_form": "Non_Haem_Iron",
            "timing_relationship": "With_Meal", "timing_min": "0", "timing_max": "0", "timing_unit": "Minutes",
            "effect_measure_type": "Relative_Percent_Change", "effect_unit": "%",
            "population_scope": "General_Adult", "calculation_method": "Multiply_Baseline",
            "calculation_eligible": "True", "evidence_strength": "Moderate"}

phytate = {**mod_base, "modifier_type": "Dietary_Component", "effect_direction": "Inhibitor",
           "source_context": "Food", "modifier_dose_unit": "mg_phytate_phosphorus",
           "dose_response_present": "True", "timing_dependent": "False",
           "population_description": "Healthy adults; radio-iron absorption from wheat rolls with added sodium phytate (Hallberg 1989)",
           "interaction_priority": "1", "stacking_allowed": "False"}

calcium = {**mod_base, "modifier_type": "Dietary_Component", "effect_direction": "Inhibitor",
           "source_context": "Food", "modifier_dose_unit": "mg_calcium",
           "dose_response_present": "True", "timing_dependent": "False",
           "population_description": "Healthy adults (126 subjects); calcium as milk, cheese or calcium chloride (Hallberg 1991)",
           "interaction_priority": "1", "stacking_allowed": "False"}

hurrell_drink = {**mod_base, "modifier_type": "Food", "effect_direction": "Inhibitor", "source_context": "Beverage",
                 "timing_max": "60", "dose_response_present": "False", "timing_dependent": "True",
                 "population_description": "Healthy adults; radio-iron absorption from a bread meal (Hurrell 1999)",
                 "interaction_priority": "2", "stacking_allowed": "False"}

append("absorption_modifiers.csv", "modifier_id", [
    {**phytate, "modifier_id": "ABS_MOD_IRON_005", "modifier_name": "Phytate_P_2mg",
     "modifier_dose_min": "2", "modifier_dose_max": "2", "effect_value": "-18",
     "effect_interpretation": "2 mg phytate phosphorus reduced non-haem iron absorption by 18%.",
     "applicability_notes": "Dose-response point. Engine interpolates on log dose between phytate points (005, 006, 007); "
                            "0% effect at 0 mg. Food phytate in mg is converted to phytate P using 28.2% (ASSUME_002)."},
    {**phytate, "modifier_id": "ABS_MOD_IRON_006", "modifier_name": "Phytate_P_25mg",
     "modifier_dose_min": "25", "modifier_dose_max": "25", "effect_value": "-64",
     "effect_interpretation": "25 mg phytate phosphorus reduced non-haem iron absorption by 64%.",
     "applicability_notes": "Dose-response point; see ABS_MOD_IRON_005."},
    {**phytate, "modifier_id": "ABS_MOD_IRON_007", "modifier_name": "Phytate_P_250mg",
     "modifier_dose_min": "250", "modifier_dose_max": "250", "effect_value": "-82",
     "effect_interpretation": "250 mg phytate phosphorus reduced non-haem iron absorption by 82%.",
     "applicability_notes": "Dose-response point; held at 82% above 250 mg."},
    {**mod_base, "modifier_id": "ABS_MOD_IRON_008", "modifier_name": "Ascorbic_Acid_Phytate_Counteraction",
     "modifier_type": "Dietary_Component", "effect_direction": "Enhancer", "source_context": "Food",
     "modifier_dose_min": "30", "modifier_dose_max": "30", "modifier_dose_unit": "mg_ascorbic_acid",
     "target_dose_min": "10", "target_dose_max": "58", "target_dose_unit": "mg_phytate_phosphorus",
     "effect_measure_type": "Proportion_Of_Inhibition_Removed", "effect_value": "100",
     "effect_interpretation": "30 mg ascorbic acid overcame the inhibition from maize bran containing 10-58 mg phytate P.",
     "dose_response_present": "True", "timing_dependent": "False",
     "population_description": "Adults; maize bran meals (Siegenberg 1991)",
     "interaction_priority": "1", "stacking_allowed": "True",
     "applicability_notes": "Engine removes phytate inhibition in proportion to ascorbic acid, scaled at 30 mg per 58 mg phytate P "
                            "(ASSUME_005). Shown on the phytate waterfall bar, not as a separate vitamin C bar."},
    {**calcium, "modifier_id": "ABS_MOD_IRON_009", "modifier_name": "Calcium_NonHaem_165mg",
     "modifier_dose_min": "165", "modifier_dose_max": "165", "effect_lower": "-60", "effect_upper": "-50",
     "effect_interpretation": "165 mg calcium (milk, cheese or calcium chloride) reduced non-haem iron absorption by 50-60%.",
     "applicability_notes": "Below 165 mg the engine scales linearly from 0% at 0 mg (ASSUME_006)."},
    {**calcium, "modifier_id": "ABS_MOD_IRON_010", "modifier_name": "Calcium_NonHaem_300_600mg",
     "modifier_dose_min": "300", "modifier_dose_max": "600", "effect_lower": "-60", "effect_upper": "-50",
     "effect_interpretation": "Inhibition was dose related up to 300 mg calcium; 300-600 mg reduced absorption by 50-60%.",
     "applicability_notes": "Held at this range above 600 mg."},
    {**calcium, "modifier_id": "ABS_MOD_IRON_011", "modifier_name": "Calcium_Haem",
     "applicable_nutrient_form": "Haem_Iron", "modifier_dose_min": "165", "modifier_dose_max": "165",
     "effect_interpretation": "165 mg calcium also reduced haem iron absorption; size not given in the abstract.",
     "calculation_eligible": "False",
     "applicability_notes": "Qualitative until the full text is extracted. Engine does not apply calcium to haem iron yet."},
    {**hurrell_drink, "modifier_id": "ABS_MOD_IRON_012", "modifier_name": "Cocoa",
     "effect_value": "-71",
     "effect_interpretation": "Cocoa reduced non-haem iron absorption by 71% versus water.",
     "applicability_notes": "Food-specific; replaces the polyphenol dose bands for cocoa."},
    {**hurrell_drink, "modifier_id": "ABS_MOD_IRON_013", "modifier_name": "Herbal_Tea",
     "effect_lower": "-84", "effect_upper": "-47",
     "effect_interpretation": "Herbal teas reduced non-haem iron absorption by 47% (camomile) to 84% (peppermint) versus water.",
     "applicability_notes": "Generic herbal tea (CoFID 17-172). Range spans the herbal teas tested; specific teas could get their own rows."},
])

rule_base = {**C, "target_nutrient": "Iron", "applicable_nutrient_form": "Non_Haem_Iron",
             "rule_type": "Dietary_Interaction_Rule", "population_scope": "General_Adult",
             "population_description": "Healthy adults eating a meal containing non-haem iron",
             "effect_direction": "Inhibitor", "calculation_action": "Apply_Modifier",
             "qualitative_only": "False", "evidence_strength": "Moderate"}

append("interaction_rules.csv", "rule_id", [
    {**rule_base, "rule_id": "RULE_IRON_004", "trigger_entity": "High_Phytate_Meal", "trigger_entity_type": "Meal_Component",
     "trigger_condition": "Meal contains at least 25 mg phytate phosphorus (about 89 mg phytate) and less than 30 mg vitamin C.",
     "timing_relationship": "With_Meal", "timing_min": "0", "timing_max": "0", "timing_unit": "Minutes",
     "modifier_id": "ABS_MOD_IRON_006", "recommendation_action": "Recommend_Addition",
     "recommendation_text_template": "The wholegrains, beans or seeds in this meal contain phytate, which reduces the iron you absorb "
                                     "by about {reduction_pct}%. Adding a vitamin C rich food such as {suggestion} counteracts it.",
     "recommendation_priority": "2", "conflict_group": "IRON_PHYTATE",
     "suppress_if_condition": "vitamin_c_mg >= 30",
     "applicability_notes": "Thresholds from Hallberg 1989 (25 mg phytate P) and Siegenberg 1991 (30 mg ascorbic acid)."},
    {**rule_base, "rule_id": "RULE_IRON_005", "trigger_entity": "High_Calcium_Meal", "trigger_entity_type": "Meal_Component",
     "trigger_condition": "Meal and drinks within the meal window contain at least 165 mg calcium.",
     "timing_relationship": "With_Meal", "timing_min": "0", "timing_max": "60", "timing_unit": "Minutes",
     "modifier_id": "ABS_MOD_IRON_009", "recommendation_action": "Recommend_Alternate_Timing",
     "recommendation_text_template": "The calcium in this meal ({calcium_sources}) can reduce the iron you absorb by about {reduction_pct}%. "
                                     "Having dairy at a different meal from your main iron source helps.",
     "recommendation_priority": "3", "conflict_group": "IRON_CALCIUM",
     "applicability_notes": "60-minute window is an assumption (ASSUME_004); Hallberg 1991 gave calcium with the meal. "
                            "Lower priority than drinks: calcium matters for bone health and should not be cut."},
    {**rule_base, "rule_id": "RULE_IRON_006", "trigger_entity": "Coffee", "trigger_entity_type": "Beverage",
     "trigger_condition": "Coffee is drunk with, or up to 120 minutes after, a meal containing non-haem iron.",
     "timing_relationship": "With_Meal", "timing_min": "0", "timing_max": "120", "timing_unit": "Minutes",
     "modifier_id": "ABS_MOD_IRON_003", "recommendation_action": "Recommend_Alternate_Timing",
     "recommendation_text_template": "Coffee with or after this meal can cut the non-haem iron you absorb by about {reduction_pct}%. "
                                     "Waiting an hour afterwards does not help, but coffee an hour before the meal had no effect.",
     "recommendation_priority": "1", "conflict_group": "IRON_POLYPHENOL_BEVERAGE", "override_rule_id": "RULE_IRON_003",
     "applicability_notes": "Morck 1983: no effect 1 h before; full effect 1 h after. Window end of 120 min is an assumption "
                            "(no data beyond 60 min). Overrides RULE_IRON_003 for coffee. Dose from ETH 2023 (219 mg polyphenols per cup)."},
])

ev = {**C, "evidence_direction": "Supports", "exclusion_from_calculation": "False", "quantitative_unit": "%"}
h89 = {**ev, "paper_id": "IRON_015", "engine_entity_type": "Absorption_Modifier", "evidence_role": "Primary_Support",
       "contribution_type": "Dose_Response", "evidence_quality": "Moderate", "applicability_match": "Direct",
       "inclusion_reason": "Direct human radio-iron absorption evidence for dose-dependent phytate inhibition."}
h91 = {**ev, "paper_id": "IRON_016", "engine_entity_type": "Absorption_Modifier", "evidence_role": "Primary_Support",
       "contribution_type": "Dose_Response", "evidence_quality": "Moderate", "applicability_match": "Direct",
       "inclusion_reason": "Direct human absorption evidence for calcium at 40-600 mg."}
hu = {**ev, "paper_id": "IRON_013", "engine_entity_type": "Absorption_Modifier", "evidence_role": "Primary_Support",
      "contribution_type": "Quantitative_Effect", "evidence_quality": "Moderate", "applicability_match": "Direct",
      "inclusion_reason": "Direct human radio-iron absorption evidence for polyphenol-containing beverages served with a meal."}

append("engine_rule_evidence.csv", "rule_evidence_id", [
    {**h89, "rule_evidence_id": "EVID_LINK_MOD_IRON_006", "engine_entity_id": "ABS_MOD_IRON_005", "quantitative_value_used": "-18.0",
     "synthesis_notes": "2 mg phytate P: 18% inhibition (abstract)."},
    {**h89, "rule_evidence_id": "EVID_LINK_MOD_IRON_007", "engine_entity_id": "ABS_MOD_IRON_006", "quantitative_value_used": "-64.0",
     "synthesis_notes": "25 mg phytate P: 64% inhibition (abstract)."},
    {**h89, "rule_evidence_id": "EVID_LINK_MOD_IRON_008", "engine_entity_id": "ABS_MOD_IRON_007", "quantitative_value_used": "-82.0",
     "synthesis_notes": "250 mg phytate P: 82% inhibition (abstract)."},
    {**ev, "rule_evidence_id": "EVID_LINK_MOD_IRON_009", "engine_entity_type": "Absorption_Modifier", "engine_entity_id": "ABS_MOD_IRON_008",
     "paper_id": "IRON_022", "evidence_role": "Primary_Support", "contribution_type": "Quantitative_Effect",
     "quantitative_value_used": "100.0", "evidence_quality": "Moderate", "applicability_match": "Partial",
     "inclusion_reason": "Human absorption study showing 30 mg ascorbic acid overcame phytate inhibition from maize bran.",
     "synthesis_notes": "Inhibition from 10-58 mg phytate P overcome by 30 mg ascorbic acid (abstract). Linear scaling is ASSUME_005."},
    {**h89, "rule_evidence_id": "EVID_LINK_MOD_IRON_010", "engine_entity_id": "ABS_MOD_IRON_008", "evidence_role": "Supporting",
     "contribution_type": "Qualitative_Effect", "applicability_match": "Direct",
     "synthesis_notes": "Ascorbic acid significantly counteracted phytate inhibition (abstract)."},
    {**h91, "rule_evidence_id": "EVID_LINK_MOD_IRON_011", "engine_entity_id": "ABS_MOD_IRON_009",
     "quantitative_lower_used": "-60.0", "quantitative_upper_used": "-50.0",
     "synthesis_notes": "165 mg calcium: 50-60% inhibition of non-haem iron (abstract)."},
    {**h91, "rule_evidence_id": "EVID_LINK_MOD_IRON_012", "engine_entity_id": "ABS_MOD_IRON_010",
     "quantitative_lower_used": "-60.0", "quantitative_upper_used": "-50.0",
     "synthesis_notes": "Dose related up to 300 mg; 300-600 mg: 50-60% inhibition (abstract)."},
    {**h91, "rule_evidence_id": "EVID_LINK_MOD_IRON_013", "engine_entity_id": "ABS_MOD_IRON_011",
     "contribution_type": "Qualitative_Effect", "exclusion_from_calculation": "True",
     "exclusion_reason": "Haem effect size not reported in the abstract.",
     "synthesis_notes": "165 mg calcium also inhibited haem iron absorption."},
    {**hu, "rule_evidence_id": "EVID_LINK_MOD_IRON_014", "engine_entity_id": "ABS_MOD_IRON_012", "quantitative_value_used": "-71.0",
     "synthesis_notes": "Cocoa: 71% inhibition (abstract)."},
    {**hu, "rule_evidence_id": "EVID_LINK_MOD_IRON_015", "engine_entity_id": "ABS_MOD_IRON_013",
     "quantitative_lower_used": "-84.0", "quantitative_upper_used": "-47.0",
     "synthesis_notes": "Peppermint 84%, pennyroyal 73%, vervain 59%, lime flower 52%, camomile 47% (abstract)."},
    {**h89, "rule_evidence_id": "EVID_LINK_IRON_009", "engine_entity_type": "Interaction_Rule", "engine_entity_id": "RULE_IRON_004",
     "quantitative_value_used": "-64.0", "synthesis_notes": "Trigger threshold 25 mg phytate P."},
    {**h91, "rule_evidence_id": "EVID_LINK_IRON_010", "engine_entity_type": "Interaction_Rule", "engine_entity_id": "RULE_IRON_005",
     "quantitative_lower_used": "-60.0", "quantitative_upper_used": "-50.0", "synthesis_notes": "Trigger threshold 165 mg calcium."},
    {**ev, "rule_evidence_id": "EVID_LINK_IRON_011", "engine_entity_type": "Interaction_Rule", "engine_entity_id": "RULE_IRON_006",
     "paper_id": "IRON_023", "evidence_role": "Primary_Support", "contribution_type": "Timing_Window",
     "quantitative_value_used": "60", "quantitative_unit": "minutes", "evidence_quality": "Moderate", "applicability_match": "Direct",
     "inclusion_reason": "Human absorption study of coffee timing relative to a meal.",
     "synthesis_notes": "Coffee 1 h before a meal: no decrease. Coffee 1 h after: same inhibition as with the meal. "
                        "Inhibition magnitudes (39% hamburger meal) held out for validation."},
])
