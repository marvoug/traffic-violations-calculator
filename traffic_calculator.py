"""
===============================================================================
 TRAFFIC VIOLATION AND INCIDENT ANALYTICS CALCULATOR
-------------------------------------------------------------------------------
 Purpose:
   Help traffic officers, urban planners and safety analysts process vehicle
   speeds, road (GPS) coordinates and citation data quickly, and reduce
   manual calculation errors.

 Problems this program solves:
   P1. Time-consuming manual processing of violation logs and accident reports
       -> Option 6 (batch citation log processing)
   P2. Difficulty calculating speed violations and stopping distances
       -> Options 1 and 2
   P3. Difficulty calculating intersection clearance times and traffic density
       -> Option 3
   P4. Difficulty converting fine units, speed metrics and distance parameters
       -> Option 4
   P5. Human errors in computing penalties, coordinates and collision data
       -> Options 1, 5, 7 (automatic, validated calculations)
===============================================================================
"""

import math
import sys

# =============================================================================
# 1. CONSTANTS AND SETTINGS
#    Kept in one place so they are easy to explain and easy to change.
# =============================================================================

GRAVITY = 9.81                 # m/s^2, acceleration due to gravity
DEFAULT_REACTION_TIME = 1.5    # seconds, typical driver perception-reaction time
EARTH_RADIUS_KM = 6371.0       # mean radius of the Earth, used for GPS distance

# Road surface friction coefficients (how well tyres grip the road)
FRICTION = {
    "dry": 0.7,
    "wet": 0.4,
    "gravel": 0.35,
    "murram": 0.35,   # common unpaved road surface in Uganda
}

# Fine settings.  In Uganda, fines are expressed in "currency points".
# These values are SAMPLE settings for the project and can be edited.
UGX_PER_CURRENCY_POINT = 20000     # 1 currency point = UGX 20,000
UGX_PER_USD = 3700                 # sample exchange rate - update before use

# Speeding fine schedule (sample): (max km/h over the limit, currency points)
SPEED_FINE_TIERS = [
    (10, 2),       # 1-10 km/h over   -> 2 currency points
    (20, 4),       # 11-20 km/h over  -> 4 currency points
    (30, 6),       # 21-30 km/h over  -> 6 currency points
    (math.inf, 10) # more than 30 over -> 10 currency points (serious offence)
]

# Fines for other common offences (sample, in currency points)
OFFENCE_FINES = {
    "speeding": None,          # calculated from the speed tiers above
    "red_light": 5,
    "no_seatbelt": 2,
    "no_helmet": 2,
    "phone_use": 4,
    "illegal_parking": 2,
}


# =============================================================================
# 2. SAMPLE TEST DATA
#    Built into the script so the demonstration always works.
# =============================================================================

SAMPLE_CITATIONS = [
    # id,    plate,      offence,        recorded speed, speed limit, lat, lon
    {"id": "C001", "plate": "UBA 123X", "offence": "speeding",
     "speed": 92, "limit": 50, "lat": 0.3136, "lon": 32.5811},   # Kampala centre
    {"id": "C002", "plate": "UAX 456K", "offence": "speeding",
     "speed": 58, "limit": 50, "lat": 0.3476, "lon": 32.5825},
    {"id": "C003", "plate": "UBE 789M", "offence": "red_light",
     "speed": 40, "limit": 50, "lat": 0.3163, "lon": 32.5822},
    {"id": "C004", "plate": "UBF 321Q", "offence": "no_seatbelt",
     "speed": 45, "limit": 80, "lat": 0.0512, "lon": 32.4637},   # Entebbe road
    {"id": "C005", "plate": "UBG 654T", "offence": "speeding",
     "speed": 112, "limit": 80, "lat": 0.0611, "lon": 32.4702},
    {"id": "C006", "plate": "UBA 123X", "offence": "phone_use",
     "speed": 30, "limit": 50, "lat": 0.3150, "lon": 32.5790},
]

# Two GPS readings of the same vehicle (for average-speed check)
SAMPLE_GPS_TRACK = [
    {"lat": 0.3136, "lon": 32.5811, "time_s": 0},     # first camera
    {"lat": 0.3476, "lon": 32.5825, "time_s": 180},   # second camera, 3 min later
]


