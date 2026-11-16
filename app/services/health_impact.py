"""Server-derived respiratory impact for /predict_policy.

STAGE 1 ONLY. Only the respiratory figure is computed here, from published
coefficients (app/data/health_coefficients.py). The other three health outputs
- healthcare savings, quality-of-life gain, life-expectancy gain - remain
model-generated (gated and flagged ``*_unsourced``) and are OUT OF SCOPE for
this change.

Method (odds-ratio model on a published baseline prevalence):
    odds0 = p0 / (1 - p0)
    odds1 = odds0 * OR ** ((new_pm25 - current_pm25) / 10)
    fewer cases per 100,000 under-fives = (p0 - p1) * 100_000

No population multiplier: the figure is a rate per 100,000 children under five,
because the state table holds total population and no sourced under-5 share.
Multiplying by total population would overstate the count about 10x.

Worse policy (new_pm25 > current_pm25): the result is NEGATIVE, i.e. more
cases, and ``direction`` says "increase". It is not clamped to zero, because a
decision-support tool must not hide that a policy is predicted to make things
worse. Zero change gives exactly 0 and "no_change".
"""

from app.data.health_coefficients import (
    ARI_BASELINE_SOURCE,
    ARI_BASELINE_URL,
    HEALTH_COEFFICIENTS,
    NATIONAL_ARI_PREVALENCE,
    STATE_ARI_PREVALENCE,
)
from app.models.datamodel1 import RespiratoryImpact

_PER = 100_000


def _baseline_percent(state: str) -> tuple[float, str]:
    """State prevalence, or the national figure when the state estimate is too
    imprecise (95% CI lower bound is 0.0, i.e. a tiny NFHS sample)."""
    row = STATE_ARI_PREVALENCE.get(state)
    if row is not None and row[1] > 0.0:
        return row[0], "state"
    return NATIONAL_ARI_PREVALENCE[0], "national"


def respiratory_impact(
    state: str, current_pm25: float, new_pm25: float
) -> RespiratoryImpact:
    coef = HEALTH_COEFFICIENTS["pm25_respiratory"]
    base_pct, basis = _baseline_percent(state)
    p0 = base_pct / 100.0
    odds0 = p0 / (1.0 - p0)
    odds1 = odds0 * coef["coefficient"] ** (
        (new_pm25 - current_pm25) / coef["per_ug_m3"]
    )
    p1 = odds1 / (1.0 + odds1)
    fewer = round((p0 - p1) * _PER, 4)
    if fewer == 0:
        fewer = 0.0  # no "-0.0"
    direction = "reduction" if fewer > 0 else "increase" if fewer < 0 else "no_change"

    caveat = (
        "Estimate for ARI symptoms in children under five (2-week prevalence), "
        "not all-age or annual cases. Uses one published odds ratio "
        f"{coef['coefficient']} (95% CI {coef['ci_95'][0]}-{coef['ci_95'][1]}) per "
        "10 ug/m3 PM2.5 from a cross-sectional study of long-term exposure; it is "
        "associational and another Indian study reports a higher OR (1.23). "
        f"The baseline is the {basis} NFHS-5 prevalence "
        f"({base_pct}%), mother-reported and not clinically validated. "
        "new_pm25 is a model estimate, not a measurement."
    )
    if basis == "national":
        caveat += (
            " The state's own NFHS-5 estimate was too imprecise (CI reaches 0), "
            "so the national prevalence was used."
        )
    return RespiratoryImpact(
        outcome="ARI symptoms in children under 5 (2-week prevalence)",
        current_pm25=current_pm25,
        new_pm25=new_pm25,
        baseline_prevalence_percent=base_pct,
        baseline_basis=basis,
        new_prevalence_percent=round(p1 * 100, 4),
        fewer_respiratory_cases_per_100k_under5=fewer,
        direction=direction,
        odds_ratio_per_10_ug_m3=coef["coefficient"],
        coefficient_source_url=coef["source_url"],
        coefficient_source_year=coef["source_year"],
        baseline_source_url=ARI_BASELINE_URL,
        baseline_source=ARI_BASELINE_SOURCE,
        coefficient_caveat=caveat,
    )
