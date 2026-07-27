import { afterEach, describe, expect, test, vi } from "vitest";

import {
  loadCommerceSkillsEvalsSnapshot,
  promoteCommerceSkillCandidate,
  rollbackCommerceActiveSkill,
} from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const CANDIDATE_ID = "skillcand_0123456789abcdef0123456789abcdef";

afterEach(() => vi.unstubAllGlobals());

describe("Commerce Skills & Evals API", () => {
  test("loads the candidate list and selected immutable evaluation evidence", async () => {
    const requests: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = requestUrl(input);
        requests.push({ url, init });
        if (url.endsWith("/api/commerce/skill-candidates")) {
          return jsonResponse({ items: [candidate()] });
        }
        if (
          url.endsWith(
            `/api/commerce/skill-candidates/${CANDIDATE_ID}/evidence`,
          )
        ) {
          return jsonResponse(evidence());
        }
        return new Response("not found", { status: 404 });
      }),
    );

    const snapshot = await loadCommerceSkillsEvalsSnapshot({
      workspaceId: WORKSPACE_ID,
      selectedCandidateId: CANDIDATE_ID,
    });

    expect(snapshot.candidates).toHaveLength(1);
    expect(snapshot.selectedEvidence?.report?.candidate.passed_count).toBe(8);
    expect(requests).toHaveLength(2);
    for (const request of requests) {
      expect(
        new Headers(request.init?.headers).get("X-Commerce-Workspace-Id"),
      ).toBe(WORKSPACE_ID);
    }
  });

  test("sends actor-scoped idempotent promotion and rollback commands", async () => {
    const requests: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        requests.push({ url: requestUrl(input), init });
        return jsonResponse({
          candidate: {
            ...candidate(),
            status: "active",
            reviewer_id: "reviewer-a",
          },
          active_pointer: activePointer(),
          replayed: false,
        });
      }),
    );

    await promoteCommerceSkillCandidate({
      workspaceId: WORKSPACE_ID,
      actorId: "reviewer-a",
      candidateId: CANDIDATE_ID,
      idempotencyKey: "promote-candidate-001",
    });
    await rollbackCommerceActiveSkill({
      workspaceId: WORKSPACE_ID,
      actorId: "reviewer-a",
      skillName: "commerce-diagnostic-synthesis",
      reason: "新留出集出现回归",
      idempotencyKey: "rollback-candidate-001",
    });

    expect(
      requests[0]?.url.endsWith(
        `/api/commerce/skill-candidates/${CANDIDATE_ID}/promote`,
      ),
    ).toBe(true);
    expect(
      requests[1]?.url.endsWith(
        "/api/commerce/skills/commerce-diagnostic-synthesis/rollback",
      ),
    ).toBe(true);
    expect(requests[0]?.init?.method).toBe("POST");
    expect(requests[1]?.init?.method).toBe("POST");
    expect(
      new Headers(requests[0]?.init?.headers).get("X-Commerce-Actor-Id"),
    ).toBe("reviewer-a");
    const rollbackBody = requests[1]?.init?.body;
    expect(typeof rollbackBody).toBe("string");
    if (typeof rollbackBody !== "string")
      throw new Error("Missing rollback body");
    expect(JSON.parse(rollbackBody)).toEqual({
      reason: "新留出集出现回归",
      idempotency_key: "rollback-candidate-001",
    });
  });
});

function candidate() {
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

function evidence() {
  return {
    candidate: candidate(),
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
        skill_content_sha256: candidate().content_sha256,
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

function activePointer() {
  return {
    schema_version: "commerce.active-skill-pointer@1.0.0",
    skill_name: "commerce-diagnostic-synthesis",
    version: "1.3.0",
    candidate_id: CANDIDATE_ID,
    previous_version: "1.2.0",
    reviewer_id: "reviewer-a",
    rolled_back_candidate_id: null,
    rollback_reviewer_id: null,
    rollback_reason: null,
  };
}

function requestUrl(input: RequestInfo | URL): string {
  return typeof input === "string"
    ? input
    : input instanceof URL
      ? input.toString()
      : input.url;
}

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
