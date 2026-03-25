from __future__ import annotations

import argparse
import csv
import mimetypes
from pathlib import Path
import statistics
import sys
import time

import httpx


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark Smart Add latency by uploading a dataset split to either the "
            "deployed Vercel proxy or the backend directly."
        )
    )
    parser.add_argument(
        "--api-base-url",
        required=True,
        help=(
            "API root to test, e.g. https://smart-pantry-xi.vercel.app/api/proxy "
            "or http://<elastic-ip>"
        ),
    )
    parser.add_argument("--email", required=True, help="Benchmark account email.")
    parser.add_argument("--password", required=True, help="Benchmark account password.")
    parser.add_argument(
        "--dataset-root",
        required=True,
        help="Root directory of the extracted Roboflow dataset.",
    )
    parser.add_argument(
        "--split",
        default="test",
        help="Dataset split folder to benchmark. Default: test",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of images to benchmark.",
    )
    parser.add_argument(
        "--warmup-count",
        type=int,
        default=1,
        help="How many images to upload first and exclude from timing summary.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=180.0,
        help="Per-request timeout. Default: 180",
    )
    parser.add_argument(
        "--display-name",
        default="Latency Bench",
        help="Display name used if the benchmark account needs registration.",
    )
    parser.add_argument(
        "--register-if-missing",
        action="store_true",
        help="Register the benchmark account if login initially fails.",
    )
    parser.add_argument(
        "--sleep-between-requests",
        type=float,
        default=0.0,
        help="Optional pause between uploads in seconds.",
    )
    parser.add_argument(
        "--csv-out",
        default=None,
        help="Optional path to write per-image results as CSV.",
    )
    return parser.parse_args()


def collect_images(dataset_root: Path, split: str, limit: int | None) -> list[Path]:
    split_dir = dataset_root / split / "images"
    if split_dir.is_dir():
        candidates = sorted(path for path in split_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)
    else:
        candidates = sorted(
            path
            for path in dataset_root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
            and f"/{split}/" in path.as_posix()
        )

    if not candidates:
        raise FileNotFoundError(
            f"No benchmark images found under split '{split}'. Expected something like "
            f"{dataset_root / split / 'images'}"
        )

    if limit is not None:
        return candidates[:limit]
    return candidates


def login(client: httpx.Client, api_base_url: str, email: str, password: str) -> str:
    response = client.post(
        f"{api_base_url}/auth/login",
        data={"username": email, "password": password},
    )
    response.raise_for_status()
    payload = response.json()
    return payload["access_token"]


def register(client: httpx.Client, api_base_url: str, email: str, password: str, display_name: str) -> None:
    response = client.post(
        f"{api_base_url}/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )
    if response.status_code not in {200, 201, 400}:
        response.raise_for_status()


def upload_one_image(
    client: httpx.Client,
    api_base_url: str,
    access_token: str,
    image_path: Path,
    timeout_seconds: float,
) -> tuple[float, int, int | None]:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    headers = {"Authorization": f"Bearer {access_token}"}
    with image_path.open("rb") as file_handle:
        start = time.perf_counter()
        response = client.post(
            f"{api_base_url}/images",
            headers=headers,
            files={"files": (image_path.name, file_handle, mime_type)},
            timeout=timeout_seconds,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", "0") or "0")
        raise RuntimeError(f"Rate limited after {elapsed_ms:.1f}ms; Retry-After={retry_after}")

    response.raise_for_status()
    payload = response.json()
    proposal_count = None
    try:
        first_result = payload["results"][0]
        session_id = first_result["detection_session"]["id"]
        session_response = client.get(
            f"{api_base_url}/detections/{session_id}",
            headers=headers,
            timeout=timeout_seconds,
        )
        session_response.raise_for_status()
        proposal_count = len(session_response.json().get("proposals", []))
    except Exception:
        proposal_count = None
    return elapsed_ms, response.status_code, proposal_count


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * pct
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def main() -> int:
    args = parse_args()
    dataset_root = Path(args.dataset_root).expanduser().resolve()
    images = collect_images(dataset_root, args.split, args.limit)

    api_base_url = args.api_base_url.rstrip("/")
    with httpx.Client(follow_redirects=True, timeout=args.timeout_seconds) as client:
        try:
            access_token = login(client, api_base_url, args.email, args.password)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401 and args.register_if_missing:
                register(client, api_base_url, args.email, args.password, args.display_name)
                access_token = login(client, api_base_url, args.email, args.password)
            else:
                raise

        rows: list[dict[str, object]] = []
        warmup_count = min(max(args.warmup_count, 0), len(images))
        timed_latencies: list[float] = []

        for index, image_path in enumerate(images, start=1):
            is_warmup = index <= warmup_count
            elapsed_ms, status_code, proposal_count = upload_one_image(
                client=client,
                api_base_url=api_base_url,
                access_token=access_token,
                image_path=image_path,
                timeout_seconds=args.timeout_seconds,
            )
            rows.append(
                {
                    "image": image_path.name,
                    "split": args.split,
                    "warmup": is_warmup,
                    "latency_ms": round(elapsed_ms, 2),
                    "status_code": status_code,
                    "proposal_count": proposal_count,
                }
            )
            if not is_warmup:
                timed_latencies.append(elapsed_ms)
            print(
                f"[{index}/{len(images)}] {image_path.name} "
                f"{'(warmup) ' if is_warmup else ''}-> {elapsed_ms:.1f} ms, "
                f"status={status_code}, proposals={proposal_count}"
            )
            if args.sleep_between_requests > 0:
                time.sleep(args.sleep_between_requests)

    if args.csv_out:
        csv_path = Path(args.csv_out).expanduser().resolve()
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["image", "split", "warmup", "latency_ms", "status_code", "proposal_count"],
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nSaved per-image results to {csv_path}")

    if not timed_latencies:
        print("\nNo timed samples were collected after warmup.")
        return 0

    sorted_latencies = sorted(timed_latencies)
    print("\nSmart Add latency summary")
    print("-------------------------")
    print(f"API base URL: {api_base_url}")
    print(f"Dataset split: {args.split}")
    print(f"Images timed: {len(timed_latencies)}")
    print(f"Warmup uploads excluded: {warmup_count}")
    print(f"Mean: {statistics.fmean(timed_latencies):.1f} ms")
    print(f"Median (p50): {statistics.median(timed_latencies):.1f} ms")
    print(f"p95: {percentile(sorted_latencies, 0.95):.1f} ms")
    print(f"p99: {percentile(sorted_latencies, 0.99):.1f} ms")
    print(f"Min: {sorted_latencies[0]:.1f} ms")
    print(f"Max: {sorted_latencies[-1]:.1f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
