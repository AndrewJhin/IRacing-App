import unittest
from pathlib import Path

from iracing_local import extract_yaml_section, header_catalog, is_active_driving_session, is_pit_entry, load_profile, parse_yaml_section, read_selected_variables


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


if __name__ == "__main__":
    unittest.main()