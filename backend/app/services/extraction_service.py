def extract_mock(text: str) -> dict:
    return {
        "document": {
            "title": None,
            "content_hash": "mock_hash",
        },
        "entities": [
            {
                "temp_id": "e1",
                "name": "红杉资本",
                "type": "Institution",
                "resolved_id": "institution_demo",
                "resolution_confidence": 0.94,
                "evidence": "红杉资本",
            },
            {
                "temp_id": "e2",
                "name": "示例科技",
                "type": "Company",
                "resolved_id": "company_demo",
                "resolution_confidence": 0.9,
                "evidence": "示例科技",
            },
        ],
        "relationships": [
            {
                "temp_id": "r1",
                "head_temp_id": "e1",
                "relation": "INVESTED_IN",
                "tail_temp_id": "e2",
                "attributes": {"role": "领投"},
                "evidence": text[:80],
                "confidence": 0.91,
                "status": "confirmed",
            }
        ],
        "warnings": [],
    }
