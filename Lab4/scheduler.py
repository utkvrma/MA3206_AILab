"""
Scheduler module for Assignment 4
MA3206: Artificial Intelligence — Assignment 4, IIT Patna, March 2026

This module defines data structures and algorithms to solve the assignment
scheduling problem. A group of g students must complete n interdependent
assignments subject to prerequisite constraints and limited daily capacity.
Each assignment requires a food item; the objective is to find a valid
schedule that minimises the total food cost.

NOTE: Since every assignment must be solved exactly once and food is
consumed individually (no sharing), the total food cost is FIXED regardless
of scheduling order. All strategies therefore compete on minimising the
total number of days (schedule length).

Usage:

    python scheduler.py input_file [--strategy STRATEGY]

Where STRATEGY is one of:
    greedy_cost   — Greedy by food cost (ascending)
    greedy_depth  — Greedy by dependency depth / descendant count (descending)
    greedy_freq   — Greedy by food-type frequency (descending)
    greedy_topo   — Greedy by topological BFS level (ascending)
    astar         — Optimal A* search (minimum total cost)

If --strategy is omitted, all four greedy strategies and A* are run.
"""

from __future__ import annotations

import argparse
import itertools
import heapq
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Assignment:
    """Represents a single assignment node in the scheduling graph."""

    aid: int                        # numeric ID of the assignment (e.g. 1 for A1)
    prereq_ids: Tuple[int, int]     # raw prerequisite node IDs from the input file
    output_id: int                  # outcome node ID produced by this assignment
    food: str                       # food item required when solving this assignment
    # Resolved later by _resolve_dependencies():
    dependencies: List[int] = field(default_factory=list)  # assignment IDs that must finish first

    def __repr__(self) -> str:
        return f"A{self.aid}(food={self.food}, deps={self.dependencies})"

# ---------------------------------------------------------------------------
# Core scheduler
# ---------------------------------------------------------------------------

