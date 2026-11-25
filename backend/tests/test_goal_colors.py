"""Unit tests for choosing a goal's colour."""

from task_master.goal_colors import least_used_color
from task_master.models import GoalColor


class TestLeastUsedColor:
    def test_first_colour_when_none_used(self) -> None:
        assert least_used_color([]) == GoalColor.SKY

    def test_skips_colours_in_use(self) -> None:
        used = [GoalColor.SKY, GoalColor.PERIWINKLE]

        assert least_used_color(used) == GoalColor.LILAC

    def test_fills_a_gap_left_earlier_in_the_palette(self) -> None:
        used = [GoalColor.SKY, GoalColor.LILAC]

        assert least_used_color(used) == GoalColor.PERIWINKLE

    def test_starts_a_second_round_when_every_colour_is_used(self) -> None:
        used = [*GoalColor, GoalColor.SKY]

        assert least_used_color(used) == GoalColor.PERIWINKLE
