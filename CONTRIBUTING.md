# Contributing to the AI Act Risk Map

We welcome community contributions to map new AI libraries to EU AI Act categories.
To ensure the integrity of our compliance engine, we require strict evidence.

## How to Add a Library

1.  Open `ai_act_check/data/risk_map.json`.
2.  Add your library using this schema:
    ```json
    "library-name": {
      "risk_description": "Exact Annex III Category (e.g. Biometrics)",
      "risk_level": "High",
      "status": "community_submitted", 
      "evidence": "LINK_TO_OFFICIAL_DOCS"
    }
    ```

3.  **Rule:** You MUST provide a valid URL in the `evidence` field showing the library's capability (e.g., function names like `recognize_face` or `score_candidate`).
4.  Submit a Pull Request.

## Risk Levels

- **High**: Falls under Annex III (Biometrics, Critical Infra, Education, Employment, etc.) or Prohibited Practices.
- **Medium**: General Purpose AI (GPAI) or powerful ML that *could* be used for high-risk purposes.
- **Low**: Tooling, visualization, etc.

## Verification

Your PR will be reviewed by the AnnexFour team. Verified entries will have their status updated to `verified`.
