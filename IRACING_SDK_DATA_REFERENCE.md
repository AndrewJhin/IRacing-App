# iRacing SDK — Telemetry and Setup Data Reference

Version: 0.1 | 2026-09-06 | Project context for Codex

## Scope and accuracy

This is a broad engineering inventory, not a claim that every listed field exists on every vehicle. The authoritative catalog is the variable headers exposed by the running simulator and the raw SessionInfo YAML. Names marked `candidate` or `family` must be verified before implementation. Never fabricate missing channels, infer a field's units from its name, or treat a setup recommendation as a supported SDK write operation.

The local SDK uses Windows shared memory for live variables and YAML for session information. Recorded `.ibt` telemetry is a separate source. The SDK is not the public iRacing Data API. The available variable list depends on the loaded car/session and is fixed for that session. Read the actual header tick rate rather than assuming a fixed sample rate.

References:
- https://github.com/mherbold/IRSDKSharper
- https://github.com/vipoo/irsdk/blob/master/irsdk_defines.h
- https://github.com/kutu/pyirsdk
- https://github.com/SVappsLAB/iRacingTelemetrySDK

## 1. Complete-capture requirement

The collector MUST enumerate every variable header and retain name, description, unit, type, count, offset, and countAsTime where available. Read every value, including arrays and unknown future fields, without requiring a hardcoded whitelist. Preserve raw values and native units. Store the complete raw YAML on every update. Export a catalog from the actual Corvette Z06 GT3.R session before declaring its exact field inventory complete.

Recommended outputs:
```
data/catalog/<car>/<build>/live_variables.json
data/catalog/<car>/<build>/live_variables.csv
data/catalog/<car>/<build>/session_info.yaml
data/catalog/<car>/<build>/car_setup.yaml
data/catalog/<car>/<build>/sample_telemetry.json
```

Catalog columns: `name,description,unit,type,count,count_as_time,source,availability,first_seen_build,last_seen_build`. Availability values: `verified_live`, `verified_ibt`, `verified_both`, `candidate`, `not_available`. Missing is distinct from zero.

## 2. Live telemetry inventory

The following is a discovery checklist. Exact spellings should be checked against the runtime catalog. A family denotes multiple related channels, not a literal SDK field.

### 2.1 Session, timing, and race control

| Data | SDK names / candidates |
|---|---|
| Session clock | `SessionTime`, `SessionTick`, `SessionTimeRemain`, `SessionTimeTotal`, `SessionTimeOfDay` |
| Session identity | `SessionNum`, `SessionState`, `SessionUniqueID`, `SessionFlags` |
| Session distance | `SessionLapsRemain`, `SessionLapsRemainEx`, `SessionLapsTotal` |
| Joker laps | `SessionJokerLapsRemain`, `SessionOnJokerLap` |
| Connection / driving | `IsOnTrack`, `IsOnTrackCar`, `IsInGarage`, `IsReplayPlaying` |
| Replay | `ReplayFrameNum`, `ReplayFrameNumEnd`, `ReplayPlaySpeed`, `ReplayPlaySlowMotion`, `ReplaySessionNum`, `ReplaySessionTime` |
| Camera | `CamCarIdx`, `CamCameraNumber`, `CamGroupNumber`, `CamCameraState` |
| Radio | `RadioTransmitCarIdx`, `RadioTransmitFrequencyIdx`, `RadioTransmitRadioIdx` |
| Race flags | `SessionFlags`, `PlayerCarFlags`, `PaceMode`, `PaceFlags` (verify names) |
| Incidents / penalties | `PlayerCarDriverIncidentCount`, `PlayerCarTeamIncidentCount`, `PlayerCarMyIncidentCount`, `PlayerCarTowTime`, `PlayerCarWeightPenalty` |

### 2.2 Lap timing and player position

`Lap`, `LapCompleted`, `LapDist`, `LapDistPct`, `LapCurrentLapTime`, `LapLastLapTime`, `LapBestLapTime`, `LapBestLap`, `LapLasNLapSeq`, `LapLastNLapTime`, `LapBestNLapTime`, `LapDeltaToBestLap`, `LapDeltaToBestLap_DD`, `LapDeltaToBestLap_OK`, `LapDeltaToOptimalLap`, `LapDeltaToOptimalLap_DD`, `LapDeltaToOptimalLap_OK`, `LapDeltaToSessionBestLap`, `LapDeltaToSessionBestLap_DD`, `LapDeltaToSessionBestLap_OK`, `LapDeltaToSessionOptimalLap`, `LapDeltaToSessionOptimalLap_DD`, `LapDeltaToSessionOptimalLap_OK`, `PlayerCarPosition`, `PlayerCarClassPosition`, `PlayerCarClass`, `PlayerCarIdx`, `PlayerCarNumber`, `PlayerCarPitSvStatus`, `PlayerCarInPitStall`, `PlayerCarSLFirstRPM`, `PlayerCarSLShiftRPM`, `PlayerCarSLLastRPM`, `PlayerCarSLBlinkRPM`.

