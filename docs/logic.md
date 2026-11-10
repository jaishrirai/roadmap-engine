# How the engine works

Everything below describes the code in `src/roadmap_engine/`. All examples use synthetic data.

## 1. NPV (`npv.py`)

```
NPV = value_year1 / (1 + r)^1 + value_year2 / (1 + r)^2 + value_year3 / (1 + r)^3  -  cost
```

Example with r = 10 percent, values 100, 200, 300 and cost 50:
90.91 + 165.29 + 225.39 - 50 = **431.59**.

**Cost of a use case** is the cost of its data sources that are still `planned`. A source that is
already `enabled` costs nothing. This is what makes the ranking dynamic.

## 2. Ranking (`prioritize.py`)

1. Start with every use case that has at least one data source.
2. Compute cost, NPV and `initial_rank` (dense rank by NPV, for reference).
3. **Exceptions first.** Each id in the `exception_use_cases` sheet is picked in the listed order.
4. Then repeat until nothing is planned:
   - if a planned use case has cost 0, pick it;
   - otherwise pick the planned use case with the highest NPV.
5. After every pick, mark its data sources `enabled` and recalculate cost and NPV of all remaining
   use cases (shared sources are now free). Sort again.

`Priority` is the pick number (1 = first). `Anchor_Cost` and `Anchor_NPV` are the cost and NPV at the
moment of the pick. `initial_cost` and `initial_NPV` are the values before any pick.

Small example: use cases A and B both need source S (cost 100). A has NPV 500 with S, B has 120.
A is picked first. S is now enabled, so B's cost drops by 100 and its NPV rises to 220.

## 3. Expected days (`durations.py`)

Each row of `project_sources` is one activity: a data source brought in for a project of a use case.
Defaults come from the `config` sheet.

| Setting | Meaning |
|---|---|
| `domain_days`, `source_days`, `use_case_days` | days when nothing is enabled yet |
| `subsequent_domain_days` | domain days once the domain already has an enabled source |
| `subsequent_source_days` | source days once that source system is already connected |
| `subsequent_use_case_days` | use case days once the use case already has an enabled activity |
| `enabled_datasource_days` | source and domain days when this data source itself is enabled |
| `enabled_datasource_usecase_days` | total days when the source and the use case are both enabled |

Durations are recalculated every time an activity finishes, because a finished activity counts as
enabled and shortens the ones that follow.

## 4. Scheduling (`scheduler.py`)

- A pod runs at most `max_activity` activities at once, and does not start before its own start date.
- Activities are taken in order of use case priority, then shorter duration first.
- Every pod starts by filling its slots on its start date.
- A heap per pod keeps running activities ordered by end date. The earliest end date in any pod is
  processed next: its activities leave the heap, count as enabled, the slot is freed, durations are
  refreshed, and activities that are now zero days are closed on that date.
- The pods that just freed a slot start their next activities on that date.
- An activity occupies its slot from the start date up to, but not including, the end date.

Output rows: `Team` (pod), `Workstream` (slot name), `start_date`, `end_date`, `Actual_Days`.

## 5. Outputs

| Sheet | Contents |
|---|---|
| `df_schedule` | one row per scheduled activity |
| `project_sources` | all activities with every intermediate column, priorities and dates |
| `use_cases_with_sources` | ranking table plus `actual_roadmap_days` (sum of activity days) |
| `projects` | projects with `project_priority_sequence` |
| `data_sources` | data sources with the initial status |

## 6. `check_capacity` (`tools.py`)

Given a pod, a number of days and the earliest start, it finds the first date (not before the pod
start date) when one more activity fits for its whole length without exceeding `max_activity`,
looking at what is already in `df_schedule`. Candidate dates are the requested date and every date
on which a booked activity ends.
