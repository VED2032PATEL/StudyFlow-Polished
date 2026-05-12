"""
Spaced Repetition — SM-2 Algorithm
====================================

SM-2 is the algorithm behind Anki and SuperMemo. It calculates the optimal
gap between reviews so information is revisited just before it is forgotten.

How it works (for Viva):
------------------------
Each topic has three state variables:
  n         — number of successful reviews so far
  easiness  — E-Factor (2.5 default), how easy the topic is (1.3 – 4.0)
  interval  — days until next review

After each review the student rates recall quality q (0–5):
  5 = perfect recall
  4 = correct with slight hesitation
  3 = correct with difficulty
  2 = incorrect but answer was close
  1 = incorrect, easy answer
  0 = complete blackout

Update rules:
  if q >= 3 (passed):
      if n == 0:  interval = 1
      elif n == 1: interval = 6
      else:        interval = round(prev_interval * easiness)
      n += 1
      easiness = max(1.3, easiness + 0.1 - (5-q)*(0.08 + (5-q)*0.02))
  else (failed):
      n = 0, interval = 1   (reset — show again tomorrow)

next_review = today + interval days

Reference: P.A. Wozniak, "Optimization of Learning", 1990
"""

import math
from datetime import date, timedelta


# Default E-factor (SM-2 specification)
DEFAULT_EASINESS = 2.5
MIN_EASINESS     = 1.3


def sm2_next(n: int, easiness: float, interval: int, quality: int):
    """
    Run one SM-2 iteration.

    Parameters
    ----------
    n         : int   – repetition count (0 = never reviewed)
    easiness  : float – E-Factor (starts at 2.5)
    interval  : int   – previous interval in days
    quality   : int   – recall quality 0-5

    Returns
    -------
    (new_n, new_easiness, new_interval, next_review_date)
    """
    quality = max(0, min(5, quality))

    if quality >= 3:
        if n == 0:
            new_interval = 1
        elif n == 1:
            new_interval = 6
        else:
            new_interval = math.ceil(interval * easiness)
        new_n = n + 1
    else:
        # Failed — reset
        new_n        = 0
        new_interval = 1

    # Update E-factor
    new_easiness = easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_easiness = max(MIN_EASINESS, round(new_easiness, 4))

    next_review = date.today() + timedelta(days=new_interval)
    return new_n, new_easiness, new_interval, next_review


def quality_from_difficulty(difficulty: int) -> int:
    """
    Auto-infer initial review quality from topic difficulty (1–5).
    Used when a topic is first marked complete with no explicit rating.
    Easier topics get a higher quality score → longer first interval.
    """
    mapping = {1: 5, 2: 4, 3: 4, 4: 3, 5: 3}
    return mapping.get(difficulty, 4)