# =============================================================================
# 3. INPUT HELPERS
#    Every number the user types is checked here, so a typing mistake
#    shows a friendly message instead of crashing the program.  (Problem P5)
# =============================================================================

def get_float(prompt, minimum=None, default=None):
    """Ask for a number until a valid one is entered."""
    while True:
        text = input(prompt).strip()
        if text == "" and default is not None:
            return default
        try:
            value = float(text)
        except ValueError:
            print("  ! Please enter a number (e.g. 60 or 12.5).")
            continue
        if minimum is not None and value < minimum:
            print(f"  ! Value must be at least {minimum}.")
            continue
        return value


def get_choice(prompt, options):
    """Ask the user to pick one word from a list of options."""
    options_text = "/".join(options)
    while True:
        text = input(f"{prompt} ({options_text}): ").strip().lower()
        if text in options:
            return text
        print(f"  ! Choose one of: {options_text}")


def heading(title):
    """Print a neat section heading."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


# =============================================================================
# 4. CALCULATION FUNCTIONS
#    Each function does ONE job and RETURNS its result.  The menu functions
#    further below handle typing and printing.  This makes every formula easy
#    to test with sample data.
# =============================================================================

# ---------- 4.1 Unit conversions (Problem P4) --------------------------------

def kmh_to_ms(kmh):
    """km/h -> m/s   (divide by 3.6)"""
    return kmh / 3.6


def ms_to_kmh(ms):
    """m/s -> km/h   (multiply by 3.6)"""
    return ms * 3.6


def kmh_to_mph(kmh):
    """km/h -> miles per hour"""
    return kmh / 1.609344


def mph_to_kmh(mph):
    """miles per hour -> km/h"""
    return mph * 1.609344


def km_to_miles(km):
    return km / 1.609344


def miles_to_km(miles):
    return miles * 1.609344


def points_to_ugx(points):
    """Currency points -> Uganda shillings"""
    return points * UGX_PER_CURRENCY_POINT


def ugx_to_usd(ugx):
    """Uganda shillings -> US dollars (sample rate)"""
    return ugx / UGX_PER_USD


# ---------- 4.2 Speed violations and fines (Problems P2, P5) ------------------

def speed_excess(speed, limit):
    """
    How far over the limit the vehicle was.
    Returns (excess in km/h, excess as a percentage of the limit).
    A vehicle at or below the limit has 0 excess.
    """
    excess = max(0.0, speed - limit)
    percent = (excess / limit) * 100 if limit > 0 else 0.0
    return excess, percent


def speeding_fine_points(excess):
    """Look up the fine (currency points) for a given excess speed."""
    if excess <= 0:
        return 0
    for max_excess, points in SPEED_FINE_TIERS:
        if excess <= max_excess:
            return points
    return SPEED_FINE_TIERS[-1][1]


def citation_fine(citation):
    """Fine for one citation record, in currency points."""
    if citation["offence"] == "speeding":
        excess, _ = speed_excess(citation["speed"], citation["limit"])
        return speeding_fine_points(excess)
    return OFFENCE_FINES.get(citation["offence"], 0)


# ---------- 4.3 Stopping distance (Problem P2) --------------------------------

def stopping_distance(speed_kmh, friction, reaction_time=DEFAULT_REACTION_TIME):
    """
    Total stopping distance using kinematic formulas.

      Reaction distance = v x t          (car keeps moving while driver reacts)
      Braking distance  = v^2 / (2 x mu x g)   (from v^2 = u^2 + 2as)
      Stopping distance = reaction distance + braking distance

    v = speed in m/s, t = reaction time (s), mu = friction, g = 9.81 m/s^2
    Returns (reaction distance, braking distance, total) in metres.
    """
    v = kmh_to_ms(speed_kmh)
    reaction = v * reaction_time
    braking = (v ** 2) / (2 * friction * GRAVITY)
    return reaction, braking, reaction + braking


# ---------- 4.4 Intersection clearance and density (Problem P3) ---------------

def clearance_time(intersection_width_m, vehicle_length_m, speed_kmh):
    """
    Time for a vehicle to completely clear an intersection.
      clearance time = (intersection width + vehicle length) / speed
    """
    v = kmh_to_ms(speed_kmh)
    return (intersection_width_m + vehicle_length_m) / v


def yellow_light_time(speed_kmh, reaction_time=1.0, deceleration=3.0):
    """
    Recommended amber (yellow) light time - standard traffic engineering formula:
      Y = t + v / (2 x a)
    t = reaction time (s), v = approach speed (m/s), a = comfortable braking (m/s^2)
    """
    v = kmh_to_ms(speed_kmh)
    return reaction_time + v / (2 * deceleration)


def traffic_density(vehicle_count, road_length_km, lanes=1):
    """
    Density = number of vehicles / length of road  (vehicles per km)
    Also returns density per lane.
    """
    density = vehicle_count / road_length_km
    return density, density / lanes


def traffic_flow(density_veh_per_km, average_speed_kmh):
    """
    Fundamental traffic equation:  flow q = density k x speed v
    Gives vehicles per hour passing a point.
    """
    return density_veh_per_km * average_speed_kmh


def density_level(density_per_lane):
    """Simple description of how congested the road is (per lane)."""
    if density_per_lane < 12:
        return "Free flow (light traffic)"
    if density_per_lane < 30:
        return "Stable flow (moderate traffic)"
    if density_per_lane < 45:
        return "Heavy traffic (near capacity)"
    return "Congested / jam"


# ---------- 4.5 GPS coordinates (Problems P1, P5) -----------------------------

def valid_coordinate(lat, lon):
    """Latitude must be -90..90 and longitude -180..180."""
    return -90 <= lat <= 90 and -180 <= lon <= 180


def haversine_km(lat1, lon1, lat2, lon2):
    """
    Distance between two GPS points along the Earth's surface (Haversine formula):
      a = sin^2(dLat/2) + cos(lat1) x cos(lat2) x sin^2(dLon/2)
      c = 2 x atan2(sqrt(a), sqrt(1 - a))
      d = R x c
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def average_speed_kmh(distance_km, time_seconds):
    """Average speed = distance / time (converted to km/h)."""
    return distance_km / (time_seconds / 3600)


