import math, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "arm"))
import bridge
signs = {"pitch": 1, "bank": 1}  # test in nose-up / right-bank-positive terms
base = {"lat": 51.0, "lon": -1.0, "alt": 1000.0, "pitch": 0, "bank": 0, "hdg": 0, "ve": 0, "vn": 0, "vu": 0}
ft = lambda m: m * 3.28084
def dne(w):  # metres north/east/up from base
    n = math.radians(w["lat"] - 51.0) * bridge.EARTH_R_FT / 3.28084
    e = math.radians(w["lon"] + 1.0) * bridge.EARTH_R_FT * math.cos(math.radians(51)) / 3.28084
    return round(n, 3), round(e, 3), round((w["alt"] - 1000) / 3.28084, 3)
print("heading N, 10 m forward  ->", dne(bridge.body_to_world(base, [0, 0, 10], signs)))
print("heading E, 10 m forward  ->", dne(bridge.body_to_world({**base, "hdg": 90}, [0, 0, 10], signs)))
print("right bank 90, 1 m up    ->", dne(bridge.body_to_world({**base, "bank": 90}, [0, 1, 0], signs)))
print("nose up 90, 1 m forward  ->", dne(bridge.body_to_world({**base, "pitch": 90}, [0, 0, 1], signs)))
assert dne(bridge.body_to_world(base, [0, 0, 10], signs))[0] == 10
assert dne(bridge.body_to_world({**base, "hdg": 90}, [0, 0, 10], signs))[1] == 10
assert dne(bridge.body_to_world({**base, "bank": 90}, [0, 1, 0], signs))[1] == 1   # top of aircraft points east (right)
assert dne(bridge.body_to_world({**base, "pitch": 90}, [0, 0, 1], signs))[2] == 1  # nose points up
p = bridge.predict({**base, "vn": ft(100)}, 0.5)
assert abs(dne(p)[0] - 50) < 0.01
print("ALL PLACEMENT TESTS PASSED")
