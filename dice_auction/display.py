import os

WIDTH = 60
SEP = "-" * WIDTH


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_banner(text: str) -> None:
    print(f"\n{'=' * WIDTH}")
    print(f"  {text}")
    print(f"{'=' * WIDTH}")


def print_separator() -> None:
    print(SEP)


def print_player_chips(players) -> None:
    print("\nChip counts:")
    for p in players:
        bar = "#" * (p.chips // 5)
        print(f"  {p.name:15s}  {p.chips:4d} chips  {bar}")


def print_public_state(players, pot_chips: int) -> None:
    print(f"\n  Pot: {pot_chips} chips")
    print("\n  Player             Chips   Dice (public)")
    print_separator()
    for p in players:
        public_dice = "  ".join(
            str(d.value) if d.revealed else "?" for d in p.dice
        )
        print(f"  {p.name:15s}  {p.chips:4d}    [{public_dice}]")


def handoff_screen(player_name: str) -> None:
    clear_screen()
    print("\n" * 3)
    print(f"{'=' * WIDTH}")
    print(f"{'PASS KEYBOARD TO: ' + player_name:^{WIDTH}}")
    print(f"{'=' * WIDTH}")
    print("\n  Press Enter when ready...", end="")
    input()
    clear_screen()


def hide_screen() -> None:
    print("\n\n  Done viewing. Pass the keyboard to the next player.")
    print("\n  Press Enter to hide...", end="")
    input()
    clear_screen()
    print("\n" * 10)
    print(f"{'=' * WIDTH}")
    print(f"{'SCREEN HIDDEN':^{WIDTH}}")
    print(f"{'=' * WIDTH}")
    print("\n" * 10)
