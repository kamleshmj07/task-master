"""Procrastination diagnosis: the fix suggested for each postpone reason.

Each reason names a different root cause, so each gets a different remedy:

- stuck: the task is unclear or too big, so make the first step tiny
- dreading: the task feels unpleasant, so lower the bar to starting
- blocked: something external is in the way, so make it explicit
- other: the user's own words, so just help them replan

"No time" is often dread in disguise, so a task repeatedly postponed as
blocked also gets a prompt to reflect on the real reason.
"""

from dataclasses import dataclass

from task_master.models import PostponeReason

# Postponing as `blocked` this many times triggers the reflection prompt.
BLOCKED_REFLECTION_THRESHOLD = 3


@dataclass(frozen=True)
class Suggestion:
    """A fix for one postponement."""

    headline: str
    actions: tuple[str, ...]
    reflection: str | None = None


SUGGESTIONS: dict[PostponeReason, Suggestion] = {
    PostponeReason.STUCK: Suggestion(
        headline="Make the first step smaller",
        actions=(
            "Rewrite the next step as one physical action of 15 minutes or less",
            "Split this task into smaller tasks",
        ),
    ),
    PostponeReason.DREADING: Suggestion(
        headline="Lower the bar to starting",
        actions=(
            "Commit to just 5 minutes, then decide whether to go on",
            "Pair it with something you enjoy",
            "Put it first in tomorrow's Top 3",
        ),
    ),
    PostponeReason.BLOCKED: Suggestion(
        headline="Clear the way",
        actions=(
            "Write down exactly what you are waiting on and who can unblock it",
            "Lower the time limit so it fits your next free slot",
        ),
    ),
    PostponeReason.OTHER: Suggestion(
        headline="Plan around it",
        actions=("Pick a realistic new date and protect time for it",),
    ),
}

BLOCKED_REFLECTION = (
    "You have postponed this {count} times as blocked. "
    "Is it really time, or is it dread?"
)


def suggest(reason: PostponeReason, blocked_count: int) -> Suggestion:
    """Return the fix for `reason`, given the task's total `blocked` count."""
    suggestion = SUGGESTIONS[reason]
    if reason is not PostponeReason.BLOCKED:
        return suggestion
    if blocked_count < BLOCKED_REFLECTION_THRESHOLD:
        return suggestion
    reflection = BLOCKED_REFLECTION.format(count=blocked_count)
    return Suggestion(suggestion.headline, suggestion.actions, reflection)
