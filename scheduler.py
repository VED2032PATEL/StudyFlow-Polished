"""
Smart Scheduling Algorithm for Study Planner
=============================================

Algorithm Explanation (for College Viva):
------------------------------------------
The scheduler uses a Priority-Based Greedy Scheduling algorithm.

Step 1 — Priority Score Calculation:
  Each topic is assigned a priority score:
    priority = (difficulty/5 x 0.35) + (urgency x 0.45) + (hours_ratio x 0.20)

  Where:
    urgency     = 1 / max(1, days_until_deadline)   (closer deadline = higher)
    hours_ratio = estimated_hours / max_in_set       (0-1 normalized)

Step 2 — Revision Buffer:
  One revision day is reserved the day before each unique deadline.

Step 3 — Greedy Slot Filling:
  Topics sorted by priority are greedily placed into the earliest available
  date where the day still has capacity. Topics needing more hours than one
  day can hold are split across multiple consecutive days.

Step 4 — Output:
  A sorted list of (date, topic, hours, type) entries.

Time Complexity: O(T log T + T x D), T = topics, D = planning horizon.
"""

from datetime import date, timedelta
from collections import defaultdict


def _score(topic, today, max_hours):
    deadline  = date.fromisoformat(topic["deadline"])
    days_left = max(1, (deadline - today).days)
    urgency   = 1.0 / days_left
    diff_norm = topic["difficulty"] / 5.0
    hrs_norm  = topic["estimated_hours"] / max_hours
    return diff_norm * 0.35 + urgency * 0.45 + hrs_norm * 0.20


def generate_schedule(topics, daily_available_hours, today=None):
    if today is None:
        today = date.today()

    pending = [t for t in topics if not t["is_completed"]]
    if not pending:
        return []

    max_hours = max(t["estimated_hours"] for t in pending) or 1.0
    ranked = sorted(pending, key=lambda t: _score(t, today, max_hours), reverse=True)

    # Collect revision days (day before each deadline)
    deadline_map = defaultdict(list)
    for t in pending:
        deadline_map[t["deadline"]].append(t)

    revision_days = set()
    for dl_str in deadline_map:
        rev = date.fromisoformat(dl_str) - timedelta(days=1)
        if rev >= today:
            revision_days.add(rev)

    day_used = defaultdict(float)
    entries  = []

    for topic in ranked:
        deadline     = date.fromisoformat(topic["deadline"])
        cutoff       = max(today, deadline - timedelta(days=2))
        hours_left   = float(topic["estimated_hours"])
        d            = today

        # Build a list of eligible days up to cutoff
        while hours_left > 0.005:
            if d > cutoff:
                break
            if d in revision_days:
                d += timedelta(days=1)
                continue
            capacity = daily_available_hours - day_used[d]
            if capacity <= 0.005:
                d += timedelta(days=1)
                continue
            alloc = min(hours_left, capacity)
            day_used[d] += alloc
            hours_left  -= alloc
            entries.append({
                "date":         d.isoformat(),
                "topic_id":     topic["id"],
                "topic_name":   topic["name"],
                "subject_name": topic["subject_name"],
                "hours":        round(alloc, 2),
                "entry_type":   "study",
                "difficulty":   topic["difficulty"],
                "deadline":     topic["deadline"],
            })
            if hours_left > 0.005:
                d += timedelta(days=1)

    # Add revision entries
    for dl_str, rev_topics in deadline_map.items():
        rev_day = date.fromisoformat(dl_str) - timedelta(days=1)
        if rev_day < today:
            continue
        active = [t for t in rev_topics if not t["is_completed"]]
        if not active:
            continue
        per_hrs = round(min(1.0, daily_available_hours / len(active)), 2)
        for t in active:
            entries.append({
                "date":         rev_day.isoformat(),
                "topic_id":     t["id"],
                "topic_name":   t["name"],
                "subject_name": t["subject_name"],
                "hours":        per_hrs,
                "entry_type":   "revision",
                "difficulty":   t["difficulty"],
                "deadline":     t["deadline"],
            })

    entries.sort(key=lambda x: x["date"])
    return entries
