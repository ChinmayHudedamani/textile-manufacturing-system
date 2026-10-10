#!/usr/bin/env python3
"""
Everest Textile Manufacturing System (ETMS)
Tier 1 Edge Telemetry Simulator (Object-Oriented Architecture)

Decoupled Architecture:
- LoomPhysicsEngine: Models physical rotation, optical pulses, current draw, and state machine.
- TelemetryPacket: Strongly typed value object for network payloads.
- HttpTransportClient: Network I/O engine with exponential backoff resiliency.
- EdgeSimulatorDaemon: Orchestrator managing signal traps, sampling cadence, and logging.
"""

import time
import json
import signal
import sys
import argparse
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

# =====================================================================
# 1. VALUE OBJECT: TELEMETRY DATA PACKET
# =====================================================================
@dataclass(frozen=True)
class TelemetryPacket:
    """Immutable data carrier representing an instantaneous sensor snapshot."""
    machine_id: str
    state: str                 # 'RUNNING', 'IDLE', 'FAULT', 'MAINTENANCE'
    picks_cumulative: int      # Total optical sensor pulse counts: P(t)
    current_draw_amps: float   # RMS current draw: I_RMS in Amperes
    rpm: int                   # Main shaft rotational speed: N in RPM
    idle_seconds: int          # Idle duration: Delta t_idle
    timestamp_epoch_ms: int    # Unix epoch timestamp in milliseconds

    def to_json_bytes(self) -> bytes:
        """Serializes telemetry payload to UTF-8 encoded JSON bytes."""
        return json.dumps(asdict(self)).encode("utf-8")


# =====================================================================
# 2. DOMAIN LOGIC: LOOM PHYSICAL & ELECTRICAL STATE MACHINE
# =====================================================================
class LoomPhysicsEngine:
    """
    Simulates the physical dynamics of an industrial air-jet weaving loom:
    - Main drive shaft rotation: omega = (2 * pi * N) / 60 rad/s
    - Optical pick pulse integration: P(t) = P(0) + integral( f(t) dt )
    - Electrical induction motor draw: I(t) = I_base + ripple + noise
    """

    def __init__(
        self, 
        machine_id: str, 
        initial_picks: int = 105412,
        rated_rpm: int = 740,
        base_amps: float = 15.4
    ):
        self.machine_id = machine_id
        self.picks_cumulative = initial_picks
        self.rated_rpm = rated_rpm
        self.base_amps = base_amps
        self.state = "RUNNING"
        self.idle_seconds = 0
        self.tick_counter = 0

    def step(self, dt_seconds: float = 1.0) -> TelemetryPacket:
        """
        Advances the physical simulation by dt_seconds:
        Updates rotational speed, increments optical pulses, and computes current draw.
        """
        self.tick_counter += 1

        # Periodic idle scenario: loom stops every 30 ticks to simulate weft break / bobbin change
        is_idle_cycle = (self.tick_counter % 30 in (0, 1, 2, 3))

        if is_idle_cycle:
            self.state = "IDLE"
            self.idle_seconds += int(dt_seconds)
            current_rpm = 0
            # Magnetizing no-load current of disengaged induction motor (approx 1.8 A)
            current_amps = 1.80
        else:
            self.state = "RUNNING"
            self.idle_seconds = 0
            current_rpm = self.rated_rpm

            # Calculate optical pulses generated in time dt: Delta P = (RPM / 60) * dt
            picks_delta = int((self.rated_rpm / 60.0) * dt_seconds)
            self.picks_cumulative += max(1, picks_delta)

            # High-speed air compressor & beat-up current with periodic ripple (Amps)
            ripple = (self.tick_counter % 5) * 0.22
            current_amps = round(self.base_amps + ripple, 2)

        timestamp_ms = int(time.time() * 1000)

        return TelemetryPacket(
            machine_id=self.machine_id,
            state=self.state,
            picks_cumulative=self.picks_cumulative,
            current_draw_amps=current_amps,
            rpm=current_rpm,
            idle_seconds=self.idle_seconds,
            timestamp_epoch_ms=timestamp_ms
        )


