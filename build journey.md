## Build Steps taken
1. Repurposed the ESP32 from the sensor project for this project.
    - The board still had the sensor project's 'main.py' on it, which
      runs automatically on every boot. Removed it, along with
      'config.py', 'db.py' and 'bme280_float.py'. Kept 'wifi.py' 
      (its 'connect()' function takes the credentials as arguments, 
      so it isn't tied to the sensor project) and left 'boot.py' alone.
    - Confirmed my PC copy of the sensor project's 'node/config.py'
      existed before deleting the board's copy, since it's gitignored
      and not in the repo.
    - Unplugged the BME280 wiring. The sensor project's node is now
      paused (historical data and the deployed dashboard remain intact).
2. Wired and tested the relay module with no load connected.
    - Stripped three female-to-female jumpers and clamped the bare ends in
      the relay's screw terminals: red to DC+, black to DC-, yellow to
      IN. The female ends went on the ESP32's VIN/5V, GND and pin 26.
    - Wrote 'esp32/relay_test.py' assuming a low-level trigger, from the
      listing title. After the script finished the green relay LED was
      still on, and it went dark when the pin went low, the opposite of
      what I expected.
    - The listing's specification describes a high/low jumper cap, and
      mine was not on the L position, so the module triggers on HIGH
      despite the listing title. Left the cap where it was and flipped
      the code, naming the polarity as constants (RELAY_ON = 1,
      RELAY_OFF = 0) rather than bare 0s and 1s. Confirmed the green
      LED (the relay-on indicator, separate from the red PWR LED) is
      dark during OFF stages, lit during ON, with a click at each
      change.
2. Wired and tested the float switch.
    - Joined each of the float's two bare leads to a stripped jumper wire
      (twisted, then [taped separately / left untaped for the bench test]).
      The switch has no polarity, so it doesn't matter which lead goes
      where: one jumper went to pin 25 and the other to GND. Used pin 25
      rather than the planned pin 27 because it avoided tangling wires with
      the relay; it's a digital input with an internal pull-up, so WiFi
      later won't affect it.
    - Wrote 'esp32/float_test.py': pin 25 as an input with the internal
      pull-up enabled, printing its value every half second.
    - Moved the float along the stem (by hand, [and in a cup of water]) and
      recorded the behaviour. With the float down the pin reads 0 (switch
      closed, pulling the pin to ground). Raised to about halfway up the
      stem it reads 1 (switch open, pin held high by the pull-up). The
      change is clean, with no flicker.
    - So: 1 = float up = water present, 0 = float down = water low.
    - Noted for the interlock: with this orientation, a broken or
      disconnected wire would also read 1, i.e. "water present", which is
      the unsafe way to fail for a pump interlock. To revisit before
      relying on it.
3. Wired the pump circuit through the relay. Not yet powered or tested.
    - Gave the pump its own power path, separate from the ESP32's: Anker
      charger USB-A port, then a male USB-to-screw-terminal adapter, then
      the relay, then a female adapter that receives the pump's USB plug.
      The relay's output contacts are electrically isolated from its
      control side, so the pump circuit doesn't connect to the ESP32 or
      its ground. The ESP32 only drives the relay's IN terminal from
      pin 26.
    - The relay switches the positive wire only: male adapter VBUS to
      relay COM, and relay NO to the female adapter's VBUS. The negative
      wire runs straight from the male adapter's GND to the female
      adapter's GND. Used NO (normally open) rather than NC, so the pump
      is off whenever the relay is off or the board is resetting.
    - Used only the VBUS and GND terminals on each adapter and ignored
      D+, D- and shield. [Read the printed labels on both adapters before
      wiring.]
    - Made the connecting wires from three jumper wires with the
      connectors cut off both ends, stripped and clamped under the screw
      terminals, [red for the + side and black for the - side], and
      tugged each one to check it held.
    - Checked the relay's boot state before connecting the pump: with pin
      26 set to input, as it is at every power-up, the relay stayed off
      and the green LED stayed dark.
4. Tested the pump through the relay.
    - Wrote 'esp32/pump_test.py': sets pin 26 to the relay's off state at
      startup, switches the relay on for a fixed time (PUMP_SECONDS = 2),
      then off. The off command is in a try/finally so the relay is
      always released, even if the script is interrupted. Polarity is
      held in named constants (RELAY_ON = 1, RELAY_OFF = 0), since this
      module triggers on HIGH.
    - Ran it with the pump fully submerged in a jug of water. 
      The relay clicked on, the pump ran, and it stopped with a second click 
      after the set time.
5. Got the capacitance sensor reading.
    - First two sensors read a flat 0 through the supplied cable and my
      splices, while pin 34 itself tested fine (4095 touched to 3.3V, 0
      to GND). A third sensor, wired with jumpers into the supplied
      connector, worked immediately. [I believe the other 2 sensors may
      have been faulty.]
    - Readings with the third sensor on [3.3V]: about 2500 in air
      (2481-2544), falling to about 590 in a cup of water (582-621),
      settling over roughly 50 seconds. Dry is high and wet is low, as
      expected for a capacitive sensor.
6. Wrote the combined local watering script and bench-tested it with
     forced readings. Not yet run on the real plant.
    - Soil readings from the pot: about 2100 bone dry, about 750 well
      soaked. Set provisional thresholds with a deliberate gap between
      them: start watering when the average reading goes above 1700, 
      count it as watered once it drops below 1300. The gap is far wider 
      than the roughly +/-20 wobble seen in earlier readings.
    - Wrote 'esp32/watering_local.py': averages ten soil readings, checks
      the float before every burst, runs the pump in short bursts (changed
      from 3 to 5 seconds after testing, still provisional until the final
      tubing is in place), waits for the water to reach the probe, then
      rechecks. Settings sit in named constants at the top, including the
      relay polarity (RELAY_ON = 1, RELAY_OFF = 0) and the float
      polarity (FLOAT_WATER_PRESENT = 1).
    - Safeguards: the relay is set to off the instant the script starts
      and in a try/finally, so it is released however the script ends; a
      cap of three bursts per episode, followed by a 30-minute cooldown if
      the soil never responds, which also limits dry running if the float
      ever misreports.
    - Decided a float that reads 0 when no water is present counts as
      "reservoir low", matching what I measured. Known weakness: a broken
      float lead reads 1, which looks like "water present". The burst cap
      is the safety net, and flipping the float later is a one-line
      change to FLOAT_WATER_PRESENT.
    - Reviewing the script, noticed both failure paths returned the same
      result, so a reservoir running low mid-episode triggered the full
      30-minute cooldown even though refilling would fix it. Changed
      water_episode() to return why it ended (WATERED, RESERVOIR_LOW or
      NO_RESPONSE), with a separate message for each, and the cooldown
      only for NO_RESPONSE.
    - Bench-tested over the sink with the pump in a cup of water, forcing
      the soil reading in code rather than moving the probe:
        - Test 1, float down with a forced dry reading of 2500: printed
          "soil is dry but reservoir is low" and the pump never ran. Pass.
        - Test 2, float up with a forced dry reading: three bursts, then
          the "soil still dry after 3 bursts" message and the cooldown.
          Also checked it with a loop feeding incrementing readings. Pass.
        - Test 3, forced wet reading of 500: only the status line printed,
          no pumping. Correct, since wet soil needs no watering.
        - Test 4, soil dry then turning wet after the first burst: still
          to run. A constant reading can't test it, because watering never
          starts, so it needs a fake that starts at 2500 and returns 500
          after about 8 seconds.
    - Ran the script from Thonny, not saved as main.py, since the
      unattended-operation safeguards (Auto/Manual states, restart
      behaviour) aren't built yet.
7. Separated the watering decision logic from the hardware code and tested it 
   with automated simulations.
    - Generated 'controller.py', containing a standalone 'WateringController' 
      state machine, and 'test_controller.py', containing automated tests for 
      its watering decisions. The controller receives soil readings and reservoir
      status through functions, rather than accessing the ESP32 hardware directly. 
      This lets the same logic run on a PC without the physical sensors or pump.
    - The controller uses four states: IDLE (waiting for the next soil check),
      PUMPING (running a timed burst), SOAKING (allowing water to spread
      before rechecking the soil), and COOLDOWN (waiting 30 minutes after
      three bursts before trying again).
    - Kept the main safeguards: check the reservoir before pumping and
      during each burst, limit each watering episode to three bursts, stop
      once the soil reading falls below the wet threshold, and enter cooldown
      if the soil never responds. The controller also uses elapsed-time
      checks rather than blocking sleeps, leaving the main loop free to
      perform other tasks.
    - Created a PC-side test harness ('Rig') with a fake clock, fake soil
      sensor and fake reservoir switch. This simulates changes in soil
      moisture and reservoir level while recording when the pump should be
      on or off. No physical hardware is operated by these tests.
    - Added 'pytest.ini' with '[pytest]' and 'pythonpath = .' so pytest can
      import 'controller.py' from the project directory.
    - Ran the automated tests on the PC using pytest. All 14 tests passed,
      covering wet and dry soil, reservoir-low conditions, five-second
      watering bursts, the soak-and-recheck cycle, repeat bursts, the
      three-burst limit, cooldown behaviour, reservoir loss during watering,
      consistency of the pump state, and timer-counter wraparound.
    - These results confirm that the controller behaves as expected in the
      simulated scenarios. They do not test the actual plant response.
    - The controller and tests are currently a separate implementation of the
      watering logic, not yet integrated into the existing
      'esp32/watering_local.py' script. 
8. Ran the controller on the board and bench-tested it with forced readings.
    - Uploaded 'controller.py' and 'watering_main.py' to the board (File,
      Save as, MicroPython device) and ran 'watering_main.py' from Thonny
      with F5, so nothing is saved as 'main.py'. [Confirmed 'import
      controller' worked first time / fixed a syntax error MicroPython
      rejected.]
    - Setup for each test: pump in a jug of water, float
      switch to hand, ESP32 on the PC's USB. For the soil reading I
      temporarily forced a value inside 'read_soil()' and removed it afterwards.
    - Tests, all run on the real board with the real relay and float:
        - Float down with a forced dry reading of 2500: the pump never
          started. Pass.
        - Float up with a forced dry reading: bursts, soak, rechecks.
          Pass. [Add whether it reached the three-burst cap and cooldown.]
        - Forced wet reading of 500: status lines only, no pumping. Pass.
        - Dry, then wet after the first burst (a fake returning 2500 for
          8 seconds, then 500): one burst, a soak, 'watered enough', back
          to idle, no second burst. Pass. The printout looked slightly
          confused, with a 'soaking | soil: 2500' status line just before
          'watered enough'. [Confirm the cause, probably the status line
          printing before the fake flipped to 500 / or drop this line.]
        - Float lowered mid-burst: the pump stopped at once. Pass.
    - The ESP32 does not reset when the pump starts, which closes the
      question I had left open since the pump test.
    - Removed every forced value afterwards and checked 'read_soil()' is
      back to returning the real average. [Also set 'SOAK_SECONDS' back to
      90 if I shortened it.]
    - These tests prove the controller's decisions on the real hardware.
      They don't test the real soil sensor in the pot or the final tubing.
9. Decided to keep the float switch orientation (ADR-004).
    - Wanted to flip the float so that a broken lead would read as
      'reservoir low' (fail-safe). Realised I can't physically reverse the
      float, and the orientation is set by the hardware, not the code.
    - Rejected changing only 'FLOAT_WATER_PRESENT' to 0, because float up
      would then read as 'reservoir low' and float down as 'water
      present', which inverts the interlock and would run the pump with
      an empty reservoir. Rewiring doesn't help either: a broken lead and
      a raised float are both open circuits to the ESP32.
    - Kept 'FLOAT_WATER_PRESENT = 1' and accepted the known weakness. The
      safety net is the layered safeguards: relay off at startup,
      'try/finally' release, 5-second bursts, the three-burst cap and the
      cooldown. Written up as 'decisions/0004-float-orientation-kept.md'.
    - Two real fixes remain if I need them later: a float with the
      opposite contact type, or a supervised input (a resistor across the
      switch read on an ADC1 pin).
    - Updated 'plant-build-guide.md' to match (Steps 1.2, 2.2, 2.3 and 2.4
      and the progress table).
10. Started Stage 3: WiFi, the Modbus library, and a first read from the PC.
    - Created 'esp32/config.py' with the WiFi credentials and confirmed it
      is gitignored with 'git check-ignore -v esp32/config.py', which
      matched the '**/config.py' rule. Saved a copy to the board.
    - Reused the existing 'wifi.py' from the sensor project. Its
      'connect()' takes the credentials as arguments and returns True or
      False without printing anything on failure, so the test script
      prints the result. It connected and the board got an IP address.
    - Installed the library over WiFi with
      'mip.install('github:brainelectronics/micropython-modbus')'.
      [Confirm 'import umodbus' ran without errors.] Its docs call the
      register-holding device a 'TCP client (slave)'; in standard Modbus
      terms the ESP32 is the server and Ignition will be the client.
    - Wrote 'esp32/modbus_test.py', the library's own TCP example with its
      default dummy registers (including holding register 93 = 19). It
      touches no pins, so the relay and pump are not involved. [Pump
      charger unplugged for this.]
    - Installed 'pymodbus' (3.16.1) on the PC and read register 93 from
      the ESP32. It returned [19]. Pass: the ESP32 answers Modbus TCP
      requests from the PC. The default device ID of 1 worked.
11. Checked that the Modbus server doesn't block the loop, and tested a write.
    - Replaced the loop in 'modbus_test.py' with one that counts how many
      times 'process()' runs in 5 seconds. Idle, it ran about 6,400 times
      per 5 seconds (the first window was 3,764). So 'process()' returns
      straight away when no request is waiting, and the controller loop
      won't be held up by it. Pass.
    - Read register 93 from the PC while that loop was running and it
      still returned [19]. The count dipped slightly to about 5,200 to
      6,500 while requests were handled. Pass.
    - Wrote 42 to holding register 93 from the PC and read it back as
      [42]. So the ESP32 accepts writes as well as reads. Pass.

12. Designed the register map and decided to add Manual mode (ADR-005).
    - Designed the map on paper before touching the code. Modbus only
      lets a client write coils and holding registers, so readings go in
      input registers and discrete inputs, which are read-only by design.
        - Coil 0: manual pump request.
        - Holding registers: 0 dry threshold, 1 wet threshold, 2 mode
          (0 Auto, 1 Manual).
        - Input registers: 0 soil reading, 1 state, 2 burst count, 3
          heartbeat (seconds, wraps at 65535), 4 fault code.
        - Discrete inputs: 0 pump on, 1 reservoir ok.
    - Decided I want to be able to command the pump from Ignition, so
      added a Manual mode instead of keeping Ignition monitor-only. The
      controller enforces every limit itself, whatever Ignition writes:
      one fixed 5-second burst per request (not a hold-to-run switch),
      the reservoir interlock before and during the burst, a 10-second
      gap between bursts, a cap of 60 seconds of manual pumping per hour,
      and a fall-back to Auto after 10 minutes of no manual activity. The
      board always starts in Auto with no request pending. Pump timings
      stay fixed in the firmware, and threshold writes are clamped so the
      gap between dry and wet can't be removed.
    - Rejected: monitor-only, hold-to-run, bypassing the reservoir check,
      and unlimited manual bursts. Written up as
      'decisions/0005-manual-pump-control.md'.

13. Added Manual mode and the Modbus layer to the code, and unit-tested it.
    - 'controller.py': added the 'manual' and 'manual_pumping' states, a
      mode switch, threshold clamping, fault codes (0 ok, 1 reservoir
      low, 2 manual refused, 3 soil not responding) and the manual limits
      above. Automatic behaviour is unchanged. The 'state' register now
      has six values (0 idle, 1 pumping, 2 soaking, 3 cooldown, 4 manual,
      5 manual pumping).
    - 'watering_main.py': sets the relay off before any other import, and
      starts WiFi without waiting for it, so the controller runs whether
      or not WiFi, the library or Ignition are available. It no longer
      uses 'wifi.py'. A blocking reconnect inside the loop could leave the
      pump running past its burst. Modbus errors are caught and printed,
      so they can never stop the loop.
    - Found my copy of 'watering_main.py' still had a leftover
      'return 2000' in 'read_soil()' and 'SOAK_SECONDS = 10' from the
      bench tests. The new file restores 'total // 10' and 90. [Checked
      the repo copy and the copy on the board.]
    - Added 'test_manual.py' with 23 tests: manual bursts, refusals, the
      gap, the hourly cap, the timeout, mode switching mid-burst,
      threshold clamping and fault codes.
    - Mistakes getting pytest to run:
        - Ran 'python test_controller.py', which printed nothing because
          the file only defines tests. Tests are run with 'pytest'.
        - 'python test_manual.py' failed with 'No module named
          controller', because plain Python only looks in the file's own
          folder. A stale copy of 'controller.py' in the tests folder
          would also have shadowed the real one, so I deleted it.
        - 'pytest' tried to run my hardware scripts ('relay_test.py' and
          the others, which match '*_test.py') and failed on 'import
          machine'. Fixed with one 'pytest.ini' in the repo root
          ('pythonpath = esp32', 'testpaths = tests', 'python_files =
          test_*.py').
        - The ini file first failed with 'unexpected value continuation'
          because a line was indented. Rewrote it from the command line.
    - Ran 'pytest' from the repo root: 37 passed (my 14 original tests
      plus the 23 new ones). The 14 passing means Automatic behaviour
      didn't change. [Added '.pytest_cache/' to '.gitignore'.]

14. Tested Manual mode and the Modbus registers on the board.
    - Uploaded the new 'controller.py' and 'watering_main.py' and ran
      'watering_main.py' from Thonny. It printed 'Modbus server listening
      on 192.168.1.67 502'. No 'modbus ...' error lines appeared, and the
      published values updated, so the library's 'set_...' calls work.
      [Pump charger unplugged / plugged in for these tests.]
    - Used 'modbus_check.py' on the PC (a small script that does one read
      or write per command). Results:
        - 'read' at the start: Auto, thresholds 1700 and 1300, fault 1
          (reservoir low). Correct: the float was down, and the probe was
          in air so the soil read dry (about 2600).
        - Switched to Manual, requested a pump burst with the float down:
          refused, 'manual pump refused: reservoir low'. Pass.
        - Raised the float and requested a burst: one burst, then 'manual
          burst done'. Pass. [Relay clicked on and off.]
        - Requested again straight away: 'refused: wait 10 s' (fault 2),
          then 'wait 3 s', then a burst once the gap had passed. Pass.
        - Wrote 9 to the mode register: mode unchanged. Pass.
        - Wrote dry 5000 and wet 100: the board corrected it to 4000 and
          100. Pass. Reset them to 1700 and 1300.
        - Switched back to Auto: it checked the soil straight away and
          started a soil-driven burst. Pass.
    - Ctrl+C in the command prompt showed 'KeyboardInterrupt' tracebacks.
      That was just me stopping the script.
    - Anomaly: some 'read' outputs showed 'pump on: True' and 'reservoir
      ok: False' while Thonny showed the pump idle and the reservoir OK.
      The two discrete inputs look swapped when read together, while
      single-bit reads (as in the 'pump' polling) were correct. I suspect
      the library packs the bits the wrong way round. If so, Ignition
      could show them swapped if it reads both in one request. Not yet
      confirmed.
    - Minor: in Manual mode, fault 1 stays set after the reservoir is
      refilled, until the next accepted burst or a mode change. [Decide
      whether to clear it when the float recovers.]
    - Not yet done: a real manual burst with the pump plugged in over the
      sink, and confirming the discrete input order with the 'bits'
      command in 'modbus_check.py'. If it confirms the swap, the plan is
      to move pump on and reservoir ok into input registers (0 or 1).
          - Anomaly: some 'read' outputs showed 'pump on: True' and 'reservoir
      ok: False' while Thonny showed the pump idle and the reservoir OK.
      Confirmed in the next entry.
    - Minor: in Manual mode, fault 1 stayed set after the reservoir was
      refilled. Fixed in the next entry.

15. Fixed the discrete input bit order, and ran a real manual burst.
    - Added a 'bits' command to 'modbus_check.py' that reads the two
      discrete inputs separately and then together. With the float up and
      the pump idle: address 0 alone read False, address 1 alone read
      True, but both together read [True, False]. So a multi-bit read
      returns the bits in reverse order (the single-bit reads were
      right). I suspect the library packs the bits the wrong way round.
      I haven't checked its source.
    - That matters because Ignition may read several addresses in one
      request and would show pump on and reservoir ok swapped. Fixed it
      by removing the discrete inputs and moving both values into input
      registers (5 pump on, 6 reservoir ok, each 0 or 1), since register
      reads aren't affected. The register map is now: coil 0 manual pump
      request; holding registers 0 to 2 (dry threshold, wet threshold,
      mode); input registers 0 to 6 (soil, state, burst count, heartbeat,
      fault, pump on, reservoir ok). Only one coil exists, so the same
      problem can't bite yet, but multi-coil reads would have it too.
    - Also changed the controller so that in Manual mode, fault 1
      (reservoir low) clears itself once the float comes back up. The
      gap and hourly-limit refusals (fault 2) are not cleared that way.
      Added two tests.
    - Uploaded the new 'controller.py' and 'watering_main.py'. 'pytest'
      from the repo root: 39 passed (my 14 original tests plus 25 for
      Manual mode, thresholds and faults). No 'modbus ...' error lines
      appeared in Thonny, so the library accepts the register definitions
      without the discrete input section.
    - Re-ran 'modbus_check.py read': 'pump on' and 'reservoir ok' now
      match what Thonny reports (soaking with the pump off and the
      reservoir OK, then manual pumping with the pump on). Pass.
    - Real manual burst with the pump plugged in: switched to Manual and
      requested a burst. The rig pumped water for one burst, stopped by
      itself, and the request coil cleared straight away. Switching back
      to Auto started a soil-driven burst at once (the probe was in air,
      so it read dry). Pass. [Add whether the relay clicked, and whether
      the ESP32 stayed connected, which it did last time.]
    - Stage 3 is done: the PC reads and writes the real controller over
      Modbus TCP.

16. Started Stage 4: installed Ignition and connected the ESP32.
    - Downloaded and installed Ignition 8.3 on the PC. First-time setup
      asked for the HTTP, HTTPS and gateway network ports (8088, 8043,
      8060). Left all three at the defaults. They are for local use only,
      and I haven't forwarded them on the router.
    - Created a Maker Edition licence on my Inductive Automation account.
      It comes with an 8-character key and a separate, very long
      activation token, and the gateway needs both, pasted into separate
      fields. [Activated / still on the two-hour trial. Say which, and
      whether I picked Maker at the first prompt of setup.] Keep the token
      private, and don't regenerate it without updating the gateway.
    - Spent a few minutes looking for 'Connections' because the home page
      before logging in only shows Home, Designer and Perspective. The
      config sections appear after clicking Log In in the top-right.
    - Added the ESP32 as a device: Modbus TCP, name 'PlantESP32',
      hostname 192.168.1.67, port 502. [Zero-based Addressing ticked:
      confirm.] It shows as Connected. Ignition's address prefixes are
      HR (holding), IR (input) and C (coil). With zero-based addressing
      on, HR0 is holding register 0 on the board. Left unticked, every
      address would be off by one.
    - Not yet done: creating tags in the Designer from the register map
      ('[PlantESP32]HR2' for mode, 'IR5' for pump on, and so on), the HMI
      screen, alarms, and checking whether the library accepts more than
      one Modbus client at once (so I know whether 'modbus_check.py' works
      while Ignition is connected).