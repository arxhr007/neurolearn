# NeuroLearn MVP Full Test Runbook

This runbook walks you through the complete end-to-end test flow:
- Create a student profile
- Set active learning goal
- Test all major runtime branches/nodes
- Verify mastery persistence
- Verify remediation behavior
- Verify drift checker behavior
- Verify profile updater changes in SQLite-backed profile

Use this as a repeatable QA checklist.

---

## 0) Preconditions

1. Open terminal in project root:

```powershell
cd C:\Users\aaron\Videos\neurolearn
```

2. Ensure `.env` has a valid `GROQ_API_KEY`.

3. Ensure dependencies are installed:

```powershell
pip install -r requirements.txt
```

4. Optional: clear screen and start clean logs.

```powershell
cls
```

---

## 1) Create Student Profile (DB)

### 1.1 Add a test student

```powershell
python .\manage_student_db.py add --student-id s100 --learning-style analogy-heavy --reading-age 12 --interests chess football
```

Expected:
- `Saved student profile: s100`

### 1.2 Verify student profile

```powershell
python .\manage_student_db.py get --student-id s100
```

Expected JSON fields:
- `student_id`
- `learning_style`
- `reading_age`
- `interest_graph`

---

## 2) Set Learning Goal (for drift checker)

### 2.1 Set active goal

```powershell
python .\manage_student_db.py set-goal --student-id s100 --goal "Learn handwashing and hygiene basics"
```

Expected:
- `Saved active learning goal for s100 (goal_id=...)`

### 2.2 Confirm active goal

```powershell
python .\manage_student_db.py active-goal --student-id s100
```

Expected:
- JSON with `goal_text`, `is_active: true`

### 2.3 Optional: list all goals history

```powershell
python .\manage_student_db.py goals --student-id s100 --limit 10
```

---

## 3) Test Drift Checker Nodes

## 3A) Off-goal query should redirect

Run:

```powershell
python .\rag_langgraph.py --student-id s100 --text "ഫുട്ബോൾ കളിയുടെ നിയമങ്ങൾ പറഞ്ഞുതരൂ"
```

What to verify in logs:
- `Intent classified as: ...`
- `Goal drift checker raw: ...`
- `Goal drift check: drift_detected=True ...`

What to verify in output:
- Answer should be a short Malayalam refocus message.
- No retrieval/personalizer/evaluator branch output expected for off-goal path.

Nodes covered:
- `parent_orchestrator`
- `intent_classifier`
- `goal_drift_checker`
- `drift_redirect`

## 3B) On-goal query should pass through

Run:

```powershell
python .\rag_langgraph.py --student-id s100 --text "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?"
```

What to verify in logs:
- `Goal drift check: drift_detected=False ...`
- Normal path continues (retriever + personalizer + gate + evaluator)

---

## 4) Test New Concept Path

Run:

```powershell
python .\rag_langgraph.py --student-id s100 --text "കൈകഴുകൽ ശരിയായി എങ്ങനെ ചെയ്യണം?"
```

What to verify in logs:
- `Intent classified as: new_concept (...)`
- `Personalizer running ...`
- `Gate A judge ...`
- `Gate A action ...`
- `Evaluator generated check question ...`

What to verify in output:
- Main Malayalam explanation answer
- `Check Question` is present

Nodes covered:
- `new_concept_retriever`
- `new_concept_personalizer`
- `personalization_gate`
- `evaluator`

---

## 5) Test Answer Path (Incorrect -> Remediation)

Run:

```powershell
python .\rag_langgraph.py --student-id s100 --text "എന്റെ ഉത്തരം: സഹകരണം ടീമിൽ ലക്ഷ്യം നേടാൻ സഹായിക്കും"
```

What to verify in logs:
- `Intent classified as: answer (...)`
- `Answer evaluator running ...`
- `Answer evaluator result: is_correct=False ...`
- `Mastery recorded: id=...`
- `Remediation node running ...`
- `Remediation explanation generated ...`

What to verify in output:
- `Evaluation Result` shows `is_correct: False`
- `Remediation (Try Again)` block appears

Nodes covered:
- `answer_retriever`
- `answer_evaluator`
- `remediation`

DB effect expected:
- New row in `mastery_events`

---

## 6) Test Answer Path (Correct -> No Remediation)

Run a known good answer-like query:

```powershell
python .\rag_langgraph.py --student-id s100 --text "എന്റെ ഉത്തരം: വിലയിരുത്തല്‍ തുടര്‍പ്രവര്‍ത്തനം രക്ഷിതാവിന്റെ സഹായത്തോടെ കൈകഴുകല്‍ ദൈനംദിന ജീവിതത്തില്‍ വീട്ടിലും പ്രായോഗികമാക്കുക"
```

