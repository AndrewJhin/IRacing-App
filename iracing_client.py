"""Small iRacing data API client and starter extraction command."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from iracing_storage import Store, default_database


class IRacingClient:
    """Authenticated client for the iRacing members data API."""

    def __init__(self, email: str, password: str, timeout: int = 30) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "iracing-data-starter/0.1"})
        self._authenticate(email, password)

    def _authenticate(self, email: str, password: str) -> None:
        password_hash = hashlib.sha256(password.encode("utf-8")).digest()
        encoded_password = base64.b64encode(password_hash).decode("ascii")

        response = self.session.post(
            "https://members-ng.iracing.com/auth",
            json={"email": email, "password": encoded_password},
            timeout=self.timeout,
        )
        response.raise_for_status()

        if response.json().get("authcode") is None:
            raise RuntimeError("iRacing authentication did not return an authcode.")

    def get_data(self, path: str, **params: Any) -> Any:
        """Fetch a data endpoint and follow iRacing's returned download link."""
        if not path.startswith("/"):
            path = f"/{path}"

        response = self.session.get(
            f"https://members-ng.iracing.com/data{path}",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict) and payload.get("link"):
            linked_response = self.session.get(payload["link"], timeout=self.timeout)
            linked_response.raise_for_status()
            return linked_response.json()

        return payload

    def get_member_info(self, customer_id: int | None = None) -> Any:
        """Extract member information for the authenticated account."""
        params = {}
        if customer_id is not None:
            params["cust_id"] = customer_id
        return self.get_data("/results/get", **params)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Pull starter data from iRacing.")
    parser.add_argument(
        "--endpoint",
        default="/member/info",
        help="Path under https://members-ng.iracing.com/data (default: /member/info)",
    )
    parser.add_argument("--customer-id", type=int, help="Optional iRacing customer ID.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/iracing-response.json"),
        help="JSON output path.",
    )
    parser.add_argument('--database', type=Path, default=default_database(), help='SQLite database path.')
    parser.add_argument('--no-database', action='store_true', help='Write the JSON response file only.')
    args = parser.parse_args()

    email = os.getenv("IRACING_EMAIL")
    password = os.getenv("IRACING_PASSWORD")
    if not email or not password:
        raise SystemExit("Set IRACING_EMAIL and IRACING_PASSWORD in .env or the environment.")

    client = IRacingClient(email, password)
    data = client.get_data(args.endpoint, cust_id=args.customer_id) if args.customer_id else client.get_data(args.endpoint)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if not args.no_database:
        with Store(args.database) as store, store.connection:
            document_id = store.add_document('iracing_api:' + args.endpoint, data,
                                             source_uri=str(args.output.resolve()))
        print(f'Stored response {document_id} in {args.database}')
    print(f"Saved iRacing response to {args.output}")


if __name__ == "__main__":
    main()
