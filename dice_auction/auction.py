import msvcrt
import time
import sys
from dataclasses import dataclass
from typing import Optional
from .models import Player, Die
from . import display, cli

# Key assignments are fixed per player index in all_players.
# Player 1 always uses '1' / 'q', Player 2 always '2' / 'w', etc.
QUICK_BID_KEYS = ['1', '2', '3', '4', '5']   # press to bid current+1
CUSTOM_BID_KEYS = ['q', 'w', 'e', 'r', 't']  # press to type a specific amount

COUNTDOWN_SECONDS = 10  # seconds of silence before auction closes
REFRESH_MS = 0.05       # display refresh interval


@dataclass
class AuctionResult:
    winner: Optional[Player]
    final_bid: int
    given_die: Optional[Die]


def _flush_input_buffer() -> None:
    """Discard any queued keystrokes before starting the live loop."""
    while msvcrt.kbhit():
        msvcrt.getch()


def _read_key() -> str:
    """
    Non-blocking key read. Returns a single lowercase character, or ''
    if no key is pressed or the key is a multi-byte special key (arrows, F-keys).
    """
    if not msvcrt.kbhit():
        return ''
    raw = msvcrt.getch()
    # Multi-byte special keys start with 0x00 or 0xe0 — discard both bytes.
    if raw in (b'\x00', b'\xe0'):
        if msvcrt.kbhit():
            msvcrt.getch()
        return ''
    try:
        return raw.decode('utf-8').lower()
    except UnicodeDecodeError:
        return ''


def _render(
    auctioning_player: Player,
    auctioned_die: Die,
    all_players: list[Player],
    current_bid: int,
    leader: Optional[Player],
    countdown: float,
    quick: dict,   # player -> key char
    custom: dict,  # player -> key char
) -> None:
    W = 64
    out = ['\033[2J\033[H']  # ANSI: clear + cursor to top-left
    out.append('=' * W + '\n')
    out.append(f'  LIVE AUCTION  —  {auctioning_player.name} auctions [ {auctioned_die.value} ]\n')
    out.append('=' * W + '\n\n')

    if leader:
        out.append(f'  Highest bid : {current_bid} chips  by {leader.name}\n')
    else:
        out.append(f'  No bids yet.\n')

    # Countdown bar
    filled = max(0, int((countdown / COUNTDOWN_SECONDS) * 44))
    bar = '█' * filled + '░' * (44 - filled)
    out.append(f'  Closes in   : [{bar}] {countdown:.1f}s\n\n')
    out.append('-' * W + '\n\n')

    for p in all_players:
        if p is auctioning_player:
            note = '(auctioning)'
            keys = ''
        elif p is leader:
            note = '*** LEADING ***'
            keys = '  Already the highest bidder'
        elif not p.can_afford(current_bid + 1):
            note = f'(cannot afford next bid of {current_bid + 1})'
            keys = ''
        else:
            note = ''
            next_bid = current_bid + 1
            keys = (
                f'  [{quick[p]}] bid {next_bid} instantly'
                f'    [{custom[p]}] type a specific amount'
            )

        out.append(f'  {p.name:15s}  {p.chips:4d} chips  {note}\n')
        if keys:
            out.append(f'{keys}\n')

    out.append('\n')
    sys.stdout.write(''.join(out))
    sys.stdout.flush()


