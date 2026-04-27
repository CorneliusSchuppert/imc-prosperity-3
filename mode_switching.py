from datamodel import OrderDepth, Order, TradingState
from typing import List
import jsonpickle
import numpy as np
import math

class Product:
    RESIN = "RAINFOREST_RESIN"
    KELP = "KELP"
    INK = "SQUID_INK"

class Trader:
    def __init__(self):
        self.kelp_prices = []
        self.kelp_vwap = []
        self.ink_prices = []
        self.ink_vwap = []

        self.LIMIT = {
            Product.RESIN: 50,
            Product.KELP: 50,
            Product.INK: 50
        }

    def take_best_orders(self, product, fair_value, take_width, orders, order_depth,
                         position, buy_order_volume, sell_order_volume,
                         prevent_adverse=False, adverse_volume=0):
        position_limit = self.LIMIT[product]

        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_ask_amount = -order_depth.sell_orders[best_ask]
            if not prevent_adverse or best_ask_amount <= adverse_volume:
                if best_ask <= fair_value - take_width:
                    quantity = min(best_ask_amount, position_limit - position)
                    if quantity > 0:
                        orders.append(Order(product, int(best_ask), quantity))
                        buy_order_volume += quantity

        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            best_bid_amount = order_depth.buy_orders[best_bid]
            if not prevent_adverse or best_bid_amount <= adverse_volume:
                if best_bid >= fair_value + take_width:
                    quantity = min(best_bid_amount, position_limit + position)
                    if quantity > 0:
                        orders.append(Order(product, int(best_bid), -quantity))
                        sell_order_volume += quantity

        return buy_order_volume, sell_order_volume

    def market_make(self, product, orders, bid, ask, position, buy_vol, sell_vol):
        buy_qty = self.LIMIT[product] - (position + buy_vol)
        if buy_qty > 0:
            orders.append(Order(product, int(round(bid)), buy_qty))

        sell_qty = self.LIMIT[product] + (position - sell_vol)
        if sell_qty > 0:
            orders.append(Order(product, int(round(ask)), -sell_qty))

        return buy_vol, sell_vol

    def clear_position_order(self, product, fair_value, orders, order_depth, position, buy_vol, sell_vol):
        pos_after = position + buy_vol - sell_vol
        fair_bid = int(math.floor(fair_value))
        fair_ask = int(math.ceil(fair_value))

        buy_qty = self.LIMIT[product] - (position + buy_vol)
        sell_qty = self.LIMIT[product] + (position - sell_vol)

        if pos_after > 0 and fair_ask in order_depth.buy_orders:
            qty = min(order_depth.buy_orders[fair_ask], pos_after)
            orders.append(Order(product, fair_ask, -min(sell_qty, qty)))
            sell_vol += min(sell_qty, qty)

        if pos_after < 0 and fair_bid in order_depth.sell_orders:
            qty = min(-order_depth.sell_orders[fair_bid], -pos_after)
            orders.append(Order(product, fair_bid, min(buy_qty, qty)))
            buy_vol += min(buy_qty, qty)

        return buy_vol, sell_vol

    def resin_orders(self, order_depth, fair_value, position):
        orders = []
        bv, sv = 0, 0
        baaf = min([p for p in order_depth.sell_orders if p > fair_value + 1], default=fair_value + 2)
        bbbf = max([p for p in order_depth.buy_orders if p < fair_value - 1], default=fair_value - 2)
        bv, sv = self.take_best_orders(Product.RESIN, fair_value, 0.5, orders, order_depth, position, bv, sv)
        bv, sv = self.clear_position_order(Product.RESIN, fair_value, orders, order_depth, position, bv, sv)
        bv, sv = self.market_make(Product.RESIN, orders, bbbf + 1, baaf - 1, position, bv, sv)
        return orders

    def kelp_orders(self, order_depth, timespan, take_width, position):
        orders = []
        bv, sv = 0, 0

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)

            filtered_ask = [p for p in order_depth.sell_orders if -order_depth.sell_orders[p] >= 15]
            filtered_bid = [p for p in order_depth.buy_orders if order_depth.buy_orders[p] >= 15]

            mm_ask = min(filtered_ask) if filtered_ask else best_ask
            mm_bid = max(filtered_bid) if filtered_bid else best_bid
            mm_mid = (mm_ask + mm_bid) / 2

            self.kelp_prices.append(mm_mid)
            vol = -order_depth.sell_orders[best_ask] + order_depth.buy_orders[best_bid]
            vwap = (best_bid * -order_depth.sell_orders[best_ask] + best_ask * order_depth.buy_orders[best_bid]) / vol
            self.kelp_vwap.append({"vol": vol, "vwap": vwap})

            if len(self.kelp_prices) > timespan:
                self.kelp_prices.pop(0)
            if len(self.kelp_vwap) > timespan:
                self.kelp_vwap.pop(0)

            fair_value = mm_mid

            bv, sv = self.take_best_orders(Product.KELP, fair_value, take_width, orders, order_depth, position, bv, sv, True, 20)
            bv, sv = self.clear_position_order(Product.KELP, fair_value, orders, order_depth, position, bv, sv)

            baaf = min([p for p in order_depth.sell_orders if p > fair_value + 1], default=fair_value + 2)
            bbbf = max([p for p in order_depth.buy_orders if p < fair_value - 1], default=fair_value - 2)

            bv, sv = self.market_make(Product.KELP, orders, bbbf + 1, baaf - 1, position, bv, sv)

        return orders

    def ink_orders(self, order_depth, timespan, take_width, position, timestamp):
        orders = []

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)
            mid_price = (best_ask + best_bid) / 2

            vol = -order_depth.sell_orders[best_ask] + order_depth.buy_orders[best_bid]
            vwap = (best_bid * -order_depth.sell_orders[best_ask] + best_ask * order_depth.buy_orders[best_bid]) / vol

            self.ink_prices.append(mid_price)
            self.ink_vwap.append(vwap)

            if len(self.ink_prices) > timespan:
                self.ink_prices.pop(0)
            if len(self.ink_vwap) > 20:
                self.ink_vwap.pop(0)

            if len(self.ink_vwap) >= 15:
                short_vwap = np.mean(self.ink_vwap[-5:])
                long_vwap = np.mean(self.ink_vwap[-15:])
                fair_value = vwap
                limit = self.LIMIT[Product.INK]

                if timestamp < 41400:
                    # Before: short-only strategy
                    if mid_price > vwap and short_vwap < long_vwap:
                        qty = min(order_depth.buy_orders[best_bid], limit + position)
                        if qty > 0:
                            orders.append(Order(Product.INK, best_bid, -qty))
                else:
                    # After: long-only strategy
                    if mid_price < vwap and short_vwap > long_vwap:
                        qty = min(-order_depth.sell_orders[best_ask], limit - position)
                        if qty > 0:
                            orders.append(Order(Product.INK, best_ask, qty))

        return orders

    def run(self, state: TradingState):
        result = {}

        resin_fair_value = 10000
        kelp_take_width = 1
        kelp_timespan = 10
        ink_take_width = 1
        ink_timespan = 10

        resin_position = state.position.get(Product.RESIN, 0)
        kelp_position = state.position.get(Product.KELP, 0)
        ink_position = state.position.get(Product.INK, 0)

        if Product.RESIN in state.order_depths:
            result[Product.RESIN] = self.resin_orders(state.order_depths[Product.RESIN], resin_fair_value, resin_position)

        if Product.KELP in state.order_depths:
            result[Product.KELP] = self.kelp_orders(state.order_depths[Product.KELP], kelp_timespan, kelp_take_width, kelp_position)

        if Product.INK in state.order_depths:
            result[Product.INK] = self.ink_orders(state.order_depths[Product.INK], ink_timespan, ink_take_width, ink_position, state.timestamp)

        traderData = jsonpickle.encode({
            "kelp_prices": self.kelp_prices,
            "kelp_vwap": self.kelp_vwap,
            "ink_prices": self.ink_prices,
            "ink_vwap": self.ink_vwap,
        })

        return result, 0, traderData