# ---------- 4.6 Collision impact (Problem P5) ---------------------------------

def collision_impact(mass_kg, speed_kmh, stop_distance_m):
    """
    Collision metrics for a vehicle that is brought to a stop by an impact.
      Kinetic energy  KE = 1/2 x m x v^2           (joules)
      Momentum        p  = m x v                   (kg.m/s)
      Average force   F  = KE / d                  (newtons; work-energy theorem)
      Deceleration    a  = v^2 / (2d), shown in "g" (a / 9.81)
    d = distance the vehicle crushes / slides during the impact.
    """
    v = kmh_to_ms(speed_kmh)
    kinetic_energy = 0.5 * mass_kg * v ** 2
    momentum = mass_kg * v
    force = kinetic_energy / stop_distance_m
    g_force = (v ** 2 / (2 * stop_distance_m)) / GRAVITY
    return kinetic_energy, momentum, force, g_force


def combined_speed_after_crash(m1, v1_kmh, m2, v2_kmh):
    """
    Two vehicles that lock together after a head-on/rear-end crash
    (conservation of momentum):  v_final = (m1v1 + m2v2) / (m1 + m2)
    Use a negative speed for a vehicle moving in the opposite direction.
    """
    return (m1 * v1_kmh + m2 * v2_kmh) / (m1 + m2)


# ---------- 4.7 Batch citation processing (Problems P1, P5) -------------------

def process_citations(citations):
    """
    Process a whole citation log automatically.
    Returns a list of result rows plus a summary dictionary.
    """
    rows = []
    total_points = 0
    offence_count = {}
    plate_count = {}
    invalid = 0

    for c in citations:
        if not valid_coordinate(c["lat"], c["lon"]):
            invalid += 1
            continue  # skip bad records instead of crashing
        excess, _ = speed_excess(c["speed"], c["limit"])
        points = citation_fine(c)
        total_points += points
        offence_count[c["offence"]] = offence_count.get(c["offence"], 0) + 1
        plate_count[c["plate"]] = plate_count.get(c["plate"], 0) + 1
        rows.append({**c, "excess": excess, "points": points,
                     "ugx": points_to_ugx(points)})

    repeat_offenders = [p for p, n in plate_count.items() if n > 1]
    summary = {
        "records": len(rows),
        "invalid": invalid,
        "total_points": total_points,
        "total_ugx": points_to_ugx(total_points),
        "offence_count": offence_count,
        "repeat_offenders": repeat_offenders,
    }
    return rows, summary


