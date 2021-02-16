# our files
import utils
import portfolio
import black_scholes as bs
import trading_functions as tf

# general libraries
import time
import numpy as np
import pandas as pd
from optibook.synchronous_client import Exchange
from datetime import datetime
import logging
import datetime as dt

R = 0
SIGMA = 3.0
LOWER_DELTA_THRESH = 10
UPPER_DELTA_THRESH = 99
UPPER_POSITION_THRESH = 99
IDLE = 2
SPREAD = 0.2


def hedging_volume(position, delta):
    vol = 0
    if delta * position > 0:
        vol = min(abs(delta), 100 + abs(position))
    else:
        vol = min(100 - abs(position), abs(delta))
    return abs(vol)


def _get_position(e, instrument_id):
    # get current position for given instrument
    # output: returns current position (int)

    positions = e.get_positions()
    pos = positions[instrument_id]
    if pos is None:
        pos = 0
    return int(pos)


def clear_all_outstanding(e):
    # clears all outstanding orders (not executed market orders)

    for instrument_id in utils.instruments.keys():
        outstanding = e.get_outstanding_orders(instrument_id)

        for o in outstanding.values():
            result = e.delete_order(instrument_id, order_id=o.order_id)


def delete_outstanding(e, instrument_id):
    time.sleep(0.04)
    outstanding = e.get_outstanding_orders(instrument_id)
    if len(outstanding) != 0:
        for o in outstanding.values():
            e.delete_order(instrument_id, order_id=o.order_id)


def update_greeks(e):
    # updates current delta metric in greeks dictionary
    portfolio.greeks['delta'] = total_delta(e)


def update_metrics(e):
    for instrument_id in portfolio.instruments.keys():
        portfolio.instruments[instrument_id][2] = _get_position(e, instrument_id)
    update_greeks(e)


def best_order(e, instrument_id, side):
    # look for best orders in market for instrument_id
    """ get best bid or ask"""
    book = e.get_last_price_book(instrument_id)
    prices, vols = [], []

    if side == 'ask':

        for t in book.asks:
            price = t.price
            prices.append(price)

            vol = t.volume
            vols.append(vol)

    if side == 'bid':

        for t in book.bids:
            price = t.price
            prices.append(price)

            vol = t.volume
            vols.append(vol)

    if len(prices) != 0:
        best_price = max(prices)
        volume = vols[np.argmax(prices)]
        best_order = dict(price=best_price,
                          volume=volume,
                          instrument_id=instrument_id,
                          side=side)

    else:
        best_order = None

    return best_order


def _get_mid(e, instrument_id):
    # using best bid/ask compute mid_price for instrument
    """Returns mid price of instrument"""

    best_bid = best_order(e=e, instrument_id=instrument_id, side='bid')
    best_ask = best_order(e=e, instrument_id=instrument_id, side='ask')

    if best_ask is not None and best_bid is not None:
        mid_price = (best_bid['price'] + best_ask['price']) / 2

    else:
        mid_price = None

    return mid_price


def _option_type(instrument_id):
    """returns type of option in the market"""
    return portfolio.instruments[instrument_id][0]


def _option_type_mkt(instrument_id):
    """returns type of option in the market"""
    if 'put' in instrument_id.lower():
        return 'put'

    if 'call' in instrument_id.lower():
        return 'call'
    else:
        return 'stock'


def position_delta(e, instrument_id):
    pos = _get_position(e, instrument_id)

    s = None
    while s is None:
        s = _get_mid(e, 'BMW')
        time.sleep(0.01)
    assert s is not None
    k = utils.instruments[instrument_id][1]

    T = float(
        bs.calculate_time_to_date(datetime.strptime('2021-03-01 12:00:00', '%Y-%m-%d %H:%M:%S'), dt.datetime.now()))

    if _option_type(instrument_id) == 'Call':
        delta = bs.call_delta(s, k, T, R, SIGMA)

    if _option_type(instrument_id) == 'Put':
        delta = bs.put_delta(s, k, T, R, SIGMA)

    oustanding_deltas = delta * pos

    return oustanding_deltas


