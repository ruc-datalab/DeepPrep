````markdown
# Simple case 1: Qualified CS students by city

## High level task description
Using the uploaded tables, build a target table that shows **how many distinct students per city** have **score >= 85** in **any CS course**.

Rules:
1. A student is "qualified" if they have at least one enrollment where:
   - the course's `department` == "CS"
   - and `score` >= 85
2. Output one row per `city`.

Output columns:
- `city`
- `qualified_student_cnt` (distinct students)

Input tables:
- `students.csv` (student_id, city)
- `courses.csv` (course_id, department)
- `enrollments.csv` (student_id, course_id, score)

## schemaJson (paste into UI)

```json
{
  "city": {"description": "Student city", "requirements": ["distinct"]},
  "qualified_student_cnt": {"description": "Number of distinct qualified students in the city", "requirements": []}
}
```

````
