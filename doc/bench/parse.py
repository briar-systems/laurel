#!/usr/bin/env python3
"""Turn one oha JSON report into a single result line.

Reads the report on stdin and prints, tab separated:

    requests_per_second  p50_ms  p99_ms  total_requests  non_2xx  errors

oha 1.16 reports `metrics.latency_ms` already in milliseconds. Older reports
only carry `latencyPercentiles`, which are in seconds, so that is the fallback
and it is converted.
"""

import json
import sys


def latencies(report):
    metrics = report.get("metrics") or {}
    in_ms = metrics.get("latency_ms")
    if isinstance(in_ms, dict) and "p50" in in_ms and "p99" in in_ms:
        return float(in_ms["p50"]), float(in_ms["p99"])

    seconds = report.get("latencyPercentiles") or report.get("latency_percentiles") or {}
    if "p50" in seconds and "p99" in seconds:
        return float(seconds["p50"]) * 1000.0, float(seconds["p99"]) * 1000.0

    raise SystemExit("parse.py: the report carries no p50/p99 latency")


def main():
    report = json.load(sys.stdin)

    summary = report.get("summary") or {}
    rps = summary.get("requestsPerSec")
    if rps is None:
        rps = (report.get("metrics") or {}).get("requests_per_sec")
    if rps is None:
        raise SystemExit("parse.py: the report carries no requests-per-second field")

    p50, p99 = latencies(report)

    # anything outside 2xx means the cell did not measure what it claims to
    codes = report.get("statusCodeDistribution") or report.get("status_code_distribution") or {}
    requests = sum(codes.values())
    non_2xx = sum(count for code, count in codes.items() if not str(code).startswith("2"))

    # transport errors are reported separately from status codes: oha ends a run
    # by dropping whatever is in flight, which shows up here as roughly one
    # error per connection and is an artifact of stopping, not of the server
    errors = report.get("errorDistribution") or {}
    error_count = sum(errors.values())

    print(
        "{:.0f}\t{:.3f}\t{:.3f}\t{}\t{}\t{}".format(
            float(rps), p50, p99, requests, non_2xx, error_count
        )
    )


if __name__ == "__main__":
    main()