### 2.3 Driver inputs and steering

`Throttle`, `Brake`, `Clutch`, `SteeringWheelAngle`, `SteeringWheelAngleMax`, `SteeringWheelTorque`, `SteeringWheelTorque_ST`, `SteeringWheelPctTorque`, `SteeringWheelPctTorqueSign`, `SteeringWheelPctDamper`, `SteeringWheelPctIntensity`, `SteeringWheelPctSmoothing`, `SteeringWheelMaxForceNm`, `SteeringWheelUseLinear`, `SteeringWheelLimiter`, `SteeringWheelLimiterMax`, `SteeringWheelPeakForceNm`, `SteeringWheelPeakForceNm_ST`, `SteeringWheelPeakForceNmMin`, `SteeringWheelPeakForceNmMax` (verify optional names).

### 2.4 Speed, engine, transmission, fuel, and electrical

`Speed`, `RPM`, `Gear`, `ShiftIndicatorPct`, `ShiftPowerPct`, `ShiftGrindRPM`, `EngineWarnings`, `OilTemp`, `OilPress`, `WaterTemp`, `WaterLevel`, `FuelLevel`, `FuelLevelPct`, `FuelUsePerHour`, `FuelPress`, `ManifoldPress`, `Voltage`, `Engine0_RPM`, `Engine0_OilTemp`, `Engine0_OilPress`, `Engine0_WaterTemp`, `Engine0_FuelPressure`, `Engine0_ManifoldPressure` (engine-family candidates), `FuelUsePerLap`, `FuelUsePerHour`, `FuelLevel`, `FuelLevelPct`.

Additional vehicle-specific candidates: engine torque, engine power, boost, turbo speed, exhaust temperature, battery state of charge, hybrid deployment, regenerative braking, energy remaining, motor temperature, and engine-map state. Do not assume these are exposed on a GT3 car.

### 2.5 Vehicle dynamics and position

`LatAccel`, `LongAccel`, `VertAccel`, `LatAccel_ST`, `LongAccel_ST`, `VertAccel_ST`, `Roll`, `Pitch`, `Yaw`, `YawNorth`, `RollRate`, `PitchRate`, `YawRate`, `RollRate_ST`, `PitchRate_ST`, `YawRate_ST`, `VelocityX`, `VelocityY`, `VelocityZ`, `VelocityX_ST`, `VelocityY_ST`, `VelocityZ_ST`, `Lat`, `Lon`, `Alt`, `Lat_ST`, `Lon_ST`, `Alt_ST`.

Other candidate channels: `PitchRate_ST`, `RollRate_ST`, `YawRate_ST`, `VelocityX_ST`, `VelocityY_ST`, `VelocityZ_ST`, `LatAccel_ST`, `LongAccel_ST`, `VertAccel_ST`, `Speed_ST`. Verify coordinate frames and units from the header. Do not equate yaw rate with understeer or assume a GPS coordinate is a precise track-map position.

### 2.6 Four-corner suspension, tires, and brakes

For each corner prefix `LF`, `RF`, `LR`, `RR`, discover all matching headers. Common engineering families include:

| Family | Example names / patterns | Notes |
|---|---|---|
| Ride height | `LFrideHeight`, `RFrideHeight`, `LRrideHeight`, `RRrideHeight` | May be recorded-only or absent live. |
| Shock displacement | `LFshockDefl`, `RFshockDefl`, `LRshockDefl`, `RRshockDefl` | Car/source dependent. |
| Shock velocity | `LFshockVel`, `RFshockVel`, `LRshockVel`, `RRshockVel` | Car/source dependent. |
| Wheel speed | `LFspeed`, `RFspeed`, `LRspeed`, `RRspeed` | Verify exact units and availability. |
| Tire temperature | `LFtempL`, `LFtempM`, `LFtempR` and equivalent corners | L/R are physical tire sides, not universally inner/outer. |
| Tire wear | `LFwearL`, `LFwearM`, `LFwearR` and equivalent corners | Often garage/recording dependent. |
| Tire pressure | `LFpressure`, `LFcoldPressure` and equivalent corners | Verify names and update semantics. |
| Brake temperature | Corner-specific brake-temperature candidates | Discover exact names; not guaranteed. |
| Tire contact / rumble | Corner-specific rumble/contact candidates | Not a guaranteed direct grip measurement. |

