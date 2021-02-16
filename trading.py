# our files
import utils
import portfolio
import black_scholes as bs

# general libraries
import time
import numpy as np
import pandas as pd
from optibook.synchronous_client import Exchange
from datetime import datetime
import logging
import datetime as dt
import market_functions as mkt


def options_trader(e):
    # clear outstanding orders
    # mkt.clear_outstanding(e)

    # get useful dtata (position per action, portfolio delta)
    mkt.update_metrics(e)
    # place orders through instruments
    trading_strategy = strategy(e)
    print(trading_strategy)
    if trading_strategy == 'market_making':
        market_maker(e)
        stock_hedging(e)
    elif trading_strategy == 'soft_hedging':
        market_maker_biased(e, 'soft_hedging')
        stock_hedging(e)
    elif trading_strategy == 'hard_hedging':
        market_maker_biased_hard(e, 'hard_hedging')

    # pause and start again
    time.sleep(mkt.IDLE)


def market_maker(e):
    for instrument_id in utils.instruments.keys():
        mkt.delete_outstanding(e, instrument_id)
        bid_volume, ask_volume = mkt.market_maker_positions(e, instrument_id)
        strike = utils.instruments[instrument_id][1]

        underlying_price = mkt._get_mid(e, 'BMW')
        fair_price = mkt.pricing_model(e, instrument_id, s=underlying_price, k=strike)
        [bid_price, ask_price] = mkt.bid_ask_market_making(e, fair_price, spread=mkt.SPREAD)

        quote(e, instrument_id, bid_price, bid_volume, 'bid',
              ask_price, ask_volume, 'ask', order_type='limit')
        time.sleep(0.04)


def market_maker_biased(e, strategy):
    for instrument_id in utils.instruments.keys():
        mkt.delete_outstanding(e, instrument_id)
        bias = mkt.bias(e, option_type=mkt._get_position(e, instrument_id))
        bid_volume, ask_volume = mkt.market_maker_positions(e, instrument_id)
        strike = utils.instruments[instrument_id][1]

        underlying_price = mkt._get_mid(e, 'BMW')
        fair_price = mkt.pricing_model(e, instrument_id, s=underlying_price, k=strike)
        [bid_price, ask_price] = mkt.bid_ask_market_making(e, fair_price, spread=mkt.SPREAD, bias=bias)

        quote(e, instrument_id, bid_price, bid_volume, 'bid',
              ask_price, ask_volume, 'ask', order_type='limit')
        time.sleep(0.04)


def market_maker_biased_hard(e, strategy):
    for instrument_id in utils.instruments.keys():
        mkt.delete_outstanding(e, instrument_id)
        bid_volume, ask_volume = mkt.market_maker_positions_biased(e, instrument_id,
                                                                   option_type=mkt._get_position(e, instrument_id))
        strike = utils.instruments[instrument_id][1]

        underlying_price = mkt._get_mid(e, 'BMW')

        fair_price = mkt.pricing_model(e, instrument_id, s=underlying_price, k=strike)

        [bid_price, ask_price] = mkt.bid_ask_market_making(e, fair_price, bias=None)

        quote(e, instrument_id, bid_price, bid_volume, 'bid',
              ask_price, ask_volume, 'ask', order_type='limit')
        time.sleep(0.04)


def strategy(e):
    mkt.update_greeks(e)
    position = mkt._get_position(e, 'BMW')

    if abs(position) > mkt.UPPER_POSITION_THRESH:
        if abs(portfolio.greeks['delta']) < mkt.UPPER_DELTA_THRESH:
            return 'soft_hedging'
        return 'hard_hedging'
    return 'market_making'


def stock_hedging(e):
    """Changed the price increment mechanism"""
    mkt.update_greeks(e)
    volume = mkt.hedging_volume(position=e.get_positions()['BMW'], delta=portfolio.greeks['delta'])
    while volume != 0 and abs(portfolio.greeks['delta']) > mkt.LOWER_DELTA_THRESH:  # as close to zero as possible

        execution = False
        bid_price, ask_price = mkt.bid_ask(e, 'BMW', mkt._get_mid(e, 'BMW'), spread=mkt.SPREAD, strategy='hedge')
        hedge_side = 'bid'
        price = bid_price
        if portfolio.greeks['delta'] > 0:
            hedge_side = 'ask'  # sell
            price = ask_price

        if price is not None:
            order_id = insert_order_(e, 'BMW',
                                     price=price,  # new_aggressive price
                                     volume=volume,
                                     side=hedge_side
                                     , order_type='ioc')

            if order_id is not None:
                execution = mkt._verify_order(e, order_id, 'BMW')
                if execution == False:
                    ##print(order_id)
                    e.delete_order('BMW', order_id)

        position = e.get_positions()['BMW']
        mkt.update_greeks(e)
        volume = mkt.hedging_volume(position=position, delta=portfolio.greeks['delta'])


def quote(e, instrument_id, price_A, volume_A, side_A, price_B, volume_B, side_B, order_type='limit'):
    if None not in [price_A, volume_A, side_A]:
        order_A_id = insert_order_(e, instrument_id, price_A, volume_A, side_A, order_type)
    if None not in [price_B, volume_B, side_B]:
        order_B_id = insert_order_(e, instrument_id, price_B, volume_B, side_B, order_type)


def insert_order_(e, instrument_id, price, volume, side, order_type='limit'):
    # print('inserting order for', instrument_id, price, volume, side, order_type)
    order_id = None
    if volume != 0 and price != 0:
        # print('inserting order for', instrument_id, price, volume, side, order_type)
        order_id = e.insert_order(instrument_id,
                                  price=price,  # new_aggressive price
                                  volume=volume,
                                  side=side
                                  , order_type=order_type)
        # print('market proposes', instrument_id, mkt.best_order(e, instrument_id, side)['price'],
        # mkt.best_order(e, instrument_id, side)['volume'], side, order_type)
    return order_id
