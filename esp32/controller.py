# Watering controller: the decision logic only, with no hardware calls.
# Hardware access is passed in as functions, so this runs unchanged on the
# ESP32 and on a PC under pytest. It never sleeps, so the main loop stays
# free to do other jobs (such as answering Modbus requests) between updates.

# Automatic-mode states
IDLE = "idle"
PUMPING = "pumping"
SOAKING = "soaking"
COOLDOWN = "cooldown"
# Manual-mode states
MANUAL = "manual"                  # manual mode, waiting for a request
MANUAL_PUMPING = "manual_pumping"  # one fixed manual burst is running

MODE_AUTO = 0
MODE_MANUAL = 1

# Why the controller last stopped or refused to pump (for Modbus / alarms)
FAULT_NONE = 0
FAULT_RESERVOIR_LOW = 1
FAULT_MANUAL_REFUSED = 2        # gap or hourly limit
FAULT_SOIL_NO_RESPONSE = 3      # burst cap reached, soil never got wet

# Numbers for the Modbus 'state' register
STATE_CODES = {
    IDLE: 0,
    PUMPING: 1,
    SOAKING: 2,
    COOLDOWN: 3,
    MANUAL: 4,
    MANUAL_PUMPING: 5,
}

# Limits for thresholds written from outside (see set_thresholds)
MIN_THRESHOLD = 100
MAX_THRESHOLD = 4000
MIN_GAP = 200                   # wet must stay at least this far below dry

_TICKS_MASK = 0x3FFFFFFF        # MicroPython's ticks_ms() wraps at 2**30
_HOUR_MS = 3600000


def elapsed_ms(now, since):
    # Milliseconds from 'since' to 'now', safe across the counter wrapping.
    return (now - since) & _TICKS_MASK


