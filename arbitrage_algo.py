# fucntion to model the spread
import time
import numpy as np
import pandas as pd
from optibook.synchronous_client import Exchange
from datetime import datetime
import logging


def connect():
    logger = logging.getLogger('client')
    logger.setLevel('ERROR')

    print("Setup was successful.")

    e = Exchange()
    if not e.is_connected():
        e.connect()
        print('connected')
    else:
        print('already connected')

    return e


def best_order(instrument_id, side, e):
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


def is_arbitrage(price_1, side_1, instrument_1, price_2, side_2, instrument_2):
    if side_1 == 'ask' and side_2 == 'bid':
        if price_1 < price_2:
            print('arbitrage spotted: can buy', instrument_1, 'for ', round(price_1, 3), 'and sell', instrument_2,
                  'for', round(price_2, 3))
            return True
    if side_1 == 'bid' and side_2 == 'ask':
        if price_2 < price_1:
            print('arbitrage spotted: can sell', instrument_1, 'for ', round(price_1, 3), 'and buy', instrument_2,
                  'for', round(price_2, 3))
            return True
    return False


def check_position(e, instrument_id):
    positions = e.get_positions()
    pos = positions[instrument_id]

    return int(pos)


def get_volume(instrument_1, instrument_2=None):
    if instrument_2 is not None:
        return min([instrument_1['volume'], instrument_2['volume']])
    return instrument_1['volume']


def execute_order_beta(e, trade_book, volume, bet, order_type, verify=False, hedge=None):
    # principal bel
    bet_id = e.insert_order(bet['instrument_id'],
                            price=bet['price'],
                            volume=volume,
                            side=bet['side']
                            , order_type=order_type)
    print('order placed:', bet['instrument_id'], bet['side'], 'at', round(bet['price'], 3), 'quantity is', volume)
    # hedge
    if hedge is not None:
        hedge_id = e.insert_order(hedge['instrument_id'],
                                  price=hedge['price'],
                                  volume=volume,
                                  side=hedge['side']
                                  , order_type=order_type)
        print('order placed:', hedge['instrument_id'], hedge['side'], 'at', round(hedge['price'], 3), 'quantity is',
              volume)

    # verify if orders went through
    # trade_hist = e.get_trade_history(instrument_id)
    # trade_book = {}
    execution = False
    verify_hedge = False
    verify_bet = False

    if verify == True:
        # for i in range(100):
        while execution == False:

            if verify_bet == False:
                verify_bet = verify_order(e, trade_book, bet_id, bet)

            if verify_hedge == False:
                verify_hedge = verify_order(e, trade_book, hedge_id, hedge)

            if all([verify_bet, verify_hedge]) == True:
                execution = True
                break

                # else:


def trade_algo_beta(e, trade_book):
    time_lim = 0.04  # floor to prevent hitting request limit

    # vol = 20

    A_ask = best_order('PHILIPS_A', 'ask', e)
    B_bid = best_order('PHILIPS_B', 'bid', e)

    if A_ask is not None and B_bid is not None:
        # if (A_ask['price'] < B_bid['price']):
        if is_arbitrage(A_ask['price'], 'ask', B_bid['price'], 'bid'):
            vol = get_volume(A_ask, B_bid)
            execute_order_beta(e, trade_book, volume=vol, bet=B_bid, hedge=A_ask, order_type='limit')

            A_close, B_close = False, False
            while A_close == False and B_close == False:
                # if New_b_ask < B_bid
                new_b_ask = best_order('PHILIPS_B', 'ask', e)
                new_a_bid = best_order('PHILIPS_A', 'bid', e)

                if new_a_bid is not None and new_b_ask is not None:
                    if (new_b_ask['price'] < B_bid['price']) and new_b_ask['volume'] >= 10:
                        # buy B
                        place_order(e, trade_book, 'PHILIPS_B',
                                    price=new_b_ask['price'],
                                    volume=vol,
                                    side='bid', order_type='limit')
                        print('buy b,', vol)

                        # sell A
                        place_order(e, trade_book, 'PHILIPS_A',

                                    price=new_a_bid['price'],
                                    volume=vol,

                                    side='ask', order_type='limit')

                        print('sell A,', vol)
                        print('posn closed')
                        pos_close = True

                    if (new_b_ask['price'] < B_bid['price']) and new_b_ask['volume'] >= 10:
                        # buy B
                        place_order(e, trade_book, 'PHILIPS_B',
                                    price=new_b_ask['price'],
                                    volume=vol,
                                    side='bid', order_type='limit')
                        print('buy b,', vol)

                        # sell A
                        place_order(e, trade_book, 'PHILIPS_A',

                                    price=new_a_bid['price'],
                                    volume=vol,

                                    side='ask', order_type='limit')

                        print('sell A,', vol)
                        print('posn closed')
                        pos_close = True

                    time.sleep(time_lim)

    A_bid = best_order('PHILIPS_A', 'bid', e)
    B_ask = best_order('PHILIPS_B', 'ask', e)
    if A_bid is not None and B_ask is not None:
        if is_arbitrage(A_bid['price'], 'bid', B_ask['price'], 'ask'):
            vol = get_volume(B_ask, A_bid)

            execute_order_beta(e, trade_book, volume=vol, bet=B_ask, hedge=A_bid, order_type='limit')

            pos_close = False
            while pos_close == False:
                # if New_b_ask < B_bid
                new_b_bid = best_order('PHILIPS_B', 'bid', e)
                new_a_ask = best_order('PHILIPS_A', 'ask', e)

                # assert new_a_bid == True
                # assert new_b_ask == True
                if new_b_bid is not None and new_a_ask is not None:

                    if (new_b_bid['price'] < B_ask['price']) \
                            and new_b_bid['volume'] >= 10:
                        place_order(e, trade_book, 'PHILIPS_B',
                                    price=new_b_bid['price'],
                                    volume=vol,
                                    side='ask', order_type='limit')
                        print('sell b,', vol)

                        place_order(e, trade_book,
                                    'PHILIPS_A',
                                    price=new_a_ask['price'],
                                    volume=vol,
                                    side='bid', order_type='limit')

                        print('buy A,', vol)
                        pos_close = True
                        print('posn closed')
                    time.sleep(time_lim)
        # sell A


    else:
        # print('nothing found')
        pass


