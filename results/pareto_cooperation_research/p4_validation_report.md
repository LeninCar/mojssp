# P4 Validation Report: Provenance Observability Instrumentation

## 1. Context and Objective

In accordance with Phase P4 guidelines, an observability instrumentation system was implemented and validated in the research worktree `..\mojssp-pareto-cooperation` (branch `experiment/pareto-archive-cooperation`).

The goal is to provide full, non-invasive traceability of which algorithm arm contributes which solutions to the Global Pareto Archive during adaptive MO-JSSP portfolio executions, without implementing active solution transfer, migration, or algorithmic modifications.

---

## 2. Mandatory Methodological Constraints & Verification

| Requirement | Implementation Mechanism | Validation Status |
| :--- | :--- | :--- |
| **Non-invasive to Core Algorithms** | Subclasses `Portfolio` (`ProvenanceObservingPortfolio`) and inspects `AlgorithmBlockResult.solutions` at the block boundary without touching algorithm internals. | **VERIFIED** |
| **No Solution Injection or Transfer** | Read-only observation of archive ingestion. Arms receive zero external guidance or solutions. | **VERIFIED** |
| **Zero Additional Function Evaluations (FE)** | Reuses evaluated solutions returned by arms; does not call `Evaluator` or `Decoder`. | **VERIFIED** |
| **Zero RNG / Random Stream Interference** | Uses deterministic hash algorithms (`blake2b`) and deterministic dictionary tracking. No calls to `random` or `numpy.random`. | **VERIFIED** |
| **Bit-for-Bit Deterministic Equivalence** | Evaluated via `test_bit_for_bit_determinism_with_and_without_observer`. Produces byte-identical archive fronts, evaluation counts, block arm sequences, and rewards. | **VERIFIED** |
| **Disabled Observer Equivalence (`enabled=False`)** | Evaluated via `test_disabled_observer_equivalence`. Reverts directly to `super().run_arm()`, behaving identically to unobserved `Portfolio`. | **VERIFIED** |
| **Distinguish Ingestion FE vs Discovery FE** | Ingestion FE is tracked strictly as cumulative portfolio evaluations at block ingestion (`ingestion_fe`). Discovery FE is explicitly recorded as `None` to prevent false attribution. | **VERIFIED** |
| **Deduplicate Cumulative Arm Snapshots** | Genotype hash set `_seen_genotypes_by_arm` detects re-offered incumbent solutions across blocks, marking them as `incumbent` rather than new discoveries. | **VERIFIED** |
| **Genotype vs Objective Identity Distinction** | Tracks `genotype_id` (SHA256/blake2b hex digest of `(sequence, modes)`) and `objective_key` (`(Cmax, T, E)`) independently. Multiple arms discovering the same objective vector with distinct genotypes are preserved and credited. | **VERIFIED** |

---

## 3. Definitive Phase 2 Portfolio Integration Verification

To validate the definitive Phase 2 architecture, a full adaptive portfolio execution was carried out with the frozen configuration:
- **Algorithms:** `MOEA/D`, `NSGA-II`, `SPEA2` (Phase 2 definitive arms).
- **Selector:** `SlidingWindowUCB` ($W=5$, $c=0.07$, neutral warmup enabled).
- **Reward:** `HypervolumeRewardTracker` with analytical instance bounds.
- **Instance:** Development instance `base_c01_5x5_b02.dzn`.
- **Budget:** 300 evaluations (6 blocks of 50 FE), Seed = 42.

Three comparative runs were executed under identical conditions:
1. `Run_Std`: Standard unobserved `Portfolio`.
2. `Run_Obs`: `ProvenanceObservingPortfolio` (`enabled=True`, `tracker=ProvenanceTracker()`).
3. `Run_Dis`: `ProvenanceObservingPortfolio` (`enabled=False`, `tracker=None`).

### Verification Results Across All Runs

| Metric | `Run_Std` (Standard) | `Run_Obs` (Observed) | `Run_Dis` (Disabled) | Equivalence |
| :--- | :--- | :--- | :--- | :--- |
| **Total FE Used** | 300 | 300 | 300 | **EXACT (300)** |
| **Block Count** | 6 | 6 | 6 | **EXACT (6)** |
| **Arm Sequence** | MOEA/D, NSGA-II, SPEA2, MOEA/D, NSGA-II, SPEA2 | MOEA/D, NSGA-II, SPEA2, MOEA/D, NSGA-II, SPEA2 | MOEA/D, NSGA-II, SPEA2, MOEA/D, NSGA-II, SPEA2 | **IDENTICAL** |
| **Block 0 Reward** | 0.8000023243930334 | 0.8000023243930334 | 0.8000023243930334 | **IDENTICAL** |
| **Block 1 Reward** | 0.021901107841258094 | 0.021901107841258094 | 0.021901107841258094 | **IDENTICAL** |
| **Block 2 Reward** | 0.019409921598967594 | 0.019409921598967594 | 0.019409921598967594 | **IDENTICAL** |
| **Block 3 Reward** | 0.02697046856513774 | 0.02697046856513774 | 0.02697046856513774 | **IDENTICAL** |
| **Block 4 Reward** | 0.0006257291400285636 | 0.0006257291400285636 | 0.0006257291400285636 | **IDENTICAL** |
| **Block 5 Reward** | 0.009467758626866885 | 0.009467758626866885 | 0.009467758626866885 | **IDENTICAL** |
| **Final HV** | 0.8783773101652923 | 0.8783773101652923 | 0.8783773101652923 | **IDENTICAL** |
| **Final Archive Size** | 18 solutions | 18 solutions | 18 solutions | **EXACT (18)** |
| **Objective Coordinates** | Exact identical set | Exact identical set | Exact identical set | **IDENTICAL** |
| **Genotype SHA Hashes** | Exact identical set | Exact identical set | Exact identical set | **IDENTICAL** |

