"""An in-memory SCALE-inspired state machine. No blockchain calls or real funds."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Mapping


class State(str, Enum):
    FUNDED = "funded"
    SUBMITTED = "submitted"
    PAID = "paid"
    REFUNDED = "refunded"


class ScaleError(ValueError):
    """A task transition violates the model's rules."""


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ScaleError("Time must be timezone-aware.")
    return value.astimezone(timezone.utc)


@dataclass
class Ledger:
    """Integer token units. The task's escrow is accounted for separately."""

    balances: dict[str, int]

    def __post_init__(self) -> None:
        if any(not isinstance(k, str) or not k.strip() or type(v) is not int or v < 0
               for k, v in self.balances.items()):
            raise ScaleError("Balances must be non-negative integer units for named actors.")
        self.balances = dict(self.balances)

    def balance(self, actor: str) -> int:
        return self.balances.get(actor, 0)

    def debit(self, actor: str, amount: int) -> None:
        if type(amount) is not int or amount <= 0:
            raise ScaleError("Amount must be positive integer units.")
        if self.balance(actor) < amount:
            raise ScaleError("Insufficient balance.")
        self.balances[actor] = self.balance(actor) - amount

    def credit(self, actor: str, amount: int) -> None:
        if type(amount) is not int or amount <= 0:
            raise ScaleError("Amount must be positive integer units.")
        self.balances[actor] = self.balance(actor) + amount


@dataclass
class Task:
    requester: str
    worker: str
    judge: str
    amount: int
    deadline: datetime
    ledger: Ledger = field(repr=False)
    state: State = field(default=State.FUNDED, init=False)
    escrow: int = field(default=0, init=False)
    work: str | None = field(default=None, init=False)
    events: list[str] = field(default_factory=list, init=False)

    @classmethod
    def create(cls, ledger: Ledger, requester: str, worker: str, judge: str,
               amount: int, deadline: datetime, now: datetime) -> "Task":
        if any(not isinstance(actor, str) or not actor.strip() for actor in (requester, worker, judge)):
            raise ScaleError("All actors must have names.")
        if len({requester, worker, judge}) != 3:
            raise ScaleError("Requester, worker and judge must be distinct.")
        if type(amount) is not int or amount <= 0:
            raise ScaleError("Amount must be positive integer units.")
        deadline, now = utc(deadline), utc(now)
        if deadline <= now:
            raise ScaleError("Deadline must be in the future.")
        task = cls(requester, worker, judge, amount, deadline, ledger)
        ledger.debit(requester, amount)
        task.escrow = amount
        task.events.append("funded")
        return task

    def submit(self, actor: str, work: str, now: datetime) -> None:
        if self.state is not State.FUNDED:
            raise ScaleError("Task is not awaiting a submission.")
        if actor != self.worker:
            raise ScaleError("Only the assigned worker can submit.")
        if utc(now) >= self.deadline:
            raise ScaleError("Submission deadline has passed; refund the task.")
        if not isinstance(work, str) or not work.strip():
            raise ScaleError("Work must not be empty.")
        self.work = work
        self.state = State.SUBMITTED
        self.events.append("submitted")

    def decide(self, actor: str, passed: bool) -> None:
        if self.state is not State.SUBMITTED:
            raise ScaleError("Task is not awaiting a verdict.")
        if actor != self.judge:
            raise ScaleError("Only the assigned judge can decide.")
        if type(passed) is not bool:
            raise ScaleError("Verdict must be a boolean.")
        self._settle(self.worker if passed else self.requester, State.PAID if passed else State.REFUNDED)

    def refund_expired(self, now: datetime) -> None:
        if self.state is not State.FUNDED:
            raise ScaleError("Only an unsubmitted task can expire.")
        if utc(now) < self.deadline:
            raise ScaleError("Submission deadline has not passed.")
        self._settle(self.requester, State.REFUNDED)

    def _settle(self, recipient: str, state: State) -> None:
        if self.escrow != self.amount:
            raise ScaleError("Escrow already settled or invalid.")
        self.ledger.credit(recipient, self.escrow)
        self.escrow = 0
        self.state = state
        self.events.append(state.value)


def scenario(name: str, passed: bool | None) -> Mapping[str, object]:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ledger = Ledger({"requester": 100, "worker": 0, "judge": 0})
    task = Task.create(ledger, "requester", "worker", "judge", 25, now + timedelta(hours=1), now)
    if passed is None:
        task.refund_expired(now + timedelta(hours=1))
    else:
        task.submit("worker", "Example result", now + timedelta(minutes=20))
        task.decide("judge", passed)
    return {"scenario": name, "state": task.state.value, "escrow": task.escrow,
            "balances": ledger.balances, "events": task.events}


def main() -> None:
    import json
    print("LOCAL SIMULATION — no blockchain calls or real RLO")
    for name, passed in (("pass", True), ("fail", False), ("deadline", None)):
        print(json.dumps(scenario(name, passed), ensure_ascii=False))


if __name__ == "__main__":
    main()
