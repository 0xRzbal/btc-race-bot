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
        if ret_bps >= TARGET_BPS or ret_bps <= -STOP_BPS or held_bars >= MAX_HOLD:
            buy_seq = None
            return [{
                "side": "sell",
                "symbol": SYM,
                "qty": held.qty,
                "max_slippage_bps": 200,
            }]
        return []
    sma = _sma()
    if sma is None or sma <= 0:
        return []
    last = state.close(SYM)
    if last is None:
        return []
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


makefun_bars.run(on_batch)
