import copy


def sample_project(project_id="proj_test_1"):
    """A small project in the shape static/qda/js/app.js stores (without sources)."""
    return copy.deepcopy({
        "id": project_id,
        "title": "Kilosa Youth Study",
        "description": "Why young people struggle to start businesses",
        "topic": "Youth entrepreneurship",
        "researcher": "Amina",
        "org": "SST",
        "date": "2026-11-24",
        "weightingEnabled": True,
        "memo": "",
        "createdAt": 1795117953695,
        "analyses": [
            {"id": "ana_main", "name": "Challenges", "question": "What holds youth back?"},
            {"id": "ana_politics", "name": "Political uprising factors", "question": ""},
        ],
        "themes": [
            {"id": "thm_finance", "parentId": None, "analysisId": "ana_main", "name": "Finance", "color": "#1B4F9C", "memo": ""},
            {"id": "thm_credit", "parentId": "thm_finance", "name": "No access to credit", "color": "#17B8A6", "memo": ""},
            {"id": "thm_jobs", "parentId": None, "analysisId": "ana_politics", "name": "Unemployment", "color": "#E08E45", "memo": ""},
        ],
        "codings": [
            {"id": "cod_1", "sourceId": "src_kii", "themeIds": ["thm_credit", "thm_jobs"], "start": 0, "end": 22,
             "quote": "We cannot get loans", "weight": 8, "memo": ""},
            {"id": "cod_2", "sourceId": "src_fgd", "speakerId": "sp_1", "themeIds": ["thm_finance"], "start": 11, "end": 40,
             "quote": "Banks ask for land titles", "weight": None, "memo": "strong"},
        ],
    })


def sample_sources():
    return copy.deepcopy([
        {"id": "src_kii", "type": "KII", "name": "KII 01 — youth leader", "text": "We cannot get loans from the banks here.",
         "memo": "", "speakers": [],
         "attributes": {"respondentId": "R01", "sex": "Female", "location": "Kilosa", "stakeholder": ["Youth", "Trader"]}},
        {"id": "src_fgd", "type": "FGD", "name": "FGD 01 — market traders", "text": "Speaker 1: Banks ask for land titles we do not have.",
         "memo": "", "speakers": [{"id": "sp_1", "label": "Participant 1"}],
         "attributes": {"respondentId": "FGD-01", "stakeholder": ["Trader"], "participants": {"women": 4, "men": 3, "undisclosed": 1}}},
    ])


def full_document(project_id="proj_test_1"):
    doc = sample_project(project_id)
    doc["sources"] = sample_sources()
    return doc
