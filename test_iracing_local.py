import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from iracing_local import capture, main, extract_yaml_section, header_catalog, is_active_driving_session, is_pit_entry, load_profile, parse_yaml_section, read_selected_variables


class Header:
    def __init__(self, name, desc, unit, type_code, count, count_as_time=False):
        self.name = name
        self.desc = desc
        self.unit = unit
        self.type = type_code
        self.count = count
        self.count_as_time = count_as_time


class FakeSDK:
    _var_headers = [
        Header("Speed", "Vehicle speed", "m/s", 4, 1),
        Header("CarIdxLap", "Lap number", "", 2, 3),
    ]

    def __getitem__(self, name):
        return {"Speed": 12.5, "CarIdxLap": [1, 2, 3]}[name]


class CollectorTests(unittest.TestCase):
    def test_catalog_and_values_include_scalars_and_arrays(self):
        sdk = FakeSDK()
        catalog = header_catalog(sdk)

        self.assertEqual([item["name"] for item in catalog], ["Speed", "CarIdxLap"])
        self.assertEqual(catalog[1]["count"], 3)
        values, unavailable = read_selected_variables(sdk, catalog, ["Speed", "CarIdxLap"])
        self.assertEqual(values["CarIdxLap"], [1, 2, 3])
        self.assertEqual(len(unavailable), 0)

    def test_unavailable_fields_are_marked(self):
        sdk = FakeSDK()
        catalog = header_catalog(sdk)
        values, unavailable = read_selected_variables(sdk, catalog, ["Speed", "NonExistentField"])
        self.assertEqual(unavailable, ["NonExistentField"])
        self.assertTrue(values["NonExistentField"].get("_unavailable"))

    def test_raw_yaml_section_is_preserved_and_parsed(self):
        raw = "WeekendInfo:\n  TrackName: Suzuka\nCarSetup:\n  Chassis:\n    RideHeight: 55 mm\nDriverInfo:\n  DriverCarIdx: 0\n"

        self.assertEqual(
            extract_yaml_section(raw, "CarSetup"),
            "CarSetup:\n  Chassis:\n    RideHeight: 55 mm\n",
        )
        self.assertEqual(parse_yaml_section(raw, "CarSetup")["Chassis"]["RideHeight"], "55 mm")

    def test_pit_entry_only_rotates_on_transition(self):
        self.assertTrue(is_pit_entry(False, True))
        self.assertFalse(is_pit_entry(True, True))
        self.assertFalse(is_pit_entry(False, False))

    def test_profile_loads_successfully(self):
        """Verify that practice_profile.json exists and is valid."""
        profile_path = Path("practice_profile.json")
        self.assertTrue(profile_path.exists(), "practice_profile.json must exist")
        profile = load_profile(profile_path)
        self.assertIn("selected_fields", profile)
        self.assertIn("profile_id", profile)
        self.assertEqual(len(profile["selected_fields"]), 130)
        self.assertIn("practice-v1", profile["profile_id"])

    def test_active_driving_session_requires_track_activity(self):
        self.assertFalse(is_active_driving_session({"IsOnTrack": False, "IsOnTrackCar": False, "IsInGarage": True, "OnPitRoad": False}))
        self.assertFalse(is_active_driving_session({"IsOnTrack": False, "IsOnTrackCar": False, "IsInGarage": False, "OnPitRoad": True}))
        self.assertTrue(is_active_driving_session({"IsOnTrack": True, "IsOnTrackCar": True, "IsInGarage": False, "OnPitRoad": False}))
        self.assertFalse(is_active_driving_session({'IsOnTrack': {'_unavailable': True}, 'IsOnTrackCar': True}))

    def test_waiting_for_simulator_can_be_cancelled_without_a_recording(self):
        sdk = Mock(is_initialized=False, is_connected=False)
        with tempfile.TemporaryDirectory() as directory, \
             patch('iracing_local.irsdk.IRSDK', return_value=sdk), \
             patch('iracing_local.time.sleep', side_effect=KeyboardInterrupt):
            root = Path(directory) / 'captures'
            self.assertEqual(capture(root, no_database=True), 'interrupted')
            self.assertFalse(root.exists())
        sdk.startup.assert_called_once()
        self.assertTrue(sdk.shutdown.called)

    def test_command_reconnects_after_disconnect_but_stops_on_interrupt(self):
        with patch('sys.argv', ['iracing_local.py']), \
             patch('iracing_local.capture', side_effect=['completed', 'interrupted']) as run:
            main()
        self.assertEqual(run.call_count, 2)

    def test_bounded_capture_does_not_restart(self):
        with patch('sys.argv', ['iracing_local.py', '--max-ticks', '120']), \
             patch('iracing_local.capture', return_value='completed') as run:
            main()
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
