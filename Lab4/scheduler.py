#!/usr/bin/env python3
"""
MA3206: Artificial Intelligence - Assignment 4
Assignment Scheduler using Greedy and A* approaches.

Usage: python scheduler.py <input_file>
"""

import sys
import heapq
from collections import defaultdict, deque
from math import ceil


# ---------------------------------------------------------------------------
# 1. INPUT PARSING
# ---------------------------------------------------------------------------

def parse_input(filename):
    """Parse the input file and return problem data."""
    costs = {}
    group_size = 1
    inputs_set = set()
    outputs_set = set()
    assignments = {}   # id -> {'food': str, 'prereqs': set, 'dependents': set}

    with open(filename) as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('%'):
                continue
            parts = line.split()
            token = parts[0]

            if token == 'C':
                # C <food-item> <value>
                costs[parts[1]] = int(parts[2])

            elif token == 'G':
                group_size = int(parts[1])

            elif token == 'I':
                # I id1 id2 ... -1
                for p in parts[1:]:
                    if p == '-1':
                        break
                    inputs_set.add(int(p))

            elif token == 'O':
                # O id1 id2 ... -1
                for p in parts[1:]:
                    if p == '-1':
                        break
                    outputs_set.add(int(p))

            elif token == 'A':
                # A <id> <input1> [<input2>] <output> <Food-name>
                # The last two tokens are always <output> <Food-name>
                # Everything between id and those is prereq node(s)
                aid = int(parts[1])
                food = parts[-1]
                output_node = int(parts[-2])
                prereq_nodes = [int(p) for p in parts[2:-2]]
                assignments[aid] = {
                    'food': food,
                    'output': output_node,
                    'prereq_nodes': prereq_nodes,   # raw node ids
                    'prereqs': set(),               # assignment ids (filled below)
                    'dependents': set(),            # filled below
                }

    # Build assignment dependency graph:
    # For each assignment A, its output node feeds into other assignments as a prereq_node.
    # Build a map: node_id -> assignment_id that produces it
    node_to_assignment = {}
    for aid, adict in assignments.items():
        node_to_assignment[adict['output']] = aid

    # Also, input nodes (books/notes) are always available — they are not assignments.
    for aid, adict in assignments.items():
        for pnode in adict['prereq_nodes']:
            if pnode in node_to_assignment:
                prereq_aid = node_to_assignment[pnode]
                adict['prereqs'].add(prereq_aid)
                assignments[prereq_aid]['dependents'].add(aid)
            # If pnode is in inputs_set, it's a book/note — always available, no constraint

    return costs, group_size, inputs_set, outputs_set, assignments


# ---------------------------------------------------------------------------
# 2. DEPENDENCY UTILITIES
# ---------------------------------------------------------------------------

def get_available(done, assignments):
    """Return set of assignment IDs whose prerequisites are all in `done`."""
    available = set()
    for aid, adict in assignments.items():
        if aid not in done and adict['prereqs'].issubset(done):
            available.add(aid)
    return available


def compute_depths(assignments):
    """
    Compute depth of each assignment: length of the longest chain starting from it.
    Uses memoisation.
    """
    memo = {}

    def depth(aid):
        if aid in memo:
            return memo[aid]
        deps = assignments[aid]['dependents']
        if not deps:
            memo[aid] = 1
        else:
            memo[aid] = 1 + max(depth(d) for d in deps)
        return memo[aid]

    for aid in assignments:
        depth(aid)
    return memo


def topological_order(assignments):
    """Return a list of assignment IDs in topological order (Kahn's algorithm)."""
    in_degree = {aid: len(adict['prereqs']) for aid, adict in assignments.items()}
    queue = deque(aid for aid, deg in in_degree.items() if deg == 0)
    order = []
    while queue:
        aid = queue.popleft()
        order.append(aid)
        for dep in assignments[aid]['dependents']:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)
    return order


def topo_rank(assignments):
    """Return dict: assignment_id -> rank (0-indexed topological position)."""
    order = topological_order(assignments)
    return {aid: i for i, aid in enumerate(order)}


# ---------------------------------------------------------------------------
# 3. SCHEDULE RUNNER (common logic for greedy)
# ---------------------------------------------------------------------------

def run_schedule(day_batches, assignments, costs):
    """
    Given a list of day batches (each batch is a list of assignment IDs),
    compute the day-by-day output with menus and costs.
    Returns: list of (day_num, batch, menu_str, day_cost)
    """
    result = []
    total_cost = 0
    for day_num, batch in enumerate(day_batches, 1):
        # Tally food items
        food_count = defaultdict(int)
        for aid in batch:
            food_count[assignments[aid]['food']] += 1
        day_cost = sum(costs[food] * cnt for food, cnt in food_count.items())
        menu_parts = [f"{cnt}-{food}" for food, cnt in sorted(food_count.items())]
        menu_str = ", ".join(menu_parts)
        result.append((day_num, batch, menu_str, day_cost))
        total_cost += day_cost
    return result, total_cost