Additional candidate families: suspension force, damper force, wheel load, tire load, tire slip ratio, tire slip angle, tire carcass temperature, brake pressure, brake torque, brake wear, and ABS intervention. These are desired engineering channels, not guaranteed SDK outputs. Mark unavailable when absent rather than synthesizing them as raw telemetry.

### 2.7 Weather and track conditions

`AirTemp`, `TrackTemp`, `TrackTempCrew`, `AirDensity`, `AirPressure`, `RelativeHumidity`, `WindVel`, `WindDir`, `FogLevel`, `SolarAltitude`, `SolarAzimuth`, `TrackWetness`, `Precipitation`, `WeatherDeclaredWet`, `Skies`, `TrackWater`, `TrackWaterDepth` (verify optional names). Preserve exact units and enum definitions. Record weather and track-condition YAML as well.

### 2.8 Pit service and strategy

`OnPitRoad`, `PlayerCarInPitStall`, `PitSvStatus`, `PitSvFlags`, `PitSvFuel`, `PitSvLFP`, `PitSvRFP`, `PitSvLRP`, `PitSvRRP`, `PitSvAutoFuel`, `PitSvAutoFuelMargin`, `PitRepairLeft`, `PitOptRepairLeft`, `TireSetsAvailable`, `TireSetsUsed`, `PlayerCarPitSvStatus`, `PlayerCarTowTime`, `PlayerCarInPitStall`, `PitstopActive`, `PitstopTime`, `PitstopTotalTime` (verify optional names).

### 2.9 Competitor arrays

Discover the full `CarIdx*` family. Common fields include:

`CarIdxLap`, `CarIdxLapCompleted`, `CarIdxLapDistPct`, `CarIdxPosition`, `CarIdxClassPosition`, `CarIdxTrackSurface`, `CarIdxTrackSurfaceMaterial`, `CarIdxOnPitRoad`, `CarIdxLastLapTime`, `CarIdxBestLapTime`, `CarIdxBestLapNum`, `CarIdxEstTime`, `CarIdxF2Time`, `CarIdxPaceLine`, `CarIdxPaceRow`, `CarIdxPaceFlags`, `CarIdxSessionFlags`, `CarIdxGear`, `CarIdxRPM`, `CarIdxSteer`, `CarIdxThrottle`, `CarIdxBrake`, `CarIdxClutch`, `CarIdxTireCompound`, `CarIdxTireType`, `CarIdxFuelPct`, `CarIdxPower`, `CarIdxWeightPenalty`, `CarIdxClass`, `CarIdxDriverIdx`, `CarIdxRadioIdx` (verify optional names).

Arrays must retain their declared count. Use `DriverInfo.Drivers[].CarIdx` to join car indices to identities. Never assume all competitor inputs, fuel, or vehicle dynamics are available.

### 2.10 In-car adjustments (`dc*`)

Enumerate every header beginning with `dc` and retain its description and unit. Common or candidate examples include `dcBrakeBias`, `dcTractionControl`, `dcTractionControl2`, `dcABS`, `dcThrottleShape`, `dcEngineBraking`, `dcFuelMixture`, `dcEngineMap`, `dcBoostLevel`, `dcDiffPreload`, `dcAntiRollFront`, `dcAntiRollRear`, `dcWeightJacker`, `dcDashPage`, `dcTearOffVisor`, `dcPitSpeedLimiterToggle`, `dcStarter`, `dcIgnition`, `dcHeadlightFlash`, `dcRainLight`, `dcWiper`, `dcWiperSpeed`, `dcDRS`, `dcPushToPass`, `dcHybridDeploy`, `dcHybridRegen`.

These are discovery candidates, not a promise that a given car supports them. Some adjustment fields have related `dc*Change`, `dc*Old`, or `dc*Str` variants. Preserve all discovered fields. The garage setup and current in-car adjustment state are different concepts.

### 2.11 Additional families to enumerate

Capture every header matching or related to: `PlayerCar*`, `CarIdx*`, `Lap*`, `Session*`, `Pit*`, `Steering*`, `Engine*`, `Fuel*`, `Tire*`, `LF*`, `RF*`, `LR*`, `RR*`, `dc*`, `dp*`, `Replay*`, `Cam*`, `Radio*`, `Weather*`, `Track*`, `Pace*`, `Is*`, `Shift*`, `Energy*`, `Hybrid*`, and `DRS*`. Do not limit collection to these prefixes: unknown fields must also be retained.

