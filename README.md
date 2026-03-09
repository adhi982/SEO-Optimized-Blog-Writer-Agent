# SEO Blog Writer Agent (Hybrid Architecture)

## Executive Summary

The SEO Blog Writer Agent is an autonomous, multi-agent AI pipeline designed to research, strategize, write, optimize, and edit publication-ready, SEO-optimized blog posts. 

By leveraging a hybrid architecture that combines the role-playing and orchestration capabilities of **CrewAI** with the stateful, loop-based execution of **LangGraph**, this system ensures high-quality content generation without human intervention. The final output is delivered as a cleanly formatted Markdown file complete with YAML frontmatter, a Table of Contents, and JSON-LD schema markup ready for direct deployment.

---

## Architecture Overview

The core strength of this project relies on its **Hybrid Multi-Agent Architecture**.

1. **CrewAI (The Orchestrator):** Manages the high-level workflow. It defines specific expert personas (e.g., Senior SEO Analyst, Expert SEO Content Writer), assigns sequential tasks, and manages the data hand-off between the different phases of content creation.
2. **LangGraph (The Engine):** Embedded within specific CrewAI agents as Custom Tools, LangGraph handles complex, iterative sub-workflows. Tasks that require loops, conditional retries (like re-running an empty search), and section-by-section processing are executed deterministically by LangGraph state machines.
3. **Multi-LLM Strategy:** The pipeline can route tasks to different LLM providers based on the workload to balance reasoning capability, speed, and cost (e.g., Groq for rapid QA, Mistral for creative writing).

### System Workflow Diagram

```mermaid
graph TD
    %% Styling
    classDef ui fill:#2A3F54,stroke:#1ABB9C,stroke-width:2px,color:#fff
    classDef crew fill:#3E5365,stroke:#fff,stroke-width:2px,color:#fff
    classDef lg fill:#1ABB9C,stroke:#fff,stroke-width:2px,color:#fff,stroke-dasharray: 5 5
    classDef node fill:#E9EDEF,stroke:#3E5365,stroke-width:1px,color:#3E5365

    UI[Streamlit UI Interface]:::ui --> CREW[CrewAI Orchestrator]:::crew

    subgraph Crew[Sequential CrewAI Pipeline]
        方向 TB
        A1(1. SEO Research Agent)
        A2(2. Content Strategist Agent)
        A3(3. Expert Writer Agent)
        A4(4. SEO Optimizer Agent)
        A5(5. Senior Editor Agent)

        A1 --> A2 --> A3 --> A4 --> A5
    end

    CREW --> Crew

    %% LangGraph Subgraphs Connect to Agents
    subgraph LG1[LangGraph: Research Sub-Graph]
        R1[Keyword Research]:::node --> R2[SERP Analysis]:::node
        R2 --> R3[Competitor Analysis]:::node
        R3 --> R4[Keyword Clustering]:::node
        R1 -. Retry on failure .-> R1
    end

    subgraph LG2[LangGraph: Writing Sub-Graph]
        W1[Write Section]:::node --> W2[Inject Citations]:::node
        W2 --> W3[Enforce Brand Voice]:::node
        W3 --> W4[Readability Check]:::node
        W4 -. Loop for each section .-> W1
    end

    subgraph LG3[LangGraph: QA Sub-Graph]
        Q1[Fact Check]:::node --> Q2[Plagiarism Scan]:::node
        Q2 --> Q3[SEO Validation]:::node
        Q3 --> Q4[Final Polish]:::node
        Q4 -. Revision Loop .-> Q1
    end

    A1 -. Tool Call .-> LG1:::lg
    A3 -. Tool Call .-> LG2:::lg
    A5 -. Tool Call .-> LG3:::lg
    
    A5 --> OUT[Output: Final Markdown File]:::ui
```

---

## Agent Breakdown

The pipeline consists of five specialized agents, executed sequentially:

### 1. Senior SEO Research Analyst
* **Responsibility:** Conduct thorough keyword research, analyze search intent, and review competitor content gaps.
* **Mechanism:** Wraps the `Research LangGraph`. It uses the `SerpAPI` tool to gather actual search data, people-also-ask questions, and top-ranking competitor snippets. If initial keyword data is insufficient, LangGraph forces a retry with expanded query terms.

### 2. Content Strategist & SEO Architect
* **Responsibility:** Transform raw research data into a highly structured blog outline.
* **Mechanism:** A pure LLM (CrewAI) agent. Analyzes research to establish a primary keyword, support secondary keywords, plan the heading hierarchy (H2/H3), layout E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) signals, and specify internal linking targets.

### 3. Expert SEO Content Writer
* **Responsibility:** Draft the blog post based strictly on the generated outline and research context.
* **Mechanism:** Wraps the `Writing LangGraph`. It operates node-by-node, iterating through each section of the outline. This ensures that long-form content is written systematically, allowing for dedicated citation injection and strict adherence to defined brand voice per section.

### 4. Technical SEO Specialist
* **Responsibility:** Evaluate the unified draft for technical SEO viability.
* **Mechanism:** A pure CrewAI agent equipped with custom Python tools. It calculates keyword density, generates JSON-LD Schema Markup (`Article`), and evaluates structural elements like image alt-text placeholders and heading consistency. 

### 5. Senior Editor & Fact Checker
* **Responsibility:** Provide the final quality assurance gate.
* **Mechanism:** Wraps the `QA LangGraph`. Utilizes the `textstat` library to calculate readability scores (Flesch Reading Ease, Flesch-Kincaid Grade Level). If the content fails target readability or stylistic targets, the graph initiates a revision loop to simplify and polish the text before finalizing.

---

## Core Technologies and Tools

* **Python 3.11+**: Core language.
* **LangChain & LangGraph**: State management, cyclic graph execution, and LLM abstraction.
* **CrewAI**: Agent role-playing, prompt execution, and sequential orchestration.
* **Streamlit**: Provides a clean, functional Graphical User Interface (GUI) for inputs and live execution tracing.
* **SerpAPI**: Real-time Google Search integration for keyword and competitor scraping.
* **Pydantic (v2)**: Strict data validation ensuring that all inputs and outputs between agents adhere to expected schemas (preventing generation crashes).
* **Textstat**: Mathematical text analysis calculating precise readability grades.
* **Frontmatter**: Assembles the final Markdown files for direct compatibility with static site generators (Hugo, Jekyll) or modern CMS platforms.

---

## Output Specifications

The final output is saved automatically to the `output/` directory as a standardized Markdown file. Features of the output include:

1. **YAML Frontmatter:** Contains Title, Description, Date, Word Count, and calculated SEO/Readability Scores.
2. **Table of Contents:** Auto-generated internal anchor links.
3. **Structured Body:** Markdown formatted text with optimized H1, H2, and H3 hierarchies.
4. **Citations:** Appended source references where applicable.
5. **JSON-LD Schema:** An embedded, hidden HTML comment containing fully compliant `Article` structured data, ready to be injected into a website's `<head>`.

---

## Installation and Execution

### Prerequisites
* Python 3.11 or higher.
* Active API keys for your preferred LLM providers (e.g., Groq, Mistral, Gemini) and SerpAPI.

### Setup

1. **Clone the repository and navigate to the root directory.**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: Alternatively, rely on `pyproject.toml` or your standard package manager).*
3. **Configure the Environment:**
   Review the `.env.example` file, create a `.env` file in the root directory, and insert your API credentials:
   ```env
   GEMINI_API_KEY=your_key_here
   GROQ_API_KEY=your_key_here
   MISTRAL_API_KEY=your_key_here
   SERPAPI_KEY=your_key_here
   ```

### Running the Application

Launch the Streamlit interface via the terminal:

```bash
python -m streamlit run app/main.py
```

1. Navigate to the **Generate Blog** page via the sidebar.
2. Input your desired Topic, Target Audience, and Tone.
3. Initiate the generation process and monitor live agent progress via the UI dashboard.
4. Retrieve the finalized post from the **Results & Export** page or directly from the local `output/` directory.