# =============================================================================
# 5. MENU SCREENS
# =============================================================================

def menu_speed_violation():
    heading("1. SPEED VIOLATION AND FINE CALCULATOR")
    speed = get_float("Recorded vehicle speed (km/h): ", minimum=0)
    limit = get_float("Speed limit on this road (km/h): ", minimum=1)
    excess, percent = speed_excess(speed, limit)
    if excess == 0:
        print("\n  RESULT: No violation - vehicle was within the speed limit.")
        return
    points = speeding_fine_points(excess)
    ugx = points_to_ugx(points)
    print(f"\n  Speed excess      : {excess:.1f} km/h over ({percent:.1f}% above limit)")
    print(f"  Fine              : {points} currency points")
    print(f"  Fine in UGX       : UGX {ugx:,.0f}")
    print(f"  Fine in USD       : about ${ugx_to_usd(ugx):,.2f}")
    if excess > 30:
        print("  WARNING           : Serious offence - more than 30 km/h over.")


def menu_stopping_distance():
    heading("2. VEHICLE STOPPING DISTANCE")
    speed = get_float("Vehicle speed (km/h): ", minimum=1)
    surface = get_choice("Road surface", list(FRICTION.keys()))
    reaction = get_float(f"Driver reaction time in seconds "
                         f"[Enter = {DEFAULT_REACTION_TIME}]: ",
                         minimum=0, default=DEFAULT_REACTION_TIME)
    r, b, total = stopping_distance(speed, FRICTION[surface], reaction)
    print(f"\n  Speed             : {speed:.1f} km/h = {kmh_to_ms(speed):.2f} m/s")
    print(f"  Friction (mu)     : {FRICTION[surface]} ({surface})")
    print(f"  Reaction distance : {r:.2f} m")
    print(f"  Braking distance  : {b:.2f} m")
    print(f"  TOTAL stopping    : {total:.2f} m")


def menu_intersection_density():
    heading("3. INTERSECTION CLEARANCE & TRAFFIC DENSITY")
    print("  a) Intersection clearance time")
    print("  b) Traffic density and flow")
    part = get_choice("Choose", ["a", "b"])
    if part == "a":
        width = get_float("Intersection width (m): ", minimum=1)
        length = get_float("Vehicle length (m) [Enter = 5]: ", minimum=1, default=5)
        speed = get_float("Vehicle speed through junction (km/h): ", minimum=1)
        t = clearance_time(width, length, speed)
        y = yellow_light_time(speed)
        print(f"\n  Clearance time    : {t:.2f} seconds")
        print(f"  Recommended amber : {y:.2f} seconds")
        print(f"  Suggested all-red : {t:.2f} seconds (so the junction empties)")
    else:
        count = get_float("Number of vehicles counted: ", minimum=0)
        length = get_float("Length of road section (km): ", minimum=0.01)
        lanes = int(get_float("Number of lanes [Enter = 1]: ", minimum=1, default=1))
        avg_speed = get_float("Average speed of traffic (km/h): ", minimum=0)
        density, per_lane = traffic_density(count, length, lanes)
        flow = traffic_flow(density, avg_speed)
        print(f"\n  Density           : {density:.1f} vehicles/km")
        print(f"  Density per lane  : {per_lane:.1f} vehicles/km/lane")
        print(f"  Traffic flow      : {flow:,.0f} vehicles/hour")
        print(f"  Traffic condition : {density_level(per_lane)}")


def menu_conversions():
    heading("4. UNIT CONVERTER (speed, distance, fines)")
    options = {
        "1": ("km/h -> m/s", kmh_to_ms),
        "2": ("m/s -> km/h", ms_to_kmh),
        "3": ("km/h -> mph", kmh_to_mph),
        "4": ("mph -> km/h", mph_to_kmh),
        "5": ("km -> miles", km_to_miles),
        "6": ("miles -> km", miles_to_km),
        "7": ("currency points -> UGX", points_to_ugx),
        "8": ("UGX -> USD", ugx_to_usd),
    }
    for key, (label, _) in options.items():
        print(f"  {key}. {label}")
    key = get_choice("Choose conversion", list(options.keys()))
    label, func = options[key]
    value = get_float("Enter value: ", minimum=0)
    print(f"\n  RESULT ({label}): {value:,.2f} -> {func(value):,.2f}")