## 2.12 Verified live capture inventory

The collector currently captures every variable exposed by the running simulator's SDK header. This inventory was generated from a live validation session on 2026-09-06 and contains 334 variables. It is session-specific and can change with car, simulator build, replay state, or session type. The collector also writes the field metadata to `catalog/live_variables.json` and `catalog/live_variables.csv`.

`[6]` means a six-element high-rate sample; `[64]` means a competitor array indexed by `CarIdx`. Every listed field is written to `telemetry.jsonl` on each unique SDK tick. The exact verified names are:

```text
AirDensity, AirPressure, AirTemp, Brake, BrakeABSactive, BrakeRaw,
CamCameraNumber, CamCameraState, CamCarIdx, CamGroupNumber, CarDistAhead, CarDistBehind,
CarIdxBestLapNum[64], CarIdxBestLapTime[64], CarIdxClass[64], CarIdxClassPosition[64], CarIdxEstTime[64], CarIdxF2Time[64], CarIdxFastRepairsUsed[64], CarIdxGear[64], CarIdxLap[64], CarIdxLapCompleted[64], CarIdxLapDistPct[64], CarIdxLastLapTime[64], CarIdxOnPitRoad[64], CarIdxP2P_Count[64], CarIdxP2P_Status[64], CarIdxPaceFlags[64], CarIdxPaceLine[64], CarIdxPaceRow[64], CarIdxPosition[64], CarIdxQualTireCompound[64], CarIdxQualTireCompoundLocked[64], CarIdxRPM[64], CarIdxSessionFlags[64], CarIdxSteer[64], CarIdxTireCompound[64], CarIdxTrackSurface[64], CarIdxTrackSurfaceMaterial[64],
CarLeftRight, ChanAvgLatency, ChanClockSkew, ChanLatency, ChanPartnerQuality, ChanQuality, Clutch, ClutchRaw, CpuUsageBG, CpuUsageFG,
dcABS, dcBrakeBias, dcDashPage, DCDriversSoFar, dcHeadlightFlash, DCLapStatus, dcLowFuelAccept, dcPitSpeedLimiterToggle, dcStarter, dcToggleWindshieldWipers, dcTractionControl, dcTractionControlToggle, dcTriggerWindshieldWipers, DisplayUnits,
dpFastRepair, dpFuelAddKg, dpFuelAutoFillActive, dpFuelAutoFillEnabled, dpFuelFill, dpLFTireChange, dpLFTireColdPress, dpLRTireChange, dpLRTireColdPress, dpRFTireChange, dpRFTireColdPress, dpRRTireChange, dpRRTireColdPress, dpWindshieldTearoff,
DriverMarker, Engine0_RPM, EngineWarnings, EnterExitReset, FastRepairAvailable, FastRepairUsed, FogLevel, FrameRate, FrontTireSetsAvailable, FrontTireSetsUsed, FuelLevel, FuelLevelPct, FuelPress, FuelUsePerHour, Gear, GpuUsage, HandbrakeRaw,
IsDiskLoggingActive, IsDiskLoggingEnabled, IsGarageVisible, IsInGarage, IsOnTrack, IsOnTrackCar, IsReplayPlaying,
Lap, LapBestLap, LapBestLapTime, LapBestNLapLap, LapBestNLapTime, LapCompleted, LapCurrentLapTime, LapDeltaToBestLap, LapDeltaToBestLap_DD, LapDeltaToBestLap_OK, LapDeltaToOptimalLap, LapDeltaToOptimalLap_DD, LapDeltaToOptimalLap_OK, LapDeltaToSessionBestLap, LapDeltaToSessionBestLap_DD, LapDeltaToSessionBestLap_OK, LapDeltaToSessionLastlLap, LapDeltaToSessionLastlLap_DD, LapDeltaToSessionLastlLap_OK, LapDeltaToSessionOptimalLap, LapDeltaToSessionOptimalLap_DD, LapDeltaToSessionOptimalLap_OK, LapDist, LapDistPct, LapLasNLapSeq, LapLastLapTime, LapLastNLapTime,
LatAccel, LatAccel_ST[6], LeftTireSetsAvailable, LeftTireSetsUsed, LFbrakeLinePress, LFcoldPressure, LFodometer, LFshockDefl, LFshockDefl_ST[6], LFshockVel, LFshockVel_ST[6], LFtempCL, LFtempCM, LFtempCR, LFTiresAvailable, LFTiresUsed, LFwearL, LFwearM, LFwearR,
LoadNumTextures, LongAccel, LongAccel_ST[6], LRbrakeLinePress, LRcoldPressure, LRodometer, LRshockDefl, LRshockDefl_ST[6], LRshockVel, LRshockVel_ST[6], LRtempCL, LRtempCM, LRtempCR, LRTiresAvailable, LRTiresUsed, LRwearL, LRwearM, LRwearR,
ManifoldPress, ManualBoost, ManualNoBoost, MemPageFaultSec, MemSoftPageFaultSec, OilLevel, OilPress, OilTemp, OkToReloadTextures, OnPitRoad, P2P_Count, P2P_Status, PaceMode, Pitch, PitchRate, PitchRate_ST[6], PitOptRepairLeft, PitRepairLeft, PitsOpen, PitstopActive, PitSvFlags, PitSvFuel, PitSvLFP, PitSvLRP, PitSvRFP, PitSvRRP, PitSvTireCompound,
PlayerCarClass, PlayerCarClassPosition, PlayerCarDriverIncidentCount, PlayerCarDryTireSetLimit, PlayerCarIdx, PlayerCarInPitStall, PlayerCarMyIncidentCount, PlayerCarPitSvStatus, PlayerCarPosition, PlayerCarPowerAdjust, PlayerCarSLBlinkRPM, PlayerCarSLFirstRPM, PlayerCarSLLastRPM, PlayerCarSLShiftRPM, PlayerCarTeamIncidentCount, PlayerCarTowTime, PlayerCarWeightPenalty, PlayerFastRepairsUsed, PlayerIncidents, PlayerTireCompound, PlayerTrackSurface, PlayerTrackSurfaceMaterial, Precipitation, PushToPass, PushToTalk, RaceLaps, RadioTransmitCarIdx, RadioTransmitFrequencyIdx, RadioTransmitRadioIdx, RearTireSetsAvailable, RearTireSetsUsed, RelativeHumidity,
ReplayFrameNum, ReplayFrameNumEnd, ReplayPlaySlowMotion, ReplayPlaySpeed, ReplaySessionNum, ReplaySessionTime,
RFbrakeLinePress, RFcoldPressure, RFodometer, RFshockDefl, RFshockDefl_ST[6], RFshockVel, RFshockVel_ST[6], RFtempCL, RFtempCM, RFtempCR, RFTiresAvailable, RFTiresUsed, RFwearL, RFwearM, RFwearR,
RightTireSetsAvailable, RightTireSetsUsed, Roll, RollRate, RollRate_ST[6], RPM, RRbrakeLinePress, RRcoldPressure, RRodometer, RRshockDefl, RRshockDefl_ST[6], RRshockVel, RRshockVel_ST[6], RRtempCL, RRtempCM, RRtempCR, RRTiresAvailable, RRTiresUsed, RRwearL, RRwearM, RRwearR,
SessionFlags, SessionJokerLapsRemain, SessionLapsRemain, SessionLapsRemainEx, SessionLapsTotal, SessionNum, SessionOnJokerLap, SessionState, SessionTick, SessionTime, SessionTimeOfDay, SessionTimeRemain, SessionTimeTotal, SessionUniqueID,
Shifter, ShiftGrindRPM, ShiftIndicatorPct, ShiftPowerPct, Skies, SolarAltitude, SolarAzimuth, Speed, SteeringFFBEnabled, SteeringWheelAngle, SteeringWheelAngleMax, SteeringWheelLimiter, SteeringWheelMaxForceNm, SteeringWheelPctDamper, SteeringWheelPctIntensity, SteeringWheelPctSmoothing, SteeringWheelPctTorque, SteeringWheelPctTorqueSign, SteeringWheelPctTorqueSignStops, SteeringWheelPeakForceNm, SteeringWheelTorque, SteeringWheelTorque_ST[6], SteeringWheelUseLinear, Throttle, ThrottleRaw,
TireLF_RumblePitch, TireLR_RumblePitch, TireRF_RumblePitch, TireRR_RumblePitch, TireSetsAvailable, TireSetsUsed, TrackTemp, TrackTempCrew, TrackWetness, VelocityX, VelocityX_ST[6], VelocityY, VelocityY_ST[6], VelocityZ, VelocityZ_ST[6], VertAccel, VertAccel_ST[6], VidCapActive, VidCapEnabled, Voltage, WaterLevel, WaterTemp, WeatherDeclaredWet, WindDir, WindVel, Yaw, YawNorth, YawRate, YawRate_ST[6]
```

