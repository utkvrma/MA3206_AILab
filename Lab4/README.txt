MA3206: Artificial Intelligence — Assignment 4
Assignment Scheduler (Greedy + A*)
===========================================

RUNNING THE PROGRAM
-------------------
  python scheduler.py <input_file>

Examples:
  python scheduler.py test1.txt
  python scheduler.py test2.txt
  python scheduler.py test3.txt

DEPENDENCIES
------------
  Python 3.7+
  Standard library only: sys, heapq, collections, math, itertools
  No external packages (no pip install required).

INPUT FILE FORMAT
-----------------
  Lines starting with '%' are comments and are ignored.

  C <food-name> <cost>       -- Food item cost (e.g., C TC 1)
  G <group-size>             -- Max assignments solvable per day
  I <id1> <id2> ... -1      -- Input node IDs (books/notes), terminated by -1
  O <id1> <id2> ... -1      -- Output node IDs (final outcomes), terminated by -1
  A <id> <in1> [<in2>] <out> <food>
                             -- Assignment: id, prerequisite node(s), output node, food required

  Example:
    C TC 1
    G 3
    I 1 2 3 -1
    O 10 -1
    A 1 1 2 7 TC
    A 2 3 2 8 PM
    A 3 7 8 10 DF

OUTPUT FORMAT
-------------
  The program prints:
    - All four Greedy strategy schedules
    - A Greedy summary table
    - The A* optimal schedule
    - A comparison between best Greedy and A*

GREEDY STRATEGIES IMPLEMENTED
------------------------------
  1. Greedy by Food Cost
     Each day, prioritise assignments whose required food item is cheapest.
     Rationale: Minimises each day's cost individually (locally optimal).

  2. Greedy by Dependency Depth
     Each day, prioritise assignments that have the longest downstream chain
     (i.e., they unlock the most future work).
     Rationale: Unblocks other assignments as early as possible.

  3. Greedy by Food Type Frequency
     Each day, prioritise assignments whose food type is most common among
     remaining (unsolved) assignments. Rationale: Aligns daily menus with the 
     dominant food type, reducing menu variety costs when daily menus are fixed.

  4. Greedy by Topological Order
     Schedule assignments in strict topological order (earliest prerequisites 
     resolved first). Rationale: Minimises idle/slack time in the schedule by 
     advancing the frontier as fast as topologically possible.

TEST CASES
----------
  test1.txt  -- Reference problem from the assignment PDF (g=3, all costs=1)
  test2.txt  -- Same graph, differentiated food costs (TC=3, DF=1, PM=2, GJ=2), g=2
  test3.txt  -- Chain-heavy dependency graph, mixed costs, g=2

AUTHOR
------
  MA3206 Artificial Intelligence Assignment 4
