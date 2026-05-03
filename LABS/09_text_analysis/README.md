![Banner Image](../docs/images/icons.png)

# README `/text_analysis`

> Learn to perform quality control on AI-generated text performance using manual techniques (stringr + dplyr) and AI-assisted quality control. Understand how to count concepts, detect patterns, and automate quality control for AI-generated content.

---

## Table of Contents

- [Activities](#activities)
- [Example Scripts](#example-scripts)
- [Reading Materials](#reading-materials)

---

## Activities

Complete these activities in order:

1. [ACTIVITY: Manual Text Quality Control](ACTIVITY_manual_quality_control.md)
   - [`01_manual_quality_control.R`](01_manual_quality_control.R) — R script: Manual quality control using stringr and dplyr
   - [`01_manual_quality_control.py`](01_manual_quality_control.py) — Python script: Manual quality control using pandas and re
2. [LAB: Build an AI Text Quality Control System](LAB_ai_quality_control.md)
   - [`02_ai_quality_control.R`](02_ai_quality_control.R) — R script: AI-assisted quality control with structured output
   - [`02_ai_quality_control.py`](02_ai_quality_control.py) — Python script: AI-assisted quality control with structured output
3. [ACTIVITY: Statistical Comparison of Prompt Performance](ACTIVITY_statistical_comparison.md)
   - [`03_statistical_comparison.R`](03_statistical_comparison.R) — R script: t-test and ANOVA using broom
   - [`03_statistical_comparison.py`](03_statistical_comparison.py) — Python script: t-test and ANOVA using pingouin


---

## Readings

- None.

---

## Learning Objectives

By the end of this module, you will be able to:

1. **Manual Quality Control**: Use `stringr` and `dplyr` to count concepts, detect patterns, and create quality control metrics for AI-generated text
2. **AI Quality Control**: Design quality control prompts, structure AI outputs as JSON, and implement multi-criteria quality control
3. **Statistical Comparison**: Use t-test and ANOVA to compare quality control scores across different prompts and determine statistical significance
4. **Quality Control**: Understand how to perform quality control on AI-generated text for accuracy, formality, faithfulness, clarity, succinctness, and relevance
5. **Iterative Improvement**: Refine quality control prompts based on results and compare manual vs. AI quality control approaches

---

## Integration with Other Modules

- **Module 3** ([`03_query_ai/`](../03_query_ai/)): Uses existing Ollama/OpenAI setup and API patterns for AI quality control
- **Module 6** ([`06_agents/`](../06_agents/)): Applies system prompts and structured outputs (JSON) concepts
- **Module 7** ([`07_rag/`](../07_rag/)): Builds on text processing concepts (string matching, pattern detection)
- **Module 11** ([`11_decision_support/`](../11_decision_support/)): Prepares for Homework 3, which requires statistical analysis of prompt performance

---

## Sample Data

- [`data/sample_reports.txt`](data/sample_reports.txt) — Sample AI-generated text reports for quality control practice (includes both good and problematic examples)
- [`data/sample_data.csv`](data/sample_data.csv) — Source data that reports should accurately represent (used for accuracy checking)
- [`data/prompt_comparison_reports.csv`](data/prompt_comparison_reports.csv) — 90+ sample reports generated from 3 different prompts (30+ per prompt)
- [`data/prompt_comparison_scores.csv`](data/prompt_comparison_scores.csv) — Pre-computed quality control scores for all reports (used for statistical comparison)

---

![Footer Image](../docs/images/icons.png)

---

← 🏠 [Back to Top](#Table-of-Contents)