What to verify in logs:
- `Answer evaluator result: is_correct=True ...`
- `Mastery recorded: id=...`
- No remediation node log

What to verify in output:
- `Evaluation Result` with `is_correct: True`
- No `Remediation` block

DB effect expected:
- New `mastery_events` row with `is_correct = true`

---

## 7) Verify Mastery Events in DB

### 7.1 Inspect recent mastery rows

```powershell
python .\manage_student_db.py mastery --student-id s100 --limit 20
```

Verify fields in each row:
- `id`
- `student_id`
- `concept_key`
- `is_correct`
- `misconception`
- `confidence`
- `timestamp`

You should now see both:
- incorrect attempts
- correct attempts

---

## 8) Verify Profile Updater Behavior + Guardrails

Profile updater has guardrails:
- minimum attempts: 8
- hysteresis thresholds:
  - increase if success rate `>= 0.80`
  - decrease if success rate `<= 0.35`
- cooldown: one reading-age change per 10 events

### 8.1 Check profile before stress run

```powershell
python .\manage_student_db.py get --student-id s100
```

Record:
- current `reading_age`
- current `interest_graph`

### 8.2 Generate multiple attempts (mix of correct/incorrect)

Repeat these commands several times:

Incorrect sample:

```powershell
python .\rag_langgraph.py --student-id s100 --text "എന്റെ ഉത്തരം: ഇത് വേറൊരു വിഷയമാണ്"
```

Correct sample:

```powershell
python .\rag_langgraph.py --student-id s100 --text "എന്റെ ഉത്തരം: വിലയിരുത്തല്‍ തുടര്‍പ്രവര്‍ത്തനം രക്ഷിതാവിന്റെ സഹായത്തോടെ കൈകഴുകല്‍ ദൈനംദിന ജീവിതത്തില്‍ വീട്ടിലും പ്രായോഗികമാക്കുക"
```

### 8.3 Re-check profile

```powershell
python .\manage_student_db.py get --student-id s100
```

Verify:
- `reading_age` only changes when guardrail conditions are satisfied.
- `interest_graph` may gain strong recurring topics.

### 8.4 Confirm updater messages in runtime logs

Look for lines like:
- `Profile auto-update: reading_age held ...`
- `Profile auto-update: reading_age X -> Y ...`
- `Profile auto-update: added interest '...'`

---

## 9) Optional Interactive Flow Test

Run interactive mode:

```powershell
python .\rag_langgraph.py --student-id s100
```

Suggested sequence in interactive session:
1. Off-goal question (expect redirect)
2. On-goal new concept question (expect explanation + check question)
3. Answer-like wrong response (expect remediation)
4. Retry with better response

Verify retry prompt behavior:
- `Do you want to try again? (yes/no/exit)`

---

## 10) Node Coverage Checklist

Mark each when observed in logs:

- [ ] `parent_orchestrator`
- [ ] `intent_classifier`
- [ ] `goal_drift_checker`
- [ ] `drift_redirect`
- [ ] `new_concept_retriever`
- [ ] `new_concept_personalizer`
- [ ] `personalization_gate`
- [ ] `evaluator`
- [ ] `answer_retriever`
- [ ] `answer_evaluator`
- [ ] `remediation`

If all are checked, MVP graph traversal coverage is complete.

---

## 11) Quick Troubleshooting

### Problem: Student not found
Fix:

```powershell
python .\manage_student_db.py add --student-id s100 --learning-style analogy-heavy --reading-age 12 --interests chess football
```

### Problem: No drift behavior seen
Fix:
1. Ensure active goal exists:

```powershell
python .\manage_student_db.py active-goal --student-id s100
```

2. Set one if missing:

```powershell
python .\manage_student_db.py set-goal --student-id s100 --goal "Learn handwashing and hygiene basics"
```

### Problem: LLM parse fallback appears
- Re-run the query once (transient generation issues happen).
- Check for logs:
  - `... raw: ''`
  - parse fallback feedback

---

## 12) Minimal Pass Criteria (MVP Acceptance)

You can call MVP test pass when all are true:
1. Off-goal input is redirected.
2. On-goal new concept flow gives explanation + check question.
3. Answer flow gives structured evaluation.
4. Incorrect answer triggers remediation.
5. Correct answer skips remediation.
6. Mastery rows are persisted and queryable.
7. Profile updater logs appear and respects guardrails.
8. Student profile remains queryable and updates persist.

---

End of runbook.
