import threading
import time
from typing import Optional
from .models import Player, Die, Pot
from .scoring import calculate_shares, distribute_pot

AUCTION_COUNTDOWN = 6.0


class Phase:
    LOBBY         = 'lobby'
    ROLLING       = 'rolling'
    AUCTION_CHOOSE = 'auction_choose'
    AUCTION_LIVE  = 'auction_live'
    EXCHANGE      = 'exchange'
    PAYOUT        = 'payout'
    GAME_OVER     = 'game_over'


class GameManager:
    def __init__(self, socketio):
        self.sio = socketio
        self._lock = threading.Lock()

        # ── persistent across resets ──────────────────────────────────────────
        self.sid_map: dict[str, str] = {}   # sid → player name

        # ── game state (reset each game) ──────────────────────────────────────
        self.phase          = Phase.LOBBY
        self.players:  list[Player] = []
        self.pot            = Pot()
        self.round_num      = 0
        self.total_rounds   = 0
        self.first_idx      = 0             # index into self.players for first auctioner
        self.history: list[str] = []

        # rolling
        self.four_dice_mode: bool = False
        self.ready_set: set[str] = set()
        self.round_auction_num = 0

        # auction
        self.auction_queue: list[Player] = []
        self.auctioner:      Optional[Player] = None
        self.auctioned_die:  Optional[Die]    = None
        self.bid             = 0
        self.bid_leader:     Optional[Player] = None
        self.auction_deadline = 0.0
        self._timer_active   = False

        # exchange
        self.exchange_winner: Optional[Player] = None

        # payout
        self.payout_data: list[dict] = []

    # ── Registration / connection ─────────────────────────────────────────────

    def register(self, sid: str, name: str) -> tuple[bool, str]:
        with self._lock:
            if self.phase != Phase.LOBBY:
                return False, 'Game already in progress'
            name = name.strip()
            if not name or len(name) > 20:
                return False, 'Name must be 1–20 characters'
            if any(p.name.lower() == name.lower() for p in self.players):
                return False, 'Name already taken'
            if len(self.players) >= 5:
                return False, 'Game is full (max 5 players)'
            self.players.append(Player(name))
            self.sid_map[sid] = name
            snap = self._snapshot()
        self._emit(snap)
        return True, ''

    def reconnect(self, sid: str, name: str) -> bool:
        """Re-associate a socket with an existing player (page refresh)."""
        with self._lock:
            player = self._find(name)
            if player is None:
                return False
            # Remove any old SID for this name
            old_sids = [k for k, v in self.sid_map.items() if v == name]
            for k in old_sids:
                del self.sid_map[k]
            self.sid_map[sid] = name
            snap = self._snapshot()
        self._emit(snap)
        return True

    def disconnect(self, sid: str):
        with self._lock:
            self.sid_map.pop(sid, None)
            snap = self._snapshot()
        self._emit(snap)

    def leave_lobby(self, sid: str) -> bool:
        """Remove the calling player from the lobby."""
        with self._lock:
            if self.phase != Phase.LOBBY:
                return False
            name = self.sid_map.get(sid)
            if not name:
                return False
            self.players = [p for p in self.players if p.name != name]
            del self.sid_map[sid]
            snap = self._snapshot()
        self._emit(snap)
        self.sio.emit('left_lobby', {}, to=sid)
        return True

    def reset_to_lobby(self, sid: str) -> bool:
        """End the current game and return everyone to the lobby with reset chips."""
        with self._lock:
            if sid not in self.sid_map:
                return False
            # Stop any running auction timer
            self._timer_active = False
            # Reset all players back to 100 chips, clear dice
            for p in self.players:
                p.chips = 100
                p.dice = []
            # Reset all game state, keep players and connections
            self.pot = Pot()
            self.phase = Phase.LOBBY
            self.round_num = 0
            self.total_rounds = 0
            self.first_idx = 0
            self.four_dice_mode = False
            self.history = []
            self.ready_set = set()
            self.round_auction_num = 0
            self.auction_queue = []
            self.auctioner = None
            self.auctioned_die = None
            self.bid = 0
            self.bid_leader = None
            self.auction_deadline = 0.0
            self.exchange_winner = None
            self.payout_data = []
            snap = self._snapshot()
        self._emit(snap)
        return True

    # ── Game flow ─────────────────────────────────────────────────────────────

    def start_game(self, sid: str, total_rounds: int) -> tuple[bool, str]:
        with self._lock:
            if self.phase != Phase.LOBBY:
                return False, 'Game already started'
            if sid not in self.sid_map:
                return False, 'You are not registered'
            if len(self.players) < 3:
                return False, 'Need at least 3 players to start'
            self.total_rounds = max(0, int(total_rounds))
            self._begin_round()
            snap = self._snapshot()
        self._emit(snap)
        return True, ''

    def toggle_four_dice_mode(self, sid: str) -> bool:
        with self._lock:
            if self.phase != Phase.LOBBY or sid not in self.sid_map:
                return False
            self.four_dice_mode = not self.four_dice_mode
            snap = self._snapshot()
        self._emit(snap)
        return True

    def mark_ready(self, sid: str) -> bool:
        snap = None
        with self._lock:
            if self.phase != Phase.ROLLING:
                return False
            name = self.sid_map.get(sid)
            if not name:
                return False
            self.ready_set.add(name)
            if len(self.ready_set) >= len(self.players):
                self._begin_auction_phase()
            snap = self._snapshot()
        self._emit(snap)
        return True

    def choose_auction_die(self, sid: str, die_index: int) -> tuple[bool, str]:
        snap = None
        with self._lock:
            if self.phase != Phase.AUCTION_CHOOSE:
                return False, 'Not in auction-choose phase'
            player = self._player_for(sid)
            if player is None or player is not self.auctioner:
                return False, 'Not your turn to auction'
            if not (0 <= die_index < len(player.dice)):
                return False, 'Invalid die index'
            self.auctioned_die = player.give_die(die_index)
            self.phase = Phase.AUCTION_LIVE
            self.auction_deadline = time.time() + AUCTION_COUNTDOWN
            self._timer_active = True
            snap = self._snapshot()
        self._emit(snap)
        self.sio.start_background_task(self._run_timer)
        return True, ''

    def place_bid(self, sid: str, amount) -> tuple[bool, str]:
        snap = None
        with self._lock:
            if self.phase != Phase.AUCTION_LIVE:
                return False, 'No active auction'
            player = self._player_for(sid)
            if player is None:
                return False, 'You are not in this game'
            if player is self.auctioner:
                return False, 'Cannot bid on your own die'
            if player is self.bid_leader:
                return False, 'You are already the highest bidder'
            # Coerce and validate
            try:
                amount = int(amount)
            except (TypeError, ValueError):
                return False, 'Bid must be a positive integer'
            if amount < 1:
                return False, 'Bid must be at least 1'
            if amount <= self.bid:
                return False, f'Bid must be higher than the current bid of {self.bid}'
            if not player.can_afford(amount):
                return False, f'You cannot afford {amount} (you have {player.chips})'
            self.bid = amount
            self.bid_leader = player
            self.auction_deadline = time.time() + AUCTION_COUNTDOWN
            snap = self._snapshot()
        self._emit(snap)
        return True, ''

    def choose_exchange_die(self, sid: str, die_index: int) -> tuple[bool, str]:
        snap = None
        with self._lock:
            if self.phase != Phase.EXCHANGE:
                return False, 'Not in exchange phase'
            player = self._player_for(sid)
            if player is None or player is not self.exchange_winner:
                return False, 'Not your turn to exchange'
            if not (0 <= die_index < len(player.dice)):
                return False, 'Invalid die index'

            given_die = player.give_die(die_index)

            # Execute the exchange
            self.exchange_winner.pay(self.bid)
            self.auctioner.receive(self.bid)
            self.exchange_winner.take_die(self.auctioned_die)

            # Both dice become public
            self.auctioned_die.revealed = True
            given_die.revealed = True
            self.auctioner.take_die(given_die)

            self.round_auction_num += 1
            self.history.append({
                'type': 'exchange',
                'round': self.round_num,
                'auction': self.round_auction_num,
                'winner': self.exchange_winner.name,
                'auctioner': self.auctioner.name,
                'bid': self.bid,
                'winner_got': self.auctioned_die.value,
                'auctioner_got': given_die.value,
            })

            self.auctioned_die = None
            self.exchange_winner = None
            self._advance_auction()
            snap = self._snapshot()
        self._emit(snap)
        return True, ''

    def next_round(self, sid: str) -> bool:
        snap = None
        with self._lock:
            if self.phase != Phase.PAYOUT:
                return False
            if sid not in self.sid_map:
                return False
            done = (self.total_rounds > 0 and self.round_num >= self.total_rounds)
            if done or len(self.players) < 2:
                self.phase = Phase.GAME_OVER
            else:
                self.first_idx = (self.first_idx + 1) % len(self.players)
                self._begin_round()
            snap = self._snapshot()
        self._emit(snap)
        return True

    def get_state_for(self, sid: str) -> dict:
        """Called on connect to send current state to a single socket."""
        with self._lock:
            return self._snapshot()

    # ── Internal state transitions (must be called under lock) ───────────────

    def _begin_round(self):
        self.round_num += 1
        self.pot = Pot()
        for p in self.players:
            ante = min(10, p.chips)
            p.pay(ante)
            self.pot.collect(ante)
        dice_count = 4 if self.four_dice_mode else 3
        for p in self.players:
            p.dice = [Die() for _ in range(dice_count)]
            for d in p.dice:
                d.roll()
        self.ready_set = set()
        self.round_auction_num = 0
        self.payout_data = []
        self.phase = Phase.ROLLING

    def _begin_auction_phase(self):
        n = len(self.players)
        forward = [self.players[(self.first_idx + i) % n] for i in range(n)]
        if self.four_dice_mode:
            # Snake: forward then reverse — last player auctions twice in a row
            self.auction_queue = forward + list(reversed(forward))
        else:
            self.auction_queue = forward
        self._next_auctioner()

    def _next_auctioner(self):
        if not self.auction_queue:
            self._do_payout()
            return
        self.auctioner = self.auction_queue.pop(0)
        self.auctioned_die = None
        self.bid = 0
        self.bid_leader = None
        self.phase = Phase.AUCTION_CHOOSE

    def _advance_auction(self):
        self._next_auctioner()

    def _do_payout(self):
        for p in self.players:
            for d in p.dice:
                d.revealed = True

        shares = calculate_shares(self.players, four_dice_mode=self.four_dice_mode)
        totals = {p: p.hand_total() for p in self.players}
        max_total = max(totals.values()) if totals else 0
        min_total = min(totals.values()) if totals else 0

        awarded = distribute_pot(self.pot, shares)

        self.payout_data = [
            {
                'name': p.name,
                'dice': [d.value for d in p.dice],
                'total': totals[p],
                'shares': round(shares.get(p, 0), 2),
                'chips_won': awarded.get(p, 0),
                'chips_now': p.chips,
                'is_highest': totals[p] == max_total,
                'is_lowest': totals[p] == min_total,
                'three_of_a_kind': p.has_three_of_a_kind() if not self.four_dice_mode else False,
                'four_of_a_kind': p.has_four_of_a_kind() if self.four_dice_mode else False,
            }
            for p in self.players
        ]

        summary = ', '.join(
            f'{r["name"]} +{r["chips_won"]}'
            for r in self.payout_data if r['chips_won'] > 0
        )
        self.history.append(f'Round {self.round_num} payout: {summary}')

        # Eliminate broke players
        self.players = [p for p in self.players if p.chips > 0]
        self.phase = Phase.PAYOUT

    # ── Auction countdown (background task) ───────────────────────────────────

    def _run_timer(self):
        while True:
            time.sleep(0.1)
            snap = None
            tick = None
            with self._lock:
                if not self._timer_active or self.phase != Phase.AUCTION_LIVE:
                    self._timer_active = False
                    break
                remaining = self.auction_deadline - time.time()
                if remaining <= 0:
                    self._timer_active = False
                    if self.bid_leader is None:
                        self.round_auction_num += 1
                        self.history.append({
                            'type': 'no_bid',
                            'round': self.round_num,
                            'auction': self.round_auction_num,
                            'auctioner': self.auctioner.name,
                            'die': self.auctioned_die.value,
                        })
                        self.auctioner.take_die(self.auctioned_die)
                        self.auctioned_die = None
                        self._advance_auction()
                    else:
                        self.exchange_winner = self.bid_leader
                        self.phase = Phase.EXCHANGE
                    snap = self._snapshot()
                else:
                    tick = {
                        'remaining': round(remaining, 1),
                        'bid': self.bid,
                        'leader': self.bid_leader.name if self.bid_leader else None,
                    }
            if snap:
                self._emit(snap)
                break
            elif tick:
                self.sio.emit('auction_tick', tick)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _player_for(self, sid: str) -> Optional[Player]:
        name = self.sid_map.get(sid)
        return self._find(name) if name else None

    def _find(self, name: Optional[str]) -> Optional[Player]:
        if name is None:
            return None
        return next((p for p in self.players if p.name == name), None)

    def _snapshot(self) -> dict:
        """Full state snapshot. Must be called under lock."""
        priv = {
            p.name: [{'value': d.value, 'revealed': d.revealed} for d in p.dice]
            for p in self.players
        }
        pub = {
            'phase': self.phase,
            'four_dice_mode': self.four_dice_mode,
            'round_num': self.round_num,
            'total_rounds': self.total_rounds,
            'pot': self.pot.chips,
            'players': [
                {
                    'name': p.name,
                    'chips': p.chips,
                    'dice_count': len(p.dice),
                    'revealed_dice': {
                        str(i): d.value
                        for i, d in enumerate(p.dice) if d.revealed
                    },
                    'connected': any(v == p.name for v in self.sid_map.values()),
                }
                for p in self.players
            ],
            'history': self.history[-40:],
            'ready_players': list(self.ready_set),
            'auctioner': self.auctioner.name if self.auctioner else None,
            'auctioned_die': self.auctioned_die.value if self.auctioned_die else None,
            'current_bid': self.bid,
            'bid_leader': self.bid_leader.name if self.bid_leader else None,
            'exchange_winner': self.exchange_winner.name if self.exchange_winner else None,
            'countdown': AUCTION_COUNTDOWN,
            'payout_data': self.payout_data,
            'auction_sub_round': (1 if self.round_auction_num < len(self.players) else 2)
                                  if self.four_dice_mode else 1,
        }
        return {'pub': pub, 'priv': priv, 'sids': dict(self.sid_map)}

    def _emit(self, snap: dict):
        """Emit public state to all and private dice to each connected player."""
        self.sio.emit('public_state', snap['pub'])
        for sid, name in snap['sids'].items():
            dice = snap['priv'].get(name, [])
            self.sio.emit('private_dice', {'name': name, 'dice': dice}, to=sid)
