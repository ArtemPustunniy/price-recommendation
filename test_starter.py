import asyncio
import unittest
from decimal import Decimal

from starter import recommend_price, sample_fetch_offers


def source(*offers, status="success"):
    """Имитация fetch_offers: offers — кортежи (seller, price, delivery_days)."""
    async def fetch_offers():
        return {
            "status": status,
            "offers": [
                {"seller": seller, "price": Decimal(price), "delivery_days": days}
                for seller, price, days in offers
            ],
        }
    return fetch_offers


class RecommendPriceTest(unittest.IsolatedAsyncioTestCase):
    # Обязательный тест 1: обычный расчёт (пример из starter.py).
    async def test_regular_calculation(self):
        result = await recommend_price(
            sample_fetch_offers,
            current_price=Decimal("4900.00"),
            min_price=Decimal("4500.00"),
        )
        self.assertEqual(result["price"], Decimal("4728.00"))
        self.assertEqual(result["decision"], "APPLY")

    # Обязательный тест 2: сбой — источник не отвечает дольше timeout_s.
    async def test_timeout_returns_current_price_and_hold(self):
        async def hanging_source():
            await asyncio.sleep(10)

        result = await recommend_price(
            hanging_source, Decimal("4900.00"), Decimal("4500.00"), timeout_s=0.05
        )
        self.assertEqual(result["price"], Decimal("4900.00"))
        self.assertEqual(result["decision"], "HOLD")

    # Дополнительно: остальные правила и границы.
    async def test_source_error_or_not_success_status_returns_hold(self):
        async def broken_source():
            raise ConnectionError("площадка недоступна")

        sources = {
            "exception": broken_source,
            "partial": source(("PARTS", "100.00", 1), status="partial"),
            "error": source(status="error"),
        }
        for name, fetch in sources.items():
            with self.subTest(name):
                result = await recommend_price(fetch, Decimal("500.00"), Decimal("400.00"))
                self.assertEqual(result["price"], Decimal("500.00"))
                self.assertEqual(result["decision"], "HOLD")

    async def test_no_suitable_offers_holds_even_below_min_price(self):
        fetch = source(
            ("MyShop", "50.00", 1),  # свой магазин в другом регистре
            ("PARTS", "50.00", None),  # доставка неизвестна
            ("SLOW", "50.00", 7),  # доставка дольше 6 дней
        )
        result = await recommend_price(fetch, Decimal("100.00"), Decimal("200.00"))
        self.assertEqual(result["price"], Decimal("100.00"))
        self.assertEqual(result["decision"], "HOLD")

    async def test_rounds_down_to_kopeck_and_respects_min_price(self):
        fetch = source(("PARTS", "1000.99", 6))  # 1000.99 * 0.985 = 985.97515
        result = await recommend_price(fetch, Decimal("1000.00"), Decimal("900.00"))
        self.assertEqual(str(result["price"]), "985.97")  # не 985.98

        result = await recommend_price(fetch, Decimal("1000.00"), Decimal("990.00"))
        self.assertEqual(result["price"], Decimal("990.00"))
        self.assertEqual(result["decision"], "APPLY")

    async def test_change_threshold_is_30_percent_in_both_directions(self):
        cases = [
            ("1319.80", "1300.00", "APPLY"),  # ровно +30%
            ("1319.81", "1300.01", "REVIEW"),
            ("710.66", "700.00", "APPLY"),  # ровно −30%
            ("710.65", "699.99", "REVIEW"),
        ]
        for competitor, expected_price, expected_decision in cases:
            with self.subTest(competitor=competitor):
                result = await recommend_price(
                    source(("PARTS", competitor, 2)), Decimal("1000.00"), Decimal("1.00")
                )
                self.assertEqual(result["price"], Decimal(expected_price))
                self.assertEqual(result["decision"], expected_decision)


if __name__ == "__main__":
    unittest.main()