def arbitrageur(e, trade_book):
    A_ask = best_order('PHILIPS_A', 'ask', e)
    B_bid = best_order('PHILIPS_B', 'bid', e)

    if A_ask is not None and B_bid is not None:
        if is_arbitrage(A_ask['price'], 'ask', 'Philips_A', B_bid['price'], 'bid', 'Philips_B'):
            vol = get_volume(A_ask, B_bid)
            execute_order_beta(e, trade_book, volume=vol, bet=B_bid, hedge=A_ask, order_type='limit')
            spread_1 = (-A_ask['price'] + B_bid['price']) * vol

            A_close, B_close = False, False

            while A_close == False and B_close == False:

                A_bid = best_order('PHILIPS_A', 'bid', e)
                B_ask = best_order('PHILIPS_B', 'ask', e)
                if B_ask is not None and A_bid is not None:

                    spread_2 = (-B_ask['price'] + A_bid['price']) * vol

                    if A_close == False and B_close == False and spread_1 + spread_2 > 0:
                        execute_order_beta(e, trade_book, volume=vol, bet=B_ask, order_type='limit', hedge=A_bid)
                        A_close, B_close = True, True

                    if B_close == False:
                        if is_arbitrage(B_ask['price'], 'ask', 'Philips_B', B_bid['price'], 'bid', 'Philips_B'):
                            # vol = get_volume(B_ask)
                            execute_order_beta(e, trade_book, volume=vol, bet=B_ask, order_type='limit')
                            B_close = True

                    if A_close == False:

                        if is_arbitrage(A_bid['price'], 'bid', 'Philips_A', A_ask['price'], 'ask', 'Philips_A'):
                            # vol = get_volume(A_bid)
                            execute_order_beta(e, trade_book, volume=vol, bet=A_bid, order_type='limit')
                            A_close = True

    A_bid = best_order('PHILIPS_A', 'bid', e)
    B_ask = best_order('PHILIPS_B', 'ask', e)

    if A_bid is not None and B_ask is not None:
        if is_arbitrage(A_bid['price'], 'bid', 'Philips_A', B_ask['price'], 'ask', 'Philips_B'):
            # arbitrage found - execute
            vol = get_volume(B_ask, A_bid)
            execute_order_beta(e, trade_book, volume=vol, bet=B_ask, hedge=A_bid, order_type='limit')
            spread_1 = (-B_ask['price'] + A_bid['price']) * vol

            # reverse position for profit
            A_close, B_close = False, False
            while A_close == False and B_close == False:

                B_bid = best_order('PHILIPS_B', 'bid', e)
                A_ask = best_order('PHILIPS_A', 'ask', e)

                if A_ask is not None and B_bid is not None:
                    spread_2 = (-A_ask['price'] + B_bid['price']) * vol

                    if A_close == False and B_close == False and spread_1 + spread_2 > 0:
                        execute_order_beta(e, trade_book, volume=vol, bet=B_bid, order_type='limit', hedge=A_ask)
                        A_close, B_close = True, True

                    if B_close == False:
                        if is_arbitrage(B_bid['price'], 'bid', 'Philips_B', B_ask['price'], 'ask', 'Philips_B'):
                            # can buy back B at a profit
                            # vol = get_volume(B_bid)
                            execute_order_beta(e, trade_book, volume=vol, bet=B_bid, order_type='limit')
                            B_close = True

                    if A_close == False:
                        if is_arbitrage(A_ask['price'], 'ask', 'Philips_A', A_bid['price'], 'bid', 'Philips_A'):
                            # can now sell A at a profit
                            # vol = get_volume(A_ask)
                            execute_order_beta(e, trade_book, volume=vol, bet=A_ask, order_type='limit')
                            A_close = True


def is_empty_order_book(e, instrument_id):
    if len(e.get_outstanding_orders(instrument_id)) > 0:
        return False
    return True


def verify_order(e, trade_book, order_id, instrument):
    trade_hist = e.get_trade_history(instrument['instrument_id'])

    trade_ids = [trade.order_id for trade in trade_hist]

    if order_id in trade_ids:
        # for trade in trade_hist:
        # if order_id == trade.order_id:

        # transaction = dict(trade_id = order_id,
        # trade_price)
        execution = True
        # print('executed')
        # trade_logger(trade_book,instrument)

        return True
    else:
        return False


def place_order(e, trade_book, instrument_id, price, volume, side, order_type, verify=True):
    request = e.insert_order(instrument_id,
                             price=price,
                             volume=volume,
                             side=side, order_type=order_type)

    # check what kind of thing request is
    order_id = int(request)

    trade_hist = e.get_trade_history(instrument_id)
    # trade_book = {}
    execution = False

    if verify == True:
        # for i in range(100):
        while execution == False:
            for trade in trade_hist:
                if order_id == trade.order_id:
                    # transaction = dict(trade_id = order_id,
                    # trade_price)
                    execution = True
                    # print('executed')
                    trade_logger(trade_book, trade)
                    break
                # else:


# !TODO: figure out how to log opening/closing posn
def trade_logger(trade_book, trade, trade_status='OPEN'):
    trade_dict = dict(trade_id=trade.order_id,
                      instrument_id=trade.instrument_id,
                      price=trade.price,
                      volume=trade.volume,
                      side=trade.side,
                      trade_time=datetime.now(),
                      trade_status=trade_status
                      )

    trade_book.append(trade_dict)

    return trade_dict


def close_positions(e, trade_book, instrument_id):
    pos = check_position(e, instrument_id)
    while abs(pos) > 10:
        print(pos)
        pos = check_position(e, instrument_id)
        if pos > 10:
            # sell
            # print(200)
            bid = best_order(instrument_id, 'bid', e=e)
            if bid != None:
                place_order(e, trade_book, instrument_id,
                            price=bid['price'],
                            volume=10,
                            side='ask', order_type='limit')

        if pos < -10:
            # print(200)
            ask = best_order(instrument_id, 'ask', e=e)
            if ask != None:
                place_order(e, trade_book, instrument_id,
                            price=ask['price'],
                            volume=10,
                            side='bid', order_type='limit')
        else:
            print('done')


