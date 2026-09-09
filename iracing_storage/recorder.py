"""Bounded batch writer used by the live collector."""

from __future__ import annotations

import time

from .database import Store, sample_row


class RecordingWriter:
    def __init__(self, store: Store, *, profile: dict, catalog: list[dict], source_uri: str,
                 batch_size: int = 60, flush_seconds: float = 1.0):
        if batch_size < 1 or flush_seconds <= 0:
            raise ValueError('Batch size and flush interval must be positive')
        self.store = store
        self.batch_size, self.flush_seconds = batch_size, flush_seconds
        self.pending: list[tuple] = []
        self.sequence = 0
        self.stint_id: int | None = None
        self.snapshot_id: int | None = None
        self.last_flush = time.monotonic()
        self.closed = False
        with store.connection:
            self.recording_id = store.create_recording(profile=profile, catalog=catalog,
                                                       source_kind='live_sdk', source_uri=source_uri)

    def start_stint(self, number: int, metadata: dict, raw_yaml: str) -> None:
        if self.closed:
            raise ValueError('Recording is closed')
        self.flush()
        with self.store.connection:
            self.stint_id = self.store.add_stint(self.recording_id, number, metadata)
            self.snapshot_id = self.store.add_snapshot(self.recording_id, self.stint_id, raw_yaml,
                                                        captured_at=metadata.get('started_at'))

    def session_update(self, update: int, raw_yaml: str) -> None:
        if self.closed or self.stint_id is None:
            raise ValueError('Start a stint before adding a session snapshot')
        self.flush()
        with self.store.connection:
            self.snapshot_id = self.store.add_snapshot(self.recording_id, self.stint_id, raw_yaml,
                                                        update=update, captured_at=time.time())

    def write_sample(self, tick: int, captured_at: float, values: dict) -> None:
        if self.closed or self.stint_id is None or self.snapshot_id is None:
            raise ValueError('A live stint is required')
        self.pending.append(sample_row(self.recording_id, self.sequence, self.stint_id,
                                       self.snapshot_id, tick, captured_at, values))
        self.sequence += 1
        if len(self.pending) >= self.batch_size:
            self.flush()
        else:
            self.flush_if_due()

    def flush_if_due(self) -> None:
        if time.monotonic() - self.last_flush >= self.flush_seconds:
            self.flush()

    def flush(self) -> None:
        if self.pending:
            with self.store.connection:
                self.store.add_samples(self.recording_id, self.pending)
            self.pending.clear()
        self.last_flush = time.monotonic()

    def close(self, status: str = 'completed') -> None:
        if self.closed:
            return
        self.flush()
        with self.store.connection:
            self.store.finish_recording(self.recording_id, status)
        self.closed = True
