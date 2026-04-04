# Personalized Hierarchical Education Agent (LangGraph)

This architecture defines a strict Orchestrator-Worker pattern. The Parent Agent acts as the single point of entry and exit, ensuring that every piece of educational content is vetted, personalized, and evaluated before reaching the student.

## 1. Sub-Agent Definitions & KPIs

| Sub-Agent | Technical Role | Success Metric (KPI) |
|---|---|---|
| Parent Orchestrator | Supervisor/Router: Interprets user intent and selects the correct graph path. | Routing Accuracy: Correctly identifying "New Concept" vs. "Answer" 98% of the time. |
| Knowledge Retriever | Context Provider: Connects to Vector DB (RAG) to pull chunked educational data. | Faithfulness: No hallucinations; output must be 100% grounded in retrieved docs. |
| Personalization Engine | Style Transformer: Maps raw knowledge to the student's interests and reading level. | Alignment: Matching the interest keywords (for example, using gaming terms) in the output. |
| Concept Evaluator | Diagnostic Analyst: Compares user response against ground truth from the researcher. | Precision: Correctly identifying "Partial Mastery" vs. "Misconception." |
| Profile Updater | Data Sync: Translates natural language evaluation into structured JSON for the DB. | Schema Integrity: Successfully updating the SQL/NoSQL mastery matrix. |

## 2. Memory Architecture & Data Schema

### A. Persistent Long-Term Memory (Profile DB)

This resides in a relational database (PostgreSQL/Supabase) and is loaded at the start of every session.

- Student Profile Table:
  - `learning_style`: e.g., "Socratic", "Analogy-heavy", "Direct"
  - `interest_graph`: JSON array of keywords used for analogies
  - `reading_age`: integer (affects vocabulary complexity)
- Mastery Matrix Table:
  - `concept_id`: unique ID for a curriculum topic
  - `proficiency_score`: float (0.0 to 1.0)
  - `attempts_count`: number of times the student has engaged with this topic

### B. Ephemeral Short-Term Memory (LangGraph State)

The graph state is the shared object passed between agents.

```python
class EducationState(TypedDict):
    user_input: str
    student_profile: dict                   # Loaded from DB at start
    retrieved_context: str                  # Raw RAG data
    personalized_explanation: str           # Final output text
    evaluation_result: dict                 # { "is_correct": bool, "feedback": str }
    internal_monologue: str                 # Parent's reasoning for debugging
    active_node: str                        # Current sub-agent in control
```

## 3. Detailed Functional Flows

### Flow 1: New Knowledge Loop

1. Intent Classification: Parent detects the user wants to learn something new.
2. RAG Fetch: Retriever pulls the top 3 most relevant chunks from the vector DB.
3. Synthesis: Personalizer receives the raw chunks plus `interest_graph` and generates relatable analogies.
4. Active Verification: Before sending, Parent forces Evaluator to generate a check-for-understanding question based only on shared information.
5. Delivery: User receives the explanation plus the question.

### Flow 2: Correction & Remediation Loop

1. Submission: User answers a question.
2. Logic Audit: Evaluator compares the user's answer to `retrieved_context`.
3. Gap Analysis: If wrong, Evaluator identifies why (for example, confusing gravity with atmospheric pressure).
4. Pivot: Parent triggers Retriever again with a targeted query, such as differences between gravity and air pressure.
5. Re-Explanation: Personalizer delivers a targeted correction.

## 4. State Machine Logic (Guardrails)

To ensure the Parent never skips a step, the graph uses directed edges and conditional logic gates.

### No-Skip Policy

- Gate A (Personalization Check): If `personalized_explanation` is too long or complex (via LLM judge or heuristic), loop back to Personalizer for a simplification pass.
- Gate B (Evaluation Requirement): The `END` node is unreachable unless `evaluation_result` is populated.

### Drift Guardrail

The Parent Agent performs a context check every 3 turns. It compares the current conversation against the mastery matrix. If the student drifts away from the intended goal, Parent responds with:

> "That's an interesting point, but let's get back to how this relates to [Original Topic]."

## 5. Example Interaction Scenarios

| Scenario | Parent Decision | Sub-Agent Chain |
|---|---|---|
| User asks a "Why" question | Deep Dive | RAG -> Personalizer -> Evaluator |
| User gives a vague answer | Probe for Clarity | Evaluator (requests more detail) -> User |
| User expresses frustration | Emotional Support | Personalizer (shifts tone to encouraging) -> RAG (simpler content) |
| User masters a topic | Progress Update | Evaluator -> Profile Updater (increments score) -> Parent (suggests next topic) |

## 6. Technical Integration Requirements

- Orchestration: LangGraph (using `StateGraph` for cyclic support).
- Vector Store: Metadata filtering is required (for example, filter by `grade_level` during RAG).
- Latency Management: Use streaming for the Personalizer node so users see explanation output while the Evaluator generates quiz questions in parallel.

## Things Not Included

1. Personalized voice (easy)
2. Subject switching within runtime (medium)
3. MCP tool integrations for the Parent Agent to send updates to teachers based on progress
4. Security guardrail to check every AI response against the student's profile and block/fix distressing output before the student sees it
