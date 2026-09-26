from market_intelligence.services import analyze_symbol

CASES = [
    ("AAPL", "US", "1D"),
    ("AAPL", "US", "7D"),
    ("AAPL", "US", "1M"),
    ("AAPL", "US", "6M"),
    ("AAPL", "US", "1Y"),
    ("AAPL", "US", "2Y"),
    ("PTT",  "TH", "1D"),
    ("PTT",  "TH", "7D"),
    ("PTT",  "TH", "1M"),
    ("PTT",  "TH", "6M"),
    ("PTT",  "TH", "1Y"),
    ("PTT",  "TH", "2Y"),
]

results = []

print("=" * 118)
print("M1 FINAL VALIDATION MATRIX")
print("=" * 118)
print(
    f"{'SYMBOL':<8} {'MKT':<5} {'TF':<5} {'STATUS':<7} "
    f"{'ROWS':>6} {'SOURCE':<10} {'RELIABILITY':<12} "
    f"{'VALID':<7} {'SIGNAL':<7} {'GAPS':>5} ISSUES"
)
print("-" * 118)

for symbol, market, timeframe in CASES:
    try:
        df, plan = analyze_symbol(symbol, market, timeframe)

        q = df.attrs.get("market_data_quality", {})
        source = df.attrs.get("market_data_source")
        reliability = df.attrs.get("market_data_reliability")

        valid = q.get("valid") is True
        signal_allowed = q.get("signal_allowed") is True
        issues = q.get("issues", [])
        gap_count = q.get("gap_count", 0)

        passed = (
            source == "yfinance"
            and reliability == "verified"
            and valid
            and signal_allowed
            and not issues
        )

        status = "PASS" if passed else "FAIL"

        print(
            f"{symbol:<8} {market:<5} {timeframe:<5} {status:<7} "
            f"{len(df):>6} {str(source):<10} {str(reliability):<12} "
            f"{str(valid):<7} {str(signal_allowed):<7} "
            f"{str(gap_count):>5} {issues}"
        )

        results.append(passed)

    except Exception as exc:
        print(
            f"{symbol:<8} {market:<5} {timeframe:<5} {'FAIL':<7} "
            f"{0:>6} {'-':<10} {'-':<12} "
            f"{'False':<7} {'False':<7} "
            f"{'-':>5} {type(exc).__name__}: {exc}"
        )
        results.append(False)

print("-" * 118)

passed = sum(results)
failed = len(results) - passed

print(f"RESULT: {passed}/{len(results)} PASS | {failed} FAIL")

if failed == 0:
    print("M1 FINAL VALIDATION: PASS")
    print("M1 MARKET DATA RELIABILITY: READY FOR SIGN-OFF")
else:
    print("M1 FINAL VALIDATION: FAIL")
    print("M1 MARKET DATA RELIABILITY: NOT READY FOR SIGN-OFF")

print("=" * 118)

raise SystemExit(0 if failed == 0 else 1)