The storage split is intentional: live telemetry contains all 334 fields per tick; raw `SessionInfo` YAML is recorded when its SDK update counter changes; `CarSetup` is written once when a stint starts and once after each detected pit entry. This inventory is the review baseline before trimming. Any reduced field set should be explicit and versioned, while unavailable fields remain unavailable rather than being replaced with zero.

## 3. SessionInfo YAML inventory

Store the entire raw YAML, not only selected fields. Common top-level sections include `WeekendInfo`, `SessionInfo`, `DriverInfo`, `CarSetup`, `CameraInfo`, `RadioInfo`, `SplitTimeInfo`, and `QualifyResultsInfo`. Sections and nested keys vary by simulator version and event.

### WeekendInfo

Discover track ID/name/configuration, length, direction, location, altitude, pit speed limit, track type, event/session identifiers, race week, event type, official status, series, team racing, driver swaps, cautions, standing starts, incident limits, weather, track state, and weekend options. Examples: `TrackID`, `TrackName`, `TrackDisplayName`, `TrackConfigName`, `TrackLength`, `TrackLengthOfficial`, `TrackDirection`, `TrackCity`, `TrackCountry`, `TrackAltitude`, `TrackPitSpeedLimit`, `TrackType`, `TrackWeatherType`, `TrackSkies`, `TrackSurfaceTemp`, `TrackAirTemp`, `TrackAirPressure`, `TrackWindVel`, `TrackWindDir`, `TrackRelativeHumidity`, `TrackFogLevel`, `TrackCleanup`, `TrackDynamicTrack`, `SeriesID`, `SeasonID`, `SessionID`, `SubSessionID`, `RaceWeek`, `EventType`, `Category`, `TeamRacing`, `MinDrivers`, `MaxDrivers`, `DCRuleSet`, `QualifyScoring`, `CourseCautions`, `StandingStart`, `Restarts`, `IncidentLimit`, `FastRepairsLimit`, `GreenWhiteCheckeredLimit`, `NightMode`, `IsOfficial`, `IsFixedSetup` (verify exact keys).