def print_schedule(strategy_name, result, total_cost):
    """Print schedule in the required format."""
    print(f"\nStrategy: {strategy_name}")
    for day_num, batch, menu_str, day_cost in result:
        anames = ", ".join(f"A{aid}" for aid in batch)
        print(f"Day-{day_num}: {anames}   Menu: {menu_str}   Cost: {day_cost}")
    total_days = len(result)
    print(f"Total Days: {total_days}")
    print(f"Total Cost: {total_cost}")
    return total_days, total_cost


# ---------------------------------------------------------------------------
# 4. GREEDY STRATEGIES
# ---------------------------------------------------------------------------

def greedy_schedule(assignments, costs, group_size, key_fn, strategy_name):
    """
    Generic greedy scheduler. Each day, pick up to `group_size` available
    assignments sorted by key_fn(aid) ascending (lower = preferred).
    """
    done = set()
    all_ids = set(assignments.keys())
    day_batches = []

    while done != all_ids:
        available = sorted(get_available(done, assignments), key=key_fn)
        batch = available[:group_size]
        if not batch:
            # Safety: should not happen with a valid DAG
            raise ValueError("No available assignments but not all done — check dependencies.")
        day_batches.append(batch)
        done.update(batch)

    result, total_cost = run_schedule(day_batches, assignments, costs)
    return print_schedule(strategy_name, result, total_cost)


def greedy_food_cost(assignments, costs, group_size):
    """Strategy 1: Prioritise assignments with cheapest food item."""
    key_fn = lambda aid: (costs[assignments[aid]['food']], aid)
    return greedy_schedule(assignments, costs, group_size, key_fn,
                           "Greedy by Food Cost")


def greedy_dependency_depth(assignments, costs, group_size):
    """Strategy 2: Prioritise assignments on the longest downstream chain."""
    depths = compute_depths(assignments)
    key_fn = lambda aid: (-depths[aid], aid)   # higher depth = higher priority
    return greedy_schedule(assignments, costs, group_size, key_fn,
                           "Greedy by Dependency Depth")


def greedy_food_frequency(assignments, costs, group_size):
    """Strategy 3: Prioritise assignments whose food type is most frequent among remaining."""
    done = set()
    all_ids = set(assignments.keys())
    day_batches = []

    while done != all_ids:
        remaining = all_ids - done
        available = get_available(done, assignments)
        # Count food frequency in remaining assignments
        freq = defaultdict(int)
        for aid in remaining:
            freq[assignments[aid]['food']] += 1
        # Sort available: descending frequency, then ascending food cost, then id
        sorted_avail = sorted(
            available,
            key=lambda aid: (-freq[assignments[aid]['food']],
                             costs[assignments[aid]['food']],
                             aid)
        )
        batch = sorted_avail[:group_size]
        if not batch:
            raise ValueError("No available assignments — check dependencies.")
        day_batches.append(batch)
        done.update(batch)

    result, total_cost = run_schedule(day_batches, assignments, costs)
    return print_schedule("Greedy by Food Type Frequency", result, total_cost)


def greedy_topological_order(assignments, costs, group_size):
    """Strategy 4: Schedule in strict topological (earliest possible) order."""
    ranks = topo_rank(assignments)
    key_fn = lambda aid: (ranks[aid], aid)
    return greedy_schedule(assignments, costs, group_size, key_fn,
                           "Greedy by Topological Order")


# ---------------------------------------------------------------------------
# 5. A* SEARCH
# ---------------------------------------------------------------------------