def total_delta(e):
    t_delta = 0

    for instrument_id in portfolio.instruments.keys():
        t_delta += position_delta(e, instrument_id)

    t_delta += _get_position(e, 'BMW')
    return round(t_delta)


def _nearest_tick(price, side):
    """Calculate price to nearest tick"""
    if side == 'bid':
        return (np.floor(price * 10)) * 0.1
    if side == 'ask':
        return (np.ceil(price * 10)) * 0.1


def bid_ask(e, instrument_id, fair_price, spread=SPREAD,
            strategy=False):  # start off by using a constant for the spread

    if fair_price is None:  # if no price align with market
        return None, None

    if strategy == 'hedge':
        # go breakve
        bid_price = best_order(e, instrument_id, 'ask')['price']
        ask_price = best_order(e, instrument_id, 'bid')['price']
        return bid_price, ask_price

    else:
        # margins on both ends
        bid_price = _nearest_tick(price=fair_price - spread / 2, side='bid')
        ask_price = _nearest_tick(price=fair_price + spread / 2, side='ask')

    return [bid_price.item(), ask_price.item()]


def _verify_order(e, order_id, instrument_id):
    trade_hist = e.get_trade_history(instrument_id)

    trade_ids = [trade.order_id for trade in trade_hist]

    if order_id in trade_ids:

        return True
    else:

        return False


def pricing_model(e, instrument_id, s, k):
    T = float(
        bs.calculate_time_to_date(datetime.strptime('2021-03-01 12:00:00', '%Y-%m-%d %H:%M:%S'), dt.datetime.now()))
    if s is not None:
        if _option_type(instrument_id) == 'Put':
            value = bs.put_value(s, k, T, R, SIGMA)
            return value

        if _option_type(instrument_id) == 'Call':
            value = bs.call_value(s, k, T, R, SIGMA)
            return value

    else:
        return None


def market_maker_positions(e, instrument_id):
    current_volume = _get_position(e, instrument_id)

    if current_volume == 0:
        bid_volume = 100
        ask_volume = 100
    if current_volume > 0:
        bid_volume = 100 - abs(current_volume)
        ask_volume = 100
    if current_volume < 0:
        bid_volume = 100
        ask_volume = 100 - abs(current_volume)

    return bid_volume, ask_volume


def market_maker_positions_biased(e, instrument_id, option_type):
    current_volume = _get_position(e, instrument_id)

    bid_volume, ask_volume = 100, 100
    if current_volume > 0:
        bid_volume = 100 - abs(current_volume)
        ask_volume = 100
    elif current_volume < 0:
        bid_volume = 100
        ask_volume = 100 - abs(current_volume)

    if portfolio.greeks['delta'] > 0:
        if option_type == 'Put':
            bid_volume = 0
        if option_type == 'Call':
            ask_volume = 0

    if portfolio.greeks['delta'] < 0:
        if option_type == 'Put':
            ask_volume = 0
        if option_type == 'Call':
            bid_volume = 0
    return bid_volume, ask_volume


def bid_ask_market_making(e, fair_price, spread=SPREAD, bias=None):  # start off by using a constant for the spread

    if fair_price is None:  # if no price align with market
        return None, None

    bid_price = _nearest_tick(price=fair_price - spread / 2, side='bid')
    ask_price = _nearest_tick(price=fair_price + spread / 2, side='ask')

    if bias == 'ask':
        bid_price = _nearest_tick(price=fair_price - spread, side='bid')
    if bias == 'bid':
        ask_price = _nearest_tick(price=fair_price + spread, side='ask')

    return [bid_price.item(), ask_price.item()]


def bias(e, option_type):
    if portfolio.greeks['delta'] > 0:
        if option_type == 'Put':
            return 'ask'
        if option_type == 'Call':
            return 'bid'

    if portfolio.greeks['delta'] < 0:
        if option_type == 'Put':
            return 'bid'
        if option_type == 'Call':
            return 'ask'
