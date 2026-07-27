import type {
  CommerceSkillCandidate,
  CommerceSkillCandidateEvidence,
} from "@/core/commerce";

const CANDIDATE_ID = "skillcand_0123456789abcdef0123456789abcdef";

export function commerceSkillCandidate(): CommerceSkillCandidate {
  return {
    schema_version: "commerce.skill-candidate@1.0.0",
    id: CANDIDATE_ID,
    skill_name: "commerce-diagnostic-synthesis",
    base_version: "1.2.0",
    candidate_version: "1.3.0",
    content:
      "Never invent numeric action thresholds; use configured server policy only.",
    content_sha256:
      "f46d8884d6ffba670f9c3d9299d702f9c9fdd477e759dbcaaabcc4450dc6b228",
    source_failure_codes: ["unsupported-action-threshold"],
    security_scan: {
      passed: true,
      findings: [],
      scanner_version: "commerce-skill-security@1.0.0",
    },
    proposed_by: "skill-evolution-runner",
    status: "shadow",
    source_experiment_id: "exp_1123456789abcdef0123456789abcdef",
    source_experiment_decision: "promote_candidate",
    experiment_id: "exp_0123456789abcdef0123456789abcdef",
    experiment_decision: "promote_candidate",
    regression_passed: true,
    holdout_passed: true,
    shadow_passed: true,
    shadow_live_run_ids: ["run_shadow_1", "run_shadow_2"],
    reviewer_id: null,
    rollback_reason: null,
    created_at: "2026-07-19T10:00:00Z",
    updated_at: "2026-07-19T10:30:00Z",
    version: 3,
  };
}

export function commerceSkillCandidateEvidence(): CommerceSkillCandidateEvidence {
  const candidate = commerceSkillCandidate();
  return {
    candidate,
    experiment_role: "offline_evaluation",
    definition: {
      schema_version: "commerce.experiment@1.0.0",
      id: "exp_0123456789abcdef0123456789abcdef",
      title: "Four-Gold threshold hardening",
      hypothesis: "Candidate improves safety and Pareto efficiency.",
      control: {
        name: "control",
        prompt_version: "prompt@1.0.0",
        context_version: "gold-case@1.0.0",
        router_version: "router@1.0.0",
        skill_version: "commerce-diagnostic-synthesis@1.2.0",
        skill_content_sha256: "a".repeat(64),
      },
      candidate: {
        name: "candidate",
        prompt_version: "prompt@1.0.0",
        context_version: "gold-case@1.0.0",
        router_version: "router@1.0.0",
        skill_version: "commerce-diagnostic-synthesis@1.3.0-candidate",
        skill_content_sha256: candidate.content_sha256,
      },
      case_keys: [
        "GC-FULFILLMENT-001",
        "GC-REVIEW-002",
        "GC-CAPABILITY-003",
        "GC-PEER-004",
      ],
      repetitions: 2,
      controlled_variables: ["model=deepseek-v4"],
      reproduction_command: "python -m app.commerce.evaluation.run_experiment",
      created_at: "2026-07-19T10:05:00Z",
    },
    report: {
      schema_version: "commerce.experiment-report@1.0.0",
      experiment_id: "exp_0123456789abcdef0123456789abcdef",
      control: {
        variant_name: "control",
        run_count: 8,
        passed_count: 6,
        hard_gate_failures: 2,
        pass_rate: 0.75,
        mean_total_tokens: 2334.625,
        mean_latency_ms: 5691.85,
      },
      candidate: {
        variant_name: "candidate",
        run_count: 8,
        passed_count: 8,
        hard_gate_failures: 0,
        pass_rate: 1,
        mean_total_tokens: 2051.875,
        mean_latency_ms: 4212.11,
      },
      decision: "promote_candidate",
      reasons: [
        "Candidate passes all hard gates and improves the Pareto frontier",
      ],
      provider_request_ids: Array.from(
        { length: 32 },
        (_, index) => `req-${index}`,
      ),
      created_at: "2026-07-19T10:20:00Z",
    },
    active_pointer: null,
  };
}
