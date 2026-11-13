"""Mean-reversion dip-buy strategy.

Strategy: compute the simple moving average of closes over the last 400 bars
(SMA400). Enter a long position when the latest close is at or below 3% under
the SMA400 (a dip). Exit when the position has returned +250bps, dropped to
-120bps, or has been held for 720 bars.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYM = "CBBTC"
SPAN = 400
DIP_PCT = 3.0
TARGET_BPS = 250
STOP_BPS = 120
MAX_HOLD = 720

closes = []
buy_seq = None


def _sma():
    if len(closes) < SPAN:
        return None
    return sum(closes[-SPAN:]) // SPAN


def on_batch(state, batch):
    global buy_seq

    def _should_exit(ret_bps, held_bars):
        # Exit bands: take profit at +250bps, stop loss at -120bps, or time out.
        if ret_bps >= TARGET_BPS or ret_bps <= -STOP_BPS or held_bars >= MAX_HOLD:
            return {
                "side": "sell",
                "symbol": SYM,
                "qty": held.qty,
                "max_slippage_bps": 200,
            }
        return None

    bars = batch.get("bars", [])
    for bar in bars:
        if bar.get("symbol") == SYM:
            closes.append(int(bar["c"]))
            if len(closes) > SPAN + 32:
                del closes[: (len(closes) - (SPAN + 32))]
    held = state.positions.get(SYM)
    if held is not None:
        value = state.value(SYM, held.qty)
        cost = held.cost
        if cost > 0:
            ret_bps = (value - cost) * 10000 // cost
        else:
            ret_bps = 0
        held_bars = (state.seq - buy_seq) if buy_seq is not None else 0
        sell_order = _should_exit(ret_bps, held_bars)
        if sell_order is not None:
            buy_seq = None
            return [sell_order]
        return []
    sma = _sma()
    if sma is None or sma <= 0:
        return []
    last = state.close(SYM)
    if last is None:
        return []
    # Enter on a dip: buy when the close is at least 3% below SMA400.
    if last * 100 >= sma * (100 - DIP_PCT):
        return []
    notional = min(state.cash, state.weight_room(SYM))
    if notional <= 0:
        return []
    buy_seq = state.seq
    return [{
        "side": "buy",
        "symbol": SYM,
        "notional_quote_units": notional,
        "max_slippage_bps": 200,
    }]


# Start the replay loop, feeding batches into on_batch.
makefun_bars.run(on_batch)