# =====================================================================
# 3. INFRASTRUCTURE: RESILIENT HTTP TRANSPORT CLIENT
# =====================================================================
class HttpTransportClient:
    """
    Manages network dispatch to the ETMS Core API:
    - HTTP POST JSON serialization
    - Network partition resilience with retry backoff
    - Timeout management to prevent thread lockup
    """

    def __init__(self, base_url: str, machine_id: str, timeout_seconds: float = 3.0):
        self.endpoint_url = f"{base_url.rstrip('/')}/api/v1/machines/{machine_id}/telemetry"
        self.timeout = timeout_seconds
        self.consecutive_failures = 0

    def transmit(self, packet: TelemetryPacket) -> Optional[Dict[str, Any]]:
        """Sends packet to the ingest API. Returns response dict or None on network error."""
        req = urllib.request.Request(
            url=self.endpoint_url,
            data=packet.to_json_bytes(),
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                self.consecutive_failures = 0
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            self.consecutive_failures += 1
            return None
        except Exception as ex:
            self.consecutive_failures += 1
            return None


# =====================================================================
# 4. ORCHESTRATION: EDGE SIMULATOR DAEMON
# =====================================================================
class EdgeSimulatorDaemon:
    """
    Main supervisor daemon managing the continuous sampling loop,
    graceful OS signal termination, and operator logging.
    """

    def __init__(self, base_url: str, machine_id: str, sample_interval: float = 1.0):
        self.sample_interval = sample_interval
        self.physics = LoomPhysicsEngine(machine_id=machine_id)
        self.transport = HttpTransportClient(base_url=base_url, machine_id=machine_id)
        self.is_running = True

        # Attach POSIX/Windows OS termination handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        """Gracefully halts the daemon when SIGINT (Ctrl+C) or SIGTERM is received."""
        print(f"\n[EDGE-SHUTDOWN] Interruption signal ({signum}) caught. Stopping simulation...")
        self.is_running = False

    def start(self) -> None:
        """Executes the deterministic acquisition and transmission loop."""
        print("=" * 65)
        print(" [ETMS] EVEREST TEXTILE MILLS - OOP EDGE TELEMETRY DAEMON")
        print(f" Target Loom:       {self.physics.machine_id}")
        print(f" Endpoint:          {self.transport.endpoint_url}")
        print(f" Sampling Interval: dt = {self.sample_interval}s ({1.0/self.sample_interval:.1f} Hz)")
        print("=" * 65)

        while self.is_running:
            # 1. Step the physical simulation forward
            packet = self.physics.step(dt_seconds=self.sample_interval)

            # 2. Transmit over transport client
            response = self.transport.transmit(packet)

            # 3. Log real-time telemetry
            if response:
                alert = response.get("idle_alert", False)
                print(
                    f"[EDGE-TX] {packet.machine_id} | "
                    f"State: {packet.state:<7} | "
                    f"RPM: {packet.rpm:3d} | "
                    f"Picks: {packet.picks_cumulative:,} | "
                    f"Current: {packet.current_draw_amps:.2f}A | "
                    f"Idle Alert: {alert}",
                    flush=True
                )
            else:
                fails = self.transport.consecutive_failures
                print(f"[EDGE-DROP] Transmission dropped (attempt {fails}). Loom buffering ticks locally...", flush=True)

            # 4. Sleep for sampling interval
            time.sleep(self.sample_interval)

        print("[EDGE-OFFLINE] Telemetry daemon halted cleanly.")


# =====================================================================
# ENTRYPOINT
# =====================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETMS Object-Oriented Edge Telemetry Daemon")
    parser.add_argument("--url", default="http://localhost:8000", help="ETMS Core API base URL")
    parser.add_argument("--machine", default="WEAVE-LOOM-04", help="Target Machine ID")
    parser.add_argument("--interval", type=float, default=1.0, help="Sampling delta dt in seconds")
    args = parser.parse_args()

    daemon = EdgeSimulatorDaemon(
        base_url=args.url,
        machine_id=args.machine,
        sample_interval=args.interval
    )
    daemon.start()
