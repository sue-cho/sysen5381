# 📌 LAB

## Build an AI Text Quality Control System

🕒 *Estimated Time: 30-45 minutes*

---

## 📋 Lab Overview

Create an AI-powered text quality control system that automatically evaluates AI-generated reports on multiple quality criteria. Design quality control prompts, implement quality control functions using Ollama or OpenAI, and iterate to improve quality control accuracy. This lab teaches you to automate quality control for AI-generated content.

---

## ✅ Your Tasks

### Task 1: Set Up AI Quality Control Prompt

- [ ] Open [`02_ai_quality_control.R`](02_ai_quality_control.R) and review the quality control prompt structure
- [ ] Understand the quality control criteria from the script:
  - Boolean accuracy check (TRUE/FALSE)
  - Likert scales (1-5) for: accuracy, formality, faithfulness, clarity, succinctness, relevance
- [ ] Review how the prompt is structured to request JSON output
- [ ] Note how source data can be included for accuracy checking

### Task 2: Implement Quality Control Function

- [ ] Choose your AI provider: Ollama (local) or OpenAI (cloud)
    - [ ] Set the `AI_PROVIDER` variable in the script to "ollama" or "openai"
    - If using OpenAI, ensure your API key is set in your `.env` file (see [`ACTIVITY_openai_api_key.md`](../03_query_ai/ACTIVITY_openai_api_key.md))
    - If using Ollama, ensure Ollama is running locally (see [`ACTIVITY_ollama_local.md`](../03_query_ai/ACTIVITY_ollama_local.md))
- [ ] Review the `query_ai_quality_control()` function to understand how it queries the AI
- [ ] Review the `parse_quality_control_results()` function to understand how JSON responses are parsed

### Task 3: Run Quality Control and Compare Results

- [ ] Run [`02_ai_quality_control.R`](02_ai_quality_control.R) to check the sample report
- [ ] Review the quality control results: check the boolean accuracy, Likert scale scores, and overall quality score
- [ ] Compare AI quality control results with manual quality control from [`01_manual_quality_control.R`](01_manual_quality_control.R)
- See any differences between manual and AI quality control approaches?

### Task 4: Iterate on Quality Control Prompts

- [ ] Modify the quality control prompt in `create_quality_control_prompt()` to:
  - Add more specific instructions for a particular criterion
  - Adjust the format requirements
  - Include additional quality control checks
- [ ] Test your modified prompt on the sample report
- [ ] Compare results before and after your changes
- [ ] Briefly document what worked and what didn't in your prompt design

---

## 📤 To Submit

- For credit: Submit:
  1. Your complete quality control script (with any modifications you made)
  2. Screenshot showing the quality control results (boolean accuracy, Likert scales, overall score)
  3. Brief explanation (3-4 sentences) describing:
     - Your prompt design choices and any modifications you made
     - How AI quality control compares to manual quality control
     - What worked well and what you would improve

---

## 💡 Tips and Resources

- **Prompt Design**: Be specific about JSON format requirements. Some models work better with explicit format instructions.
- **Model Selection**: For JSON output, use models that support structured output (e.g., `llama3.2:latest` for Ollama, `gpt-4o-mini` for OpenAI)
- **Error Handling**: If JSON parsing fails, the script extracts JSON from text responses. You may need to adjust parsing logic for your specific model.
- **Quality Control Criteria**: The criteria are based on research in `docs/prep/samplevalidation.tex`. You can adapt them for your specific use case.
- **Batch Quality Control**: The script includes a function to check multiple reports. Uncomment the batch quality control section to test it.
- **Reference Files**: 
  - [`01_manual_quality_control.R`](01_manual_quality_control.R) — Manual quality control approach for comparison
  - [`02_ai_quality_control.R`](02_ai_quality_control.R) — AI quality control implementation
  - [`03_query_ai/02_ollama.R`](../03_query_ai/02_ollama.R) — Basic Ollama query pattern
  - [`03_query_ai/04_openai.R`](../03_query_ai/04_openai.R) — Basic OpenAI query pattern
- **Integration**: This lab builds on concepts from Module 3 (AI API calls) and Module 6 (system prompts and structured outputs)

---

![](../docs/images/icons.png)

---

← 🏠 [Back to Top](#LAB)
