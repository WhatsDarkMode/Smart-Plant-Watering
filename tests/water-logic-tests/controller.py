# Watering controller: the decision logic only, with no hardware calls.
# Hardware access is passed in as functions, so this runs unchanged on the
# ESP32 and on a PC under pytest. It never sleeps, so the main loop stays
# free to do other jobs (such as answering Modbus requests) between updates.

IDLE = "idle"
PUMPING = "pumping"
SOAKING = "soaking"
COOLDOWN = "cooldown"

_TICKS_MASK = 0x3FFFFFFF    # MicroPython's ticks_ms() wraps at 2**30


def elapsed_ms(now, since):
    # Milliseconds from 'since' to 'now', safe across the counter wrapping.
    return (now - since) & _TICKS_MASK


class WateringController:
    def __init__(self, read_soil, reservoir_ok, dry_threshold, wet_threshold,
                 pump_ms, soak_ms, max_bursts, cooldown_ms, check_ms):
        self.read_soil = read_soil
        self.reservoir_ok = reservoir_ok
        self.dry_threshold = dry_threshold
        self.wet_threshold = wet_threshold
        self.pump_ms = pump_ms
        self.soak_ms = soak_ms
        self.max_bursts = max_bursts
        self.cooldown_ms = cooldown_ms
        self.check_ms = check_ms

        self.state = IDLE
        self.since = 0              # when the current state began
        self.bursts = 0             # bursts so far in this episode
        self.last_soil = None
        self.message = "starting"
        self._check_now = True      # check straight away on the first update

    @property
    def pump_on(self):
        return self.state == PUMPING

    def _enter(self, state, now_ms, message):
        self.state = state
        self.since = now_ms
        self.message = message

    def update(self, now_ms):
        # Call this often. Returns True if the pump should be running.
        elapsed = elapsed_ms(now_ms, self.since)

        if self.state == IDLE:
            if self._check_now or elapsed >= self.check_ms:
                self._check_now = False
                self.since = now_ms
                self.last_soil = self.read_soil()
                if self.last_soil > self.dry_threshold:
                    if self.reservoir_ok():
                        self.bursts = 1
                        self._enter(PUMPING, now_ms, "soil dry: burst 1")
                    else:
                        self.message = ("soil is dry but reservoir is low: "
                                        "not watering")
                else:
                    self.message = "soil ok"

        elif self.state == PUMPING:
            if not self.reservoir_ok():
                # The interlock is live during the burst, not just between.
                self.bursts = 0
                self._enter(IDLE, now_ms,
                            "reservoir ran low during watering: stopped")
            elif elapsed >= self.pump_ms:
                self._enter(SOAKING, now_ms,
                            "soaking after burst %d" % self.bursts)

        elif self.state == SOAKING:
            if elapsed >= self.soak_ms:
                self.last_soil = self.read_soil()
                if self.last_soil < self.wet_threshold:
                    self.bursts = 0
                    self._enter(IDLE, now_ms, "watered enough")
                elif self.bursts >= self.max_bursts:
                    self._enter(COOLDOWN, now_ms,
                                "soil still dry after %d bursts: check pump, "
                                "tubing, probe" % self.max_bursts)
                elif not self.reservoir_ok():
                    self.bursts = 0
                    self._enter(IDLE, now_ms,
                                "reservoir low: stopped before next burst")
                else:
                    self.bursts += 1
                    self._enter(PUMPING, now_ms,
                                "soil still dry: burst %d" % self.bursts)

        elif self.state == COOLDOWN:
            if elapsed >= self.cooldown_ms:
                self.bursts = 0
                self._check_now = True
                self._enter(IDLE, now_ms, "cooldown over")

        return self.pump_on