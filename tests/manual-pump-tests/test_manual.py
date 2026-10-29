# Tests for manual mode, threshold clamping and the fault codes.
# Standalone: has its own fake clock, soil sensor and reservoir switch.

from controller import (
    WateringController, MODE_AUTO, MODE_MANUAL,
    IDLE, PUMPING, SOAKING, COOLDOWN, MANUAL, MANUAL_PUMPING,
    FAULT_NONE, FAULT_RESERVOIR_LOW, FAULT_MANUAL_REFUSED,
    FAULT_SOIL_NO_RESPONSE,
)

STEP = 100  # ms per update, like the real main loop


class Rig:
    def __init__(self, soil=500, reservoir=True, **kw):
        self.now = 0
        self.soil = soil
        self.reservoir = reservoir
        self.pump_ms_total = 0
        self.c = WateringController(
            read_soil=lambda: self.soil,
            reservoir_ok=lambda: self.reservoir,
            dry_threshold=1700, wet_threshold=1300,
            pump_ms=5000, soak_ms=90000, max_bursts=3,
            cooldown_ms=1800000, check_ms=60000, **kw)

    def run(self, ms):
        for _ in range(ms // STEP):
            self.now += STEP
            if self.c.update(self.now):
                self.pump_ms_total += STEP

    def manual(self):
        self.c.set_mode(MODE_MANUAL, self.now)

    def request(self):
        self.c.manual_request = True


# ---------- Manual mode ----------

def test_starts_in_auto():
    r = Rig()
    assert r.c.mode == MODE_AUTO


def test_request_ignored_in_auto():
    r = Rig(soil=500)
    r.request()
    r.run(1000)
    assert r.pump_ms_total == 0
    assert r.c.manual_request is False


def test_switching_to_manual_stops_automatic_burst_at_once():
    r = Rig(soil=2500)
    r.run(1000)
    assert r.c.state == PUMPING and r.c.pump_on
    r.c.set_mode(MODE_MANUAL, r.now)
    assert r.c.update(r.now + STEP) is False
    assert r.c.state == MANUAL


def test_manual_request_runs_one_fixed_burst():
    r = Rig()
    r.manual()
    r.request()
    r.run(10000)
    assert r.pump_ms_total == 5000
    assert r.c.state == MANUAL
    assert r.c.fault == FAULT_NONE


def test_manual_does_not_start_without_request():
    r = Rig(soil=2500)
    r.manual()
    r.run(120000)
    assert r.pump_ms_total == 0


def test_manual_refused_when_reservoir_low():
    r = Rig(reservoir=False)
    r.manual()
    r.request()
    r.run(2000)
    assert r.pump_ms_total == 0
    assert r.c.fault == FAULT_RESERVOIR_LOW


def test_reservoir_loss_mid_manual_burst_stops_pump_at_once():
    r = Rig()
    r.manual()
    r.request()
    r.run(2000)
    assert r.c.pump_on
    r.reservoir = False
    r.now += STEP
    assert r.c.update(r.now) is False
    assert r.c.state == MANUAL
    assert r.c.fault == FAULT_RESERVOIR_LOW


def test_request_during_burst_does_not_extend_it():
    r = Rig()
    r.manual()
    r.request()
    r.run(2000)
    r.request()
    r.run(10000)
    assert r.pump_ms_total == 5000


def test_second_request_inside_gap_is_refused_then_allowed():
    r = Rig()
    r.manual()
    r.request()
    r.run(5200)                  # burst over, gap running
    r.request()
    r.run(500)
    assert r.c.fault == FAULT_MANUAL_REFUSED
    assert r.pump_ms_total == 5000
    r.run(10000)                 # gap over
    r.request()
    r.run(6000)
    assert r.pump_ms_total == 10000
    assert r.c.fault == FAULT_NONE


def test_hourly_budget_limits_total_manual_pumping():
    r = Rig()                    # budget 60 s = 12 bursts of 5 s
    r.manual()
    for _ in range(12):
        r.request()
        r.run(5200)
        r.run(10000)
    assert r.pump_ms_total == 60000
    r.request()
    r.run(1000)
    assert r.pump_ms_total == 60000
    assert r.c.fault == FAULT_MANUAL_REFUSED
    assert "hourly" in r.c.message


def test_hourly_budget_resets_after_an_hour():
    r = Rig(manual_timeout_ms=10 * 3600000)
    r.manual()
    for _ in range(12):
        r.request()
        r.run(5200)
        r.run(10000)
    r.run(3600000)
    r.request()
    r.run(6000)
    assert r.pump_ms_total == 65000


def test_manual_times_out_back_to_auto():
    r = Rig(soil=500)
    r.manual()
    r.run(599000)
    assert r.c.mode == MODE_MANUAL
    while r.c.mode == MODE_MANUAL:
        r.run(STEP)
    assert r.c.state == IDLE
    assert "timed out" in r.c.message


def test_manual_activity_restarts_the_timeout():
    r = Rig(soil=500)
    r.manual()
    r.run(540000)                # 9 minutes
    r.request()
    r.run(6000)
    r.run(540000)                # 9 more minutes, still inside the timeout
    assert r.c.mode == MODE_MANUAL
    r.run(120000)
    assert r.c.mode == MODE_AUTO


def test_invalid_mode_is_ignored():
    r = Rig()
    assert r.c.set_mode(7, r.now) == MODE_AUTO
    assert r.c.set_mode(-1, r.now) == MODE_AUTO
    r.manual()
    assert r.c.set_mode(7, r.now) == MODE_MANUAL


def test_back_to_auto_checks_soil_straight_away():
    r = Rig(soil=2500)
    r.manual()
    r.run(5000)
    r.c.set_mode(MODE_AUTO, r.now)
    r.run(300)
    assert r.c.state == PUMPING
    assert r.c.pump_on


def test_switching_mode_clears_pending_request_and_fault():
    r = Rig(reservoir=False)
    r.manual()
    r.request()
    r.run(500)
    assert r.c.fault == FAULT_RESERVOIR_LOW
    r.c.set_mode(MODE_AUTO, r.now)
    assert r.c.fault == FAULT_NONE
    assert r.c.manual_request is False


# ---------- Threshold clamping ----------

def test_thresholds_applied_when_valid():
    r = Rig()
    assert r.c.set_thresholds(1800, 1200) == (1800, 1200)
    assert r.c.dry_threshold == 1800 and r.c.wet_threshold == 1200


def test_wet_is_pulled_below_dry_to_keep_the_gap():
    r = Rig()
    assert r.c.set_thresholds(1000, 900) == (1000, 800)
    assert r.c.set_thresholds(1000, 2000) == (1000, 800)


def test_values_are_clamped_to_the_allowed_range():
    r = Rig()
    assert r.c.set_thresholds(5000, 100) == (4000, 100)
    assert r.c.set_thresholds(0, 0) == (300, 100)
    assert r.c.set_thresholds(65535, 65535) == (4000, 3800)


def test_new_thresholds_change_behaviour():
    r = Rig(soil=1500)
    r.run(1000)
    assert r.pump_ms_total == 0          # 1500 is below dry 1700
    r.c.set_thresholds(1400, 1000)
    r.run(61000)                         # next soil check
    assert r.pump_ms_total > 0


# ---------- Fault codes in Auto ----------

def test_fault_reservoir_low_in_auto():
    r = Rig(soil=2500, reservoir=False)
    r.run(500)
    assert r.pump_ms_total == 0
    assert r.c.fault == FAULT_RESERVOIR_LOW


def test_fault_soil_no_response_then_clears():
    r = Rig(soil=2500)
    r.run(3 * (5000 + 90000) + 2000)
    assert r.c.state == COOLDOWN
    assert r.c.fault == FAULT_SOIL_NO_RESPONSE
    r.run(1800000 + 1000)
    assert r.c.state == PUMPING          # soil still dry: a fresh episode
    assert r.c.fault == FAULT_NONE


def test_auto_watering_still_works():
    r = Rig(soil=2500)
    r.run(1000)
    assert r.c.pump_on
    r.run(5000)
    assert r.c.state == SOAKING
    r.soil = 500
    r.run(90000)
    assert r.c.state == IDLE
    assert r.c.message == "watered enough"
    assert r.pump_ms_total == 5000
    assert r.c.fault == FAULT_NONE