def test_trade_algo():
    time_lim = 0.04
    A_bid = best_order('PHILIPS_A', 'bid')  # connect ask and bid at the same time?

    A_ask = best_order('PHILIPS_A', 'ask')

    B_bid = best_order('PHILIPS_B', 'bid')

    B_ask = best_order('PHILIPS_B', 'ask')

    # need to check if order book is empty

    if A_ask is not None and B_bid != None:
        if (A_ask['price'] < B_bid['price']):

            print('trade opp')
            # sell B B, less liquid
            if B_bid['volume'] >= 10:
                # e.insert_order('PHILIPS_B',
                #                 price=B_bid['price'],
                #                 volume=10,
                #                 side='ask', order_type='limit')
                print('sell B , ', vol)

                # buy A #hedge

                # e.insert_order('PHILIPS_A',
                #                 price=A_ask['price'],
                #                 volume=10,
                #                 side='bid', order_type='limit')
                print('buy A , ', vol)

                # calc new best price moment spread shifts, revert trade
                # hol pos_n

                pos_close = False
                while pos_close == False:
                    # if New_b_ask < B_bid
                    new_b_ask = best_order('PHILIPS_B', 'ask')
                    new_a_bid = best_order('PHILIPS_A', 'bid')

                    # assert new_a_bid == True
                    # assert new_b_ask == True
                    if new_a_bid == True and new_b_ask == True:
                        if (new_b_ask['price'] < B_bid['price']) and new_b_ask['volume'] >= 10:
                            # buy B
                            # e.insert_order('PHILIPS_B',
                            #             price=new_b_ask['price'],
                            #             volume=10,
                            #             side='bid', order_type='limit')
                            print('buy b,', vol)

                            # sell A
                            # e.insert_order('PHILIPS_A',

                            #                 price=new_b_ask['price'],
                            #                 volume=10,
                            #                 side='ask', order_type='limit')

                            print('sell A,', vol)
                            print('posn closed')
                            pos_close = True
                        time.sleep(time_lim)

    # assert B_ask == True
    # assert A_bid == True
    if A_bid is not None and B_ask != None:
        if B_ask['price'] < A_bid['price']:
            print('opp 2')
            if A_bid['volume'] >= 10:
                # e.insert_order('PHILIPS_B',
                #                 price=B_bid['price'],
                #                 volume=10,
                #                 side='ask', order_type='limit')
                print('buy B  , ', vol)

                # buy A #hedge

                # e.insert_order('PHILIPS_A',
                #                 price=A_ask['price'],
                #                 volume=10,
                #                 side='bid', order_type='limit')
                print('sell A , ', vol)

                # calc new best price moment spread shifts, revert trade
                # hol pos_n

                pos_close = False
                while pos_close == False:
                    # if New_b_ask < B_bid
                    new_b_bid = best_order('PHILIPS_B', 'bid')
                    new_a_ask = best_order('PHILIPS_A', 'ask')

                    # assert new_a_bid == True
                    # assert new_b_ask == True
                    if new_b_bid == True and new_a_ask == True:
                        if (new_b_ask['price'] < B_bid['price']) and new_b_ask['volume'] >= 10:
                            # buy B
                            # e.insert_order('PHILIPS_B',
                            #             price=new_b_ask['price'],
                            #             volume=10,
                            #             side='bid', order_type='limit')
                            print('sell b,', vol)

                            # sell A
                            # e.insert_order('PHILIPS_A',

                            #                 price=new_b_ask['price'],
                            #                 volume=10,
                            #                 side='ask', order_type='limit')

                            print('buy A,', vol)
                            pos_close = True
                            print('posn closed')
                        time.sleep(time_lim)
            # sell A


    else:
        # print('nothing found')
        # buy B
        pass


