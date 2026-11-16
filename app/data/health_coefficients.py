"""Published health coefficients for the Policy Simulator.

STAGE 1 (this file): respiratory outcome only. The other three health outputs
(healthcare savings, quality-of-life gain, life-expectancy gain) are still
model-generated and are OUT OF SCOPE here; they stay gated and flagged
``*_unsourced`` (see UNSOURCED_HEALTH_FIELDS).

Why this is not "cases per 100k per ug/m3": no published, defensible
coefficient in that unit was found. Published exposure-response figures are
odds/relative risks, and turning them into cases needs a baseline rate. So the
method is: published odds ratio x published baseline prevalence.

Outcome: acute respiratory infection (ARI) symptoms in children under five,
as 2-week period prevalence. Mother-reported "cough with short, rapid,
chest-related breathing in the two weeks before the survey". It is NOT annual
incidence, NOT all ages, and NOT clinician-diagnosed.
"""

# --- Exposure-response: odds ratio per 10 ug/m3 of PM2.5 -----------------------
HEALTH_COEFFICIENTS = {
    "pm25_respiratory": {
        "coefficient": 1.11,  # odds ratio per +10 ug/m3 PM2.5; 95% CI 1.08-1.13
        "ci_95": (1.08, 1.13),
        "per_ug_m3": 10.0,
        "unit": (
            "odds ratio of ARI symptoms (children under 5, 2-week prevalence) "
            "per +10 ug/m3 ambient PM2.5"
        ),
        "source": (
            "Chaudhary E, George F, Saji A, et al. Cumulative effect of PM2.5 "
            "components is larger than the effect of PM2.5 mass on child "
            "health in India. Nat Commun 14, 6955 (2023). doi:10.1038/s41467-023-42709-1"
        ),
        "source_url": "https://www.nature.com/articles/s41467-023-42709-1",
        "source_year": 2023,
        "notes": (
            "Cross-sectional NFHS-4 (2015-16) under-5s; exposure is the "
            "life-course average of monthly satellite-derived PM2.5 at "
            "cluster level, so it reflects long-term, not short-term, change. "
            "Associational, not causal. The authors report mostly nonlinear, "
            "non-monotonic exposure-response curves and possible unadjusted "
            "confounding; a single constant odds ratio is a simplification. "
            "A separate DHS analysis (Environ Health 2024) reports OR 1.23 "
            "(1.19-1.27), so the estimate is study-dependent."
        ),
    }
}

# --- Baseline: ARI 2-week prevalence in under-5s, NFHS-5 (2019-21) --------------
ARI_BASELINE_SOURCE = (
    "Varghese JS, Muhammad T. Prevalence, potential determinants, and "
    "treatment-seeking behavior of acute respiratory infection among children "
    "under age five in India: Findings from the National Family Health Survey, "
    "2019-21. BMC Pulm Med 23, 195 (2023). doi:10.1186/s12890-023-02487-4, Table 1"
)
ARI_BASELINE_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC10243276/"
ARI_BASELINE_YEAR = 2023  # publication year; survey fieldwork 2019-21

NATIONAL_ARI_PREVALENCE = (2.8, 2.7, 2.9)  # percent: value, CI low, CI high

# Percent (value, CI low, CI high), transcribed from Table 1. Keys match
# app/data/state_population.STATE_POPULATION.
STATE_ARI_PREVALENCE: dict[str, tuple[float, float, float]] = {
    "Andaman and Nicobar Islands": (1.7, 0.0, 5.7),
    "Andhra Pradesh": (2.4, 2.0, 2.8),
    "Arunachal Pradesh": (2.1, 0.0, 4.3),
    "Assam": (2.5, 2.1, 2.9),
    "Bihar": (3.5, 3.3, 3.8),
    "Chandigarh": (0.3, 0.0, 1.3),
    "Chhattisgarh": (1.5, 1.1, 1.8),
    "Dadra and Nagar Haveli and Daman and Diu": (0.3, 0.0, 1.5),
    "Delhi": (5.6, 4.8, 6.4),
    "Goa": (0.9, 0.0, 2.3),
    "Gujarat": (1.0, 0.8, 1.2),
    "Haryana": (2.3, 1.8, 2.7),
    "Himachal Pradesh": (1.5, 0.7, 2.2),
    "Jammu and Kashmir": (3.9, 2.9, 4.8),
    "Jharkhand": (2.1, 1.8, 2.4),
    "Karnataka": (1.5, 1.3, 1.8),
    "Kerala": (2.4, 2.0, 2.9),
    "Ladakh": (5.3, 0.0, 14.0),
    "Lakshadweep": (1.4, 0.0, 9.1),
    "Madhya Pradesh": (2.6, 2.3, 2.9),
    "Maharashtra": (3.2, 2.9, 3.4),
    "Manipur": (1.8, 0.5, 3.0),
    "Meghalaya": (4.8, 3.4, 6.3),
    "Mizoram": (0.6, 0.0, 1.7),
    "Nagaland": (1.1, 0.0, 2.5),
    "Odisha": (3.2, 2.7, 3.6),
    "Puducherry": (4.9, 1.4, 8.4),
    "Punjab": (2.5, 2.0, 2.9),
    "Rajasthan": (2.9, 2.7, 3.2),
    "Sikkim": (0.7, 0.0, 2.9),
    "Tamil Nadu": (1.1, 0.9, 1.3),
    "Telangana": (2.2, 1.8, 2.6),
    "Tripura": (1.3, 0.4, 2.2),
    "Uttar Pradesh": (3.5, 3.4, 3.7),
    "Uttarakhand": (2.3, 1.6, 3.0),
    "West Bengal": (2.8, 2.6, 3.1),
}
