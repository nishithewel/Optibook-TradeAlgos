# fucntion to model the spread
import time
import numpy as np
import pandas as pd
from optibook.synchronous_client import Exchange
from datetime import datetime
import logging
import datetime as dt

import black_scholes as bs
import utils
import utils
import market_functions as mf
import pricing

# Global vars
R = 0
SIGMA = 3.0
DELTA_THRESH = 50
IDLE = 0.04
SPREAD = 0.2


# compare fair value to market value -> everything looks arbitrageable

def _get_mid(e, instrument_id):
    """Returns mid price of instrument"""

    best_bid = best_order(e=e, instrument_id=instrument_id, side='bid')
    best_ask = best_order(e=e, instrument_id=instrument_id, side='ask')

    if best_ask is not None and best_bid is not None:
        mid_price = (best_bid['price'] + best_ask['price']) / 2

    else:
        mid_price = None

    return mid_price


def best_order(e, instrument_id, side):
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


def get_min_volume(instrument_1, instrument_2=None):
    if instrument_2 is not None:
        return min([instrument_1['volume'], instrument_2['volume']])
    return instrument_1['volume']


def _verify_order(e, order_id, instrument_id):
    time.sleep(0.01)
    trade_hist = e.get_trade_history(instrument_id)

    trade_ids = [trade.order_id for trade in trade_hist]

    if order_id in trade_ids:
        ##print('executed')

        return True
    else:

        return False


def _get_position(e, instrument_id):
    positions = e.get_positions()
    pos = positions[instrument_id]

    return int(pos)


def pricing_model(e, instrument_id, mid_price, strike):
    k = strike
    s = mid_price
    T = float(
        bs.calculate_time_to_date(datetime.strptime('2021-03-01 12:00:00', '%Y-%m-%d %H:%M:%S'), dt.datetime.now()))
    if mid_price is not None:
        assert T
        assert k
        assert s
        if _option_type(instrument_id) == 'put':
            value = bs.put_value(s, k, T, R, SIGMA)
            # print(instrument_id, 'value @', value, 'mkt @', _get_mid(e, instrument_id))
            return value

        if _option_type(instrument_id) == 'call':
            value = bs.call_value(s, k, T, R, SIGMA)
            # print(instrument_id, 'value @', value, 'mkt @', _get_mid(e, instrument_id))
            return value

    else:
        return None


def _nearest_tick(price, side):
    """Calculate price to nearest tick"""
    if side == 'bid':
        return (np.floor(price * 10)) * 0.1
    if side == 'ask':
        return (np.ceil(price * 10)) * 0.1


def exploit_market(e, fair_price, instrument_id, current_volume):
    market_bid = round(best_order(e, instrument_id, 'bid')['price'], 1)
    market_ask = round(best_order(e, instrument_id, 'ask')['price'], 1)

    # current_volume = e.get_positions()[instrument_id]
    order_volume = 100

    if market_bid > fair_price and current_volume != -100:  # we sell
        if current_volume < 0:
            order_volume = 100 - abs(current_volume)
        e.insert_order(instrument_id,
                       price=market_bid,
                       volume=order_volume,
                       side='ask'
                       , order_type='ioc')
        print('arbitraged:', instrument_id, 'sold @', market_bid, 'fair price', fair_price)
    if market_ask < fair_price and current_volume != 100:  # we buy
        if current_volume > 0:
            order_volume = 100 - abs(current_volume)
        e.insert_order(instrument_id,
                       price=market_ask,
                       volume=order_volume,
                       side='bid'
                       , order_type='ioc')
        print('arbitraged:', instrument_id, 'bought @', market_ask, 'fair price', fair_price)


