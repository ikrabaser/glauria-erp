CANDIDATE_ASSESSMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_score": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
        },
        "strengths": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "matched_skills": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "missing_skills": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "recommendation": {
            "type": "string",
            "enum": [
                "strong_interview",
                "interview",
                "review",
                "not_recommended",
            ],
        },
        "summary": {
            "type": "string",
        },
    },
    "required": [
        "overall_score",
        "strengths",
        "risks",
        "matched_skills",
        "missing_skills",
        "recommendation",
        "summary",
    ],
    "additionalProperties": False,
}
