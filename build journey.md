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