def run_auction(
    auctioning_player: Player,
    auctioned_die: Die,
    all_players: list[Player],
    pot_chips: int,
) -> AuctionResult:
    active_bidders = [p for p in all_players if p is not auctioning_player]
    if not active_bidders:
        return AuctionResult(winner=None, final_bid=0, given_die=None)

    # Fixed key assignment by position in all_players
    quick = {p: QUICK_BID_KEYS[i] for i, p in enumerate(all_players)}
    custom = {p: CUSTOM_BID_KEYS[i] for i, p in enumerate(all_players)}
    key_to_player_quick = {v: k for k, v in quick.items()}
    key_to_player_custom = {v: k for k, v in custom.items()}

    current_bid = 0
    leader: Optional[Player] = None
    deadline = time.time() + COUNTDOWN_SECONDS

    _flush_input_buffer()

    # ── Live bidding loop ─────────────────────────────────────────────────────
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            break

        _render(auctioning_player, auctioned_die, all_players,
                current_bid, leader, remaining, quick, custom)

        ch = _read_key()

        # ── Quick bid: player's number key → bid current+1 ───────────────────
        if ch in key_to_player_quick:
            bidder = key_to_player_quick[ch]
            if bidder is not auctioning_player and bidder is not leader:
                new_bid = current_bid + 1
                if new_bid >= 1 and bidder.can_afford(new_bid):
                    current_bid = new_bid
                    leader = bidder
                    deadline = time.time() + COUNTDOWN_SECONDS

        # ── Custom bid: player's letter key → type an amount ─────────────────
        elif ch in key_to_player_custom:
            bidder = key_to_player_custom[ch]
            if bidder is not auctioning_player and bidder is not leader:
                min_bid = current_bid + 1
                sys.stdout.write(
                    f'\n  {bidder.name} — enter bid amount'
                    f' (positive integer, min {min_bid}, max {bidder.chips}): '
                )
                sys.stdout.flush()
                try:
                    raw = input()
                    val = int(raw.strip())
                    if val >= 1 and val > current_bid and bidder.can_afford(val):
                        current_bid = val
                        leader = bidder
                        deadline = time.time() + COUNTDOWN_SECONDS
                    else:
                        msg = (
                            f'  Invalid. Must be a positive integer > {current_bid}'
                            f' and ≤ {bidder.chips}.\n'
                            f'  Press any key to continue...'
                        )
                        sys.stdout.write(msg)
                        sys.stdout.flush()
                        _flush_input_buffer()
                        msvcrt.getch()
                except ValueError:
                    sys.stdout.write(
                        '  Invalid input — must be a whole positive number.\n'
                        '  Press any key to continue...'
                    )
                    sys.stdout.flush()
                    _flush_input_buffer()
                    msvcrt.getch()
                _flush_input_buffer()

        time.sleep(REFRESH_MS)

    # ── Auction over ──────────────────────────────────────────────────────────
    display.clear_screen()

    if leader is None:
        display.print_banner('AUCTION RESULT: No bids')
        print(f'\n  No one bid on {auctioning_player.name}\'s die.')
        print(f'  Die [ {auctioned_die.value} ] is returned.\n')
        input('  Press Enter to continue...')
        return AuctionResult(winner=None, final_bid=0, given_die=None)

    # Winner: show result, then handle the exchange privately
    display.print_banner(f'AUCTION WON by {leader.name}!')
    print(f'\n  {leader.name} wins with a bid of {current_bid} chips.')
    print(f'  Die acquired: [ {auctioned_die.value} ]\n')
    input('  Press Enter for the exchange phase...')

    display.handoff_screen(leader.name)
    given_idx = cli.get_exchange_die(leader, auctioned_die)
    given_die = leader.give_die(given_idx)

    # Execute financial exchange
    leader.pay(current_bid)
    auctioning_player.receive(current_bid)
    leader.take_die(auctioned_die)

    # Both exchanged dice become public
    auctioned_die.revealed = True
    given_die.revealed = True
    auctioning_player.take_die(given_die)

    display.clear_screen()
    display.print_banner('EXCHANGE COMPLETE')
    print(f'\n  {leader.name} paid {current_bid} chips to {auctioning_player.name}')
    print(f'  {leader.name} received:  [ {auctioned_die.value} ] (was auctioned)')
    print(f'  {leader.name} gave back: [ {given_die.value} ] (returned to {auctioning_player.name})')
    print()
    input('  Press Enter to continue...')

    return AuctionResult(winner=leader, final_bid=current_bid, given_die=given_die)
