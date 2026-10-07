from app.api.icp import DEFAULT_WEIGHTS, discovery_defaults, normalize_profile, profile_complete, score_lead

def profile():
    return normalize_profile({
        "offer":"Content production",
        "target_industries":["boutique hotel"],
        "business_types":["independent hospitality"],
        "geography":["Miami, FL"],
        "buyer_roles":["Owner","Marketing Manager"],
        "problems_solved":["weak visual content"],
        "positive_signals":["new location","expanding"],
        "excluded_industries":["payday lending"],
        "excluded_geographies":["California"],
        "ideal_customer_value":1500,
    })

def test_icp_score_is_explainable_and_profile_driven():
    result=score_lead({"name":"Harbor Boutique Hotel expanding","category":"boutique hotel","city":"Miami","state":"FL","phone":"3055550100","owner":"A. Owner"},profile(),DEFAULT_WEIGHTS)
    assert result["score"] >= 80
    assert result["priority"] == "HIGH_PRIORITY"
    assert result["matches"]
    assert result["recommended_action"]
    assert set(result["dimensions"]) == {"fit","need","authority","value","friction","timing"}

def test_hard_geography_mismatch_caps_score():
    result=score_lead({"name":"Harbor Boutique Hotel expanding","category":"boutique hotel","city":"Los Angeles","state":"CA","phone":"1","owner":"Owner"},profile(),DEFAULT_WEIGHTS)
    assert result["score"] <= 49
    assert result["priority"] == "LOW_PRIORITY"
    assert result["disqualifiers"]

def test_profile_completion_and_discovery_defaults():
    value=profile()
    assert profile_complete(value)
    defaults=discovery_defaults(value)
    assert defaults["suggested_business_type"] == "independent hospitality"
    assert defaults["suggested_city"] == "Miami"
    assert defaults["suggested_state"] == "FL"


def test_contact_offer_value_and_name_do_not_inflate_business_fit():
    base={"name":"Hotel expanding", "city":"Miami","state":"FL"}
    result=score_lead({**base,"phone":"555","owner":"Owner"},profile())
    assert result['score']==50
    assert result['signals']==[]
    assert result['score_type']=='RECORDED_CRITERIA_FIT'
    assert score_lead({**base,"category":"boutique hotel","city":"Orlando"},profile())['score']<=49
