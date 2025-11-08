from dataclasses import dataclass
from datetime import datetime, timedelta
from dateutil import parser

@dataclass
class Task:
    name: str
    duration: int   # minutes
    priority: int   # 1–5

@dataclass
class Block:
    start: datetime
    end: datetime
    name: str

def plan_day(wake_time, sleep_time, tasks, break_every=60, break_len=5):
    start = parser.parse(wake_time)
    end = parser.parse(sleep_time)
    if end <= start:
        end += timedelta(days=1)

    tasks = sorted(tasks, key=lambda t: (-t.priority, -t.duration))
    cur = start
    focus = 0
    plan = []

    for t in tasks:
        if focus >= break_every and cur + timedelta(minutes=break_len) <= end:
            b_end = cur + timedelta(minutes=break_len)
            plan.append(Block(cur, b_end, "Short Break"))
            cur, focus = b_end, 0

        tlen = timedelta(minutes=t.duration)
        if cur + tlen <= end:
            plan.append(Block(cur, cur + tlen, t.name))
            cur += tlen
            focus += t.duration

    if cur < end:
        plan.append(Block(cur, end, "Free Time / Buffer"))
    return plan

def format_blocks(blocks):
    return [{"Time": f"{b.start.strftime('%I:%M %p')}–{b.end.strftime('%I:%M %p')}",
             "Task": b.name} for b in blocks]
