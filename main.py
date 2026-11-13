import os
import sys

# Put the SDK shim from vendor/ on sys.path, then import it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
MAX_CLOSES = 432
SMA_WINDOW = 400
BUY_DIP_BPS_THRESHOLD = 97  # close * 100 < sma * 97  <=>  3.0% below SMA400
SELL_WIN_BPS = 250
SELL_LOSS_BPS = -120
MAX_BARS_HELD = 720
MAX_SLIPPAGE_BPS = 200

_closes = []
_buy_seq = None


def on_batch(state, batch):
    global _buy_seq

    # Collect the CBBTC closes from this batch.
    for bar in batch["bars"]:
        if bar.get("symbol") == SYMBOL:
            _closes.append(int(bar["c"]))
    if len(_closes) > MAX_CLOSES:
        del _closes[:-MAX_CLOSES]

    # Not enough history yet.
    if len(_closes) < SMA_WINDOW:
        return []

    latest_close = state.close(SYMBOL)
    if latest_close is None:
        return []

    held = state.positions.get(SYMBOL)

    if held is not None:
        # Holding: check the exit conditions.
        value = state.value(SYMBOL, held.qty)
        cost = held.cost
        if cost > 0:
            ret_bps = (value - cost) * 10000 // cost
        else:
            ret_bps = 0
        bars_held = state.seq - (_buy_seq if _buy_seq is not None else state.seq)
        if ret_bps >= SELL_WIN_BPS or ret_bps <= SELL_LOSS_BPS or bars_held >= MAX_BARS_HELD:
            return [
                {
                    "side": "sell",
                    "symbol": SYMBOL,
                    "qty": held.qty,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            ]
        return []

    # Flat: buy the dip.
    sma = sum(_closes[-SMA_WINDOW:]) // SMA_WINDOW
    if latest_close * 100 < sma * BUY_DIP_BPS_THRESHOLD:
        _buy_seq = state.seq
        notional = min(state.cash, state.weight_room(SYMBOL))
        return [
            {
                "side": "buy",
                "symbol": SYMBOL,
                "notional_quote_units": notional,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }
        ]
    return []


makefun_bars.run(on_batch)
