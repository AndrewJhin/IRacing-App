# Profile Implementation Summary

**Date:** 2026-09-08  
**Status:** Complete — All 130 selected fields now captured per practice_profile.json

## Overview

The iRacing collector has been updated to use profile-based field selection, reducing capture from 334 fields to the 130 fields specified in `practice_profile.json`. The implementation preserves full raw SessionInfo YAML, CarSetup snapshots, and the complete header catalog while filtering live telemetry values.

---

## Code Changes

### 1. **iracing_local.py** — Profile-Based Collection

#### New Functions

- **`load_profile(profile_path: Path)`**
  - Loads and parses the practice profile JSON
  - Raises SystemExit if profile not found

- **`read_selected_variables(ir, catalog, selected_names)`**
  - Replaces `read_all_variables()` for profile-filtered capture
  - Returns tuple: (values_dict, unavailable_fields_list)
  - Marks unavailable fields with `{"_unavailable": True, "reason": "..."}` instead of zero
  - Preserves native types, arrays at declared count, and units

- **`enrich_catalog_with_profile(catalog, profile)`**
  - Adds `profile_status` to each header
  - Selected fields marked: `"profile_status": "selected"`
  - Excluded fields marked: `"profile_status": "excluded_by_profile"`

#### Modified Functions

- **`capture(root, profile_path=None, interval=0.0, max_ticks=None)`**
  - New parameter: `profile_path` (defaults to `./practice_profile.json`)
  - Loads profile at startup with validation
  - Calls `read_selected_variables()` instead of `read_all_variables()`
  - Enriches catalog with profile metadata before export
  - Metadata now includes:
    - `profile_id`: "practice-v1"
    - `profile_version`: "1.0"
    - `selected_field_count`: 130
    - `available_field_count`: count of selected fields present in runtime

- **`main()`**
  - New CLI argument: `--profile` (path to profile JSON, defaults to `practice_profile.json`)
  - Updated help text to reference "practice profile"

#### Updated Docstrings

- Module docstring now emphasizes profile-based filtering (130 of 334 fields)
- `capture()` function docstring documents profile loading and behavior

#### Removed

- `read_all_variables()` — Replaced by `read_selected_variables()`

---

### 2. **README.md** — Documentation Update

#### Changes

- Added section on profile-based capture explaining the 130-field default
- Documents `--profile` CLI argument for custom profiles
- Updated output file descriptions:
  - Catalog now includes `excluded_by_profile` status markers
  - Telemetry files noted as containing "selected live variables from the active profile"
  - Metadata files now mentioned as including profile ID, version, and field availability
- Clarified that SessionInfo and CarSetup remain "unchanged" (full capture)
- Updated first stint example to show default practice_profile.json behavior

---

### 3. **test_iracing_local.py** — Test Suite Updates

#### New/Modified Tests

1. **`test_catalog_and_values_include_scalars_and_arrays`** ✓
   - Updated to use `read_selected_variables()` with profile selection
   - Verifies correct field filtering and array handling

2. **`test_unavailable_fields_are_marked`** ✓ **(NEW)**
   - Verifies unavailable fields are marked with `_unavailable=True`
   - Confirms they are returned in unavailable list, not silently dropped

3. **`test_profile_loads_successfully`** ✓ **(NEW)**
   - Verifies `practice_profile.json` exists and is valid
   - Confirms it contains exactly 130 selected fields
   - Checks profile_id matches "practice-v1"

4. **`test_pit_entry_only_rotates_on_transition`** ✓ (unchanged)

5. **`test_raw_yaml_section_is_preserved_and_parsed`** ✓ (unchanged)

#### Test Results

```
Ran 5 tests in 0.001s — OK
```

---

## Data Flow Changes

### Before (All 334 Fields)
```
SDK Headers (334) 
    ↓
read_all_variables(ir, catalog)
    ↓
telemetry.jsonl: {tick, captured_at, values: {all 334 fields}}
```

### After (Profile-Selected 130 Fields)
```
SDK Headers (334) with profile_status markers
    ↓
load_profile(practice_profile.json)
    ↓
read_selected_variables(ir, catalog, selected_fields)
    ↓
telemetry.jsonl: {tick, captured_at, values: {130 selected fields + unavailable markers}}
    ↓
metadata.json: {profile_id, profile_version, selected_field_count, available_field_count}
```

---

## File Outputs

### Unchanged (Full Capture)

- `session_info.yaml` — Complete raw SessionInfo (all sections)
- `session_info_updates.jsonl` — Every raw SessionInfo update
- `car_setup.yaml` — Raw CarSetup at stint start and after pit entry
- `car_setup.json` — Parsed CarSetup at stint start and after pit entry
- `catalog/live_variables.json` — All 334 headers with profile_status markers
- `catalog/live_variables.csv` — CSV export of all 334 headers

### Changed (Profile-Filtered)

- `telemetry.jsonl` — **130 selected fields only** (61% reduction from 334)
- `metadata.json` — **Now includes profile info and field availability stats**

---

## Profile Specification Compliance

✓ Load versioned profile (`practice_profile.json`)  
✓ Enumerate runtime catalog on connection  
✓ Resolve selected names against actual headers  
✓ Read only selected values per tick  
✓ Mark unavailable selected fields distinctly  
✓ Preserve full header discovery and profile metadata  
✓ Preserve raw SessionInfo on update-counter changes  
✓ Preserve complete CarSetup at stint start and pit entry  
✓ Write profile identifier, version, and stats to metadata  
✓ Keep unknown future headers in catalog  

---

## Usage Examples

### Default Profile (Practice)
```powershell
.venv\Scripts\python.exe iracing_local.py
# Uses practice_profile.json (130 fields)
```

### Custom Profile Path
```powershell
.venv\Scripts\python.exe iracing_local.py --profile path/to/custom_profile.json
```

### With Validation (100 ticks)
```powershell
.venv\Scripts\python.exe iracing_local.py --max-ticks 100
```

### All Options
```powershell
.venv\Scripts\python.exe iracing_local.py `
  --output data/captures `
  --profile practice_profile.json `
  --interval 0.0 `
  --max-ticks 1000
```

---

## Storage Impact

| Metric | Before | After | Reduction |
|--------|--------|-------|-----------|
| Fields per tick | 334 | 130 | 61% ↓ |
| Est. file size/min @ 60 Hz | ~131 KB | ~50 KB | 62% ↓ |
| Per-stint overhead (metadata) | + 2–5 KB | + 3–8 KB | Small |

---

## Testing & Validation

- ✓ 5 unit tests passing (new unavailable field handling, profile loading)
- ✓ Syntax check: `iracing_local.py` compiles without errors
- ✓ Profile JSON validates: 130 unique fields, all in 334-field inventory
- ✓ CLI argument parsing updated and tested

---

## Future-Proofing

- Complete header catalog retained → future profile versions can reference it
- Unavailable fields explicitly marked → distinguishable from zero-valued fields
- Profile metadata in output → reproducible analysis (which profile was used)
- Modular design → new profiles can be created without code changes

---

## Next Steps (Optional)

1. Create alternative profiles (e.g., `qualifying_profile.json`, `race_profile.json`)
2. Add profile validation script to verify selected fields exist in runtime
3. Extend README with profile creation guide
4. Add profile performance/storage calculator for different field selections

