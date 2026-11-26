import math, random, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "arm"))
import ik
cfg = ik.load_aircraft("hawk_t2")
random.seed(1)
def rand_rot():
    return ik.mm(ik.mm(ik.Rz(random.uniform(-180,180)), ik.Ry(random.uniform(-80,80))), ik.Rx(random.uniform(-180,180)))
worst_p = worst_r = 0
for _ in range(2000):
    # random reachable target in front/above shoulder
    while True:
        t = [random.uniform(-.5,.5), random.uniform(-.2,.55), random.uniform(-.5,.55)]
        if 0.08 < ik.norm(t) < cfg["upper_arm"] + cfg["forearm"] - 0.01: break
    H = rand_rot()
    ch = ik.solve_arm(t, H, cfg)
    e, w, H2 = ik.forward(ch, cfg)
    worst_p = max(worst_p, ik.norm(ik.sub(w, t)))
    worst_r = max(worst_r, max(abs(H[i][j]-H2[i][j]) for i in range(3) for j in range(3)))
    assert abs(ik.norm(e) - cfg["upper_arm"]) < 1e-9
print(f"IK round trip over 2000 poses: max wrist error {worst_p*1000:.4f} mm, max hand-rotation error {worst_r:.2e}")
assert worst_p < 1e-6 and worst_r < 1e-6
# elbow should sit toward the pole (left/down) for a normal signal position
ch = ik.solve_arm(ik.cockpit_to_b(cfg["signal_box"]["center"]), ik.from_cols([1,0,0],[0,1,0],[0,0,1]), cfg)
e,_,_ = ik.forward(ch, cfg)
print("elbow for centre-of-box signal (x right, y fwd, z up):", [round(v,3) for v in e])
_,wr,_ = ik.forward(ch, cfg); assert e[0] < 0 and e[2] < wr[2]  # elbow outboard and below the raised hand
# unreachable target clamps instead of failing
ch = ik.solve_arm([0, 2.0, 0], ik.from_cols([1,0,0],[0,1,0],[0,0,1]), cfg)
print("far target -> elbow", round(ch["elbow"],2), "deg (near straight)")
# anim mapping
a = ik.to_anim({"elbow": 75, "sh_pitch": 0}, ik.load_channels())
assert abs(a["elbow"]-50) < 1e-9 and a["sh_pitch"] == 0
print("ALL IK TESTS PASSED")