def menu_gps():
    heading("5. GPS COORDINATE ANALYSIS")
    print("  Enter two GPS readings of the same vehicle (e.g. from two cameras).")
    lat1 = get_float("Point 1 latitude : ")
    lon1 = get_float("Point 1 longitude: ")
    lat2 = get_float("Point 2 latitude : ")
    lon2 = get_float("Point 2 longitude: ")
    if not (valid_coordinate(lat1, lon1) and valid_coordinate(lat2, lon2)):
        print("  ! Invalid coordinate: latitude -90..90, longitude -180..180.")
        return
    seconds = get_float("Time between readings (seconds): ", minimum=0.1)
    limit = get_float("Speed limit on this stretch (km/h): ", minimum=1)
    dist = haversine_km(lat1, lon1, lat2, lon2)
    avg = average_speed_kmh(dist, seconds)
    excess, _ = speed_excess(avg, limit)
    print(f"\n  Distance travelled: {dist:.3f} km ({dist * 1000:.0f} m)")
    print(f"  Average speed     : {avg:.1f} km/h")
    if excess > 0:
        pts = speeding_fine_points(excess)
        print(f"  VIOLATION         : {excess:.1f} km/h over -> {pts} points "
              f"(UGX {points_to_ugx(pts):,.0f})")
    else:
        print("  Status            : Within speed limit")


def menu_citations():
    heading("6. CITATION LOG PROCESSING (sample data)")
    rows, summary = process_citations(SAMPLE_CITATIONS)
    print(f"  {'ID':<5}{'Plate':<10}{'Offence':<13}{'Spd':>5}{'Lim':>5}"
          f"{'Over':>6}{'Pts':>5}{'Fine (UGX)':>13}")
    print("  " + "-" * 62)
    for r in rows:
        print(f"  {r['id']:<5}{r['plate']:<10}{r['offence']:<13}{r['speed']:>5}"
              f"{r['limit']:>5}{r['excess']:>6.0f}{r['points']:>5}{r['ugx']:>13,.0f}")
    print("  " + "-" * 62)
    print(f"  Records processed : {summary['records']} "
          f"(invalid skipped: {summary['invalid']})")
    print(f"  Total fines       : {summary['total_points']} points = "
          f"UGX {summary['total_ugx']:,.0f}")
    print("  Offences          : " + ", ".join(
        f"{k} x{v}" for k, v in summary["offence_count"].items()))
    print("  Repeat offenders  : " + (", ".join(summary["repeat_offenders"]) or "none"))


def menu_collision():
    heading("7. COLLISION IMPACT ANALYSIS")
    print("  a) Single vehicle impact")
    print("  b) Two vehicles locking together (momentum)")
    part = get_choice("Choose", ["a", "b"])
    if part == "a":
        mass = get_float("Vehicle mass (kg): ", minimum=1)
        speed = get_float("Speed at impact (km/h): ", minimum=0)
        crush = get_float("Crush/stopping distance in impact (m): ", minimum=0.01)
        ke, p, f, g = collision_impact(mass, speed, crush)
        print(f"\n  Kinetic energy    : {ke:,.0f} J ({ke / 1000:,.1f} kJ)")
        print(f"  Momentum          : {p:,.0f} kg.m/s")
        print(f"  Average force     : {f:,.0f} N ({f / 1000:,.1f} kN)")
        print(f"  Deceleration      : {g:.1f} g")
    else:
        m1 = get_float("Vehicle 1 mass (kg): ", minimum=1)
        v1 = get_float("Vehicle 1 speed (km/h): ")
        m2 = get_float("Vehicle 2 mass (kg): ", minimum=1)
        v2 = get_float("Vehicle 2 speed (km/h, negative if opposite way): ")
        vf = combined_speed_after_crash(m1, v1, m2, v2)
        print(f"\n  Speed of wreck just after crash: {vf:.1f} km/h")


# =============================================================================
# 6. AUTOMATIC DEMONSTRATION WITH SAMPLE DATA
#    Runs every feature with known values - no typing needed.
# =============================================================================

