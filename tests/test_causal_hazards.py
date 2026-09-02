from agent_experiment_context.causal_hazards import (
    RoutedUnit,
    TenantMemorySpecialist,
    effect_of_a_given_b,
    intent_to_treat_mean,
    marginal_effect_of_a_when_b_balanced,
    observed_exposure_mean,
)


def test_shared_tenant_state_contaminates_later_control_execution():
    specialist = TenantMemorySpecialist()

    clean_control = specialist.answer(
        tenant_id="tenant-clean", arm="control", request="invoice"
    )
    specialist.answer(tenant_id="tenant-shared", arm="treatment", request="refund")
    contaminated_control = specialist.answer(
        tenant_id="tenant-shared", arm="control", request="invoice"
    )

    assert clean_control == "arm=control;memory=empty"
    assert contaminated_control == "arm=control;memory=refund"


def test_conditioning_on_treatment_dependent_exposure_creates_false_effect():
    units = [
        RoutedUnit("easy-1", "easy", 10.0),
        RoutedUnit("easy-2", "easy", 10.0),
        RoutedUnit("hard-1", "hard", 0.0),
        RoutedUnit("hard-2", "hard", 0.0),
    ]

    # There is no treatment effect on the potential outcome by construction.
    assert intent_to_treat_mean(units) == 5.0

    # Yet conditioning on who was actually routed/exposed creates a false delta.
    control_exposed = observed_exposure_mean("control", units)
    treatment_exposed = observed_exposure_mean("treatment", units)
    assert control_exposed == 0.0
    assert treatment_exposed == 5.0
    assert treatment_exposed - control_exposed == 5.0


def test_concurrent_interaction_can_hide_opposite_conditional_effects():
    assert effect_of_a_given_b("control") == 2.0
    assert effect_of_a_given_b("treatment") == -2.0
    assert marginal_effect_of_a_when_b_balanced() == 0.0