class AssignmentScheduler:
    """
    Implements the four greedy heuristics and an optimal A* search for the
    assignment scheduling problem.

    Strategies
    ----------
    greedy_cost  : Sort available assignments by ascending food cost, USING PRIORITY QUEUE; 
                   tie-break by assignment ID.  Attempts to minimise each day's food bill,
                   though the total cost is fixed so this merely shifts when
                   expensive days occur.

    greedy_depth : Sort by descending downstream-assignment count (descendant
                   count), USING EXPLORATORY DFS.  Processes critical-path nodes first,
                   maximising the set of tasks available after each day.  This is the
                   recommended strategy and a greedy approximation of CPM.

    greedy_freq  : Sort by descending frequency of the required food type among
                   remaining assignments; tie-break by ascending food cost then
                   by assignment ID.  Clusters same-food assignments together,
                   useful when menu-identity discounts apply.

    greedy_topo  : Sort by ascending BFS level in the dependency DAG (shallowest
                   nodes first), USING KAHN'S ALGORITHM tie-break by assignment ID. 
                   Equivalent to a BFS traversal of the dependency graph; produces 
                   predictable, cycle-free schedules.

    astar        : Optimal A* search over the space of subsets (represented as
                   bitmasks) of completed assignments.  The heuristic h(n) is the
                   sum of food costs of all remaining assignments — admissible and
                   consistent (in fact exact, since h = h*).  Returns the schedule
                   with minimum total food cost (= minimum days, given fixed cost).
    """

    def __init__(self, costs: Dict[str, int], group_size: int,
                 initial_inputs: Set[int], outputs: Set[int],
                 assignments: List[Assignment]):
        if group_size <= 0:
            raise ValueError("Group size must be positive")
        self.costs = dict(costs)
        self.g = group_size
        self.initial_inputs = set(initial_inputs)
        self.final_outputs = set(outputs)

        # Primary lookup: assignment ID -> Assignment object
        self.assignments: Dict[int, Assignment] = {a.aid: a for a in assignments}
        # Map output node ID -> assignment ID that produced it
        self.output_to_aid: Dict[int, int] = {a.output_id: a.aid for a in assignments}

        # Build dependency lists
        self._resolve_dependencies()

        # Precompute descendant counts (for greedy_depth primary key)
        self.descendant_counts: Dict[int, int] = self._compute_descendant_counts()

        # Precompute BFS levels (for greedy_depth secondary key and greedy_topo)
        self.bfs_levels: Dict[int, int] = self._compute_bfs_levels()

    # -----------------------------------------------------------------------
    # Initialisation helpers
    # -----------------------------------------------------------------------

    def _resolve_dependencies(self) -> None:
        """
        Convert raw prerequisite node IDs into resolved assignment dependencies.
        A prerequisite is either an initial input (→ no dependency) or the
        output of another assignment (→ dependency on that assignment).
        """
        for assignment in self.assignments.values():
            deps: List[int] = []
            for pid in assignment.prereq_ids:
                if pid in self.initial_inputs:
                    continue  # available from the start, no assignment dependency
                if pid in self.output_to_aid:
                    deps.append(self.output_to_aid[pid])
                else:
                    raise ValueError(
                        f"Unrecognised prerequisite ID {pid} "
                        f"for assignment A{assignment.aid}"
                    )
            assignment.dependencies = deps

    def _compute_descendant_counts(self) -> Dict[int, int]:
        """
        Count the total number of downstream (descendant) assignments reachable
        from each assignment in the dependency DAG.  Used as the primary sort
        key for the greedy_depth strategy.
        """
        # Build child adjacency list: aid -> list of aids that depend on it
        children: Dict[int, List[int]] = {aid: [] for aid in self.assignments}
        for assignment in self.assignments.values():
            for dep in assignment.dependencies:
                children[dep].append(assignment.aid)

        memo: Dict[int, int] = {}

        def dfs(aid: int) -> int:
            if aid in memo:
                return memo[aid]
            count = 0
            for child in children[aid]:
                count += 1 + dfs(child)
            memo[aid] = count
            return count

        for aid in self.assignments:
            dfs(aid)
        return memo

    def _compute_bfs_levels(self) -> Dict[int, int]:
        """
        Compute the BFS depth level for each assignment in the dependency DAG.
        Level 0 = assignments with no dependencies.
        Level k = assignments whose deepest dependency is at level k-1.

        Used as primary sort key for greedy_topo (ascending level = earliest ready).
        """
        # Compute in-degree
        indeg: Dict[int, int] = {aid: 0 for aid in self.assignments}
        for a in self.assignments.values():
            for dep in a.dependencies:
                indeg[a.aid] += 1

        # BFS from all sources (indeg == 0) to compute levels
        level: Dict[int, int] = {}
        queue: deque[int] = deque()
        for aid, d in indeg.items():
            if d == 0:
                level[aid] = 0
                queue.append(aid)

        # Build child adjacency list
        children: Dict[int, List[int]] = {aid: [] for aid in self.assignments}
        for a in self.assignments.values():
            for dep in a.dependencies:
                children[dep].append(a.aid)

        remaining_indeg = dict(indeg)
        while queue:
            aid = queue.popleft()
            for child in children[aid]:
                # Level of child = max level of its parents + 1
                level[child] = max(level.get(child, 0), level[aid] + 1)
                remaining_indeg[child] -= 1
                if remaining_indeg[child] == 0:
                    queue.append(child)

        return level

    # -----------------------------------------------------------------------
    # Availability helper
    # -----------------------------------------------------------------------

    def _available_assignments(self, solved: Set[int]) -> List[int]:
        """Return IDs of assignments whose prerequisites are all satisfied."""
        return [
            aid for aid, a in self.assignments.items()
            if aid not in solved and all(dep in solved for dep in a.dependencies)
        ]

    # -----------------------------------------------------------------------
    # Greedy selection
    # -----------------------------------------------------------------------

    def _greedy_select(self, avail: List[int], strategy: str,
                       solved: Set[int]) -> List[int]:
        """
        Select up to g assignments from *avail* according to *strategy*.

        Sorting keys (per strategy):
          greedy_cost  : (asc food cost, asc assignment ID)
          greedy_depth : (desc descendant count, desc BFS level, asc assignment ID)
          greedy_freq  : (desc remaining food-type frequency, asc food cost, asc ID)
          greedy_topo  : (asc BFS level, asc assignment ID)
        """
        if not avail:
            return []

        n_take = min(self.g, len(avail))

        if strategy == 'greedy_cost':
            # Primary: ascending food cost; tie-break: ascending assignment ID
            sorted_avail = sorted(
                avail,
                key=lambda aid: (self.costs[self.assignments[aid].food], aid)
            )

        elif strategy == 'greedy_depth':
            # Primary: descending descendant count (more unlocks = higher priority)
            # Secondary: descending BFS level (deeper in the DAG = schedule later,
            #            so we prefer nodes that are higher up when counts tie)
            # Tertiary: ascending assignment ID for determinism
            sorted_avail = sorted(
                avail,
                key=lambda aid: (
                    -self.descendant_counts.get(aid, 0),
                    -self.bfs_levels.get(aid, 0),
                    aid
                )
            )

        elif strategy == 'greedy_freq':
            # Count remaining frequency of each food type
            remaining_freq: Dict[str, int] = {}
            for rid, a in self.assignments.items():
                if rid not in solved:
                    remaining_freq[a.food] = remaining_freq.get(a.food, 0) + 1
            # Primary: descending food-type frequency
            # Secondary: ascending food cost (prefer cheaper items within same freq)
            # Tertiary: ascending assignment ID for determinism
            sorted_avail = sorted(
                avail,
                key=lambda aid: (
                    -remaining_freq[self.assignments[aid].food],
                    self.costs[self.assignments[aid].food],
                    aid
                )
            )

        elif strategy == 'greedy_topo':
            # Primary: ascending BFS level (shallowest = schedule earliest)
            # Secondary: ascending assignment ID for determinism
            sorted_avail = sorted(
                avail,
                key=lambda aid: (self.bfs_levels.get(aid, 0), aid)
            )

        else:
            raise ValueError(f"Unknown strategy '{strategy}'")

        return sorted_avail[:n_take]

    # -----------------------------------------------------------------------
    # Greedy runner
    # -----------------------------------------------------------------------

    def run_greedy(self, strategy: str) -> ScheduleResult:
        """
        Execute a greedy scheduling loop using the specified strategy.

        At each day:
          1. Find all available assignments (prerequisites satisfied, not yet done).
          2. Sort by the strategy's key and pick the top-g.
          3. Mark them solved, record the day's menu and cost.
          4. Repeat until all assignments are completed.
        """
        solved: Set[int] = set()
        schedule: List[List[int]] = []
        menus: List[Dict[str, int]] = []
        costs_per_day: List[int] = []

        while len(solved) < len(self.assignments):
            avail = self._available_assignments(solved)
            if not avail:
                raise RuntimeError(
                    "No available assignments — check for dependency cycles "
                    "or unsatisfied prerequisites."
                )
            selected = self._greedy_select(avail, strategy, solved)
            menu_counts: Dict[str, int] = {}
            day_cost = 0
            for aid in selected:
                food = self.assignments[aid].food
                menu_counts[food] = menu_counts.get(food, 0) + 1
                day_cost += self.costs[food]
                solved.add(aid)
            schedule.append(selected)
            menus.append(menu_counts)
            costs_per_day.append(day_cost)

        return ScheduleResult(
            strategy=strategy,
            schedule=schedule,
            menus=menus,
            costs_per_day=costs_per_day,
            total_days=len(schedule),
            total_cost=sum(costs_per_day),
        )

    def run_all_greedies(self) -> List[ScheduleResult]:
        """Run all four greedy strategies and return their results."""
        results = []
        for strat in ['greedy_cost', 'greedy_depth', 'greedy_freq', 'greedy_topo']:
            try:
                results.append(self.run_greedy(strat))
            except RuntimeError:
                results.append(ScheduleResult(
                    strategy=strat, schedule=[], menus=[],
                    costs_per_day=[], total_days=0, total_cost=math.inf
                ))
        return results

    # -----------------------------------------------------------------------
    # A* search — optimal scheduling
    # -----------------------------------------------------------------------

    def run_astar(self) -> ScheduleResult:
        """
        A* search for the schedule with minimum total food cost.

        State representation
        --------------------
        An integer bitmask where bit i is 1 iff the i-th assignment (in sorted
        ID order) has been solved.  Bitmasks are compact, hashable, and enable
        O(1) set operations.

        Cost function g(n)
        ------------------
        The total food cost accumulated from the initial state to state n.

        Heuristic h(n)  (admissible AND consistent)
        -------------------------------------------
        h(n) = sum of cost(food(A_i)) for all A_i NOT yet solved in state n.

        Admissibility: every remaining assignment MUST eventually be solved and
        its food item consumed individually — no omission, no sharing. Hence
        h(n) ≤ h*(n) for every state.

        Consistency: for any day-transition solving set D,
          c(n, D, n') = Σ cost(food(A_i)), A_i ∈ D
          h(n) − h(n') = Σ cost(food(A_i)), A_i ∈ D = c(n, D, n')
        so h(n) ≤ c(n, D, n') + h(n') with equality — h is consistent (exact).

        Because h = h* (exact heuristic), A* only expands states on optimal
        paths, ensuring correctness and efficiency via visited-state pruning.

        Priority queue entry
        --------------------
        (f_score, counter, g_cost, mask, day_count, path)
        An integer counter is included to break ties in the heap without
        ever comparing frozensets or lists, avoiding Python TypeError.
        """
        aids = sorted(self.assignments.keys())
        n = len(aids)
        aid_to_bit = {aid: i for i, aid in enumerate(aids)}
        all_done = (1 << n) - 1

        # Pre-compute per-bit food cost and prerequisite bitmask
        bit_cost: List[int] = [
            self.costs[self.assignments[aids[i]].food] for i in range(n)
        ]
        prereq_mask: List[int] = [0] * n
        for aid in aids:
            bit = aid_to_bit[aid]
            for dep in self.assignments[aid].dependencies:
                prereq_mask[bit] |= (1 << aid_to_bit[dep])

        total_cost_all = sum(bit_cost)

        # visited_cost[mask] = lowest g_cost seen when reaching this state
        visited_cost: Dict[int, int] = {0: 0}

        # Priority queue: (f, counter, g, mask, day_count, path)
        counter = 0
        pq: List = []
        heapq.heappush(pq, (total_cost_all, counter, 0, 0, 0, []))
        explored = 0

        while pq:
            f, _cnt, g_cost, mask, day_count, path = heapq.heappop(pq)
            explored += 1

            if mask == all_done:
                # Reconstruct schedule from path of bit-index lists
                schedule: List[List[int]] = []
                menus: List[Dict[str, int]] = []
                costs_per_day: List[int] = []
                for day_bits in path:
                    day_aids = [aids[b] for b in day_bits]
                    schedule.append(day_aids)
                    menu: Dict[str, int] = {}
                    day_cost = 0
                    for aid in day_aids:
                        food = self.assignments[aid].food
                        menu[food] = menu.get(food, 0) + 1
                        day_cost += self.costs[food]
                    menus.append(menu)
                    costs_per_day.append(day_cost)
                return ScheduleResult(
                    strategy='astar',
                    schedule=schedule, menus=menus,
                    costs_per_day=costs_per_day,
                    total_days=len(schedule),
                    total_cost=g_cost,
                    explored_states=explored,
                )

            # Prune if a cheaper path to this state was already found
            if visited_cost.get(mask, math.inf) < g_cost:
                continue

            # Find available (unsolved, prerequisites satisfied) assignment bits
            avail_bits = [
                b for b in range(n)
                if not (mask >> b & 1) and (prereq_mask[b] & mask) == prereq_mask[b]
            ]
            if not avail_bits:
                continue

            max_r = min(self.g, len(avail_bits))
            for r in range(max_r, 0, -1):
                for combo in itertools.combinations(avail_bits, r):
                    next_mask = mask
                    cost_inc = 0
                    for b in combo:
                        next_mask |= (1 << b)
                        cost_inc += bit_cost[b]
                    new_g = g_cost + cost_inc
                    # h = total_cost_all - new_g  (exact heuristic)
                    # f = g + h = total_cost_all (constant — acts like Dijkstra)
                    if visited_cost.get(next_mask, math.inf) <= new_g:
                        continue
                    visited_cost[next_mask] = new_g
                    counter += 1
                    heapq.heappush(
                        pq,
                        (total_cost_all, counter, new_g, next_mask,
                         day_count + 1, path + [list(combo)])
                    )

        raise RuntimeError("A* search failed to find a complete schedule.")


