from .models import Player, Pot
from .scoring import calculate_shares, distribute_pot, scoring_breakdown
from .auction import run_auction
from . import display, cli


class Game:
    def __init__(self):
        self.players: list[Player] = []
        self.pot = Pot()
        self.round_num = 0
        self.total_rounds = 0
        self.first_player_index = 0

    def run(self) -> None:
        self._setup()
        while True:
            self.round_num += 1
            if self.total_rounds > 0 and self.round_num > self.total_rounds:
                break

            display.print_banner(f"ROUND {self.round_num}" + (
                f" of {self.total_rounds}" if self.total_rounds else ""
            ))
            display.print_player_chips(self.players)
            input("\n  Press Enter to start the round...")

            self._ante_phase()
            self._roll_phase()
            self._auction_phase()
            self._reveal_and_payout()

            # Eliminate players with 0 chips
            eliminated = [p for p in self.players if p.chips <= 0]
            if eliminated:
                display.print_separator()
                for p in eliminated:
                    print(f"  {p.name} has been eliminated (0 chips).")
                self.players = [p for p in self.players if p.chips > 0]

            if len(self.players) < 2:
                print("\n  Not enough players to continue.")
                break

            # Rotate first player
            self.first_player_index = (self.first_player_index + 1) % len(self.players)

            # Early exit option (unlimited mode or after each round)
            if self.total_rounds == 0 or (self.total_rounds > 0 and self.round_num < self.total_rounds):
                print()
                if not cli.prompt_yes_no("Continue to next round?"):
                    break

        self._final_standings()

    def _setup(self) -> None:
        names, self.total_rounds = cli.setup_game()
        self.players = [Player(name) for name in names]

    def _ante_phase(self) -> None:
        display.print_banner("ANTE PHASE")
        print(f"\n  Each player antes 5 chips into the pot.\n")
        for p in self.players:
            ante = min(5, p.chips)
            p.pay(ante)
            self.pot.collect(ante)
            print(f"  {p.name} antes {ante} chips.")
        print(f"\n  Pot is now: {self.pot.chips} chips")
        input("\n  Press Enter to continue...")

    def _roll_phase(self) -> None:
        display.print_banner("ROLL PHASE")
        print("\n  Each player will roll their 3 dice privately.")
        print("  Pass the keyboard to each player when prompted.\n")
        input("  Press Enter to begin rolling...")

        for p in self.players:
            # Give each player 3 fresh dice
            from .models import Die
            p.dice = [Die() for _ in range(3)]
            for d in p.dice:
                d.roll()
            cli.show_private_roll(p)

        display.clear_screen()
        display.print_banner("ALL PLAYERS HAVE ROLLED")
        print("\n  All dice are hidden until auctioned or revealed.\n")
        input("  Press Enter to begin the Auction Phase...")

    def _auction_phase(self) -> None:
        display.print_banner("AUCTION PHASE")
        print(f"\n  Each player will auction exactly one die.")
        print(f"  Starting player this round: {self.players[self.first_player_index].name}\n")
        input("  Press Enter to begin...")

        n = len(self.players)
        for i in range(n):
            idx = (self.first_player_index + i) % n
            auctioning_player = self.players[idx]

            display.print_banner(f"AUCTION {i + 1}/{n}: {auctioning_player.name}'s turn")
            display.print_public_state(self.players, self.pot.chips)

            # Player privately chooses which die to auction
            die_idx = cli.get_die_to_auction(auctioning_player)
            auctioned_die = auctioning_player.give_die(die_idx)

            # Run the auction
            run_auction(auctioning_player, auctioned_die, self.players, self.pot.chips)

    def _reveal_and_payout(self) -> None:
        display.print_banner("REVEAL & PAYOUT")

        # Reveal all dice
        for p in self.players:
            for d in p.dice:
                d.revealed = True

        print("\n  Final hands:\n")
        for p in self.players:
            dice_str = "  ".join(str(d.value) for d in p.dice)
            total = p.hand_total()
            trips = " (THREE OF A KIND!)" if p.has_three_of_a_kind() else ""
            print(f"  {p.name:15s}  [{dice_str}]  = {total}{trips}")

        print()
        shares = calculate_shares(self.players)
        total_shares = sum(shares.values())

        display.print_separator()
        print("\n  Scoring:\n")
        print(scoring_breakdown(self.players, shares))
        print(f"\n  Total shares: {total_shares:.2f}")
        print(f"  Pot: {self.pot.chips} chips\n")
        display.print_separator()

        awarded = distribute_pot(self.pot, shares)

        print("\n  Payout:\n")
        for p in self.players:
            chips = awarded[p]
            if chips > 0:
                print(f"  {p.name:15s} receives {chips} chips")
            else:
                print(f"  {p.name:15s} receives nothing")

        print()
        display.print_player_chips(self.players)
        input("\n  Press Enter to continue...")
