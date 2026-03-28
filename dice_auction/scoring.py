from .models import Player, Pot


def calculate_shares(players: list[Player]) -> dict[Player, float]:
    """
    Returns fractional shares per player.
    - Highest total: 1 share split among tied players.
    - Lowest total: 1 share split among tied players.
    - Each 3-of-a-kind: 1 full share each (no split).
    """
    shares: dict[Player, float] = {p: 0.0 for p in players}

    totals = {p: p.hand_total() for p in players}

    # Highest total
    max_total = max(totals.values())
    high_winners = [p for p in players if totals[p] == max_total]
    for p in high_winners:
        shares[p] += 1.0 / len(high_winners)

    # Lowest total
    min_total = min(totals.values())
    low_winners = [p for p in players if totals[p] == min_total]
    for p in low_winners:
        shares[p] += 1.0 / len(low_winners)

    # 3-of-a-kind
    for p in players:
        if p.has_three_of_a_kind():
            shares[p] += 1.0

    return shares


def distribute_pot(pot: Pot, shares: dict[Player, float]) -> dict[Player, int]:
    """
    Distributes pot chips proportionally by shares.
    Remainders go to the player with the largest fractional part.
    Returns dict of chips awarded to each player.
    """
    total_shares = sum(shares.values())
    pot_amount = pot.take_all()
    awarded: dict[Player, int] = {p: 0 for p in shares}

    if total_shares == 0 or pot_amount == 0:
        # No shares or empty pot — return pot to players equally (edge case)
        if shares:
            per_player = pot_amount // len(shares)
            remainder = pot_amount % len(shares)
            for p in shares:
                awarded[p] = per_player
            # Give remainder to first player
            if remainder and shares:
                first = next(iter(shares))
                awarded[first] += remainder
        return awarded

    raw: dict[Player, float] = {
        p: (s / total_shares) * pot_amount for p, s in shares.items()
    }
    floored: dict[Player, int] = {p: int(v) for p, v in raw.items()}
    remainder = pot_amount - sum(floored.values())

    # Distribute remainder chips to players with highest fractional parts
    fractions = sorted(shares.keys(), key=lambda p: raw[p] - floored[p], reverse=True)
    for i, p in enumerate(fractions):
        if i < remainder:
            floored[p] += 1

    for p, amount in floored.items():
        p.receive(amount)
        awarded[p] = amount

    return awarded


def scoring_breakdown(players: list[Player], shares: dict[Player, float]) -> str:
    """Returns a human-readable scoring summary."""
    totals = {p: p.hand_total() for p in players}
    max_total = max(totals.values())
    min_total = min(totals.values())

    lines = []
    for p in players:
        dice_str = "  ".join(str(d.value) for d in p.dice)
        total = totals[p]
        reasons = []
        if total == max_total:
            reasons.append("highest total")
        if total == min_total:
            reasons.append("lowest total")
        if p.has_three_of_a_kind():
            reasons.append("three-of-a-kind")
        share_str = f"{shares[p]:.2f}" if shares[p] != int(shares[p]) else str(int(shares[p]))
        reason_str = ", ".join(reasons) if reasons else "no shares"
        lines.append(f"  {p.name:15s} [{dice_str}] = {total:2d}   shares: {share_str}  ({reason_str})")
    return "\n".join(lines)
