# Hardware roadmap (Phase 10): a proposal, not a plan of record

Status of everything below: **nothing exists**. No hardware is connected, no spacecraft is
built, and nothing here has been verified against a real mission. Technical statements come
from general engineering knowledge and were not checked against sources during this project;
verify each against current official documents before relying on it.

## 1. Verified versus proposed

| Item | Status |
|---|---|
| Orbit propagation, frames, pass maths (Python) | Built and tested; SIMULATED |
| Real fire and vegetation data pipelines | Built and run on real data |
| Telemetry packet and health monitor (C) | Built and tested on a laptop only |
| Hardware abstraction layer, command format, link protocol | Not built |
| Any flight computer, sensor, radio, power system, structure | Proposed only |
| Ground station and tracking | Proposed only |
| Launch, spectrum, regulatory approvals | Proposed only, procedures not verified |

## 2. A realistic path: build up real hardware in stages

Going straight to orbit is the hardest route. Each stage below produces real data and real
lessons, and each can be done without a launch:

1. **Software only (current).** Real public data, simulated spacecraft.
2. **Bench hardware.** Run the C health monitor on a small microcontroller board with real
   sensors (voltage, temperature) and a hardware watchdog. Compare its packets with the
   Python decoder, using the same cross-check tests.
3. **Ground-based or aerial sensing.** Fly a thermal or near-infrared camera on a drone or a
   high-altitude balloon over farmland (check local aviation rules first). This produces
   genuine observations that use the same NDVI and alert ideas, at a fraction of the cost.
4. **Ground station.** Receive signals from existing amateur satellites using our orbit code
   for pass prediction. This tests tracking and radio skills without building a spacecraft.
5. **Flight-hardware prototype.** Only after the stages above: a small satellite design
   study (for example a CubeSat-class platform) with qualification testing.

This ordering is my recommendation, not a requirement.

## 3. What a small Earth-observation satellite needs

| Subsystem | What it does | Main questions to answer |
|---|---|---|
| Structure and thermal | Holds everything and survives launch; manages heat | Standard form factor? Launch provider's requirements? |
| Power | Solar panels, battery, regulators | Orbit-average power budget, eclipse duration |
| Onboard computer | Runs flight software, watchdog, data handling | Processor family, memory, real-time OS or bare metal, radiation tolerance of components |
| Attitude determination and control | Points the camera and antennas | Required pointing accuracy; sensors and actuators; imaging needs this |
| Communications | Commands up, telemetry and images down | Frequency band, data rate, link budget, protocol |
| Payload | Camera or thermal sensor | Resolution, spectral bands, data volume (see section 4) |
| Ground segment | Antenna, radio, tracking software, data processing | Location, pass frequency, automation |
| Launch and integration | Getting to orbit | Provider, orbit, schedule, integration tests |

## 4. Worked example: what resolution can a camera give?

Ground sample distance (GSD) in metres = pixel pitch x altitude / focal length.

Illustrative numbers only (assumed, not a real product): pixel pitch 5 micrometres, focal
length 50 mm, altitude 500 km. GSD = 5e-6 x 500e3 / 0.05 = **50 m**. To reach 10 m at the
same pitch and altitude, the focal length must be 250 mm, which is a much larger and
heavier optic. With 4000 pixels across, a 50 m GSD gives a 200 km swath.

This ignores diffraction, signal-to-noise, motion blur, atmosphere and data downlink
volume, all of which matter. For comparison, Sentinel-2 delivers 10 m red and near-infrared
bands today for free, so any new satellite needs a clear reason to exist beyond that.

## 5. What would change in the software

- **C code:** compile for the target processor with its toolchain; re-run all tests there.
  Add a hardware abstraction layer so the same logic runs against simulated or real
  sensors. Replace the software watchdog with a hardware one.
- **Link protocol:** select a real framing and addressing standard instead of the
  project-chosen sync word and layout.
- **Commands:** define an authenticated command format. A CRC detects accidents, not
  tampering.
- **Fault logic:** the thresholds in `health.h` are illustrative and must come from real
  component specifications and an analysis of failure modes.
- **Radiation and reliability:** component selection, memory protection and fault recovery
  need to be designed for the actual orbit. Desktop-grade code is not flight-qualified.

## 6. Legal and regulatory (not verified)

Any radio transmission, launch or on-orbit operation needs authorisation. Typical areas:
spectrum licensing and frequency coordination, launch and operations approval, space-debris
mitigation, export controls on components, insurance and liability. In India the relevant
bodies include the space-sector authority and the telecom spectrum authority; I have not
verified current procedures, forms or timelines. Check with them before committing money.

## 7. Verification gates

1. Software-in-the-loop: all current tests pass, no skips (done for what exists).
2. Hardware-in-the-loop: flight logic on the target board with real sensor inputs.
3. Environmental tests: vibration, thermal cycling, thermal vacuum, as required by the launcher.
4. Radio compliance and link tests on the ground.
5. Independent review of fault protection and command security.
6. Launch-provider acceptance.

## 8. Suggested next steps

1. Decide the goal: learning, a research instrument, or an operational monitoring product.
2. Try stage 2 or 3 above with inexpensive hardware.
3. Compare costs against buying existing data: Sentinel-2 and VIIRS are free.
4. Revisit this document and replace each "proposed" with a verified fact as you go.