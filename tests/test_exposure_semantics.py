from agent_experiment_context.events import ExperimentEventRecorder, ExperimentEventType


def add(recorder, kind, at, execution="e1"):
    recorder.record(kind, experiment_id="exp", arm="B", execution_id=execution, component_id="specialist", event_time=at, reason="test")


def test_observed_is_not_exposed():
    recorder = ExperimentEventRecorder()
    add(recorder, ExperimentEventType.OBSERVED, 1.0)
    assert recorder.of_type(ExperimentEventType.EXPOSED) == []


def test_materialized_can_precede_exposed():
    recorder = ExperimentEventRecorder()
    add(recorder, ExperimentEventType.MATERIALIZED, 1.0)
    assert recorder.of_type(ExperimentEventType.EXPOSED) == []
    add(recorder, ExperimentEventType.EXPOSED, 2.0)
    assert recorder.of_type(ExperimentEventType.EXPOSED)[0].event_time == 2.0


def test_later_failure_does_not_remove_prior_event():
    recorder = ExperimentEventRecorder()
    add(recorder, ExperimentEventType.EXPOSED, 2.0)
    assert len(recorder.of_type(ExperimentEventType.EXPOSED)) == 1


def test_raw_repeats_and_first_view():
    recorder = ExperimentEventRecorder()
    add(recorder, ExperimentEventType.EXPOSED, 2.0)
    add(recorder, ExperimentEventType.EXPOSED, 3.0)
    assert len(recorder.of_type(ExperimentEventType.EXPOSED)) == 2
    assert [event.event_time for event in recorder.first_exposures()] == [2.0]


def test_first_view_is_execution_scoped():
    recorder = ExperimentEventRecorder()
    add(recorder, ExperimentEventType.EXPOSED, 2.0, execution="e1")
    add(recorder, ExperimentEventType.EXPOSED, 3.0, execution="e2")
    assert len(recorder.first_exposures()) == 2
