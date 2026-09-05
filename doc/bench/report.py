#!/usr/bin/env python3
"""Render the measured matrix into the results markdown.

Reads the tab separated files run.sh produced and writes one document: a
machine description, one table per route, and a resource table. Numbers are
printed exactly as measured; nothing here averages a failed cell away.
"""

import argparse
import platform
import subprocess
import sys

SERVERS = [
    ("laurel", "Laurel + hedge", "single threaded"),
    ("go1", "Go net/http", "GOMAXPROCS=1"),
    ("axum1", "axum", "tokio current_thread"),
    ("gon", "Go net/http", "all cores"),
    ("axumn", "axum", "tokio multi_thread"),
]

SINGLE = ["laurel", "go1", "axum1"]
PARALLEL = ["gon", "axumn"]

ROUTES = [
    ("json", "`GET /json`", "a fixed JSON body"),
    ("echo", "`GET /echo/42`", "a typed u64 path parameter"),
    ("submit", "`POST /submit`", "a urlencoded form body"),
]


def label(name):
    for key, engine, mode in SERVERS:
        if key == name:
            return "{} ({})".format(engine, mode)
    return name


def read_results(path):
    rows = {}
    with open(path) as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            server, route, conns, rps, p50, p99, total, non2xx, errors = line.split("\t")
            rows[(server, route, int(conns))] = {
                "rps": int(rps),
                "p50": float(p50),
                "p99": float(p99),
                "total": int(total),
                "non2xx": int(non2xx),
                "errors": int(errors),
            }
    return rows


def read_resources(path):
    rows = {}
    with open(path) as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            server, rss_kb, cpu_s = line.split("\t")
            rows[server] = {"rss_kb": int(rss_kb), "cpu_s": float(cpu_s)}
    return rows


def cpu_model():
    try:
        with open("/proc/cpuinfo") as handle:
            for line in handle:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def cpu_topology():
    try:
        out = subprocess.run(
            ["lscpu"], capture_output=True, text=True, check=False
        ).stdout
        cores = threads = sockets = None
        for line in out.splitlines():
            if line.startswith("Core(s) per socket:"):
                cores = line.split(":", 1)[1].strip()
            elif line.startswith("Thread(s) per core:"):
                threads = line.split(":", 1)[1].strip()
            elif line.startswith("Socket(s):"):
                sockets = line.split(":", 1)[1].strip()
        if cores and threads and sockets:
            total = int(cores) * int(threads) * int(sockets)
            return "{} cores, {} threads".format(int(cores) * int(sockets), total)
    except (OSError, ValueError):
        pass
    return "unknown"


def load_average():
    try:
        with open("/proc/loadavg") as handle:
            return handle.read().split()[0]
    except OSError:
        return "unknown"