def bid_and_ask(e, instrument_id, fair_price, spread=SPREAD,
                strategy=False):  # start off by using a constant for the spread

    if fair_price is None:  # if no price align with market
        return None, None

    if strategy == 'hedge':
        # go breakve
        bid_price = best_order(e, instrument_id, 'ask')['price']
        ask_price = best_order(e, instrument_id, 'bid')['price']
        return bid_price, ask_price

    elif strategy == 'bid':
        # take bid as closer to mid price than ask
        bid_price = _nearest_tick(fair_price - spread / 2, 'bid')
        # take some margins on the ask
        ask_price = _nearest_tick(price=fair_price + spread, side='ask')
    elif strategy == 'ask':
        # ask closer to mid than bid
        bid_price = _nearest_tick(price=fair_price - spread, side='bid')
        ask_price = _nearest_tick(fair_price + spread / 2, 'ask')
    else:
        # margins on both ends
        bid_price = _nearest_tick(price=fair_price - spread / 2, side='bid')
        ask_price = _nearest_tick(price=fair_price + spread / 2, side='ask')

    return [bid_price.item(), ask_price.item()]


def get_volume(e, instrument_id):
    # verify how much we already own
    positions = e.get_positions()
    if instrument_id in positions:
        current_volume = abs(positions[instrument_id])
    if current_volume < 100:
        return min(100 - current_volume, 100)
    return 0


# Part B - Delta Hedge
def _option_type(instrument_id):
    """returns type of option"""
    if 'put' in instrument_id.lower():
        return 'put'

    if 'call' in instrument_id.lower():
        return 'call'
    else:
        # this should be the BMW stock
        return None


# 1 compute delta for position
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

    if _option_type(instrument_id) == 'call':
        delta = bs.call_delta(s, k, T, R, SIGMA)

    if _option_type(instrument_id) == 'put':
        delta = bs.put_delta(s, k, T, R, SIGMA)

    oustanding_deltas = delta * pos

    return oustanding_deltas


# 2 compute outstanding delta over whole book
def total_delta(e):
    t_delta = 0

    for instrument_id in utils.instruments.keys():
        t_delta += position_delta(e, instrument_id)

    t_delta += _get_position(e, 'BMW')
    return round(t_delta)


def limit_order(position, delta):
    vol = 0
    if delta * position > 0:
        vol = min(abs(delta), 100 + abs(position))
    else:
        vol = min(100 - abs(position), abs(delta))
    return abs(vol)


def collapse_delta(e):
    """Changed the price increment mechanism"""
    delta = total_delta(e)
    # execution = False
    volume = limit_order(position=e.get_positions()['BMW'], delta=delta)
    t = 0

    while volume != 0 and abs(delta) > DELTA_THRESH and t < 10:  # as close to zero as possible
        position = e.get_positions()['BMW']
        volume = limit_order(position=position, delta=delta)
        execution = False
        mid_price = _get_mid(e, 'BMW')
        if mid_price is not None:
            bid_price, ask_price = bid_and_ask(e, 'BMW', mid_price, spread=SPREAD, strategy='hedge')

        hedge_side = 'bid'
        price = bid_price
        if delta > 0:
            hedge_side = 'ask'  # sell
            price = ask_price
        if price is not None and volume != 0:
            r_id = e.insert_order('BMW',
                                  price=price,  # new_aggressive price
                                  volume=volume,
                                  side=hedge_side
                                  , order_type='ioc')

            execution = _verify_order(e, r_id, 'BMW')
            if execution == False:
                result = e.delete_order('BMW', order_id=r_id)

        delta = total_delta(e, )

        time.sleep(IDLE)
        t += 1


def quote(e, instrument_id, bid, ask, order_type='limit', verify=False, volume=None):
    # buy
    if volume is None or volume == 0:
        volume = 100
        # sell
        order_1_id = e.insert_order(instrument_id,
                                    price=ask,
                                    volume=volume,
                                    side='ask'
                                    , order_type=order_type)

        # buy
        order_2_id = e.insert_order(instrument_id,
                                    price=bid,
                                    volume=volume,
                                    side='bid'
                                    , order_type=order_type)

        return [order_1_id, order_2_id]
    elif volume > 0:
        order_1_id = e.insert_order(instrument_id,
                                    price=ask,
                                    volume=100,
                                    side='ask'
                                    , order_type=order_type)

        order_2_id = e.insert_order(instrument_id,
                                    price=bid,
                                    volume=100 - abs(volume),
                                    side='bid'
                                    , order_type=order_type)

    elif volume < 0:
        order_1_id = e.insert_order(instrument_id,
                                    price=ask,
                                    volume=100 - abs(volume),
                                    side='ask'
                                    , order_type=order_type)

        order_2_id = e.insert_order(instrument_id,
                                    price=bid,
                                    volume=100,
                                    side='bid'
                                    , order_type=order_type)
    return [order_1_id, order_2_id]


