# Tests for the 24-hour cap on automatic pumping.

from controller import (
    WateringController, MODE_MANUAL, IDLE,
    FAULT_NONE, FAULT_DAILY_LIMIT,
)

DAY = 86400000


class Rig:
    def __init__(self, soil=2500, budget=60000, step=500):
        self.now = 0
        self.soil = soil
        self.step = step
        self.pump_total = 0
        self.c = WateringController(
            read_soil=lambda: self.soil, reservoir_ok=lambda: True,
            dry_threshold=1700, wet_threshold=1300,
            pump_ms=5000, soak_ms=90000, max_bursts=3,
            cooldown_ms=1800000, check_ms=60000,
            auto_daily_budget_ms=budget)

    def run(self, ms):
        for _ in range(ms // self.step):
            self.now += self.step
            if self.c.update(self.now):
                self.pump_total += self.step


def test_no_cap_by_default_runs_every_cycle():
    r = Rig(budget=None)
    r.run(DAY - 1000)
    assert r.pump_total > 60000          # a dry probe keeps pumping all day


def test_cap_limits_a_day_of_a_probe_that_never_gets_wet():
    r = Rig(budget=60000)
    r.run(DAY - 1000)
    assert r.pump_total <= 60000
    assert r.pump_total >= 55000         # it did use its allowance


def test_blocked_start_reports_the_daily_limit_fault():
    r = Rig(budget=0)
    r.run(2000)
    assert r.pump_total == 0
    assert r.c.state == IDLE
    assert r.c.fault == FAULT_DAILY_LIMIT
    assert "daily" in r.c.message


def test_cap_stops_the_next_burst_mid_episode():
    r = Rig(budget=10000)                # two 5 s bursts
    r.run(5 * 60 * 1000)
    assert r.pump_total == 10000
    assert r.c.state == IDLE
    assert r.c.fault == FAULT_DAILY_LIMIT


def test_pumping_resumes_after_24_hours():
    r = Rig(budget=10000)
    r.run(10 * 60 * 1000)
    assert r.pump_total == 10000
    r.run(DAY)                           # window rolls over
    assert r.pump_total >= 20000


def test_wet_soil_clears_the_fault():
    r = Rig(budget=0)
    r.run(2000)
    assert r.c.fault == FAULT_DAILY_LIMIT
    r.soil = 500
    r.run(61000)                         # next soil check
    assert r.c.fault == FAULT_NONE
    assert r.c.message == "soil ok"


def test_manual_pumping_is_not_blocked_by_the_automatic_cap():
    r = Rig(budget=0)
    r.run(2000)
    r.c.set_mode(MODE_MANUAL, r.now)
    r.c.manual_request = True
    r.run(6000)
    assert r.pump_total == 5000