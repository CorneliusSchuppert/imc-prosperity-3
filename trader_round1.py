from datamodel import OrderDepth, Order, TradingState
from typing import List
import jsonpickle
import numpy as np
import math
import statistics as stats

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

    def take_best_orders(self, product: str, 
                            fair_value: int, 
                            take_width: float, 
                            orders: List[Order], 
                            order_depth: OrderDepth,
                            position: int, 
                            buy_order_volume: int, 
                            sell_order_volume: int, 
                            prevent_adverse: bool = False, 
                            adverse_volume: int = 0
                            ) -> (int, int):

        position_limit = self.LIMIT[product]

        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_ask_amount = -order_depth.sell_orders[best_ask]
            if not prevent_adverse or best_ask_amount <= adverse_volume:
                if best_ask <= fair_value - take_width:
                    quantity = min(best_ask_amount, position_limit - position)
                    if quantity > 0:
                        orders.append(Order(product, best_ask, quantity))
                        buy_order_volume += quantity

        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            best_bid_amount = order_depth.buy_orders[best_bid]
            if not prevent_adverse or best_bid_amount <= adverse_volume:
                if best_bid >= fair_value + take_width:
                    quantity = min(best_bid_amount, position_limit + position)
                    if quantity > 0:
                        orders.append(Order(product, best_bid, -quantity))
                        sell_order_volume += quantity

        return buy_order_volume, sell_order_volume

    def market_make(self, product: str, orders: List[Order], bid: int, ask: int, position: int, buy_order_volume: int,
                    sell_order_volume: int) -> (int, int):
        buy_quantity = self.LIMIT[product] - (position + buy_order_volume)
        if buy_quantity > 0:
            orders.append(Order(product, bid, buy_quantity))

        sell_quantity = self.LIMIT[product] + (position - sell_order_volume)
        if sell_quantity > 0:
            orders.append(Order(product, ask, -sell_quantity))

        return buy_order_volume, sell_order_volume

    def clear_position_order(self, product: str, fair_value: float, orders: List[Order], order_depth: OrderDepth,
                             position: int, buy_order_volume: int, sell_order_volume: int) -> (int, int):
        position_after_take = position + buy_order_volume - sell_order_volume
        fair_bid = math.floor(fair_value)
        fair_ask = math.ceil(fair_value)

        buy_quantity = self.LIMIT[product] - (position + buy_order_volume)
        sell_quantity = self.LIMIT[product] + (position - sell_order_volume)

        if position_after_take > 0 and fair_ask in order_depth.buy_orders:
            clear_qty = min(order_depth.buy_orders[fair_ask], position_after_take)
            orders.append(Order(product, fair_ask, -min(sell_quantity, clear_qty)))
            sell_order_volume += min(sell_quantity, clear_qty)

        if position_after_take < 0 and fair_bid in order_depth.sell_orders:
            clear_qty = min(-order_depth.sell_orders[fair_bid], -position_after_take)
            orders.append(Order(product, fair_bid, min(buy_quantity, clear_qty)))
            buy_order_volume += min(buy_quantity, clear_qty)

        return buy_order_volume, sell_order_volume

    def resin_orders(self, order_depth: OrderDepth, fair_value: int, position: int) -> List[Order]:
        orders = []
        buy_vol, sell_vol = 0, 0

        baaf = min([p for p in order_depth.sell_orders if p > fair_value + 1], default=fair_value + 2)
        bbbf = max([p for p in order_depth.buy_orders if p < fair_value - 1], default=fair_value - 2)

        buy_vol, sell_vol = self.take_best_orders(Product.RESIN, fair_value, 0.5, orders, order_depth, position, buy_vol, sell_vol)
        buy_vol, sell_vol = self.clear_position_order(Product.RESIN, fair_value, orders, order_depth, position, buy_vol, sell_vol)
        buy_vol, sell_vol = self.market_make(Product.RESIN, orders, bbbf + 1, baaf - 1, position, buy_vol, sell_vol)

        return orders

    def kelp_orders(self, order_depth: OrderDepth, timespan: int, take_width: float, position: int) -> List[Order]:
        orders = []
        buy_vol, sell_vol = 0, 0

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

            buy_vol, sell_vol = self.take_best_orders(Product.KELP, fair_value, take_width, orders, order_depth, position, buy_vol, sell_vol, True, 20)
            buy_vol, sell_vol = self.clear_position_order(Product.KELP, fair_value, orders, order_depth, position, buy_vol, sell_vol)

            baaf = min([p for p in order_depth.sell_orders if p > fair_value + 1], default=fair_value + 2)
            bbbf = max([p for p in order_depth.buy_orders if p < fair_value - 1], default=fair_value - 2)

            buy_vol, sell_vol = self.market_make(Product.KELP, orders, bbbf + 1, baaf - 1, position, buy_vol, sell_vol)

        return orders

    
    def ink_orders(self, order_depth: OrderDepth, timespan: int, take_width: float, position: int) -> List[Order]:
        orders = []
        buy_vol, sell_vol = 0, 0

        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)

            filtered_ask = [p for p in order_depth.sell_orders if -order_depth.sell_orders[p] >= 15]
            filtered_bid = [p for p in order_depth.buy_orders if order_depth.buy_orders[p] >= 15]

            mm_ask = min(filtered_ask) if filtered_ask else best_ask
            mm_bid = max(filtered_bid) if filtered_bid else best_bid
            mm_mid = (mm_ask + mm_bid) / 2

            self.ink_prices.append(mm_mid)
            vol = -order_depth.sell_orders[best_ask] + order_depth.buy_orders[best_bid]
            vwap = (best_bid * -order_depth.sell_orders[best_ask] + best_ask * order_depth.buy_orders[best_bid]) / vol
            self.ink_vwap.append({"vol": vol, "vwap": vwap})

            if len(self.ink_prices) > timespan:
                self.ink_prices.pop(0)
            if len(self.ink_vwap) > timespan:
                self.ink_vwap.pop(0)

            fair_value = mm_mid

            buy_vol, sell_vol = self.take_best_orders(Product.INK, fair_value, take_width, orders, order_depth, position, buy_vol, sell_vol, True, 20)
            buy_vol, sell_vol = self.clear_position_order(Product.INK, fair_value, orders, order_depth, position, buy_vol, sell_vol)

            baaf = min([p for p in order_depth.sell_orders if p > fair_value + 1], default=fair_value + 2)
            bbbf = max([p for p in order_depth.buy_orders if p < fair_value - 1], default=fair_value - 2)

            buy_vol, sell_vol = self.market_make(Product.INK, orders, bbbf + 1, baaf - 1, position, buy_vol, sell_vol)

        return orders

    def run(self, state: TradingState):
        result = {}

        resin_fair_value = 10000
        kelp_take_width = 1
        kelp_timespan = 20
        ink_timespan = 10
        ink_take_width = 1

        resin_position = state.position.get(Product.RESIN, 0)
        kelp_position = state.position.get(Product.KELP, 0)
        ink_position = state.position.get(Product.INK, 0)

        if Product.RESIN in state.order_depths:
            result[Product.RESIN] = self.resin_orders(state.order_depths[Product.RESIN], resin_fair_value, resin_position)

        if Product.KELP in state.order_depths:
            result[Product.KELP] = self.kelp_orders(state.order_depths[Product.KELP], kelp_timespan, kelp_take_width, kelp_position)

        if Product.INK in state.order_depths:
            result[Product.INK] = self.ink_orders(state.order_depths[Product.INK], ink_timespan, ink_take_width, ink_position)

        traderData = jsonpickle.encode({
            "kelp_prices": self.kelp_prices,
            "kelp_vwap": self.kelp_vwap,
            "ink_prices": self.ink_prices,
            "ink_vwap": self.ink_vwap
        })

        return result, 0, traderData
