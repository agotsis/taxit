import argparse
import json
import yaml
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class FilterResult:
    kept: int
    removed: int


def segment_is_kept(
    seg: Dict[str, Any],
    cutoff: datetime,
    mode: str,
) -> bool:
    start_s = seg.get("startTime")
    end_s = seg.get("endTime")

    if not isinstance(start_s, str) or not isinstance(end_s, str):
        return False

    start_dt = datetime.fromisoformat(start_s).astimezone(timezone.utc)
    end_dt = datetime.fromisoformat(end_s).astimezone(timezone.utc)

    if mode == "start":
        return start_dt >= cutoff
    if mode == "end":
        return end_dt >= cutoff
    if mode == "overlap":
        # Keep if segment overlaps the interval [cutoff, +inf)
        return end_dt >= cutoff

    raise ValueError(f"Unknown mode: {mode}")


def filter_timeline_doc(
    doc: Dict[str, Any],
    cutoff: datetime,
    mode: str,
) -> FilterResult:
    segments = doc.get("semanticSegments")
    if not isinstance(segments, list):
        raise ValueError("Expected top-level key 'semanticSegments' to be a list")

    kept_segments: List[Any] = []
    removed = 0

    for seg in segments:
        if not isinstance(seg, dict):
            removed += 1
            continue

        if segment_is_kept(seg, cutoff=cutoff, mode=mode):
            kept_segments.append(seg)
        else:
            removed += 1

    doc["semanticSegments"] = kept_segments
    return FilterResult(kept=len(kept_segments), removed=removed)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Filter Google Timeline export JSON to segments in/after a given year. "
            "Only 'semanticSegments' is filtered; other top-level fields are preserved. "
            "Outputs YAML format."
        )
    )
    parser.add_argument(
        "--input",
        default=str(Path(__file__).with_name("Timeline-agotsis.json")),
        help="Input Timeline JSON path (default: ../data/Timeline-agotsis.json)",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).with_name("Timeline-agotsis-2023plus.yaml")),
        help="Output YAML path (default: ../data/Timeline-agotsis-2023plus.yaml)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2023,
        help="Keep segments from this year and later (default: 2023)",
    )
    parser.add_argument(
        "--mode",
        choices=["start", "end", "overlap"],
        default="start",
        help=(
            "Filtering mode. 'start' keeps segments whose startTime is >= cutoff; "
            "'end' keeps segments whose endTime is >= cutoff; "
            "'overlap' keeps segments that overlap the cutoff (same as 'end' for open-ended range)."
        ),
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    cutoff = datetime(args.year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    with input_path.open("r", encoding="utf-8") as f:
        doc = json.load(f)

    if not isinstance(doc, dict):
        raise ValueError("Expected root JSON value to be an object")

    result = filter_timeline_doc(doc, cutoff=cutoff, mode=args.mode)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        # Output as YAML
        yaml.dump(doc, f, allow_unicode=True, default_flow_style=False)

    print(
        f"Wrote {output_path}. Kept {result.kept} segments; removed {result.removed}. "
        f"Cutoff={args.year}-01-01Z mode={args.mode}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
