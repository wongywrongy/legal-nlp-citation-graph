# Evaluation Plan (AI Context)

- Golden set: 20 opinions with hand-labeled edges.
- Metrics: precision/recall on citation edges; mean confidence; % requiring LLM.
- Guardrail tests: short forms (“id.”, “supra”), parallel citations, ambiguous same-volume reporter pages.
- Regression: any change to normalization/resolution must not reduce precision >1% without explicit approval.
