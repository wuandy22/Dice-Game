import random
from typing import Optional


class Die:
    def __init__(self):
        self.value: Optional[int] = None
        self.revealed: bool = False

    def roll(self) -> None:
        self.value = random.randint(1, 6)

    def __str__(self) -> str:
        if self.revealed or self.value is not None:
            return str(self.value)
        return "?"

    def face_str(self) -> str:
        """Always show value (for private views)."""
        return str(self.value) if self.value is not None else "?"


class Player:
    def __init__(self, name: str, starting_chips: int = 100):
        self.name = name
        self.chips = starting_chips
        self.dice: list[Die] = []

    def can_afford(self, amount: int) -> bool:
        return self.chips >= amount

    def pay(self, amount: int) -> None:
        if amount > self.chips:
            raise ValueError(f"{self.name} cannot afford {amount} chips (has {self.chips})")
        self.chips -= amount

    def receive(self, amount: int) -> None:
        self.chips += amount

    def give_die(self, index: int) -> "Die":
        return self.dice.pop(index)

    def take_die(self, die: "Die") -> None:
        self.dice.append(die)

    def hand_total(self) -> int:
        return sum(d.value for d in self.dice if d.value is not None)

    def has_three_of_a_kind(self) -> bool:
        vals = [d.value for d in self.dice]
        return len(set(vals)) == 1 and all(v is not None for v in vals)

    def has_four_of_a_kind(self) -> bool:
        vals = [d.value for d in self.dice]
        return len(vals) == 4 and len(set(vals)) == 1 and all(v is not None for v in vals)

    def __repr__(self) -> str:
        return f"Player({self.name!r}, chips={self.chips})"


class Pot:
    def __init__(self):
        self.chips = 0

    def collect(self, amount: int) -> None:
        self.chips += amount

    def take_all(self) -> int:
        amount = self.chips
        self.chips = 0
        return amount