def astar_search(assignments, costs, group_size):
    """
    A* search for the schedule that minimises total food cost.

    State: (g_cost, day, frozenset_of_done_assignments, schedule_so_far)
    g(n): total food cost so far
    h(n): lower-bound on remaining cost
          = ceil(|remaining| / g) × min_cost_among_remaining_foods
    """
    all_ids = frozenset(assignments.keys())
    min_cost = min(costs.values())

    def heuristic(done):
        remaining = len(all_ids) - len(done)
        if remaining == 0:
            return 0
        return ceil(remaining / group_size) * min_cost

    # Priority queue entries: (f, g_cost, day, done_frozenset, schedule)
    # schedule is a list of batches, each batch is a sorted list of aids
    start_done = frozenset()
    start_h = heuristic(start_done)
    heap = [(start_h, 0, 0, start_done, [])]

    # Visited: done_frozenset -> best g_cost seen
    visited = {}
    states_explored = 0

    while heap:
        f, g_cost, day, done, schedule = heapq.heappop(heap)

        if done in visited and visited[done] <= g_cost:
            continue
        visited[done] = g_cost
        states_explored += 1

        # Goal check
        if done == all_ids:
            # Build result output
            result, total_cost = run_schedule(schedule, assignments, costs)
            return result, total_cost, states_explored, day

        # Generate successors: choose up to group_size assignments from available
        available = sorted(
            [aid for aid in all_ids if aid not in done
             and assignments[aid]['prereqs'].issubset(done)]
        )

        if not available:
            continue

        # Enumerate all combinations of up to `group_size` from available
        # To keep state space manageable, we prune: consider all subsets of size
        # min(group_size, len(available)).
        # For large instances this could be expensive; we use a bounded search by
        # considering only the top-k candidates by food cost then generating
        # all combinations from those (up to group_size).
        batch_size = min(group_size, len(available))
        from itertools import combinations
        for batch in combinations(available, batch_size):
            batch = list(batch)
            # Compute day cost
            food_count = defaultdict(int)
            for aid in batch:
                food_count[assignments[aid]['food']] += 1
            day_cost = sum(costs[food] * cnt for food, cnt in food_count.items())

            new_g = g_cost + day_cost
            new_done = done | frozenset(batch)
            new_h = heuristic(new_done)
            new_f = new_g + new_h
            new_schedule = schedule + [batch]
            new_day = day + 1

            if new_done not in visited or visited[new_done] > new_g:
                heapq.heappush(heap, (new_f, new_g, new_day, new_done, new_schedule))

    return None, None, states_explored, 0


# ---------------------------------------------------------------------------
# 6. MAIN
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python scheduler.py <input_file>")
        sys.exit(1)

    filename = sys.argv[1]
    costs, group_size, inputs_set, outputs_set, assignments = parse_input(filename)

    print("=" * 60)
    print(f"Problem: {len(assignments)} assignments, group size g={group_size}")
    print(f"Food costs: {costs}")
    print("=" * 60)

    # ---- Task 1: Greedy Strategies ----
    print("\n" + "=" * 60)
    print("TASK 1: GREEDY STRATEGIES")
    print("=" * 60)

    days1, cost1 = greedy_food_cost(assignments, costs, group_size)
    days2, cost2 = greedy_dependency_depth(assignments, costs, group_size)
    days3, cost3 = greedy_food_frequency(assignments, costs, group_size)
    days4, cost4 = greedy_topological_order(assignments, costs, group_size)

    greedy_results = [
        ("Greedy by Food Cost",          days1, cost1),
        ("Greedy by Dependency Depth",   days2, cost2),
        ("Greedy by Food Type Frequency",days3, cost3),
        ("Greedy by Topological Order",  days4, cost4),
    ]
    best_greedy = min(greedy_results, key=lambda x: (x[2], x[1]))

    print("\n" + "-" * 60)
    print("Greedy Summary Table:")
    print(f"{'Strategy':<35} {'Days':>6} {'Cost':>6}")
    print("-" * 50)
    for name, d, c in greedy_results:
        marker = " <-- BEST" if (name, d, c) == best_greedy else ""
        print(f"{name:<35} {d:>6} {c:>6}{marker}")

    # ---- Task 2: A* Search ----
    print("\n" + "=" * 60)
    print("TASK 2: A* SEARCH")
    print("=" * 60)

    print("\nRunning A* search (this may take a moment)...")
    astar_result, astar_cost, states_explored, astar_days = astar_search(
        assignments, costs, group_size
    )

    if astar_result is None:
        print("A* search failed to find a solution.")
    else:
        print(f"\nOptimal Schedule (A*):")
        for day_num, batch, menu_str, day_cost in astar_result:
            anames = ", ".join(f"A{aid}" for aid in batch)
            print(f"Day-{day_num}: {anames}   Menu: {menu_str}   Cost: {day_cost}")
        print(f"Total Days: {astar_days}")
        print(f"Total Cost: {astar_cost}")
        print(f"Total States Explored: {states_explored}")

        print("\n" + "-" * 60)
        print("Comparison: Best Greedy vs A*")
        print(f"  Best Greedy Strategy : {best_greedy[0]}")
        print(f"  Best Greedy Cost     : {best_greedy[2]}  (Days: {best_greedy[1]})")
        print(f"  A* Optimal Cost      : {astar_cost}  (Days: {astar_days})")
        cost_diff = best_greedy[2] - astar_cost
        day_diff  = best_greedy[1] - astar_days
        print(f"  Cost Difference      : {cost_diff} ({'Greedy suboptimal' if cost_diff > 0 else 'Both optimal'})")
        print(f"  Day Difference       : {day_diff}")


if __name__ == "__main__":
    main()