def run_demo():
    heading("DEMO: ALL FEATURES WITH SAMPLE TEST DATA")

    print("\n[1] Speed violation: 92 km/h in a 50 km/h zone")
    excess, pct = speed_excess(92, 50)
    pts = speeding_fine_points(excess)
    print(f"    Excess = 92 - 50 = {excess:.0f} km/h ({pct:.0f}%), "
          f"fine = {pts} points = UGX {points_to_ugx(pts):,.0f}")

    print("\n[2] Stopping distance: 60 km/h, dry road, 1.5 s reaction")
    r, b, t = stopping_distance(60, FRICTION["dry"])
    print(f"    Reaction {r:.2f} m + braking {b:.2f} m = {t:.2f} m")
    r, b, t = stopping_distance(60, FRICTION["wet"])
    print(f"    Same speed on WET road = {t:.2f} m")

    print("\n[3] Intersection: 20 m wide, 5 m car, 40 km/h")
    print(f"    Clearance time = {clearance_time(20, 5, 40):.2f} s, "
          f"amber = {yellow_light_time(40):.2f} s")

    print("\n[3] Density: 120 vehicles on 2 km of 2-lane road at 30 km/h")
    d, dl = traffic_density(120, 2, 2)
    print(f"    {d:.0f} veh/km, {dl:.0f} veh/km/lane, flow = "
          f"{traffic_flow(d, 30):,.0f} veh/h -> {density_level(dl)}")

    print("\n[4] Conversions")
    print(f"    100 km/h = {kmh_to_ms(100):.2f} m/s = {kmh_to_mph(100):.2f} mph")
    print(f"    6 currency points = UGX {points_to_ugx(6):,.0f} "
          f"= ${ugx_to_usd(points_to_ugx(6)):.2f}")

    print("\n[5] GPS: two camera readings 180 s apart (50 km/h zone)")
    a, b2 = SAMPLE_GPS_TRACK
    dist = haversine_km(a["lat"], a["lon"], b2["lat"], b2["lon"])
    avg = average_speed_kmh(dist, b2["time_s"] - a["time_s"])
    print(f"    Distance = {dist:.3f} km, average speed = {avg:.1f} km/h")

    print("\n[7] Collision: 1,200 kg car at 50 km/h, 0.6 m crush")
    ke, p, f, g = collision_impact(1200, 50, 0.6)
    print(f"    KE = {ke:,.0f} J, momentum = {p:,.0f} kg.m/s, "
          f"force = {f:,.0f} N, {g:.1f} g")
    print(f"    Car 1500 kg @ 60 + car 1000 kg @ -40 lock together -> "
          f"{combined_speed_after_crash(1500, 60, 1000, -40):.1f} km/h")

    print()
    menu_citations()   # [6] batch processing of the sample citation log


# =============================================================================
# 7. MAIN MENU
# =============================================================================

def main():
    actions = {
        "1": ("Speed violation & fine", menu_speed_violation),
        "2": ("Stopping distance", menu_stopping_distance),
        "3": ("Intersection clearance / traffic density", menu_intersection_density),
        "4": ("Unit converter (speed, distance, fines)", menu_conversions),
        "5": ("GPS coordinate analysis", menu_gps),
        "6": ("Process citation log (sample data)", menu_citations),
        "7": ("Collision impact analysis", menu_collision),
        "8": ("Run full demo with sample data", run_demo),
    }
    while True:
        heading("TRAFFIC VIOLATION & INCIDENT ANALYTICS CALCULATOR")
        for key, (label, _) in actions.items():
            print(f"  {key}. {label}")
        print("  0. Exit")
        choice = input("\nSelect an option: ").strip()
        if choice == "0":
            print("Goodbye - drive safely!")
            break
        if choice in actions:
            try:
                actions[choice][1]()
            except ZeroDivisionError:
                print("  ! A value of zero made this calculation impossible.")
            input("\nPress Enter to return to the menu...")
        else:
            print("  ! Invalid option, try again.")


if __name__ == "__main__":
    try:
        if "--demo" in sys.argv:
            run_demo()
        else:
            main()
    except (KeyboardInterrupt, EOFError):
        print("\nProgram closed.")