### DriverInfo

Store `DriverInfo` in full. Discover `DriverCarIdx`, `DriverUserID`, `PaceCarIdx`, `DriverHeadPosX`, `DriverHeadPosY`, `DriverHeadPosZ`, `DriverCarIdleRPM`, `DriverCarRedLine`, `DriverCarEngCylinderCount`, `DriverCarFuelKgPerLtr`, `DriverCarFuelMaxLtr`, `DriverCarMaxFuelPct`, `DriverCarGearNumForward`, `DriverCarShiftLight*`, `DriverCarSL*`, `DriverCarEstLapTime`, `DriverCarPitTrkPct`, `DriverCarPitTrkPct`, `DriverCarClass`, `DriverCarClassRelSpeed`, `DriverCarClassMaxFuelPct`, `DriverCarClassWeightPenalty`, `DriverCarClassDryTireSetLimit`, `DriverCarClassColor`, `DriverCarClassEstLapTime`, and all other available car properties.

For each `Drivers[]` entry discover `CarIdx`, `UserName`, `AbbrevName`, `Initials`, `UserID`, `TeamID`, `TeamName`, `CarNumber`, `CarNumberRaw`, `CarPath`, `CarClassID`, `CarID`, `CarIsPaceCar`, `CarIsAI`, `CarIsElectric`, `CarScreenName`, `CarScreenNameShort`, `CarClassShortName`, `CarClassRelSpeed`, `CarClassLicenseLevel`, `CarClassMaxFuelPct`, `CarClassWeightPenalty`, `CarClassDryTireSetLimit`, `CarClassColor`, `CarClassEstLapTime`, `IRating`, `LicLevel`, `LicSubLevel`, `LicString`, `LicColor`, `ClubName`, `DivisionName`, `HelmetType`, `CarDesignStr`, `CarNumberDesignStr`, `HelmetDesignStr`, `SuitDesignStr`, `BodyType`, `FaceType`, `HelmetPattern`, `SuitPattern` (verify optional keys). Treat driver identifiers as personal data and avoid unnecessary retention or publication.

### SessionInfo and results

