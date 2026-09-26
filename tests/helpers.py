import os
import re
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LLM_PROVIDER"] = "custom"

import dates as D
import orchestrator as O

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def day(n: int) -> str:
    return (D.today_for() + timedelta(days=n)).isoformat()


def spoken(n: int) -> str:
    """A future date the way people type it, e.g. '14 Oct'."""
    d = D.today_for() + timedelta(days=n)
    return f"{d.day} {MONTHS[d.month - 1]}"


class Chat:
    def __init__(self, lang=None, mode=None):
        self.s = O.new_state("test")
        self.lang, self.mode = lang, mode
        self.replies = []

    def say(self, text, button=False):
        self.s = O.run_turn(self.s, text, lang=self.lang, lang_mode=self.mode, from_button=button)
        self.replies.append(self.s["_last"]["reply"])
        return self.s["_last"]

    def act(self, action, **payload):
        self.s = O.run_turn(self.s, "", action=action, payload=payload, lang=self.lang, lang_mode=self.mode)
        self.replies.append(self.s["_last"]["reply"])
        return self.s["_last"]

    def pick_flight(self, leg=0, index=0):
        opt = self.s["results"]["flights"][str(leg)][index]
        return self.act("select_flight", leg=leg, id=opt["id"]), opt

    def pick_hotel(self, index=0):
        h = self.s["results"]["hotels"][index]
        return self.act("select_hotel", id=h["id"]), h

    @property
    def last(self):
        return self.s["_last"]

    def block(self, kind):
        return next((b for b in self.last["blocks"] if b["type"] == kind), None)

    def qr_values(self):
        return [q["value"] for q in self.last["quick_replies"]]


EMPTY_SUMMARY = re.compile(r"from\s+to\b|\bto\s+departing|departing\s+returning|departing\s*\)|returning\s*\)|\(\s*\)|\bNone\b|\{\w+\}|  ")


def assert_clean(reply: str):
    assert not EMPTY_SUMMARY.search(reply), f"unfinished/empty summary in reply: {reply!r}"
