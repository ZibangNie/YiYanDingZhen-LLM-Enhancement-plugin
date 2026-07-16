"""调用本地一言鼎臻插件接口的最小示例。"""

from __future__ import annotations

import argparse

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--base-url", default="http://127.0.0.1:8081")
    parser.add_argument("--session-id", default="example-client")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    response = requests.post(
        f"{args.base_url.rstrip('/')}/set_Query",
        json={
            "query_content": args.query,
            "session_id": args.session_id,
        },
        timeout=30,
    )
    response.raise_for_status()
    print(response.json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
