from typing import Optional
from .models import Player, Die
from . import display


def prompt_int(message: str, min_val: int, max_val: int) -> int:
    while True:
        raw = input(f"  {message} [{min_val}-{max_val}]: ").strip()
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
            print(f"  Please enter a number between {min_val} and {max_val}.")
        except ValueError:
            print("  Please enter a valid number.")


def prompt_choice(message: str, choices: list[str]) -> str:
    choices_lower = [c.lower() for c in choices]
    choices_display = "/".join(choices)
    while True:
        raw = input(f"  {message} ({choices_display}): ").strip().lower()
        if raw in choices_lower:
            return raw
        print(f"  Please enter one of: {choices_display}")


def prompt_yes_no(message: str) -> bool:
    return prompt_choice(message, ["y", "n"]) == "y"


def setup_game() -> tuple[list[str], int]:
    display.print_banner("DICE AUCTION")
    print("\n  Welcome to Dice Auction!\n")

    num_players = prompt_int("Number of players", 3, 5)
    names = []
    for i in range(num_players):
        while True:
            name = input(f"  Name for Player {i + 1}: ").strip()
            if name and name not in names:
                names.append(name)
                break
            elif not name:
                print("  Name cannot be empty.")
            else:
                print("  Name already taken.")

    print()
    mode = prompt_choice("Play for a set number of rounds or unlimited?", ["rounds", "unlimited"])
    if mode == "rounds":
        total_rounds = prompt_int("How many rounds", 1, 50)
    else:
        total_rounds = 0  # 0 means unlimited

    return names, total_rounds


def show_private_roll(player: Player) -> None:
    display.handoff_screen(player.name)
    print(f"\n  Your dice:\n")
    for i, die in enumerate(player.dice):
        print(f"    Die {i + 1}: [ {die.face_str()} ]")
    print()
    display.hide_screen()


def get_die_to_auction(player: Player) -> int:
    display.handoff_screen(player.name)
    print(f"\n  {player.name}, choose a die to auction.\n")
    print(f"  Your dice:")
    for i, die in enumerate(player.dice):
        label = f"Die {i + 1}: [ {die.face_str()} ]"
        if die.revealed:
            label += "  (already public)"
        print(f"    {i + 1}. {label}")
    print()
    idx = prompt_int("Which die to auction (1/2/3)", 1, len(player.dice)) - 1
    display.hide_screen()
    return idx


def get_exchange_die(winner: Player, received_die: Die) -> int:
    print(f"\n  {winner.name}, you won the auction and received die [ {received_die.value} ].")
    print(f"  You must give one of your dice in exchange.\n")
    print(f"  Your current dice:")
    for i, die in enumerate(winner.dice):
        label = f"Die {i + 1}: [ {die.face_str()} ]"
        if die.revealed:
            label += "  (already public)"
        print(f"    {i + 1}. {label}")
    print()
    idx = prompt_int("Which die to give back (1/2/3)", 1, len(winner.dice)) - 1
    return idx
