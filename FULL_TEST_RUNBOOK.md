# NeuroLearn MVP Full Test Runbook (Latest)

This runbook validates the current MVP from a clean database through every major path:
- student profile creation
- neurodivergent profile adaptation (known + custom labels)
- learning-goal drift checking
- new concept flow
- answer evaluation flow
- remediation flow
- mastery persistence
- profile updater guardrails
- answer source traceability

Primary execution style in this runbook: Interactive mode (`python .\\rag_langgraph.py --student-id s100`).

## Document Status

- Scope: complete end-to-end QA flow for current MVP
- Audience: testers and developers
- Status: aligned with latest implementation

---

## 0) Preconditions

1. Run from project root:

```powershell
cd C:\Users\aaron\Videos\neurolearn
```

2. Ensure `.env` contains a valid `GROQ_API_KEY`.

3. Install dependencies (if needed):

```powershell
pip install -r requirements.txt
```

4. Optional clean terminal:

```powershell
cls
```

---

## 1) Start From Clean DB

Run this once:

```powershell
@'
import sqlite3
from pathlib import Path

db = Path('./data/student_profiles.db')
conn = sqlite3.connect(db)
cur = conn.cursor()
for t in ['students', 'mastery_events', 'learning_goals', 'profile_update_meta']:
    cur.execute(f"DELETE FROM {t}")
conn.commit()
counts = {t: cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ['students','mastery_events','learning_goals','profile_update_meta']}
print('After clear:', counts)
conn.close()
'@ | python -
```

Expected:
- all four counts are `0`

---

## 2) Create Student Profile With Neuro Profile

### 2.1 Add student

Interactive (recommended):

```powershell
python .\manage_student_db.py
```

or non-interactive:

```powershell
python .\manage_student_db.py add --student-id s100 --name "Test User" --learning-style analogy-heavy --reading-age 12 --interests chess football --neuro-profile adhd dyslexia
```

### 2.2 Verify student

```powershell
python .\manage_student_db.py get --student-id s100
```

Expected fields:
- `student_id`
- `name`
- `learning_style`
- `reading_age`
- `interest_graph`
- `neuro_profile`

### 2.3 Test custom/unknown neuro label support

```powershell
python .\manage_student_db.py add --student-id s100 --name "Test User" --learning-style analogy-heavy --reading-age 12 --interests chess football --neuro-profile adhd dyslexia dyspraxia
python .\manage_student_db.py get --student-id s100
```

Expected:
- `neuro_profile` includes `dyspraxia` and app still runs normally.

---

## 3) Set and Verify Active Learning Goal

```powershell
python .\manage_student_db.py set-goal --student-id s100 --goal "Learn handwashing and hygiene basics"
python .\manage_student_db.py active-goal --student-id s100
python .\manage_student_db.py goals --student-id s100 --limit 10
```

Expected:
- active goal exists and `is_active` is true.

---

## 4) Drift Checker Validation

Start interactive session once and keep it running for Sections 4-7:

```powershell
python .\rag_langgraph.py --student-id s100
```

When prompted, type each test input exactly as shown below.

### 4A) Off-goal input should redirect

Input in interactive prompt:

```text
ഫുട്ബോൾ കളിയുടെ നിയമങ്ങൾ പറഞ്ഞുതരൂ
```

Verify logs:
- `Intent classified as:`
- `Goal drift checker raw:`
- `Goal drift check: drift_detected=True`

Verify output:
- short Malayalam refocus message
- no full concept pipeline output

### 4B) On-goal input should continue normal flow

Input in interactive prompt:

```text
കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?
```

Verify logs:
- `Goal drift check: drift_detected=False`

---

## 5) New Concept Path Validation

Input in interactive prompt:

```text
കൈകഴുകൽ ശരിയായി എങ്ങനെ ചെയ്യണം?
```

Verify logs:
- `Intent classified as: new_concept`
- `Personalizer running`
- `Gate A judge`
- `Evaluator generated check question`

Verify output:
- main answer text
- `Answer Sources` block
- `Check Question` present

Expected nodes:
- `new_concept_retriever`
- `new_concept_personalizer`
- `personalization_gate`
- `evaluator`

---

## 6) Answer Path Validation (Incorrect -> Remediation)

Input in interactive prompt:

```text
എന്റെ ഉത്തരം: സഹകരണം ടീമിൽ ലക്ഷ്യം നേടാൻ സഹായിക്കും
```

Verify logs:
- `Intent classified as: answer`
- `Answer evaluator result: is_correct=False`
- `Mastery recorded: id=`
- `Remediation node running`

Verify output:
- `Evaluation Result` with `is_correct: False`
- `Remediation (Try Again)` block appears

Expected nodes:
- `answer_retriever`
- `answer_evaluator`
- `remediation`

---

## 7) Answer Path Validation (Correct -> No Remediation)

Input in interactive prompt:

```text
എന്റെ ഉത്തരം: വിലയിരുത്തല്‍ തുടര്‍പ്രവര്‍ത്തനം രക്ഷിതാവിന്റെ സഹായത്തോടെ കൈകഴുകല്‍ ദൈനംദിന ജീവിതത്തില്‍ വീട്ടിലും പ്രായോഗികമാക്കുക
```

Verify logs:
- `Answer evaluator result: is_correct=True`
- `Mastery recorded: id=`
- no remediation-node log

Verify output:
- `Evaluation Result` with `is_correct: True`
- no remediation section

---

## 8) Mastery Persistence Validation

```powershell
python .\manage_student_db.py mastery --student-id s100 --limit 20
```

Verify each row includes:
- `id`
- `student_id`
- `concept_key`
- `is_correct`
- `misconception`
- `confidence`
- `source_doc`
- `source_page`
- `source_chunk_id`
- `timestamp`

Expected:
- both incorrect and correct rows present.

---

## 9) Answer Source Traceability Validation

For any successful query output, verify `Answer Sources` lines include:
- `textbook=<pdf>`
- `page=<number>`
- `chunk_id=<number>` (or vector id fallback)
- `json=output/rag_chunks/<book>.json`

Optional chunk schema integrity check:

```powershell
$files = Get-ChildItem .\output\rag_chunks\*.json | Where-Object { $_.Name -ne '_manifest.json' }
$issues = @()
foreach ($f in $files) {
  $data = Get-Content $f.FullName -Raw | ConvertFrom-Json
  $rows = @($data)
  $bad = $rows | Where-Object { -not $_.source -or $null -eq $_.page -or $null -eq $_.chunk_id -or -not $_.text }
  if ($bad.Count -gt 0) { $issues += [pscustomobject]@{file=$f.Name; total=$rows.Count; bad_rows=$bad.Count} }
}
"Chunk JSON files checked: $($files.Count)"
"Files with schema issues: $($issues.Count)"
```

---

## 10) Profile Updater Guardrail Validation

Guardrails to validate:
- minimum attempts before change: `8`
- hysteresis:
  - increase when success rate `>= 0.80`
  - decrease when success rate `<= 0.35`
- cooldown: max one reading-age change per 10 events

### 10.1 Capture baseline profile

```powershell
python .\manage_student_db.py get --student-id s100
```

### 10.2 Generate mixed attempts

Incorrect sample:

```powershell
python .\rag_langgraph.py --student-id s100 --text "എന്റെ ഉത്തരം: ഇത് വേറൊരു വിഷയമാണ്"
```

Correct sample:

```powershell
python .\rag_langgraph.py --student-id s100 --text "എന്റെ ഉത്തരം: വിലയിരുത്തല്‍ തുടര്‍പ്രവര്‍ത്തനം രക്ഷിതാവിന്റെ സഹായത്തോടെ കൈകഴുകല്‍ ദൈനംദിന ജീവിതത്തില്‍ വീട്ടിലും പ്രായോഗികമാക്കുക"
```

Repeat as needed, then:

```powershell
python .\manage_student_db.py get --student-id s100
```

Verify:
- reading age only changes when thresholds + cooldown conditions are satisfied.
- interest graph may gain strong recurring topics.

---

## 11) Optional Interactive Session Test

```powershell
python .\rag_langgraph.py --student-id s100
```

Note: If you already completed Sections 4-7 in the same session, this section is already covered.

Suggested sequence:
1. Off-goal query (expect redirect)
2. On-goal concept query (expect explanation + check question)
3. Incorrect answer-like response (expect remediation)
4. Retry with better answer

Current behavior note:
- no global yes/no retry prompt is shown
- if a check question is pending, your next input is treated as the answer to that check question

---

## 12) Node Coverage Checklist

Mark when observed in logs:

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

---

## 13) Quick Troubleshooting

### Student not found

```powershell
python .\manage_student_db.py add --student-id s100 --name "Test User" --learning-style analogy-heavy --reading-age 12 --interests chess football --neuro-profile adhd dyslexia
```

### No drift redirect happens
1. Check active goal:

```powershell
python .\manage_student_db.py active-goal --student-id s100
```

2. Set active goal if missing:

```powershell
python .\manage_student_db.py set-goal --student-id s100 --goal "Learn handwashing and hygiene basics"
```

### Parse fallback appears
- Re-run query (transient model output variance can happen).
- Check raw evaluator/drift logs for malformed JSON.

---

## 14) MVP Pass Criteria

MVP test pass when all are true:
1. Off-goal input redirects early.
2. On-goal new concept flow gives explanation + check question.
3. Answer flow returns structured evaluation.
4. Incorrect answer triggers remediation.
5. Correct answer skips remediation.
6. Mastery rows persist and are queryable.
7. Profile updater guardrails behave as expected.
8. Student profile remains queryable and persists updates.
9. Answer Sources lines map to valid chunk metadata.
10. Custom neuro-profile labels run without code changes.

---

End of runbook.

## Related Docs

- [README.md](README.md)
- [FLOW.md](FLOW.md)
- [plan.md](plan.md)
- [FROM_SCRATCH_SUMMARY.md](FROM_SCRATCH_SUMMARY.md)
