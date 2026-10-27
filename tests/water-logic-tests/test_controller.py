from controller import (WateringController, IDLE, PUMPING, SOAKING, COOLDOWN,
                        elapsed_ms)


class Rig:
    """A controller with a fake clock, fake soil sensor and fake float."""

    def __init__(self, soil=2500, reservoir=True):
        self.soil = soil
        self.reservoir = reservoir
        self.now = 0
        self.pump_log = []
        self.c = WateringController(
            read_soil=lambda: self.soil,
            reservoir_ok=lambda: self.reservoir,
            dry_threshold=1700, wet_threshold=1300,
            pump_ms=5000, soak_ms=90000, max_bursts=3,
            cooldown_ms=1800000, check_ms=60000)

    def run(self, seconds, step_ms=100):
        end = self.now + int(seconds * 1000)
        while self.now < end:
            self.now += step_ms
            self.c.update(self.now)
            self.pump_log.append(self.c.pump_on)

    def bursts(self):
        # Count the pump switching from off to on.
        log = [False] + self.pump_log
        return sum(1 for a, b in zip(log, log[1:]) if b and not a)


def test_wet_soil_never_pumps():
    rig = Rig(soil=500)
    rig.run(600)
    assert not any(rig.pump_log)
    assert rig.c.state == IDLE


def test_dry_soil_starts_pumping_at_the_first_check():
    rig = Rig(soil=2500)
    rig.run(1)
    assert rig.c.state == PUMPING
    assert rig.c.pump_on


def test_dry_soil_with_low_reservoir_does_not_pump():
    rig = Rig(soil=2500, reservoir=False)
    rig.run(300)
    assert not any(rig.pump_log)
    assert "reservoir is low" in rig.c.message


def test_a_burst_lasts_the_set_pump_time():
    rig = Rig(soil=2500)
    rig.run(10)
    on_ms = sum(rig.pump_log) * 100
    assert 4900 <= on_ms <= 5100
    assert rig.c.state == SOAKING


def test_soil_getting_wet_ends_the_episode_after_one_burst():
    rig = Rig(soil=2500)
    rig.run(10)
    rig.soil = 500
    rig.run(91)
    assert rig.c.state == IDLE
    assert rig.c.message == "watered enough"
    assert rig.bursts() == 1


def test_soil_between_the_thresholds_gets_another_burst():
    rig = Rig(soil=2500)
    rig.run(10)
    rig.soil = 1500          # wetter, but not below the wet threshold yet
    rig.run(86)              # lands inside the second burst
    assert rig.c.state == PUMPING
    assert rig.bursts() == 2


def test_no_response_stops_after_max_bursts_then_cools_down():
    rig = Rig(soil=2500)
    rig.run(300)
    assert rig.bursts() == 3
    assert rig.c.state == COOLDOWN
    assert "check pump" in rig.c.message


def test_no_pumping_during_cooldown():
    rig = Rig(soil=2500)
    rig.run(300)
    rig.run(1000)            # well inside the 1800 second cooldown
    assert rig.bursts() == 3
    assert rig.c.state == COOLDOWN


def test_checks_again_after_the_cooldown():
    rig = Rig(soil=2500)
    rig.run(300 + 1800 + 5)
    assert rig.bursts() > 3


def test_reservoir_running_low_mid_burst_stops_the_pump_at_once():
    rig = Rig(soil=2500)
    rig.run(2)
    assert rig.c.pump_on
    rig.reservoir = False
    rig.run(0.2)
    assert not rig.c.pump_on
    assert rig.c.state == IDLE
    assert "ran low" in rig.c.message


def test_reservoir_low_mid_episode_does_not_trigger_the_long_cooldown():
    rig = Rig(soil=2500)
    rig.run(2)
    rig.reservoir = False
    rig.run(0.2)
    rig.reservoir = True     # refilled
    rig.run(61)
    assert rig.c.state in (PUMPING, SOAKING)
    assert rig.c.state != COOLDOWN


def test_reservoir_low_after_the_soak_stops_the_episode():
    rig = Rig(soil=2500)
    rig.run(10)
    rig.reservoir = False
    rig.run(91)
    assert rig.c.state == IDLE
    assert rig.bursts() == 1
    assert "reservoir low" in rig.c.message


def test_pump_is_only_ever_on_in_the_pumping_state():
    rig = Rig(soil=2500)
    for _ in range(3000):
        rig.run(0.1)
        assert rig.c.pump_on == (rig.c.state == PUMPING)


def test_elapsed_time_survives_the_tick_counter_wrapping():
    assert elapsed_ms(5, 0x3FFFFFFF - 5) == 11