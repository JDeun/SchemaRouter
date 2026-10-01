"""Run the separately packaged decision-backend entry-point example.

Install the example package first:

    python -m pip install -e examples/decision_backend_plugin_demo
"""

from schemarouter import (
    DecisionOption,
    DecisionRequest,
    choose_sync,
    discover_decision_backend_plugins,
    load_decision_backend_plugin,
)


def main() -> None:
    discovered = {plugin.name: plugin for plugin in discover_decision_backend_plugins()}
    plugin = discovered["demo_bounded"]
    assert plugin.value == "schemarouter_demo_decision:DemoBoundedDecisionBackend"

    backend = load_decision_backend_plugin("demo_bounded")

    selected = choose_sync(
        backend,
        DecisionRequest(
            query="use weather for this request",
            options=[
                DecisionOption(id="weather", label="Weather"),
                DecisionOption(id="search", label="Search"),
            ],
        ),
    )
    assert [item.option_id for item in selected.selections] == ["weather"]
    assert selected.abstained is False

    abstained = choose_sync(
        backend,
        DecisionRequest(
            query="none of the registered choices match",
            options=[
                DecisionOption(id="weather", label="Weather"),
                DecisionOption(id="search", label="Search"),
            ],
        ),
    )
    assert abstained.selections == []
    assert abstained.abstained is True

    substring_only = choose_sync(
        backend,
        DecisionRequest(
            query="weathered data should not select that route",
            options=[
                DecisionOption(id="weather", label="Weather"),
                DecisionOption(id="search", label="Search"),
            ],
        ),
    )
    assert substring_only.selections == []
    assert substring_only.abstained is True

    print(
        {
            "plugin": plugin.name,
            "selected": selected.selections[0].option_id,
            "abstained_when_unmatched": abstained.abstained,
        }
    )


if __name__ == "__main__":
    main()