# ---------------------------------------------------------------------------
# Input file parser
# ---------------------------------------------------------------------------

def parse_input_file(
    path: str,
) -> Tuple[Dict[str, int], int, Set[int], Set[int], List[Assignment]]:
    """
    Parse an input specification file.

    File format (non-comment lines only):

      C <food-item> <cost>                     # food cost
      G <number>                               # group size
      I <id> ... -1                            # initial input node IDs
      O <id> ... -1                            # required output node IDs
      A <id> <pre1> <pre2> <outcome> <food>    # assignment definition
      % ...                                    # comment (ignored)
    """
    costs: Dict[str, int] = {}
    group_size: Optional[int] = None
    inputs: Set[int] = set()
    outputs: Set[int] = set()
    assignments: List[Assignment] = []

    with open(path, 'r') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('%'):
                continue
            parts = line.split()
            tag = parts[0]
            if tag == 'C':
                if len(parts) != 3:
                    raise ValueError(f"Bad cost line: {line!r}")
                costs[parts[1]] = int(parts[2])
            elif tag == 'G':
                if len(parts) != 2:
                    raise ValueError(f"Bad group-size line: {line!r}")
                group_size = int(parts[1])
            elif tag == 'I':
                for tok in parts[1:]:
                    if tok == '-1':
                        break
                    inputs.add(int(tok))
            elif tag == 'O':
                for tok in parts[1:]:
                    if tok == '-1':
                        break
                    outputs.add(int(tok))
            elif tag == 'A':
                if len(parts) != 6:
                    raise ValueError(f"Bad assignment line: {line!r}")
                aid, pre1, pre2, out = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                assignments.append(
                    Assignment(aid=aid, prereq_ids=(pre1, pre2), output_id=out, food=parts[5])
                )
            else:
                raise ValueError(f"Unknown line tag: {line!r}")

    if group_size is None:
        raise ValueError("Group size (G line) not found in input file")
    return costs, group_size, inputs, outputs, assignments


