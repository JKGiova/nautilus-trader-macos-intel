#!/usr/bin/env python3
"""Exercise the installed Rust/Cython extensions, Arrow persistence and backtesting offline."""
import argparse
import platform
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-version", default="1.231.0")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "x86_64":
        raise SystemExit("Smoke test requires native Intel macOS Python")
    import nautilus_trader
    from nautilus_trader.core import nautilus_pyo3
    from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.model.currencies import USD
    from nautilus_trader.model.data import QuoteTick
    from nautilus_trader.model.enums import AccountType, OmsType
    from nautilus_trader.model.identifiers import Venue
    from nautilus_trader.model.objects import Money, Price, Quantity
    from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog
    from nautilus_trader.test_kit.providers import TestInstrumentProvider

    assert nautilus_trader.__version__ == args.expected_version
    assert nautilus_pyo3.Price.from_str("1.23456").as_double() == 1.23456
    instrument = TestInstrumentProvider.default_fx_ccy("AUD/USD")
    ticks = [
        QuoteTick(instrument_id=instrument.id,
                  bid_price=Price.from_str("0.65000"), ask_price=Price.from_str("0.65010"),
                  bid_size=Quantity.from_int(100000), ask_size=Quantity.from_int(100000),
                  ts_event=1_700_000_000_000_000_000 + i * 1_000_000_000,
                  ts_init=1_700_000_000_000_000_000 + i * 1_000_000_000)
        for i in range(3)
    ]
    with tempfile.TemporaryDirectory() as directory:
        catalog = ParquetDataCatalog(path=str(Path(directory) / "catalog"))
        catalog.write_data([instrument])
        catalog.write_data(ticks)
        assert len(catalog.quote_ticks()) == len(ticks)
    engine = BacktestEngine(config=BacktestEngineConfig(logging=LoggingConfig(bypass_logging=True)))
    try:
        engine.add_venue(venue=Venue("SIM"), oms_type=OmsType.HEDGING,
                         account_type=AccountType.MARGIN, base_currency=USD,
                         starting_balances=[Money(100000, USD)])
        engine.add_instrument(instrument)
        engine.add_data(ticks)
        engine.run()
        assert engine.get_result().iterations == len(ticks)
    finally:
        engine.dispose()
    print(f"PASS: NautilusTrader {nautilus_trader.__version__}, Python {platform.python_version()}, "
          f"macOS {platform.mac_ver()[0]}, {platform.machine()}")


if __name__ == "__main__":
    main()
