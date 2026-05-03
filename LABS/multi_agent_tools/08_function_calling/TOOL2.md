# 📌 TOOL

## App V2: Enhanced AI-Powered Application with Agents and Advanced AI

🕒 *Estimated Time: 4-6 hours*

---

## 📋 Tool Overview

Refine and enhance your **AI-powered data analytics application** from App V1. Your app must add **Agentic Orchestration** and either **RAG** or **Tool Calling** (or both) in a way that adds value for your stakeholders. The app must remain **deployed** and accessible online. **You are expected and encouraged to use Cursor to support your coding.**

This tool builds on App V1 and adds work from:
- [`LAB_prompt_design.md`](../06_agents/LAB_prompt_design.md) - Agentic orchestration and multi-agent systems
- [`LAB_custom_rag_query.md`](../07_rag/LAB_custom_rag_query.md) - RAG queries (if implementing RAG)
- [`LAB_multi_agent_with_tools.md`](LAB_multi_agent_with_tools.md) - Tool calling (if implementing tools)

**Note**: This is a **group assignment**. Your team should refine your existing App V1. You must add Agentic Orchestration and at least one of: RAG or Tool Calling. Both RAG and Tool Calling can be added if they add value for your stakeholders.

---

## 📝 Instructions

### Who?
Group assignment - 1 app per team.

### What?
Refine your deployed **ShinyApp dashboard** from App V1 by adding **Agentic Orchestration** and either **RAG** or **Tool Calling** (or both). Your enhanced app must remain **deployed** and accessible online. **Submit a single .docx file.**

### Why?
This tool demonstrates your ability to integrate advanced AI capabilities (agentic orchestration, RAG, and tool calling) into a working, deployed software tool that provides value to stakeholders.

---

## ✅ Your Task

Your enhanced deployed ShinyApp must include all requirements from App V1, plus:

- [ ] **📊 [60 pts] Functional App**: The app must run a meaningful analysis using thoughtful, well-designed AI queries with agentic orchestration and RAG/tool calling. (This means you probably need to use a cloud AI provider for your queries, eg. OpenAI or Ollama Cloud. Contact me if your company expressly forbids that.)
    - [ ] **[25 pts] Agentic Orchestration**: Multi-agent system with 2-3 agents working together to complete tasks
        - Each agent has a clear role and system prompt
        - Agents coordinate to accomplish workflow goals
        - Agent outputs are integrated into your app's functionality
    - [ ] **[25 pts] RAG OR Tool Calling** (at least one):
        - **RAG Option**: Context-aware responses using retrieval from a custom data source (text file, CSV, or SQLite database)
        - **Tool Calling Option**: Agents that use tools/functions to interact with external APIs, data sources, or computational resources
    - [ ] **[10 pts] Effective User Interface/Visual Design**
- [ ] **🔗 [10 pts] Deployed App Link**: Working link to your deployed app (Posit Cloud Connect, or DigitalOcean). The link **must work** and be accessible.
- [ ] **📝 [30 pts] App Description and Documentation**: Written description and documentation of your app. **Your score depends on creating sufficient documentation.** (Now that your system is bigger, AI is now allowed for documentation.) Clarify:
    - **📝 [10 pts] Description**: What your app does, what API it uses, what new features you added (agentic orchestration, RAG/tool calling), and **how they add value for specific stakeholders**. Written in your own words (3-5 paragraphs)
    - **🛠️ [10 pts] Process Diagram**: Visual diagram showing data flow including agentic orchestration and RAG/tool calling (hand-drawn or digital)
    - **📚 [10 pts] Technical Documentation**: Sufficient AI-generated documentation for your app. Must be accurate and concise. Include:
        - **System Architecture**: Description of your agent roles, workflow, and how components interact
        - **RAG/Tool Implementation**: Description of your RAG data source and search function OR your tool functions (name, purpose, parameters, what they return)
        - **Technical Details**: API keys, endpoints, packages, file structure, deployment platform
        - **Usage Instructions**: How to use your deployed app (include password if applicable)
  - [ ] **👥 [0 pts] Team Members by Role**: List of team members and their roles. (Note: *everyone* is a developer here.) Suggested developer roles include:
    - 🧪 Project Manager: System architecture, system integration, performance testing, deployment
    - 🔌 Backend Developer: API integration, data processing, and data pipeline
    - 🎨 Frontend Developer: UI/UX design, reactive components, and visual design
    - 🤖 Prompt Engineer: AI integration, prompt engineering, and AI-powered insights
    - 🤖 Agent Orchestration Engineer: Manage orchestration of agents, content pipeline
    - 🛠️ Database Engineer: Manage database and RAG operations
    - 📊 Data Engineer: Statistical analysis, data transformations, and visualizations
    - 🚀 DevOps Engineer: Deployment, testing, and performance optimization
    - 📊 Full Stack Developer: Integration across components, reactive text, and value boxes
    - 🧪 QA Engineer: Quality assurance, testing, and validation

**Total: 100 pts**

---

## 📤 To Submit

Submit a single docx file containing:
- a link to your github repository main page, which will contain all documentation details.
- a link to your live app.
- Make sure it is very, very clear to your instructor where to find your answers to the questions above.

---

## ⚠️ Important Notes

- **Deployment Required**: App must remain deployed and accessible online. Local-only apps will not receive credit.
- **Agentic Orchestration Required**: You must add multi-agent orchestration to your app.
- **RAG OR Tool Calling Required**: You must add at least one of these features. Both can be added if they add value.
- **Value for Stakeholders**: The new features must add meaningful value—be prepared to explain how in your documentation.
- **Documentation Quality**: Your app description score depends on creating sufficient documentation. Use AI to help create comprehensive documentation if needed.
- **If Private Data**: If using private data, you are encouraged to add a basic password authorization screen and provide the password in your submission. (Ask Cursor for help.)
- **AI Warning**: You can use AI - so I expect that the app will be good! :)

---

Submit via Canvas by the due date specified in the course schedule.

---

![](../docs/images/homework.png)

---

← 🏠 [Back to Top](#TOOL)