# ---------------------------------------------------------------------------
# Pretty-print helper
# ---------------------------------------------------------------------------

STRATEGY_LABELS = {
    'greedy_cost':  'Greedy-Cost  (ascending food cost)',
    'greedy_depth': 'Greedy-Depth (descending descendant count + BFS level)',
    'greedy_freq':  'Greedy-Freq  (descending food-type frequency)',
    'greedy_topo':  'Greedy-Topo  (ascending BFS level / topological order)',
    'astar':        'A* Search    (optimal)',
}


def print_result(res: ScheduleResult) -> None:
    label = STRATEGY_LABELS.get(res.strategy, res.strategy)
    print(f"\nStrategy: {label}")
    for day_idx, day_aids in enumerate(res.schedule):
        aids_str = ', '.join(f'A{aid}' for aid in day_aids)
        menu_str = ', '.join(f'{cnt}×{food}' for food, cnt in res.menus[day_idx].items())
        print(f"  Day {day_idx + 1:2d}: [{aids_str}]   Menu: [{menu_str}]   Cost: {res.costs_per_day[day_idx]}")
    print(f"  Total Days: {res.total_days}   Total Cost: Rs.{res.total_cost}")
    if res.explored_states is not None:
        print(f"  States explored: {res.explored_states}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assignment scheduling solver — MA3206 AI Assignment 4"
    )
    parser.add_argument('input_file', help='Path to input specification file')
    parser.add_argument(
        '--strategy', default=None,
        help=('Strategy: greedy_cost | greedy_depth | greedy_freq | '
              'greedy_topo | astar. Omit to run all.')
    )
    args = parser.parse_args()

    costs, group_size, inputs, outputs, assignments = parse_input_file(args.input_file)
    scheduler = AssignmentScheduler(costs, group_size, inputs, outputs, assignments)

    if args.strategy is None:
        for strat in ['greedy_cost', 'greedy_depth', 'greedy_freq', 'greedy_topo']:
            print_result(scheduler.run_greedy(strat))
        print_result(scheduler.run_astar())
    elif args.strategy == 'astar':
        print_result(scheduler.run_astar())
    else:
        print_result(scheduler.run_greedy(args.strategy))


if __name__ == '__main__':
    main()
