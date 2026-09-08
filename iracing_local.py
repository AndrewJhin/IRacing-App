"""Capture iRacing SDK telemetry according to the practice profile (130 selected fields of 334).

The collector uses practice_profile.json to select which live variables to record on each SDK tick.
Complete raw SessionInfo YAML and CarSetup snapshots are preserved independently of the live-field
selection. The runtime header catalog is always exported for metadata and future profile expansion.
Unavailable selected fields are marked as such, not replaced with zero.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import irsdk
import yaml


TYPE_NAMES = {0: "char", 1: "bool", 2: "int", 3: "unsigned_int", 4: "float", 5: "double"}


def header_catalog(ir: Any) -> list[dict[str, Any]]:
    """Export every header exposed by the running SDK."""
    return [
        {
            "name": header.name,
            "description": header.desc,
            "unit": header.unit,
            "type": TYPE_NAMES.get(header.type, f"unknown_{header.type}"),
            "type_code": header.type,
            "count": header.count,
            "count_as_time": header.count_as_time,
            "source": "live_sdk",
            "availability": "verified_live",
        }
        for header in ir._var_headers
    ]


def load_profile(profile_path: Path) -> dict[str, Any]:
    """Load the telemetry capture profile (e.g., practice_profile.json)."""
    return json.loads(profile_path.read_text(encoding="utf-8"))


def read_selected_variables(ir: Any, catalog: list[dict[str, Any]], selected_names: list[str]) -> tuple[dict[str, Any], list[str]]:
    """Read only the selected live variables from the SDK, preserving arrays and native types.
    
    Returns:
        (values_dict, unavailable_fields): dictionary of selected values and list of missing selected fields.
    """
    values: dict[str, Any] = {}
    catalog_dict = {item["name"]: item for item in catalog}
    unavailable = []
    
    for name in selected_names:
        if name not in catalog_dict:
            unavailable.append(name)
            values[name] = {"_unavailable": True, "reason": "not_in_runtime_catalog"}
        else:
            try:
                value = ir[name]
                values[name] = value
            except (KeyError, Exception):
                unavailable.append(name)
                values[name] = {"_unavailable": True, "reason": "read_error"}
    
    return values, unavailable


def raw_session_info(ir: Any) -> str:
    """Read the complete raw SessionInfo YAML from pyirsdk's shared memory."""
    header = ir._header
    raw = ir._shared_mem[header.session_info_offset : header.session_info_offset + header.session_info_len]
    encoding = "utf-8" if ir.is_session_info_utf8 else "cp1252"
    return raw.rstrip(b"\x00").decode(encoding, errors="replace")


def extract_yaml_section(raw_yaml: str, section: str) -> str | None:
    """Extract one top-level YAML section while retaining its original text."""
    lines = raw_yaml.splitlines(keepends=True)
    start = next((index for index, line in enumerate(lines) if line.rstrip("\r\n") == f"{section}:"), None)
    if start is None:
        return None

    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and not line[0].isspace() and ":" in line:
            end = index
            break
    return "".join(lines[start:end])


def parse_yaml_section(raw_yaml: str, section: str) -> Any:
    section_text = extract_yaml_section(raw_yaml, section)
    if not section_text:
        return None
    parsed = yaml.safe_load(section_text)
    return parsed.get(section) if isinstance(parsed, dict) else parsed


