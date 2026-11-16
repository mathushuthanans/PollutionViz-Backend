"""Fixed state population table and its use in analyse_policy."""

import pytest

from app.data.state_population import STATE_POPULATION, get_state_population
from app.errors import UnknownStateError
from app.models.datamodel1 import PredictPolicyRequest
from app.services.policy_impact import analyse_policy


@pytest.fixture
def request_obj(valid_request):
    return PredictPolicyRequest(**valid_request)


def test_known_state_returns_table_values():
    row = get_state_population("Maharashtra")
    assert row["state"] == "Maharashtra"
    assert row["population"] == 112_374_333
    assert row["year"] == 2011
    assert row["source"]


def test_lookup_ignores_case_whitespace_and_diacritics():
    assert get_state_population("  maharashtra ")["state"] == "Maharashtra"
    assert get_state_population("TAMIL   NADU")["state"] == "Tamil Nadu"
    assert get_state_population("Tamil Nādu")["state"] == "Tamil Nadu"
    assert get_state_population("Jammu & Kashmir")["state"] == "Jammu and Kashmir"


@pytest.mark.parametrize("name", ["Atlantis", "", "   ", "Mumbai"])
def test_unknown_state_raises_unknown_state_error(name):
    with pytest.raises(UnknownStateError):
        get_state_population(name)


def test_table_covers_28_states_and_8_uts():
    assert len(STATE_POPULATION) == 36


@pytest.mark.parametrize("name", sorted(STATE_POPULATION))
def test_every_entry_is_sourced_and_urban_plus_rural_is_100(name):
    row = STATE_POPULATION[name]
    assert isinstance(row["population"], int) and row["population"] > 0
    assert row["source"].strip()
    assert isinstance(row["year"], int)
    assert row["urban_pct"] + row["rural_pct"] == pytest.approx(100, abs=1e-6)


def test_model_reply_with_wrong_population_is_overwritten(
    request_obj, valid_estimate, fake_ask
):
    valid_estimate.update(total_population=1, urban_percent=1.0, rural_percent=99.0)
    ask = fake_ask(valid_estimate)
    result = analyse_policy(request_obj, ask=ask)

    table = STATE_POPULATION["Maharashtra"]
    pop = result.measured.population
    assert pop.total_population == table["population"]
    assert pop.urban_percent == table["urban_pct"]
    assert pop.rural_percent == table["rural_pct"]
    assert pop.source == table["source"] and pop.year == table["year"]
    dumped = result.model_dump()["estimated"]
    assert not {"total_population", "urban_percent", "rural_percent"} & dumped.keys()
    assert ask.calls == 1  # a wrong population is discarded, not a retry


def test_urban_plus_rural_still_sums_to_100_in_the_response(
    request_obj, valid_estimate, fake_ask
):
    result = analyse_policy(request_obj, ask=fake_ask(valid_estimate))
    pop = result.measured.population
    assert pop.urban_percent + pop.rural_percent == pytest.approx(100, abs=0.01)


def test_prompt_injects_fixed_population_and_does_not_ask_for_it(
    request_obj, valid_estimate, fake_ask
):
    ask = fake_ask(valid_estimate)
    analyse_policy(request_obj, ask=ask)
    prompt = ask.prompts[0]
    assert "Population: 112374333, urban 45.22%, rural 54.78%" in prompt
    assert "do not change these" in prompt
    assert '"total_population"' not in prompt  # not in the schema sent to the model


def test_unknown_state_fails_before_any_model_call(valid_request, fake_ask):
    valid_request["location"] = "Atlantis"
    ask = fake_ask()
    with pytest.raises(UnknownStateError):
        analyse_policy(PredictPolicyRequest(**valid_request), ask=ask)
    assert ask.calls == 0