def trade_algo(e, trade_book):
    time_lim = 0.04  # floor to prevent hitting request limit

    # vol = 20

    A_ask = best_order('PHILIPS_A', 'ask', e)

    B_bid = best_order('PHILIPS_B', 'bid', e)

    if A_ask is not None and B_bid is not None:
        if (A_ask['price'] <= B_bid['price']):
            vol = get_volume(A_ask, B_bid)

            print('trade opp')
            # sell B B, less liquid
            # if B_bid['volume'] >= 10:
            place_order(e, trade_book, 'PHILIPS_B',
                        price=B_bid['price'],
                        volume=vol,
                        side='ask', order_type='limit')
            print('sell B ', vol)

            # buy A #hedge

            place_order(e, trade_book, 'PHILIPS_A',
                        price=A_ask['price'],
                        volume=vol,
                        side='bid', order_type='limit')
            print('buy A , ', vol)

            pos_close = False
            while pos_close == False:
                # if New_b_ask < B_bid
                new_b_ask = best_order('PHILIPS_B', 'ask', e)
                new_a_bid = best_order('PHILIPS_A', 'bid', e)

                if new_a_bid is not None and new_b_ask is not None:
                    if (new_b_ask['price'] < B_bid['price']) and new_b_ask['volume'] >= 10:
                        # buy B
                        place_order(e, trade_book, 'PHILIPS_B',
                                    price=new_b_ask['price'],
                                    volume=vol,
                                    side='bid', order_type='limit')
                        print('buy b,', vol)

                        # sell A
                        place_order(e, trade_book, 'PHILIPS_A',

                                    price=new_a_bid['price'],
                                    volume=vol,  # this is nishithe, ill try reading the code

                                    side='ask', order_type='limit')

                        print('sell A,', vol)
                        print('posn closed')
                        pos_close = True
                    time.sleep(time_lim)

    A_bid = best_order('PHILIPS_A', 'bid', e)
    B_ask = best_order('PHILIPS_B', 'ask', e)
    if A_bid is not None and B_ask is not None:
        if B_ask['price'] <= A_bid['price']:
            vol = get_volume(B_ask, A_bid)
            # print('opp 2')
            # if A_bid['volume'] >= 10:
            place_order(e, trade_book, 'PHILIPS_B',
                        price=B_ask['price'],
                        volume=vol,
                        side='bid', order_type='limit')
            print('buy B  , ', vol)

            # sell A as a hedge

            place_order(e, trade_book, 'PHILIPS_A',
                        price=A_bid['price'],
                        volume=vol,
                        side='ask', order_type='limit')
            print('sell A , ', vol)

            # calc new best price moment spread shifts, revert trade
            # hol pos_n

            pos_close = False
            while pos_close == False:
                # if New_b_ask < B_bid
                new_b_bid = best_order('PHILIPS_B', 'bid', e)
                new_a_ask = best_order('PHILIPS_A', 'ask', e)

                # assert new_a_bid == True
                # assert new_b_ask == True
                if new_b_bid is not None and new_a_ask is not None:
                    if (new_b_bid['price'] < B_ask['price']) \
                            and new_b_bid['volume'] >= 10:
                        place_order(e, trade_book, 'PHILIPS_B',
                                    price=new_b_bid['price'],
                                    volume=vol,
                                    side='ask', order_type='limit')
                        print('sell b,', vol)

                        place_order(e, trade_book,
                                    'PHILIPS_A',
                                    price=new_a_ask['price'],
                                    volume=vol,
                                    side='bid', order_type='limit')

                        print('buy A,', vol)
                        pos_close = True
                        print('posn closed')
                    time.sleep(time_lim)
        # sell A


    else:
        # print('nothing found')
        pass


def main():
    e = connect()
    trade_book = []  # save this somewhere?

    assert e.is_connected()
    while True:
        arbitrageur(e, trade_book)
        # close_positions(e,trade_book,'PHILIPS_A')
    print('done')


main()

# TODO: the volume problem
# execution time of the hedge