class StintWriter:
    def __init__(self, root: Path, stint_number: int, setup: Any, raw_yaml: str, metadata: dict[str, Any]) -> None:
        self.directory = root / f"stint-{stint_number:04d}"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.telemetry = (self.directory / "telemetry.jsonl").open("w", encoding="utf-8")
        self.session_updates = (self.directory / "session_info_updates.jsonl").open("w", encoding="utf-8")
        (self.directory / "session_info.yaml").write_text(raw_yaml, encoding="utf-8")
        setup_raw = extract_yaml_section(raw_yaml, "CarSetup")
        if setup_raw:
            (self.directory / "car_setup.yaml").write_text(setup_raw, encoding="utf-8")
        (self.directory / "car_setup.json").write_text(json.dumps(setup, indent=2, default=str), encoding="utf-8")
        (self.directory / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")

    def write_telemetry(self, tick: int, values: dict[str, Any]) -> None:
        self.telemetry.write(json.dumps({"tick": tick, "captured_at": time.time(), "values": values}, default=str) + "\n")
        self.telemetry.flush()

    def write_session_update(self, update: int, raw_yaml: str) -> None:
        self.session_updates.write(json.dumps({"update": update, "raw_yaml": raw_yaml}) + "\n")
        self.session_updates.flush()
        (self.directory / "session_info.yaml").write_text(raw_yaml, encoding="utf-8")

    def close(self) -> None:
        self.telemetry.close()
        self.session_updates.close()


def enrich_catalog_with_profile(catalog: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Add profile status to each header in the catalog.\n    
    Marks which fields are selected by the active profile and which are excluded.
    """
    selected_set = set(profile.get("selected_fields", []))
    for item in catalog:
        if item["name"] in selected_set:
            item["profile_status"] = "selected"
        else:
            item["profile_status"] = "excluded_by_profile"
    return catalog


def export_catalog(root: Path, catalog: list[dict[str, Any]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "live_variables.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    with (root / "live_variables.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(catalog[0]))
        writer.writeheader()
        writer.writerows(catalog)


def is_pit_entry(previous_pit_state: bool, current_pit_state: bool) -> bool:
    return current_pit_state and not previous_pit_state


def is_active_driving_session(values: dict[str, Any]) -> bool:
    """Return True only when the simulator is actively driving on track.

    We intentionally ignore garage/menu states and pit-lane states because those are not a live run.
    """
    if not isinstance(values, dict):
        return False

    is_on_track = bool(values.get("IsOnTrack", False))
    is_on_track_car = bool(values.get("IsOnTrackCar", False))
    in_garage = bool(values.get("IsInGarage", False))
    on_pit_road = bool(values.get("OnPitRoad", False))

    # In the simulator, being in the garage/menu or on pit road is not a live driving state.
    # The session only becomes active once the car is actually on track and not in the garage.
    return is_on_track and is_on_track_car and not in_garage and not on_pit_road


def capture(root: Path, profile_path: Path | None = None, interval: float = 0.0, max_ticks: int | None = None) -> None:
    """Capture live telemetry according to the practice profile.
    
    Args:
        root: Output directory for captures.
        profile_path: Path to practice_profile.json. Defaults to ./practice_profile.json.
        interval: Extra sleep between ticks (0 = no extra delay).
        max_ticks: Stop after this many SDK ticks (None = infinite).
    """
    if profile_path is None:
        profile_path = Path("practice_profile.json")
    
    if not profile_path.exists():
        raise SystemExit(f"Profile not found: {profile_path}")
    
    profile = load_profile(profile_path)
    selected_fields = profile.get("selected_fields", [])
    
    ir = irsdk.IRSDK()
    ir.startup()
    if not ir.is_initialized or not ir.is_connected:
        raise SystemExit("No running iRacing instance was found. Start the simulator first.")

    session_root = root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    catalog = header_catalog(ir)
    catalog = enrich_catalog_with_profile(catalog, profile)
    export_catalog(session_root / "catalog", catalog)
    
    # Validate that selected fields exist in the catalog or are marked unavailable
    available_count = sum(1 for name in selected_fields if any(h["name"] == name for h in catalog))
    
    tick_rate = ir._header.tick_rate
    previous_tick: int | None = None
    previous_pit_state = False
    stint_number = 0
    writer: StintWriter | None = None
    previous_session_update = -1
    ticks_captured = 0
    active_session_started = False

    try:
        while max_ticks is None or ticks_captured < max_ticks:
            ir.freeze_var_buffer_latest()
            tick = ir._var_buffer_latest.tick_count
            if tick == previous_tick:
                if interval:
                    time.sleep(interval)
                continue
            previous_tick = tick
            values, unavailable = read_selected_variables(ir, catalog, selected_fields)
            current_pit_state = bool(values.get("OnPitRoad", False)) if not isinstance(values.get("OnPitRoad"), dict) else False
            session_update = ir.session_info_update
            raw_yaml = raw_session_info(ir)

            driving_active = is_active_driving_session(values)

            # Do not create or write telemetry while the car is in the garage/menu or on pit road.
            # Only begin capture once we have a genuine live driving state.
            if not active_session_started and driving_active:
                setup = parse_yaml_section(raw_yaml, "CarSetup")
                writer = StintWriter(
                    session_root / "stints",
                    stint_number,
                    setup,
                    raw_yaml,
                    {
                        "tick_rate": tick_rate,
                        "started_at": time.time(),
                        "start_reason": "on_track_start",
                        "profile_id": profile.get("profile_id"),
                        "profile_version": profile.get("version"),
                        "selected_field_count": len(selected_fields),
                        "available_field_count": available_count,
                    },
                )
                stint_number += 1
                active_session_started = True
                previous_pit_state = current_pit_state
            elif active_session_started and is_pit_entry(previous_pit_state, current_pit_state):
                if writer:
                    writer.close()
                setup = parse_yaml_section(raw_yaml, "CarSetup")
                writer = StintWriter(
                    session_root / "stints",
                    stint_number,
                    setup,
                    raw_yaml,
                    {
                        "tick_rate": tick_rate,
                        "started_at": time.time(),
                        "start_reason": "pit_entry",
                        "profile_id": profile.get("profile_id"),
                        "profile_version": profile.get("version"),
                        "selected_field_count": len(selected_fields),
                        "available_field_count": available_count,
                    },
                )
                stint_number += 1
                previous_pit_state = current_pit_state
            elif not driving_active:
                # Garage/menu states are intentionally ignored to avoid inflating data collection.
                if writer is not None:
                    writer.close()
                    writer = None
                active_session_started = False
                previous_pit_state = current_pit_state
                if interval:
                    time.sleep(interval)
                continue

            if writer is None:
                if interval:
                    time.sleep(interval)
                continue

            if session_update != previous_session_update:
                writer.write_session_update(session_update, raw_yaml)
                previous_session_update = session_update

            writer.write_telemetry(tick, values)
            previous_pit_state = current_pit_state
            ticks_captured += 1
            if interval:
                time.sleep(interval)
    finally:
        if writer:
            writer.close()
        ir.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture iRacing SDK telemetry using the practice profile.")
    parser.add_argument("--output", type=Path, default=Path("data/captures"), help="Capture root directory.")
    parser.add_argument("--profile", type=Path, default=Path("practice_profile.json"), help="Telemetry profile JSON.")
    parser.add_argument("--interval", type=float, default=0.0, help="Extra sleep after each captured tick.")
    parser.add_argument("--max-ticks", type=int, help="Stop after this many unique SDK ticks; useful for validation.")
    args = parser.parse_args()
    capture(args.output, profile_path=args.profile, interval=max(0.0, args.interval), max_ticks=args.max_ticks)


if __name__ == "__main__":
    main()
