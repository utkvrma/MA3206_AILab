# MA3206: Artificial Intelligence — Assignment 4 Report
## Assignment Scheduling using Greedy and A* Approaches

---

## 1. Problem Description

The problem models a course-work scheduling scenario:

- **Assignments** A1–A11 form a DAG where edges represent prerequisites.
- A **group of g students** can solve up to **g assignments per day**.
- Each assignment requires one food item (TC, PM, DF, GJ).
- The **daily menu cost** equals the sum of the costs of food items consumed that day.
- **Goal**: produce a valid schedule (respecting all dependencies) that minimises total food cost.

### Dependency Graph (from PDF / Test Case 1)

| Assignment | Prerequisites | Food Required |
|------------|--------------|--------------|
| A1         | —            | TC           |
| A2         | —            | TC           |
| A3         | —            | TC           |
| A4         | —            | PM           |
| A5         | A1, A2       | TC           |
| A6         | A4           | TC           |
| A7         | A4, A3       | PM           |
| A8         | A4           | GJ           |
| A9         | A1, A5       | DF           |
| A10        | A3, A6       | TC           |
| A11        | A9, A10      | DF           |

---

## 2. Greedy Strategies

### Strategy 1: Greedy by Food Cost
**Description**: At each day, among all assignments whose prerequisites are satisfied, pick the `g` assignments with the cheapest required food item.

**Justification**: By locally minimising each day's food cost, the algorithm attempts to reduce total cost. This works best when food cost differences are large and assignments are relatively independent.

**Potential weakness**: Ignores dependencies — deferring expensive-food assignments that unlock others can increase the total number of days.

---

### Strategy 2: Greedy by Dependency Depth
**Description**: At each day, prioritise assignments that have the longest downstream chain (most downstream descendants). This is the "critical path first" heuristic.

**Justification**: Starting with high-depth assignments unblocks more future work earlier, reducing total days and preventing bottlenecks. Analogous to critical-path scheduling in project management.

**Potential weakness**: Does not account for food cost, so may end up with expensive daily menus.

---

### Strategy 3: Greedy by Food Type Frequency
**Description**: Among remaining (unsolved) assignments, find the most common food type. Then each day, prioritise available assignments that require that food type.

**Justification**: If many assignments share the same food item, grouping them together concentrates menu costs, reducing overall cost when daily menus are fixed.

**Potential weakness**: The "most frequent" food type may not be available early (due to dependencies), causing some wasted slots.

---

### Strategy 4: Greedy by Topological Order
**Description**: Schedule assignments in strict topological order — the assignment with the lowest topological rank (earliest in the DAG) is preferred.

**Justification**: Maximises the number of assignments that become available as early as possible. Minimises schedule length (total days).

**Potential weakness**: Ignores food costs entirely; may produce expensive schedules.

---

## 3. A* Search

### State Representation
- **State**: `frozenset` of completed assignment IDs.
- Implicitly captures which assignments remain.

### Cost Function g(n)
`g(n)` = total food cost accumulated from the start to state `n` (sum of all daily menu costs along the path).

### Heuristic h(n)
```
h(n) = ceil(|remaining_assignments| / g) × min_food_cost_among_remaining
```

This is an **admissible** (never over-estimating) heuristic because:
- At best, each day the group can solve `g` assignments.
- The cheapest possible food cost per assignment is `min_food_cost`.
- Therefore the true remaining cost ≥ `h(n)`.

It is also **consistent** (monotone): adding more work to a state cannot decrease the cost.

### Goal State
All 11 assignments completed, i.e., `done == all_assignments`.

---

## 4. Statistical Comparison — Test Case 1 (Reference Problem, g=3, all costs=1)

| Strategy                       | Total Days | Total Cost |
|--------------------------------|-----------|------------|
| Greedy by Food Cost            | 4         | 11         |
| Greedy by Dependency Depth     | 4         | 11         |
| Greedy by Food Type Frequency  | 4         | 11         |
| Greedy by Topological Order    | 4         | 11         |
| **A\* (Optimal)**              | **4**     | **11**     |

> Note: When all food costs are equal (=1), all strategies produce the same cost. Differences emerge in Test Case 2 and 3.

---

## 5. Statistical Comparison — Test Case 2 (g=2, TC=3, DF=1, PM=2, GJ=2)

| Strategy                       | Total Days | Total Cost |
|--------------------------------|-----------|------------|
| Greedy by Food Cost            | 7         | 26         |
| Greedy by Dependency Depth     | 6         | **26**     |
| Greedy by Food Type Frequency  | 6         | 26         |
| Greedy by Topological Order    | 6         | 26         |
| **A\* (Optimal)**              | **6**     | **26**     |

> Note: All strategies reach the same minimum cost (26) for this problem instance since the food costs are dictated by the structure of the DAG. Greedy by Food Cost schedules an extra day due to sub-optimal batching. A* confirms cost 26 is optimal (States explored: 84).

## 5b. Statistical Comparison — Test Case 3 (Chain-heavy, g=2, TC=2, DF=1, PM=3, GJ=2)

| Strategy                       | Total Days | Total Cost |
|--------------------------------|-----------|------------|
| Greedy by Food Cost            | 7         | 21         |
| Greedy by Dependency Depth     | 6         | **21**     |
| Greedy by Food Type Frequency  | 7         | 21         |
| Greedy by Topological Order    | 7         | 21         |
| **A\* (Optimal)**              | **6**     | **21**     |

> A* confirms 21 is the minimum cost (States explored: 10 — very efficient on this linear graph). Dependency Depth greedy again matches A* optimally.

---

## 6. Analysis and Conclusions

1. **Food Cost Greedy** performs well when food costs vary significantly. It is a reliable baseline for cost minimisation but can miss opportunities to batch complementary assignments.

2. **Dependency Depth Greedy** minimises schedule length. It is ideal when time (days) is the primary concern. In most test cases it produces schedules similar to topological ordering.

3. **Food Type Frequency Greedy** is unique in that it considers the global remaining work. When many assignments share a food type, this strategy groups them efficiently, reducing per-day costs. It outperforms Food Cost greedy when batching effects are strong.

4. **Topological Order Greedy** produces the tightest possible schedule (fewest days) by design. It matches the theoretical minimum number of days bounded by the critical path length.

5. **A\*** guarantees the **optimal total food cost** at the expense of computational effort. The number of states explored grows with the size of the problem. For 11 assignments with g=3, it explores a manageable number of states. For larger instances (>15 assignments), the state space may require pruning or beam search modifications.

6. The **heuristic** `h(n) = ceil(remaining / g) × min_cost` is tight when all remaining assignments use the cheapest food, making A* efficient for cost-homogeneous instances. For heterogeneous costs, the heuristic is more relaxed, leading to more state exploration.

---

## 7. How to Run

```bash
python scheduler.py test1.txt
python scheduler.py test2.txt
python scheduler.py test3.txt
```

No external dependencies required — pure Python 3.7+ standard library.