def table(rows, servers, route, conns_list):
    lines = []
    lines.append(
        "| server | connections | requests/s | p50 ms | p99 ms | non-2xx |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")
    for server in servers:
        for conns in conns_list:
            cell = rows.get((server, route, conns))
            if cell is None:
                lines.append(
                    "| {} | {} | not measured | | | |".format(label(server), conns)
                )
                continue
            lines.append(
                "| {} | {} | {:,} | {:.3f} | {:.3f} | {} |".format(
                    label(server),
                    conns,
                    cell["rps"],
                    cell["p50"],
                    cell["p99"],
                    cell["non2xx"],
                )
            )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--resources", required=True)
    parser.add_argument("--duration", required=True)
    parser.add_argument("--load-before", default="unknown")
    parser.add_argument("--oha", required=True)
    parser.add_argument("--mach", required=True)
    parser.add_argument("--laurel", required=True)
    parser.add_argument("--hedge", required=True)
    parser.add_argument("--go", required=True)
    parser.add_argument("--rustc", required=True)
    args = parser.parse_args()

    rows = read_results(args.results)
    resources = read_resources(args.resources)
    conns_list = sorted({key[2] for key in rows})

    out = sys.stdout
    out.write("# Benchmark results\n\n")
    out.write(
        "Measured by `doc/bench/run.sh`. Every server answers the same three\n"
        "routes with the same response bodies, on loopback, over HTTP/1.1.\n\n"
    )

    out.write("## Machine\n\n")
    out.write("| | |\n|---|---|\n")
    out.write("| CPU | {} |\n".format(cpu_model()))
    out.write("| Topology | {} |\n".format(cpu_topology()))
    out.write("| Kernel | {} |\n".format(platform.release()))
    out.write("| Load average before the run | {} |\n".format(args.load_before))
    out.write(
        "| Load average after the run | {} |\n".format(load_average())
    )
    out.write("| mach | {} |\n".format(args.mach))
    out.write("| laurel | {} |\n".format(args.laurel))
    out.write("| hedge | {} |\n".format(args.hedge))
    out.write("| go | {} |\n".format(args.go))
    out.write("| rustc | {} |\n".format(args.rustc))
    out.write("| oha | {} |\n".format(args.oha))
    out.write("| duration per cell | {} s |\n".format(args.duration))
    out.write("\n")

    out.write("## Like for like: one thread each\n\n")
    out.write(
        "Hedge's serve loop is single threaded, so this is the comparison that\n"
        "measures the same machine doing the same work. Go runs with\n"
        "`GOMAXPROCS=1` and axum on tokio's current-thread runtime.\n\n"
    )
    for key, title, description in ROUTES:
        out.write("### {} — {}\n\n".format(title, description))
        out.write(table(rows, SINGLE, key, conns_list))
        out.write("\n\n")

    out.write("## What parallelism buys the baselines\n\n")
    out.write(
        "The same Go and Rust programs with every core available. Laurel has no\n"
        "row here: hedge serves from one thread, so there is nothing to widen.\n\n"
    )
    for key, title, description in ROUTES:
        out.write("### {} — {}\n\n".format(title, description))
        out.write(table(rows, PARALLEL, key, conns_list))
        out.write("\n\n")

    out.write("## Footprint\n\n")
    out.write(
        "Peak resident set is `VmHWM` from `/proc/<pid>/status`, the highest the\n"
        "kernel ever saw. CPU time is user plus system over the whole matrix, so\n"
        "it covers all three routes at both connection counts.\n\n"
    )
    out.write("| server | peak RSS | CPU time over the matrix |\n")
    out.write("|---|---:|---:|\n")
    for key, _, _ in SERVERS:
        entry = resources.get(key)
        if entry is None:
            out.write("| {} | not measured | |\n".format(label(key)))
            continue
        out.write(
            "| {} | {:.1f} MiB | {:.2f} s |\n".format(
                label(key), entry["rss_kb"] / 1024.0, entry["cpu_s"]
            )
        )
    out.write("\n")

    out.write("## Cell health\n\n")
    failures = [key for key, cell in rows.items() if cell["non2xx"] > 0]
    if not failures:
        out.write("Every request in every cell was answered with a 2xx status.\n\n")
    else:
        out.write(
            "Cells where the server answered outside 2xx. A cell listed here did\n"
            "not measure what its row claims.\n\n"
        )
        out.write("| server | route | connections | requests | non-2xx |\n")
        out.write("|---|---|---:|---:|---:|\n")
        for key in sorted(failures):
            cell = rows[key]
            out.write(
                "| {} | {} | {} | {:,} | {} |\n".format(
                    label(key[0]), key[1], key[2], cell["total"], cell["non2xx"]
                )
            )
        out.write("\n")

    out.write(
        "Transport errors are counted separately. oha ends a run by dropping\n"
        "whatever is still in flight, so a count near the connection count is an\n"
        "artifact of stopping rather than a server fault. Cells well above that\n"
        "are listed here.\n\n"
    )
    noisy = [
        key
        for key, cell in rows.items()
        if cell["errors"] > key[2] * 1.5
    ]
    if not noisy:
        out.write("No cell exceeded one and a half transport errors per connection.\n")
    else:
        out.write("| server | route | connections | transport errors |\n")
        out.write("|---|---|---:|---:|\n")
        for key in sorted(noisy):
            out.write(
                "| {} | {} | {} | {} |\n".format(
                    label(key[0]), key[1], key[2], rows[key]["errors"]
                )
            )
    out.write("\n")


if __name__ == "__main__":
    main()