Discover `Sessions[]`, `SessionNum`, `SessionLaps`, `SessionTime`, `SessionNumLapsToAvg`, `SessionType`, `SessionTrackRubberState`, `SessionName`, `SessionSubType`, `SessionSkipped`, `SessionRunGroupsUsed`, `SessionEnforceTireCompoundChange`, `SessionResultsPositions`, `SessionResultsFastestLap`, `SessionResultsAverageLapTime`, `SessionResultsNumCautionFlags`, `SessionResultsNumCautionLaps`, `SessionResultsNumLeadChanges`, `SessionResultsLapsComplete`, `SessionResultsOfficial`, `SessionResultsPenalty`, `SessionResultsDriver`, `SessionResultsCar`, `SessionResultsReasonOut`, `SessionResultsReasonOutStr` (verify optional names).

Store complete nested result rows, including position, class position, car index, lap count, last/best/average lap times, incidents, laps led, reason out, and points where provided. Also retain `QualifyResultsInfo`, `SplitTimeInfo`, `CameraInfo`, and `RadioInfo` without filtering.

## 4. CarSetup — complete discovery and modeling requirements

### 4.1 What is actually available

`CarSetup` is a nested YAML section whose structure is vehicle-specific. The SDK does not define a universal flat setup schema. The exact Corvette Z06 GT3.R setup must be captured from the simulator. A garage setting may have a display label, value, unit, options, or additional metadata, but these are not guaranteed to follow one universal representation. Preserve the raw tree and build a normalized view separately.

A setup snapshot is not equivalent to an editable `.sto` file. The SDK's telemetry and broadcast interface does not provide a general-purpose arbitrary garage-setup writer. Treat `.sto` parsing, validation, and generation as a separate, versioned, experimentally verified subsystem. Never claim that a generated setup is valid without testing it in iRacing.

### 4.2 Setup inventory (all categories to discover)

The following are garage concepts, not literal YAML paths or guaranteed options. The collector must enumerate every actual `CarSetup` leaf, including unknown or car-specific sections.

#### Tires and wheels
- Tire compound / dry or wet selection; tire set selection.
- LF/RF/LR/RR cold pressures and any displayed hot pressures.
- Tire temperatures (inner/middle/outer), wear, and condition when included in setup/garage information.
- Tire stagger, circumference, diameter, or other tire-specific parameters where supported.
- Tire-set limits and tire-service options, which may instead belong to session/pit metadata.

#### Chassis and geometry
- Front and rear ride heights; individual corner ride heights if adjustable.
- Front and rear spring rates; corner spring rates; spring perch offsets.
- Front/rear anti-roll bar size, blade position, arm position, or stiffness.
- Front and rear toe; individual wheel toe where supported.
- Front and rear camber; caster; steering ratio; steering offset.
- Wheelbase, track width, bump steer, roll-center, or geometry settings where adjustable.
- Crossweight, corner weights, ballast, weight distribution, and ballast position.
- Third springs/heave springs, bump stops, packers, bump rubber gap/rate, and travel limits.
- Suspension travel, droop, pushrod length, and other vehicle-specific geometry.

#### Dampers
- LF/RF/LR/RR low-speed compression and low-speed rebound.
- LF/RF/LR/RR high-speed compression and high-speed rebound.
- Damper clicks, slopes, knee speeds, or other multi-adjustable damper settings.
- Third/heave damper settings where available.
- Damper-specific constraints, ranges, and coupled settings.

#### Aerodynamics
- Front splitter, front wing, dive planes, or front aero configuration.
- Rear wing angle, rear wing configuration, gurney, and aero balance controls.
- Rake, ride-height-dependent aero settings, and underfloor/diffuser-related options.
- Cooling ducts, radiator openings, brake ducts, and other drag/cooling tradeoffs.
- Aero balance, downforce, drag, or platform readouts if shown in the garage.

#### Brakes
- Brake bias, master cylinder sizes, pedal ratio, brake pressure settings.
- Front/rear brake pad compound, brake ducts, brake cooling.
- ABS settings or profiles where configurable in the garage.
- Brake balance readouts and any car-specific brake-system options.

#### Drivetrain and differential
- Differential preload, power ramp, coast ramp, clutch plates, locking settings.
- Final drive, gear ratios, gear stack, transmission options.
- Clutch, engine braking, throttle map, traction control, ABS, and engine-map defaults where configurable.
- Differential and drivetrain cooling or other car-specific settings.

#### Fuel, electronics, and strategy
- Starting fuel quantity and fuel capacity restrictions.
- Fuel mixture, engine map, boost, energy deployment, or hybrid settings where supported.
- Traction control, ABS, throttle shape, brake migration, and other electronic defaults.
- Pit-service defaults, tire changes, fuel additions, and fast repair (may be separate from CarSetup).

#### Other car-specific setup sections
- Steering, suspension geometry, chassis stiffness, wheel alignment, engine, cooling, transmission, electronics, aero, and any future sections not listed above.
- Preserve read-only garage measurements and calculated values separately from adjustable parameters.

