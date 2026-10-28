"""Independent validation of the MO-JSSP loader, decoder and evaluator (expert review step 1)."""
import csv, glob, random, re, sys
from pathlib import Path

ROOT = Path(r"C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-loop-agent")
sys.path.insert(0, str(ROOT / "src"))
from mojssp.io import load_dzn
from mojssp.decoder import Decoder
from mojssp.evaluator import Evaluator
from mojssp.solution import Solution

SCRATCH = Path(__file__).parent  # writes hand_2x2.dzn next to this script

# ---------- hand-solved 2x2 example (computed on paper) ----------
HAND = """JOBS = 1..2;
MACHINES = 1..2;
SPEED = 2;
time = array3d(JOBS, MACHINES, 1..SPEED, [3, 1,  2, 1,   4, 2,  3, 2]);
energy = array3d(JOBS, MACHINES, 1..SPEED, [1, 5,  2, 4,   3, 6,  1, 3]);
precedence = array2d(JOBS, MACHINES, [0, 1,  1, 0]);
releaseDate = array2d(JOBS, MACHINES, [0, 0, 0, 0]);
dueDate = array2d(JOBS, MACHINES, [5, 5, 6, 6]);
"""
(SCRATCH / "hand_2x2.dzn").write_text(HAND, encoding="utf-8")
inst = load_dzn(SCRATCH / "hand_2x2.dzn")
cases = [((1, 2, 1, 2), (1, 1, 1, 2), (5, 0, 10.0)),   # worked by hand
         ((2, 1, 2, 1), (1, 1, 1, 1), (7, 1, 7.0))]
for seq, modes, expected in cases:
    sched = Decoder().decode(inst, Solution(seq, modes))
    got = Evaluator().evaluate(inst, sched).to_tuple()
    assert got == expected, (seq, modes, got, expected)
print("hand example: OK", [c[2] for c in cases])

# ---------- independent parser ----------
def nums(text, name):
    m = re.search(rf"{name}\s*=\s*array\dd\(.*?\[(.*?)\]\s*\)", text, re.S)
    body = re.sub(r"%[^\n]*", "", m.group(1))
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", body)]

def scalar(text, name):
    m = re.search(rf"{name}\s*=\s*(?:1\.\.)?(\d+)\s*;", text)
    return int(m.group(1))

def parse(path):
    t = re.sub(r"%[^\n]*", "", Path(path).read_text(encoding="utf-8"))
    n, m, s = scalar(t, "JOBS"), scalar(t, "MACHINES"), scalar(t, "SPEED")
    tm, en, pr = nums(t, "time"), nums(t, "energy"), nums(t, "precedence")
    rel = nums(t, "releaseDate") if "releaseDate" in t else [0] * (n * m)
    due = nums(t, "dueDate") if "dueDate" in t else [0] * (n * m)
    jobs = []
    for j in range(n):
        ops = []
        for k in range(m):
            i = j * m + k
            ops.append(dict(prec=pr[i], machine=k + 1, rel=int(rel[i]), due=int(due[i]),
                            modes=[(int(tm[i * s + v]), en[i * s + v]) for v in range(s)]))
        ops.sort(key=lambda o: o["prec"])
        dues = {o["due"] for o in ops}
        jobs.append(dict(ops=ops, due=ops[0]["due"] if len(dues) == 1 else ops[-1]["due"]))
    return jobs

def my_decode(jobs, seq, modes):
    canon, c = {}, 0
    for j, job in enumerate(jobs):
        for k in range(len(job["ops"])):
            canon[(j, k)] = c; c += 1
    nxt, jready, mready, out = [0] * len(jobs), [0] * len(jobs), {}, []
    for jid in seq:
        j = jid - 1; k = nxt[j]; op = jobs[j]["ops"][k]
        d, e = op["modes"][modes[canon[(j, k)]] - 1]
        st = max(jready[j], mready.get(op["machine"], 0), op["rel"])
        out.append(dict(j=j, k=k, mach=op["machine"], s=st, c=st + d, d=d, e=e, rel=op["rel"]))
        jready[j] = mready[op["machine"]] = st + d; nxt[j] += 1
    return out

def check_feasible(jobs, sch):
    n_ops = sum(len(j["ops"]) for j in jobs)
    assert len(sch) == n_ops and len({(o["j"], o["k"]) for o in sch}) == n_ops
    by = {(o["j"], o["k"]): o for o in sch}
    for o in sch:
        assert o["c"] == o["s"] + o["d"] and o["s"] >= o["rel"]
        if o["k"] > 0: assert o["s"] >= by[(o["j"], o["k"] - 1)]["c"]
    per = {}
    for o in sch: per.setdefault(o["mach"], []).append(o)
    for ops in per.values():
        ops.sort(key=lambda o: o["s"])
        for a, b in zip(ops, ops[1:]): assert b["s"] >= a["c"]

def my_objectives(jobs, sch):
    comp = {}
    for o in sch: comp[o["j"]] = max(comp.get(o["j"], 0), o["c"])
    return (max(o["c"] for o in sch), sum(max(0, comp[j] - jobs[j]["due"]) for j in range(len(jobs))),
            sum(o["e"] for o in sch))

files = sorted(glob.glob(str(ROOT / "data/validation/*.dzn")))
split = list(csv.DictReader(open(ROOT / "data/generated/expanded_200/experimental_split.csv", encoding="utf-8-sig")))
rng = random.Random(2026)
files += [str(ROOT / r["file_path"]) for r in rng.sample(split, 24)]
files += sorted(glob.glob(str(ROOT / "results/experiments/blmr_to_moead_dynamic_injection_20261024/instances/*.dzn")))
checked = 0
for f in files:
    jobs, inst = parse(f), load_dzn(f)
    # loader equality
    assert len(jobs) == inst.num_jobs
    for j, job in enumerate(inst.jobs):
        assert job.due_date == jobs[j]["due"], (f, j)
        for k, op in enumerate(job.operations):
            mine = jobs[j]["ops"][k]
            assert op.machine_id == mine["machine"] and op.release_date == mine["rel"]
            assert [(m.duration, m.energy) for m in op.modes] == mine["modes"]
    for _ in range(40):
        seq = [j + 1 for j, job in enumerate(jobs) for _ in job["ops"]]; rng.shuffle(seq)
        modes = [rng.randint(1, len(op["modes"])) for job in jobs for op in job["ops"]]
        sch = my_decode(jobs, seq, modes); check_feasible(jobs, sch)
        proj = Decoder().decode(inst, Solution(tuple(seq), tuple(modes)))
        po = {(o.job_id - 1, o.op_id - 1): (o.start, o.completion) for o in proj.operations}
        assert all(po[(o["j"], o["k"])] == (o["s"], o["c"]) for o in sch), f
        a = Evaluator().evaluate(inst, proj).to_tuple(); b = my_objectives(jobs, sch)
        assert a[0] == b[0] and a[1] == b[1] and abs(a[2] - b[2]) < 1e-9, (f, a, b)
        checked += 1
print(f"instances: {len(files)}  random solutions checked: {checked}  loader/decoder/evaluator: OK")
