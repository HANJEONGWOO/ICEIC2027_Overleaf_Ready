#!/usr/bin/env python3
"""Reanalyse frozen runner reports; never build a model or execute a device.

Run: python figures/summarize_kv_execution_breakdown.py
Python standard library only. Defaults identify the original experiments;
--source-root and --codec-root allow equivalent archived input locations.
Outputs are written beside this script unless --output-dir is supplied.

The partition is host-observed QNN graph-call time, input/cache preparation
plus cache commit, and the remaining measured phase time. It is NOT a
partition into encoder, decoder, attention, or pure accelerator kernels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


DEFAULT_SOURCE = Path(
    "/mnt/d/ai-hub-models/binaries/turboquant/iceic2027_k8_repeat_20261027"
)
DEFAULT_CODEC = Path(
    "/mnt/d/ai-hub-models/binaries/turboquant/lloyd_max_k8_convergence_20261020"
)
GROUPS = ("odd_lm", "odd_structured", "boundary_lm", "boundary_structured")
COMPONENTS = ("total", "qnn", "prepare_commit", "remaining")
PREFIX = "kv_cache_execution_breakdown"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def close(actual: float, expected: float, description: str) -> None:
    require(
        math.isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-7),
        f"{description}: {actual} != {expected}",
    )


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--codec-root", type=Path, default=DEFAULT_CODEC)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    root, codec_root = args.source_root.resolve(), args.codec_root.resolve()
    hashes: dict[str, str] = {}

    def read(path: Path) -> dict:
        hashes[str(path)] = digest(path)
        return json.loads(path.read_text(encoding="utf-8"))

    protocol = read(root / "protocol.json")
    original_summary = read(root / "summary.json")
    require(set(protocol["groups"]) == set(GROUPS), "Unexpected configurations")
    require(len(protocol["schedule"]) == 10, "Expected ten paired rounds")
    require(original_summary["samples"] == 40, "Expected 40 measured sessions")
    require(original_summary["warmups_excluded"] == 40, "Expected 40 excluded warm-ups")
    raw_path = root / "raw.csv"
    hashes[str(raw_path)] = digest(raw_path)
    with raw_path.open(newline="", encoding="utf-8") as stream:
        raw_rows = list(csv.DictReader(stream))
    raw = {(int(r["round"]), r["group"]): r for r in raw_rows}
    require(len(raw_rows) == len(raw) == 40, "Missing/duplicate raw measurements")
    # Verify the executable identity recorded before the original experiment.
    runner_binary = Path(protocol["runner"])
    hashes[str(runner_binary)] = digest(runner_binary)
    require(
        hashes[str(runner_binary)] == protocol["frozen_inputs"][str(runner_binary)],
        "Original runner binary no longer matches the frozen identity",
    )

    session_rows: list[dict] = []
    original_metrics = {g: [] for g in GROUPS}
    expected_attempts: set[str] = set()
    for round_index, order in enumerate(protocol["schedule"], start=1):
        require(set(order) == set(GROUPS), "Incomplete counterbalanced round")
        for position, group in enumerate(order, start=1):
            attempt = f"r{round_index:02d}_p{position}_{group}"
            expected_attempts.add(attempt)
            folder = root / "attempts" / attempt
            result = read(folder / "result.json")
            report = read(folder / "runner.json")
            require(result["success"] is True, f"Unsuccessful attempt: {attempt}")
            require(result["group"] == group, "Result group mismatch")
            require(result["round"] == round_index, "Result round mismatch")
            require(result["position"] == position, "Result order mismatch")
            require(report["mode"] == "generate", "Expected generation run")
            require(report["burst_power"] is True, "Expected burst-power run")
            require(not report["op_profiles"], "Detailed profiling must be disabled")
            require(report["context_length"] == 1024, "Unexpected context capacity")
            require(report["prompt_tokens"] == 897, "Unexpected prompt length")
            require(report["kv_store_bytes"] == 30277632, "KV budget changed")
            require(len(report["sessions"]) == 2, "Expected warm-up and measured session")
            warmup, measured = report["sessions"]
            require(warmup["session"] == 0 and measured["session"] == 1,
                    "Unexpected session numbering")
            require(measured["generated"] == report["generated"] == warmup["generated"],
                    "Measured outputs or reset check differ")
            require(len(report["generated"]) == 128, "Expected 128 generated tokens")
            require(measured["cached_tokens_at_end"] == 1024, "Cache length mismatch")
            close(report["ttft_s"], measured["ttft_s"], "Measured TTFT selection")
            close(report["ttft_s"] * 1000, result["ttft_ms"], "Result TTFT")
            for key in ("prefill_tok_per_s", "decode_tok_per_s"):
                close(report[key], measured[key], "Measured " + key)
                close(report[key], result[key], "Result " + key)
            for key in ("ttft_ms", "prefill_tok_per_s", "decode_tok_per_s"):
                close(result[key], float(raw[round_index, group][key]), "Raw CSV " + key)
            close(897 / report["prefill_s"], report["prefill_tok_per_s"], "Prefill TPS")

            steps = report["steps"]
            require(len(steps) == 135, "Expected 8 prefill + 127 AR1 records")
            prefill, decode = steps[:8], steps[8:]
            require([s["kind"] for s in prefill] == ["prefill"] * 8,
                    "Unexpected prefill records")
            require([s["ar"] for s in prefill] == [128] * 8, "Prefill shape changed")
            require([s["new_tokens"] for s in prefill] == [1] + [128] * 7,
                    "Prefill chunk schedule changed")
            require([s["cached_before"] for s in prefill] == [0] + list(range(1, 770, 128)),
                    "Prefill cache positions changed")
            require([s["kind"] for s in decode] == ["decode"] * 127,
                    "Unexpected decode records")
            require(all(s["ar"] == s["new_tokens"] == 1 for s in decode),
                    "Expected AR1 decode")
            require([s["cached_before"] for s in decode] == list(range(897, 1024)),
                    "Decode cache positions changed")
            for step in steps:
                require(step["graph_context"] == 1024, "Graph context changed")
                require(len(step["part_s"]) == 4, "Expected four sequential graph calls")
                require(not step["profile_read_s"], "Profile read in unprofiled timing")
                values = [step["prepare_s"], step["commit_s"], *step["part_s"]]
                require(all(math.isfinite(v) and v >= 0 for v in values),
                        "Invalid measured component")
                require(step["total_s"] >= sum(values) - 1e-8,
                        "Step component sum exceeds step total")
            decode_times = report["decode_step_s"]
            require(len(decode_times) == 127, "Expected 127 end-to-end AR1 durations")
            require(all(t >= s["total_s"] - 1e-8 for t, s in zip(decode_times, decode)),
                    "Step total exceeds end-to-end token time")
            close(127 / sum(decode_times), report["decode_tok_per_s"], "Decode TPS")
            close(statistics.mean(decode_times) * 1000, measured["decode_ms_per_token"],
                  "Session mean decode time")
            require(sum(s["total_s"] for s in prefill) <= report["prefill_s"] + 1e-8,
                    "Prefill records exceed measured phase")
            require(report["prefill_s"] <= report["ttft_s"], "TTFT shorter than prefill")

            for phase, records, total, factor, unit in (
                ("prefill", prefill, report["ttft_s"] * 1000, 1000, "ms"),
                ("decode", decode, statistics.mean(decode_times) * 1000,
                 1000 / 127, "ms/token"),
            ):
                qnn = sum(sum(s["part_s"]) for s in records) * factor
                prepare_commit = sum(s["prepare_s"] + s["commit_s"] for s in records) * factor
                remaining = total - qnn - prepare_commit
                require(remaining >= 0, "Negative phase residual")
                session_rows.append({
                    "group": group,
                    "placement": "Odd" if group.startswith("odd_") else "Boundary",
                    "method": "Lloyd–Max K8" if group.endswith("_lm") else "PU-K8",
                    "round": round_index, "position": position, "session": 1,
                    "phase": phase, "unit": unit, "step_count": len(records),
                    "total": total, "qnn": qnn, "prepare_commit": prepare_commit,
                    "remaining": remaining,
                    "runner_report": str(folder / "runner.json"),
                    "runner_sha256": hashes[str(folder / "runner.json")],
                })
            original_metrics[group].append(result)

    actual_attempts = {p.name for p in (root / "attempts").iterdir() if p.is_dir()}
    require(actual_attempts == expected_attempts, "Unexpected/missing attempted sessions")
    aggregates = []
    for group in GROUPS:
        for metric in ("ttft_ms", "prefill_tok_per_s", "decode_tok_per_s"):
            values = [r[metric] for r in original_metrics[group]]
            original = original_summary["summary"][group][metric]
            require(original["n"] == len(values) == 10, "Expected n=10 per configuration")
            close(statistics.mean(values), original["mean"], "Original mean " + metric)
            close(statistics.stdev(values), original["sample_sd"], "Original SD " + metric)
        for phase in ("prefill", "decode"):
            rows = [r for r in session_rows if r["group"] == group and r["phase"] == phase]
            aggregate = {k: rows[0][k] for k in ("group", "placement", "method", "phase", "unit")}
            aggregate["n"] = len(rows)
            for component in COMPONENTS:
                values = [r[component] for r in rows]
                aggregate[component + "_mean"] = statistics.mean(values)
                aggregate[component + "_sd"] = statistics.stdev(values)
            close(aggregate["total_mean"], sum(aggregate[c + "_mean"] for c in COMPONENTS[1:]),
                  "Aggregate partition")
            aggregates.append(aggregate)

    # Preserve the distinction between standalone SDK probe times and model timings.
    codecs = read(codec_root / "codec_costs.json")
    probes = []
    for source_group, method in (("lm8_converged", "Lloyd–Max K8"), ("structured", "PU-K8")):
        for tokens in (1, 128):
            matches = [r for r in codecs["encoder"] if r["group"] == source_group
                       and r["tokens"] == tokens and r["case"] == "layer0"]
            require(len(matches) == 1, "Ambiguous encoder probe")
            timing = matches[0]["timings"]["accelerator_execute_us"]
            require(len(timing) == 1, "Expected single encoder probe")
            probes.append({"component": "Encoder", "method": method, "tokens": tokens,
                           "n": 1, "sdk_execute_us": timing[0], "source_group": source_group})
        row = next(r for r in codecs["decoder"] if r["group"] == source_group and r["tokens"] == 256)
        require(row["bit_exact_fraction"] == 1, "Decoder failed its own FP16 reference")
        profile = codec_root / f"decoder_{source_group}/device/out_native_t256/qnn-profiling-data_0.log"
        hashes[str(profile)] = digest(profile)
        require(hashes[str(profile)] == row["profile_sha256"], "Decoder profile hash mismatch")
        probes.append({"component": "Decoder", "method": method, "tokens": 256, "n": 1,
                       "sdk_execute_us": row["accelerator_execute_us"],
                       "sdk_execute_excluding_wait_us": row["accelerator_execute_excluding_wait_us"],
                       "source_group": source_group, "profile_sha256": row["profile_sha256"]})
    expected = {("Lloyd–Max K8", "Encoder", 1): 1472, ("PU-K8", "Encoder", 1): 1328,
                ("Lloyd–Max K8", "Encoder", 128): 3187, ("PU-K8", "Encoder", 128): 1523,
                ("Lloyd–Max K8", "Decoder", 256): 4491, ("PU-K8", "Decoder", 256): 4429}
    require({(p["method"], p["component"], p["tokens"]): p["sdk_execute_us"] for p in probes} == expected,
            "Published standalone probe inputs changed")

    document = {
        "schema_version": 1,
        "source_root": str(root), "codec_root": str(codec_root),
        "analysis": "Reanalysis of existing reports only; no new device experiment.",
        "definitions": {
            "prefill_total": "TTFT for 897 prompt tokens, including first-token selection; milliseconds.",
            "decode_total": "Per-session arithmetic mean of 127 measured AR1 token durations; milliseconds/token.",
            "qnn": "Sum of host-observed synchronous QNN graph-call wall times (part_s). Includes scheduling/launch/wait and all graph work; not pure kernel time.",
            "prepare_commit": "Sum of runner input/cache preparation and cache commit durations, including work other than KV copies.",
            "remaining": "Measured phase total minus qnn minus prepare_commit, including token selection and unassigned host overhead.",
            "statistics": "Unweighted mean and sample SD (ddof=1) of ten session-level values per configuration. Token steps are not independent repetitions.",
            "throughput": "Mean latency is averaged per session; it need not equal 1000 divided by the published mean throughput.",
            "session_selection": "Warm-up is session 0; session 1 is measured. Runner clears steps at each session (qnn_runner/src/main.cpp), so steps contain only the final measured session.",
        },
        "limitations": [
            "This partition locates observed differences within graph-call versus host time. It does not isolate encoder, decoder, attention, compiler, scheduling, or other causes inside QNN calls.",
            "Inputs, shapes, masks, and library are matched by the original protocol, but greedy continuations can differ across configurations.",
            "Independent instrumented codec probes use qnn-net-run default power policy, unlike the warmed unprofiled full-model burst-policy runs. Probe times cannot be summed or extrapolated into whole-model latency.",
            "AR128 encoding measures a prefill shape; AR1 encoding is the autoregressive shape. The 256-token decoder probe is one standalone invocation, not a whole model step.",
            "Lloyd-Max and PU-K8 decoder reconstruction levels differ. Each matches its own FP16 reference; this is not a same-codebook decoder-only ablation.",
        ],
        "validation": {
            "measured_sessions": 40, "excluded_warmups": 40,
            "per_session_prefill_steps": 8, "per_session_decode_steps": 127,
            "original_ttft_and_throughput_means_and_sample_sds_match": True,
            "all_partitions_nonnegative": True, "frozen_runner_hash_matches": True,
        },
        "aggregate": aggregates, "codec_probes": probes,
        "source_sha256": hashes,
    }
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / f"{PREFIX}_sessions.csv", session_rows)
    write_csv(output / f"{PREFIX}.csv", aggregates)
    (output / f"{PREFIX}.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Validated 40 measured sessions; wrote {len(session_rows)} session-phase and {len(aggregates)} aggregate rows.")
    for row in aggregates:
        print(row["placement"], row["method"], row["phase"],
              ", ".join(f"{c}={row[c + '_mean']:.4f} +/- {row[c + '_sd']:.4f}" for c in COMPONENTS), row["unit"])


if __name__ == "__main__":
    main()