### 4.3 Normalized setup parameter schema

```json
{
  "parameter_id": "car-specific-stable-id",
  "raw_path": ["CarSetup", "..."],
  "display_name": "Rear wing angle",
  "raw_value": "example only",
  "numeric_value": null,
  "unit": null,
  "category": "aero",
  "corner": null,
  "axle": "rear",
  "adjustable": null,
  "minimum": null,
  "maximum": null,
  "step": null,
  "allowed_values": null,
  "source": "session_info",
  "verified": false
}
```

Do not invent limits, increments, dependencies, or units. Extract them from actual garage data, verified setup files, or a separately maintained car-specific ruleset. Store the original value string even when a numeric representation is parsed.

### 4.4 Setup snapshots and comparison

Every run should retain:
- Simulator build, car ID/path, track ID/configuration, session ID, and timestamp.
- Raw CarSetup YAML and a content hash.
- Normalized setup parameter values and a setup version identifier.
- Original `.sto` file and its hash if the user explicitly imports it.
- Fuel load, tire compound/set, weather, track temperature, wetness, and track state.
- Driver feedback, setup changes, run purpose, and baseline relationship.
- Validation status: `imported`, `sdk_snapshot`, `generated_unverified`, `validated_in_sim`, `rejected`.

A setup comparison must show raw old/new values, units, and the source of each value. Never infer that a change caused an improvement without accounting for conditions and driver variation.

## 5. Data architecture for the analytics platform

### Raw capture

Collect all live variables at the actual SDK rate. Preserve native units, arrays, bitfields, and source timestamps. Store raw YAML updates and immutable setup snapshots. A writer queue should prevent dashboard or AI processing from blocking the capture loop. Track dropped frames and reconnects.

### Storage model

Suggested entities: `sessions`, `runs`, `laps`, `telemetry_samples`, `telemetry_variable_catalog`, `session_info_snapshots`, `setup_snapshots`, `setup_parameters`, `setup_changes`, `driver_feedback`, `derived_metrics`, `analysis_reports`.

For high-frequency data, use columnar files such as Parquet for historical analytics and a small relational database for metadata. Preserve raw data even when normalized fields are added. Do not force all car-specific channels into a fixed SQL table.

### Derived analytics (not raw SDK fields)

- Corner entry/apex/exit speed, braking point, brake release, throttle pickup, minimum speed.
- Distance-aligned lap delta, sector delta, consistency, and fuel-corrected comparisons.
- Steering demand, yaw response, rotation timing, understeer/oversteer indicators.
- Tire pressure/temperature/wear trends, wheel-speed differences, suspension travel and bottoming indicators where measured.
- Setup A/B comparisons, driver feedback correlation, confidence and uncertainty.

Derived metrics must record their formula, source channels, units, assumptions, and version. Missing direct tire forces or slip angles must not be presented as measured values.

## 6. Codex implementation task

Build a Windows-compatible iRacing SDK discovery and capture module. Use a maintained wrapper or a direct shared-memory reader. Do not hardcode the telemetry catalog. On connection, enumerate all variable headers and export the catalog. Read every field and array using its declared type/count. Capture raw SessionInfo YAML and extract CarSetup without dropping unknown keys. Save a sample snapshot and a short recording. Implement graceful handling of missing fields, reconnects, simulator shutdown, and session changes. Include tests using synthetic headers and YAML fixtures so development does not require the simulator to be running.

Acceptance criteria:
1. Every discovered variable is present in the exported catalog.
2. Every variable can be read without a hardcoded field-specific accessor.
3. Arrays retain their declared count and car-index mapping.
4. Raw YAML is preserved exactly, with a parsed copy available separately.
5. CarSetup is exported as raw YAML and a flattened parameter inventory.
6. Missing fields are represented as unavailable, not zero.
7. No setup-write or `.sto` generation capability is claimed until separately implemented and validated.
8. The Corvette/Suzuka catalog can be generated from a real session and used to replace all candidate names in this reference with verified names.

## 7. Corrections and cautions for earlier planning

Some commonly circulated telemetry lists mix live fields, recorded-only fields, deprecated names, and derived metrics. This document intentionally labels uncertain families rather than asserting they are all live. Tire temperature/wear, ride height, shock velocity, brake temperature, and setup values must be verified for the actual car and source. The SDK is not a direct measurement of tire grip, tire slip angle, or setup quality. The first engineering milestone is an accurate raw data inventory, not an AI recommendation engine.
