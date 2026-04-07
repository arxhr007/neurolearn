# Examples

## 1. Create a student profile

```powershell
python .\manage_student_db.py
```

Example profile:

```powershell
python .\manage_student_db.py add --student-id s100 --name "Test User" --learning-style analogy-heavy --reading-age 12 --interests chess football --neuro-profile adhd dyslexia
```

## 2. Set the active learning goal

```powershell
python .\manage_student_db.py set-goal --student-id s100 --goal "Learn handwashing and hygiene basics"
```

## 3. Ask the tutor a question

```powershell
python .\rag.py --student-id s100 --text "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?"
```

## 4. Use the optional PDF pipeline

```powershell
python .\pipeline\pdf_content_pipeline.py
python .\pipeline\build_vector_index.py
```

## 5. Inspect progress

```powershell
python .\manage_student_db.py get --student-id s100
python .\manage_student_db.py mastery --student-id s100 --limit 20
```

## Example learner patterns

- A student with a shorter reading age can get simpler explanations and shorter phrasing.
- A student who learns by analogy can get more comparison-driven explanations.
- A student with an active learning goal can be redirected if the question drifts too far away.
