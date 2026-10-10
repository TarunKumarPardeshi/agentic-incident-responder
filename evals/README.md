# Evaluation Harness

This benchmark suite evaluates the agent's incident triage performance across **20 synthetic production incident scenarios** representing real-world failure patterns:
- Pod `OOMKilled` and `CrashLoopBackOff`
- Database Connection Pool Exhaustion
- Upstream Service Rate Limiting & Latency Spikes
- Misconfigured Deployments & Breaking Changes

## Running the Benchmark

```bash
python -m evals.run --incidents evals/synthetic/
```

## Key Metrics Evaluated

1. **RCA Category Precision**: Correctly isolating the underlying failure domain.
2. **Severity Classification**: Adherence to standard SRE SLO error budget severity tiers (`SEV-1`, `SEV-2`, `SEV-3`).
3. **Safety & HITL Compliance**: Strictly enforces that zero destructive actions are executed without human review.
4. **Triage Latency**: Sub-second telemetry aggregation and mitigation formulation.