class WateringController:
    def __init__(self, read_soil, reservoir_ok, dry_threshold, wet_threshold,
                 pump_ms, soak_ms, max_bursts, cooldown_ms, check_ms,
                 manual_pump_ms=5000, manual_gap_ms=10000,
                 manual_timeout_ms=600000, manual_budget_ms=60000):
        self.read_soil = read_soil
        self.reservoir_ok = reservoir_ok
        self.dry_threshold = dry_threshold
        self.wet_threshold = wet_threshold
        self.pump_ms = pump_ms
        self.soak_ms = soak_ms
        self.max_bursts = max_bursts
        self.cooldown_ms = cooldown_ms
        self.check_ms = check_ms
        # Manual-mode limits. These are fixed in firmware, never set remotely.
        self.manual_pump_ms = manual_pump_ms        # one manual burst
        self.manual_gap_ms = manual_gap_ms          # rest between bursts
        self.manual_timeout_ms = manual_timeout_ms  # idle time before Auto
        self.manual_budget_ms = manual_budget_ms    # pump time per hour

        self.mode = MODE_AUTO       # always starts in Auto
        self.state = IDLE
        self.since = 0              # when the current state began
        self.bursts = 0             # bursts so far in this episode
        self.last_soil = None
        self.message = "starting"
        self.fault = FAULT_NONE
        self.manual_request = False  # set from outside, cleared by update()
        self._check_now = True      # check straight away on the first update
        self._manual_activity = 0   # last manual request or burst end
        self._manual_end = None     # when the last manual burst ended
        self._budget_start = None   # start of the current hour window
        self._budget_used = 0       # manual pump ms used in this window

    @property
    def pump_on(self):
        return self.state == PUMPING or self.state == MANUAL_PUMPING

    @property
    def state_code(self):
        return STATE_CODES[self.state]

    def _enter(self, state, now_ms, message):
        self.state = state
        self.since = now_ms
        self.message = message

    def set_thresholds(self, dry, wet):
        # Apply thresholds from outside, clamped so a bad value can never
        # remove the gap between them. Returns the values actually applied.
        dry = max(MIN_THRESHOLD, min(MAX_THRESHOLD, dry))
        wet = max(MIN_THRESHOLD, min(MAX_THRESHOLD, wet))
        if wet > dry - MIN_GAP:
            wet = dry - MIN_GAP
        if wet < MIN_THRESHOLD:
            wet = MIN_THRESHOLD
            dry = wet + MIN_GAP
        self.dry_threshold = dry
        self.wet_threshold = wet
        return dry, wet

    def set_mode(self, mode, now_ms):
        # Switch between Auto and Manual. Anything that isn't a valid mode
        # is ignored. Returns the mode now in force.
        if mode not in (MODE_AUTO, MODE_MANUAL) or mode == self.mode:
            return self.mode
        self.mode = mode
        self.manual_request = False
        self.fault = FAULT_NONE
        self.bursts = 0
        if mode == MODE_MANUAL:
            # Any automatic burst stops here: the state change turns the
            # pump off on the next relay write.
            self._manual_activity = now_ms
            self._enter(MANUAL, now_ms,
                        "manual mode: automatic watering paused")
        else:
            self._check_now = True      # check the soil straight away
            self._enter(IDLE, now_ms, "auto mode: automatic watering resumed")
        return self.mode

    def _try_manual_burst(self, now_ms):
        if not self.reservoir_ok():
            self.fault = FAULT_RESERVOIR_LOW
            self.message = "manual pump refused: reservoir low"
            return
        if self._manual_end is not None:
            wait = self.manual_gap_ms - elapsed_ms(now_ms, self._manual_end)
            if wait > 0:
                self.fault = FAULT_MANUAL_REFUSED
                self.message = ("manual pump refused: wait %d s"
                                % ((wait + 999) // 1000))
                return
        if (self._budget_start is None
                or elapsed_ms(now_ms, self._budget_start) >= _HOUR_MS):
            self._budget_start = now_ms
            self._budget_used = 0
        if self._budget_used + self.manual_pump_ms > self.manual_budget_ms:
            self.fault = FAULT_MANUAL_REFUSED
            self.message = "manual pump refused: hourly limit reached"
            return
        self._budget_used += self.manual_pump_ms
        self.fault = FAULT_NONE
        self._enter(MANUAL_PUMPING, now_ms, "manual pump: burst")

    def update(self, now_ms):
        # Call this often. Returns True if the pump should be running.
        elapsed = elapsed_ms(now_ms, self.since)

        if self.mode == MODE_AUTO:
            self.manual_request = False     # requests are ignored in Auto

        if self.state == IDLE:
            if self._check_now or elapsed >= self.check_ms:
                self._check_now = False
                self.since = now_ms
                self.last_soil = self.read_soil()
                if self.last_soil > self.dry_threshold:
                    if self.reservoir_ok():
                        self.bursts = 1
                        self.fault = FAULT_NONE
                        self._enter(PUMPING, now_ms, "soil dry: burst 1")
                    else:
                        self.fault = FAULT_RESERVOIR_LOW
                        self.message = ("soil is dry but reservoir is low: "
                                        "not watering")
                else:
                    self.fault = FAULT_NONE
                    self.message = "soil ok"

        elif self.state == PUMPING:
            if not self.reservoir_ok():
                # The interlock is live during the burst, not just between.
                self.bursts = 0
                self.fault = FAULT_RESERVOIR_LOW
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
                    self.fault = FAULT_NONE
                    self._enter(IDLE, now_ms, "watered enough")
                elif self.bursts >= self.max_bursts:
                    self.fault = FAULT_SOIL_NO_RESPONSE
                    self._enter(COOLDOWN, now_ms,
                                "soil still dry after %d bursts: check pump, "
                                "tubing, probe" % self.max_bursts)
                elif not self.reservoir_ok():
                    self.bursts = 0
                    self.fault = FAULT_RESERVOIR_LOW
                    self._enter(IDLE, now_ms,
                                "reservoir low: stopped before next burst")
                else:
                    self.bursts += 1
                    self.fault = FAULT_NONE
                    self._enter(PUMPING, now_ms,
                                "soil still dry: burst %d" % self.bursts)

        elif self.state == COOLDOWN:
            if elapsed >= self.cooldown_ms:
                self.bursts = 0
                self._check_now = True
                self.fault = FAULT_NONE
                self._enter(IDLE, now_ms, "cooldown over")

        elif self.state == MANUAL:
            if self.fault == FAULT_RESERVOIR_LOW and self.reservoir_ok():
                self.fault = FAULT_NONE     # the reservoir has recovered
            if self.manual_request:
                self.manual_request = False
                self._manual_activity = now_ms
                self._try_manual_burst(now_ms)
            elif (elapsed_ms(now_ms, self._manual_activity)
                    >= self.manual_timeout_ms):
                # Nobody has used Manual for a while: go back to Auto so the
                # plant is never left unwatered by a forgotten mode switch.
                self.set_mode(MODE_AUTO, now_ms)
                self.message = "manual mode timed out: back to auto"

        elif self.state == MANUAL_PUMPING:
            self.manual_request = False     # no queuing or extending a burst
            if not self.reservoir_ok():
                self._manual_end = now_ms
                self._manual_activity = now_ms
                self.fault = FAULT_RESERVOIR_LOW
                self._enter(MANUAL, now_ms,
                            "reservoir ran low during manual pumping: stopped")
            elif elapsed >= self.manual_pump_ms:
                self._manual_end = now_ms
                self._manual_activity = now_ms
                self._enter(MANUAL, now_ms, "manual burst done")

        return self.pump_on