---

## 4. Observability Telemetry & Snapshot Deduplication

The telemetry recorded by `ProvenanceTracker` for the 6 executed blocks demonstrates correct snapshot deduplication and lifecycle accounting:

### Per-Block Ingestion Breakdown

| Block | Selected Arm | Offered | Accepted New | Incumbent (Re-observed) | Rejected Dominated | Evicted Old | Active Archive Size |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0** | `MOEA/D` | 11 | 11 | 0 | 0 | 0 | 11 |
| **1** | `NSGA-II` | 9 | 9 | 0 | 0 | 9 | 11 |
| **2** | `SPEA2` | 7 | 4 | 0 | 3 | 6 | 9 |
| **3** | `MOEA/D` | 11 | 10 | 0 | 1 | 4 | 15 |
| **4** | `NSGA-II` | 15 | 7 | **2** | 6 | 1 | 21 |
| **5** | `SPEA2` | 9 | 6 | **1** | 2 | 9 | 18 |

> **Conservation Equation:** For every block $b$, the conservation equality holds strictly:
> $$\text{solutions\_offered} = \text{accepted\_new} + \text{incumbent} + \text{rejected\_dominated} + \text{rejected\_duplicate}$$
> No solutions disappear or are counted in multiple categories within a block.

> **Snapshot Deduplication:** In Blocks 4 and 5, `NSGA-II` and `SPEA2` re-offered solutions previously discovered in earlier blocks. The tracker correctly identified them as `incumbent=2` and `incumbent=1`, preventing inflation of new discovery counts.

---

## 5. Non-Equivalence of Contribution Measures

A critical methodological finding of the audit is that **contribution in number of solutions**, **sub-archive Hypervolume**, and **accrued dynamic reward** are fundamentally different, non-equivalent dimensions of performance:

| Dimension | Definition | Nature | Properties |
| :--- | :--- | :--- | :--- |
| **1. Solution Count Contribution** | Number of active solutions in final archive originally introduced by arm $i$. | Discrete structural quantity. | Does not reflect objective distribution, Pareto spread, or extreme point quality. |
| **2. Sub-archive Hypervolume** | $HV(\text{Archive}_i)$ computed solely on the final solutions originating from arm $i$. | Static spatial geometric metric. | Evaluates the independent quality of arm $i$'s contribution to the final objective space. **Crucially: $HV(\text{Archive}_i)$ does NOT equal the canonical marginal contribution $MC_i = HV(U) - HV(ND(U \setminus A_i))$**, because it ignores synergy and non-dominated coverage overlaps with other arms. |
| **3. Accrued Dynamic Reward** | $\sum_{b \in \text{Blocks}_i} \max(0, HV_{\text{after}} - HV_{\text{before}})$ accumulated during execution. | Dynamic temporal trajectory metric. | Strongly dependent on block arrival order. Arms executing early (e.g. Block 0 during warmup) capture large initial HV expansion, whereas arms executing later encounter diminishing returns. |

### Empirical Comparison on Pilot Run (300 FE, Seed 42)

| Algorithm Arm | Active Solutions in Final Front | Sub-Archive Hypervolume ($HV_i$) | Cumulative Accrued Reward |
| :--- | :---: | :---: | :---: |
| **`MOEA/D`** | **8** (44.4%) | **0.864341** | **0.826973** (94.1%) |
| **`NSGA-II`** | **3** (16.7%) | **0.842364** | **0.022527** (2.6%) |
| **`SPEA2`** | **7** (38.9%) | **0.868136** | **0.028878** (3.3%) |

> **Key Analytical Takeaway:** `SPEA2` contributed **7 of the 18 solutions** and achieved the **highest individual sub-archive HV (0.868136)**, yet accrued only **3.3% of the total reward** because `MOEA/D` executed first in Block 0 capturing the initial baseline expansion ($0.800002$). Equating dynamic reward to Pareto contribution would severely misrepresent the value of `SPEA2`. The provenance telemetry successfully decouples these three metrics.

---

## 6. Verification of 1-to-1 Archive Correspondence & Objective Ties

A deep inspection of the 18 solutions residing in the final Pareto archive confirmed:

1. **Exact 1-to-1 Match:** The 18 entries in `global_archive.entries` correspond exactly to the 18 active records (`status == "ACTIVE"`) in `tracker.solutions`. The set of active genotype hashes matches with zero discrepancies ($18 = 8 + 3 + 7$).
2. **Genotypic vs Objective Disambiguation:** 
   - Across the 18 active solutions, there are **17 unique objective vectors**.
   - Objective vector `(491, 1071, 1326.0)` is represented by **two distinct genotypes**:
     - Genotype `c4e20ce080a1...`
     - Genotype `50b40f522f69...`
   - Both were preserved in the global archive as distinct entries, and the tracker tracked each genotype independently without conflation.
   - On instances with smaller objective spaces (e.g. `data/validation/toy_instance.dzn`), objective vectors were discovered independently by multiple arms (MOEA/D, NSGA-II, SPEA2) through different genotypes, with `objective_provenance` registering all discovering arms without corrupting genotypic identity.

---

## 7. Audit of `src/mojssp/__init__.py` Exact Module Exception Handling

The package initialization in `src/mojssp/__init__.py` was refined to eliminate prefix/suffix heuristics:

### Final Implementation

```python
try:
    from .pairing import ( ... )
    _PAIRING_SYMBOLS = [ ... ]
except ModuleNotFoundError as _err:
    if _err.name not in (f"{__name__}.pairing", "mojssp.pairing"):
        raise
    _PAIRING_SYMBOLS = []
```

### Verification & Automated Test
- When `mojssp.pairing` itself is absent, `_err.name` exactly equals `"mojssp.pairing"` (or `"src.mojssp.pairing"` depending on import root) and optional pairing symbols are omitted from `__all__`.
- If an internal dependency fails during an import (e.g. `_err.name == 'some_internal_package'`), it does not match `mojssp.pairing`, and the exception is immediately re-raised.
- Automated in `tests/test_provenance_observability.py::test_import_internal_errors_not_suppressed` (PASSED).

---

## 8. Deterministic Reproduction of `base_c01_5x5_b02.dzn` and Full Suite Execution

### 8.1. Instance Reproduction Recipe
Under authorization of **Alternativa A**, the single fixture required by `test_phase2_portfolio_integration.py` was deterministically synthesized using the canonical generator:

```python
from scripts.generate_mojssp_instances import InstanceConfig, generate_single_instance

cfg = InstanceConfig(
    name="base_c01_5x5_b02",
    group="expanded_200",
    profile="base_balanced",
    num_jobs=5,
    num_machines=5,
    seed=10201,  # Rule: Seed(C=1, b=2) = 10000*1 + 100*2 + 1 = 10201
)
dzn_str, _ = generate_single_instance(cfg)
Path("data/generated/expanded_200/base_c01_5x5_b02.dzn").write_text(dzn_str, encoding="utf-8")
```

### 8.2. Verification Against Original Worktree
Comparing in read-only mode against `..\mojssp-dmab\data\generated\expanded_200\base_c01_5x5_b02.dzn`:
- **Textual Equality:** `True`
- **Byte Equality:** `True`
- **SHA-256 Checksum:** `e2eb85afe8aef99207c407bae4d4c242da0f2b7f76bdcbe539d6125db90b6ff9` (Exact match)
- **Line Endings:** Both files contain native `\r\n` (CRLF).

### 8.3. Full Automated Test Suite Results
Running `python -m unittest discover tests` across the entire worktree:

- **Total Tests Discovered and Run:** **361**
- **Successful (Passed):** **361**
- **Failures:** **0**
- **Errors:** **0**
- **Skipped:** **0**
- **Verification of `test_phase2_portfolio_integration.py`:** **6/6 tests executed and PASSED** (0 skipped).
- **Verification of `test_provenance_observability.py`:** **6/6 tests executed and PASSED** (0 skipped).

---

## 9. Limitations & Architectural Boundaries

1. **Ingestion FE vs Inner-Loop Discovery FE:**
   The exact evaluation at which a solution is created inside the evolutionary loop (e.g. evaluation 234 of 500) cannot be observed without instrumenting the internal loops of `MOEADArm`, `NSGA2Arm`, and `SPEA2Arm`. Telemetry strictly records `ingestion_fe` (FE accumulated by the portfolio when the arm finishes its block).
2. **Set-Level Hypervolume Attribution:**
   Hypervolume is a non-linear set metric. The attribution of hypervolume gains is computed strictly at the block level ($\Delta HV$). Solution-level attribution is intentionally omitted to avoid misleading order-dependent biases.
3. **Sub-Archive HV vs Marginal Contribution ($MC$):**
   The sub-archive hypervolume $HV(\text{Archive}_i)$ evaluates the standalone spread of arm $i$'s solutions in the final front, but must **not** be confused with canonical marginal contribution $MC_i = HV(U) - HV(ND(U \setminus A_i))$, nor with dynamic reward accrued over time.
4. **No Active Cooperation:**
   The archive remains strictly a passive global repository. No solution migration, injection, or seeding of arm populations from the global archive was implemented.
