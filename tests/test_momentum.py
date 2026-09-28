from app.api.momentum import EVENT_POINTS, LEVELS, level_for


def test_momentum_rewards_meaningful_sales_events_only():
    assert "page_view" not in EVENT_POINTS
    assert "button_clicked" not in EVENT_POINTS
    assert EVENT_POINTS["qualified_lead_contacted"] < EVENT_POINTS["meeting_booked"]
    assert EVENT_POINTS["meeting_booked"] < EVENT_POINTS["deal_won"]


def test_levels_report_current_and_next_progress():
    progress = level_for(740)
    assert progress == {
        "name": "Pipeline Builder",
        "floor": 300,
        "next_name": "Conversation Starter",
        "next_at": 750,
        "remaining": 10,
    }
    assert level_for(LEVELS[-1][1] + 100)["next_name"] is None
