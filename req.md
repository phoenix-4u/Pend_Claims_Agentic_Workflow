

### Original Prompt

```
Write a an pend claim analysis agentic application using python and streamlit. You should read the sql file to understand underlying table structure. The B007 and F027 files are the SOPs that contain the steps and sql queries necessary to get the data needed to execute the step. The application flow should start with entering the unique ICN number. The first condition code from claim lines table to understand which SOP to call. Based on the same it should read the corresponding SOP table i.e. B007/ F027 or other SOPs as applicable. The agent should read each step execute each query via MCP langchain client connecting to MCP server that is exposed separately. Then based on the instruction and the data retrieved, the agent should ultimately provide either decision to reject the claim or override the pend. Each step and corresponding data retrieved should also be visible on screen for adjudicator's reference. While executing the steps, the application should show with extensive visualization what actions the agent is executing 1 by 1. Implement extensive logging using python default logger into a separate log file. Implement the entire workflow using langgraph.
```

### Expanded and Finetuned Prompt for Windsurf

"**Develop an AI-powered agentic application for pend claim analysis using Python and Streamlit, designed and optimized within the Windsurf AI-native IDE environment.**

**Core Functionality:**

*   **SQL Database Interaction:** The application must dynamically read and interpret SQL schema definitions from a provided `.sql` file to understand the underlying table structures. This should inform the agent's query generation and data retrieval processes.
*   **SOP-Driven Workflow (B007, F027, etc.):**
    *   The application flow initiates with the entry of a unique ICN (Internal Control Number).
    *   Upon ICN input, the agent will identify the primary condition code from the `claim_lines` table.
    *   Based on this condition code, the application must dynamically select and process the appropriate Standard Operating Procedure (SOP) file (e.g., `B007`, `F027`, or other relevant SOPs). Each SOP file contains predefined steps and associated SQL queries required for data extraction and analysis.
*   **Agentic Execution with LangGraph and MCP:**
    *   The core agent workflow will be orchestrated using **LangGraph**, enabling a robust, multi-step, and stateful execution pipeline for claim analysis.
    *   Each step defined within the SOPs will involve executing specific SQL queries via an **MCP (Model Context Protocol) LangChain client**, which connects to a separately exposed MCP server. Windsurf's integration with MCP should facilitate seamless tool calling and data exchange.[1]
    *   The agent will process the retrieved data according to the instructions within the SOPs.
    *   The final output of the agent will be a clear decision: either **reject the claim** or **override the pend**.

**User Interface and Experience (Streamlit & Windsurf Enhancement):**

*   **Interactive Adjudicator Dashboard:**
    *   Utilize **Streamlit** to create a highly interactive and intuitive user interface.
    *   **Real-time Step Visualization:** As the agent executes each step of the claim analysis, the UI must provide **extensive, step-by-step visualizations** of the actions being performed by the agent. This includes displaying the SQL queries being run, the data retrieved at each stage, and the agent's intermediate reasoning or decisions.
    *   **Data Visibility for Adjudicators:** Each executed step and its corresponding retrieved data should be prominently displayed on the screen for the adjudicator's real-time reference and oversight.
*   **Windsurf's Role in UI/UX:** Leverage Windsurf's AI-native capabilities to generate and refine the Streamlit UI components, ensuring a clean, responsive, and user-friendly design. Prompt Windsurf for suggestions on effective data visualization techniques for agent workflows.

**Robustness and Observability:**

*   **Comprehensive Logging:** Implement extensive logging using Python's default logging module, directing all logs to a separate, dedicated log file. This logging should capture agent actions, data interactions, errors, and decision points for auditing and debugging.
*   **Error Handling and Resilience:** Design the application with robust error handling mechanisms, particularly for SQL query execution and SOP parsing.

**Windsurf Specific Instructions:**

*   **Code Generation and Refinement:** Utilize Windsurf's AI coding assistant features to accelerate the development of Python code for Streamlit UI, LangGraph orchestration, SQL interactions, and MCP client integration.
*   **Project Structure and Setup:** Leverage Windsurf to assist in setting up the optimal project structure, managing dependencies, and configuring the development environment.
*   **Iterative Development:** Be prepared to provide specific feedback to Windsurf for UI adjustments, functionality changes, or architectural improvements as the application is being built and refined. Ask Windsurf to explain its approach and reasoning for suggested code or design patterns.
*   **Performance Optimization:** Consult with Windsurf for best practices in optimizing the performance of the Streamlit application and LangGraph agent, especially concerning database queries and data processing.
*   **"Vibe Coding" with Windsurf:** Embrace Windsurf's "vibe coding" paradigm, using natural language prompts to describe desired features and allowing the AI to generate and refine the underlying code