def delete_outstanding(e, instrument_id):
    outstanding = e.get_outstanding_orders(instrument_id)
    if len(outstanding) != 0:
        for o in outstanding.values():
            e.delete_order(instrument_id, order_id=o.order_id)


def order_manager(e, instrument_id, bid_price, ask_price, fair_price, order_type='limit', verify=False):
    current_volume = e.get_positions()[instrument_id]

    if abs(current_volume) < 100:
        quote(e, instrument_id, bid_price, ask_price, order_type='limit', verify=verify, volume=current_volume)
        return None
    elif current_volume == -100:
        e.insert_order(instrument_id,
                       price=bid_price,
                       volume=100,
                       side='bid'
                       , order_type='limit')
        return None


    elif current_volume == 100:
        e.insert_order(instrument_id,
                       price=ask_price,
                       volume=100,
                       side='ask'
                       , order_type='limit')
        return None


def option_hedging(delta, instrument_id, stock_position):
    if abs(stock_position) == 100 and abs(delta) > 4 * DELTA_THRESH:
        if delta * stock_position > 0:
            # delta can be hedged with stocks, no need to change portfolio
            return 'False'
        # delta and position not aligned + we reached our stock hedge limit
        if delta > 0:
            # need to go short delta
            if _option_type(instrument_id) == 'call':
                return 'ask'  # place more aggressive asks // sell calls for cheaper

            return 'bid'  # buy puts for cheaper

        if _option_type(instrument_id) == 'put':
            return 'bid'  # place more aggressive buying orders
        return 'ask'
    return 'False'


def clear_outstanding(e):
    for instrument_id in utils.instruments.keys():
        outstanding = e.get_outstanding_orders(instrument_id)

        for o in outstanding.values():
            result = e.delete_order(instrument_id, order_id=o.order_id)


def options_trader(e):
    # A
    # A1 delete all outstanding orders
    # clear_outstanding(e)

    # A2 fair price and orders
    # A.2.a call options
    stock_position = _get_position(e, 'BMW')
    delta = total_delta(e)

    for instrument_id in utils.instruments.keys():
        delete_outstanding(e, instrument_id)
        strategy = option_hedging(delta, instrument_id, stock_position)
        strike = utils.instruments[instrument_id][1]
        mid_price = _get_mid(e, 'BMW')  # mid price of the underlying stock
        fair_price = pricing_model(e, instrument_id, mid_price, strike)

        [bid_price, ask_price] = bid_and_ask(e, instrument_id, fair_price, spread=SPREAD, strategy=strategy)
        order_manager(e, instrument_id, bid_price, ask_price, fair_price, order_type='limit', verify=False)
        collapse_delta(e)
        time.sleep(IDLE)
    # /!\ makes a HUUUUGE DIFFERENCE
    # /!\ sleep 1 => breakeven, >1 => positive pnl (what is sweet spot?)
    return None


def arbitrageur(e):
    # clear_outstanding(e)
    for instrument_id in utils.instruments.keys():
        delete_outstanding(e, instrument_id)
        volume = e.get_positions()[instrument_id]
        mid_price = _get_mid(e, 'BMW')
        strike = utils.instruments[instrument_id][1]
        fair_price = round(pricing_model(e, instrument_id, mid_price, strike), 1)
        exploit_market(e, fair_price, instrument_id, volume)
    collapse_delta(e)


def main():
    e = utils.connect()

    assert e.is_connected()
    while True:
        arbitrageur(e)
        options_trader(e)
        time.sleep(3)
        # arbitrageur(e)
    ###print('done')


main()
