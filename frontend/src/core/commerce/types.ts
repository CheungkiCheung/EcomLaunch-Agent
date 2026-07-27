import { z } from "zod";

const isoDateTimeSchema = z.string().datetime({ offset: true });
const sourceLocalDateTimeSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?$/u);
const metricWindowDateTimeSchema = z.union([
  isoDateTimeSchema,
  sourceLocalDateTimeSchema,
]);

export const commerceCaseSchema = z
  .object({
    id: z.string().min(1),
    workspace_id: z.string().min(1),
    title: z.string().min(1),
    severity: z.string().min(1),
    status: z.string().min(1),
    summary: z.string().nullable(),
    evidence_ids: z.array(z.string().min(1)),
    hypothesis_ids: z.array(z.string().min(1)),
    action_ids: z.array(z.string().min(1)),
    opened_at: isoDateTimeSchema,
    updated_at: isoDateTimeSchema,
    version: z.number().int().positive(),
  })
  .strict();

export const commerceCaseLineageSchema = z
  .object({
    schema_version: z.string().min(1),
    workspace_id: z.string().min(1),
    case_id: z.string().min(1),
    dataset_id: z.string().min(1),
    seller_entity_id: z.string().min(1),
    seller_external_key: z.string().min(1),
    baseline_start: isoDateTimeSchema,
    baseline_end: isoDateTimeSchema,
    current_start: isoDateTimeSchema,
    current_end: isoDateTimeSchema,
    anomaly_ids: z.array(z.string().min(1)),
    metric_observation_ids: z.array(z.string().min(1)),
    analysis_artifact_relative_path: z.string().min(1),
    analysis_artifact_sha256: z.string().min(1),
    created_at: isoDateTimeSchema,
  })
  .strict();

export const commerceEvidenceSchema = z
  .object({
    id: z.string().min(1),
    workspace_id: z.string().min(1),
    case_id: z.string().min(1),
    summary: z.string().min(1),
    relation: z.string().min(1),
    semantic_status: z.string().min(1),
    confidence: z.number().min(0).max(1),
    fact_ids: z.array(z.string().min(1)),
    metric_observation_ids: z.array(z.string().min(1)),
  })
  .strict();

export const commerceHypothesisSchema = z
  .object({
    id: z.string().min(1),
    workspace_id: z.string().min(1),
    case_id: z.string().min(1),
    statement: z.string().min(1),
    status: z.string().min(1),
    confidence: z.number().min(0).max(1),
    supporting_evidence_ids: z.array(z.string().min(1)),
    contradicting_evidence_ids: z.array(z.string().min(1)),
    version: z.number().int().positive(),
  })
  .strict();

export const commerceMetricObservationSchema = z
  .object({
    id: z.string().min(1),
    metric_name: z.string().min(1),
    semantic_status: z.string().min(1),
    value: z.string().nullable(),
    unit: z.string().nullable(),
    formula_version: z.string().nullable(),
    window_start: metricWindowDateTimeSchema.nullable(),
    window_end: metricWindowDateTimeSchema.nullable(),
    sample_size: z.number().int().nonnegative().nullable(),
    numerator: z.string().nullable(),
    denominator: z.string().nullable(),
    source_fact_count: z.number().int().nonnegative(),
    unknown_reason: z.string().nullable(),
  })
  .strict();

export const commerceCaseAnomalySchema = z
  .object({
    id: z.string().min(1),
    metric_name: z.string().min(1),
    baseline_observation_id: z.string().min(1),
    current_observation_id: z.string().min(1),
    baseline_value: z.string().min(1),
    current_value: z.string().min(1),
    absolute_change: z.string().min(1),
    relative_change: z.string().nullable(),
    direction: z.string().min(1),
    severity: z.string().min(1),
    confidence: z.number().min(0).max(1),
    baseline_sample_size: z.number().int().nonnegative(),
    current_sample_size: z.number().int().nonnegative(),
    sample_adequate: z.boolean(),
    reason: z.string().min(1),
  })
  .strict();

export const commerceCaseAnalysisSchema = z
  .object({
    status: z.enum(["available", "unavailable"]),
    unavailable_reason: z.string().nullable(),
    baseline_metrics: z.array(commerceMetricObservationSchema),
    current_metrics: z.array(commerceMetricObservationSchema),
    anomalies: z.array(commerceCaseAnomalySchema),
  })
  .strict();

export const commerceCaseActionSummarySchema = z
  .object({
    id: z.string().min(1),
    title: z.string().min(1),
    description: z.string().min(1),
    kind: z.string().min(1),
    status: z.string().min(1),
    risk_level: z.string().min(1),
    policy_level: z.string().min(1),
    approval_required: z.boolean(),
    approval_status: z.string().min(1),
    evidence_ids: z.array(z.string().min(1)),
    created_at: isoDateTimeSchema,
    updated_at: isoDateTimeSchema,
    version: z.number().int().positive(),
  })
  .strict();

export const commerceDomainEventSchema = z
  .object({
    id: z.string().min(1),
    workspace_id: z.string().min(1),
    case_id: z.string().nullable(),
    run_id: z.string().nullable(),
    event_type: z.string().min(1),
    schema_version: z.string().min(1),
    case_sequence: z.number().int().positive().nullable(),
    run_sequence: z.number().int().positive().nullable(),
    occurred_at: isoDateTimeSchema,
    recorded_at: isoDateTimeSchema,
    trace_id: z.string().min(1),
    correlation_id: z.string().min(1),
    causation_event_id: z.string().nullable(),
    actor: z.string().min(1),
    payload: z.record(z.string(), z.unknown()),
  })
  .strict();

export const commerceRunSchema = z
  .object({
    id: z.string().min(1),
    workspace_id: z.string().min(1),
    case_id: z.string().min(1),
    run_type: z.string().min(1),
    status: z.string().min(1),
    phase: z.string().min(1),
    goal: z.string().min(1),
    parent_run_id: z.string().nullable(),
    subject_action_id: z.string().nullable(),
    action_operation: z.string().nullable(),
    requested_paths: z.array(z.string().min(1)),
    wait_reason: z.string().nullable(),
    stop_reason: z.string().nullable(),
    created_at: isoDateTimeSchema,
    started_at: isoDateTimeSchema.nullable(),
    ended_at: isoDateTimeSchema.nullable(),
    updated_at: isoDateTimeSchema,
    version: z.number().int().positive(),
  })
  .strict();

export const commerceCaseListResponseSchema = z
  .object({
    items: z.array(commerceCaseSchema),
    limit: z.number().int().positive(),
    offset: z.number().int().nonnegative(),
  })
  .strict();

export const commerceCaseDetailResponseSchema = z
  .object({
    case: commerceCaseSchema,
    lineage: commerceCaseLineageSchema.nullable(),
    evidence: z.array(commerceEvidenceSchema),
    hypotheses: z.array(commerceHypothesisSchema),
    analysis: commerceCaseAnalysisSchema,
    actions: z.array(commerceCaseActionSummarySchema),
  })
  .strict();

const commerceMetricWindowSchema = z
  .object({
    start: metricWindowDateTimeSchema,
    end: metricWindowDateTimeSchema,
  })
  .strict();

const commercePeerCohortPolicySchema = z
  .object({
    formula_version: z.string().min(1),
    product_category: z.string().min(1),
    min_orders_per_seller: z.number().int().min(2),
    match_seller_state: z.boolean(),
    single_seller_orders_only: z.literal(true),
    pure_category_orders_only: z.literal(true),
  })
  .strict();

export const commerceExplicitCaseResponseSchema = z
  .object({
    case: commerceCaseSchema,
    trigger: z
      .object({
        trigger_type: z.literal("explicit_user_request"),
        requested_paths: z
          .array(z.enum(["fulfillment", "seller_peer", "review_experience"]))
          .min(1)
          .max(3),
        peer_policy: commercePeerCohortPolicySchema.nullable(),
      })
      .strict(),
    baseline_window: commerceMetricWindowSchema,
    current_window: commerceMetricWindowSchema,
  })
  .strict();

export const commerceDomainEventListResponseSchema = z
  .object({ items: z.array(commerceDomainEventSchema) })
  .strict();

export const commerceRunListResponseSchema = z
  .object({
    items: z.array(commerceRunSchema),
    limit: z.number().int().positive(),
    offset: z.number().int().nonnegative(),
  })
  .strict();

const commerceAgentBudgetLimitSchema = z
  .object({
    max_iterations: z.number().int().positive(),
    max_tool_calls: z.number().int().nonnegative(),
    max_path_agents: z.number().int().min(0).max(3),
    max_tokens: z.number().int().positive(),
    max_wall_time_seconds: z.number().positive(),
    max_model_escalations: z.number().int().nonnegative(),
    max_verification_repairs: z.number().int().nonnegative(),
    max_repeated_actions: z.number().int().nonnegative(),
    max_consecutive_no_new_evidence: z.number().int().positive(),
  })
  .strict();

const commerceBudgetUsageSchema = z
  .object({
    iterations: z.number().int().nonnegative(),
    tool_calls: z.number().int().nonnegative(),
    path_agents: z.number().int().nonnegative(),
    tokens: z.number().int().nonnegative(),
    wall_time_seconds: z.number().nonnegative(),
    model_escalations: z.number().int().nonnegative(),
    verification_repairs: z.number().int().nonnegative(),
    repeated_actions: z.number().int().nonnegative(),
    consecutive_no_new_evidence: z.number().int().nonnegative(),
  })
  .strict();

const commerceModelAssignmentSchema = z
  .object({
    schema_version: z.string().min(1),
    role: z.enum([
      "lead",
      "answer",
      "path",
      "verifier",
      "structured_repair",
      "offline_candidate",
      "action_planner",
    ]),
    base_profile: z.enum([
      "fast_structured",
      "balanced_tool_user",
      "strong_synthesizer",
      "strong_verifier",
      "offline_candidate_builder",
    ]),
    profile: z.enum([
      "fast_structured",
      "balanced_tool_user",
      "strong_synthesizer",
      "strong_verifier",
      "offline_candidate_builder",
    ]),
    model_alias: z.string().min(1),
    effort: z.enum(["low", "medium", "high"]),
    max_output_tokens: z.number().int().positive(),
    timeout_seconds: z.number().positive(),
    reason_codes: z.array(z.string().min(1)).min(1),
    router_version: z.string().min(1),
    escalation_count: z.number().int().nonnegative(),
  })
  .strict();

const commerceCheckpointToolStateSchema = z
  .object({
    tool_name: z.string().min(1),
    status: z.enum(["planned", "running", "succeeded", "failed", "denied"]),
    request_sha256: z.string().regex(/^[0-9a-f]{64}$/u),
    result_sha256: z
      .string()
      .regex(/^[0-9a-f]{64}$/u)
      .nullable(),
    error_code: z.string().min(1).nullable(),
  })
  .strict();

const commerceCheckpointSkillVersionSchema = z
  .object({
    skill_id: z.string().min(1),
    version: z.string().min(1),
  })
  .strict();

export const commerceGoalLoopCheckpointSchema = z
  .object({
    schema_version: z.string().min(1),
    workspace_id: z.string().min(1),
    run_id: z.string().min(1),
    case_id: z.string().min(1),
    goal: z.string().min(1),
    loop_iteration: z.number().int().nonnegative(),
    budget_snapshot: z
      .object({
        limit: commerceAgentBudgetLimitSchema,
        usage: commerceBudgetUsageSchema,
      })
      .strict(),
    evidence_ids: z.array(z.string().min(1)),
    hypothesis_ids: z.array(z.string().min(1)),
    active_path_task_ids: z.array(z.string().min(1)),
    model_assignments: z.array(commerceModelAssignmentSchema),
    skill_versions: z.array(commerceCheckpointSkillVersionSchema),
    context_sha256: z.string().regex(/^[0-9a-f]{64}$/u),
    tool_state: z.array(commerceCheckpointToolStateSchema),
    wait_reason: z
      .enum(["awaiting_user_input", "awaiting_approval"])
      .nullable(),
    resume_token_sha256: z
      .string()
      .regex(/^[0-9a-f]{64}$/u)
      .nullable(),
  })
  .strict();

export const commerceRunCheckpointSchema = z
  .object({
    id: z.string().min(1),
    sequence: z.number().int().positive(),
    checkpoint: commerceGoalLoopCheckpointSchema,
    created_at: isoDateTimeSchema,
  })
  .strict();

export const commerceRunDetailResponseSchema = z
  .object({
    run: commerceRunSchema,
    latest_checkpoint: commerceRunCheckpointSchema.nullable(),
  })
  .strict();

export const commerceRunCheckpointListResponseSchema = z
  .object({ items: z.array(commerceRunCheckpointSchema) })
  .strict();

const commerceExperimentDecisionSchema = z.enum([
  "promote_candidate",
  "hold",
  "reject_candidate",
]);

const commerceSkillCandidateStatusSchema = z.enum([
  "candidate",
  "offline_evaluated",
  "shadow",
  "active",
  "rejected",
  "rolled_back",
]);

export const commerceSkillCandidateSchema = z
  .object({
    schema_version: z.string().min(1),
    id: z.string().min(1),
    skill_name: z.string().regex(/^[a-z][a-z0-9-]*$/u),
    base_version: z.string().regex(/^\d+\.\d+\.\d+$/u),
    candidate_version: z.string().regex(/^\d+\.\d+\.\d+$/u),
    content: z.string().min(1),
    content_sha256: z.string().regex(/^[0-9a-f]{64}$/u),
    source_failure_codes: z.array(z.string().min(1)).min(1),
    security_scan: z
      .object({
        passed: z.boolean(),
        findings: z.array(z.string()),
        scanner_version: z.string().min(1),
      })
      .strict(),
    proposed_by: z.string().min(1),
    status: commerceSkillCandidateStatusSchema,
    source_experiment_id: z.string().nullable(),
    source_experiment_decision: commerceExperimentDecisionSchema.nullable(),
    experiment_id: z.string().nullable(),
    experiment_decision: commerceExperimentDecisionSchema.nullable(),
    regression_passed: z.boolean().nullable(),
    holdout_passed: z.boolean().nullable(),
    shadow_passed: z.boolean().nullable(),
    shadow_live_run_ids: z.array(z.string().min(1)),
    reviewer_id: z.string().min(1).nullable(),
    rollback_reason: z.string().min(1).nullable(),
    created_at: isoDateTimeSchema,
    updated_at: isoDateTimeSchema,
    version: z.number().int().positive(),
  })
  .strict();

export const commerceSkillCandidateListResponseSchema = z
  .object({ items: z.array(commerceSkillCandidateSchema) })
  .strict();

const commerceExperimentVariantSchema = z
  .object({
    name: z.string().min(1),
    prompt_version: z.string().min(1),
    context_version: z.string().min(1),
    router_version: z.string().min(1),
    skill_version: z.string().min(1),
    skill_content_sha256: z
      .string()
      .regex(/^[0-9a-f]{64}$/u)
      .nullable(),
  })
  .strict();

const commerceExperimentDefinitionSchema = z
  .object({
    schema_version: z.string().min(1),
    id: z.string().min(1),
    title: z.string().min(1),
    hypothesis: z.string().min(1),
    control: commerceExperimentVariantSchema,
    candidate: commerceExperimentVariantSchema,
    case_keys: z.array(z.string().min(1)).min(1),
    repetitions: z.number().int().min(2).max(20),
    controlled_variables: z.array(z.string().min(1)).min(1),
    reproduction_command: z.string().min(1),
    created_at: isoDateTimeSchema,
  })
  .strict();

const commerceVariantAggregateSchema = z
  .object({
    variant_name: z.string().min(1),
    run_count: z.number().int().positive(),
    passed_count: z.number().int().nonnegative(),
    hard_gate_failures: z.number().int().nonnegative(),
    pass_rate: z.number().min(0).max(1),
    mean_total_tokens: z.number().nonnegative(),
    mean_latency_ms: z.number().nonnegative(),
  })
  .strict();

const commerceExperimentReportSchema = z
  .object({
    schema_version: z.string().min(1),
    experiment_id: z.string().min(1),
    control: commerceVariantAggregateSchema,
    candidate: commerceVariantAggregateSchema,
    decision: commerceExperimentDecisionSchema,
    reasons: z.array(z.string().min(1)).min(1),
    provider_request_ids: z.array(z.string().min(1)).min(1),
    created_at: isoDateTimeSchema,
  })
  .strict();

export const commerceActiveSkillPointerSchema = z
  .object({
    schema_version: z.string().min(1),
    skill_name: z.string().regex(/^[a-z][a-z0-9-]*$/u),
    version: z.string().regex(/^\d+\.\d+\.\d+$/u),
    candidate_id: z.string().min(1).nullable(),
    previous_version: z.string().regex(/^\d+\.\d+\.\d+$/u),
    reviewer_id: z.string().min(1),
    rolled_back_candidate_id: z.string().min(1).nullable(),
    rollback_reviewer_id: z.string().min(1).nullable(),
    rollback_reason: z.string().min(1).nullable(),
  })
  .strict();

export const commerceSkillCandidateEvidenceResponseSchema = z
  .object({
    candidate: commerceSkillCandidateSchema,
    experiment_role: z
      .enum(["offline_evaluation", "source_proposal"])
      .nullable(),
    definition: commerceExperimentDefinitionSchema.nullable(),
    report: commerceExperimentReportSchema.nullable(),
    active_pointer: commerceActiveSkillPointerSchema.nullable(),
  })
  .strict();

export const commerceSkillCandidateTransitionResponseSchema = z
  .object({
    candidate: commerceSkillCandidateSchema,
    active_pointer: commerceActiveSkillPointerSchema,
    replayed: z.boolean(),
  })
  .strict();

const commerceDatasetFileSchema = z
  .object({
    id: z.string().min(1),
    original_name: z.string().min(1),
    stored_relative_path: z.string().min(1),
    format: z.string().min(1),
    size_bytes: z.number().int().nonnegative(),
    sha256: z.string().regex(/^[0-9a-f]{64}$/u),
    encoding: z.string().min(1).nullable(),
    read_only: z.boolean(),
    parent_source_id: z.string().min(1).nullable(),
    archive_member: z.string().min(1).nullable(),
  })
  .strict();

const commerceDatasetTableManifestSchema = z
  .object({
    table_name: z.string().min(1),
    source_file_id: z.string().min(1),
    format: z.string().min(1),
    sheet_name: z.string().min(1).nullable(),
    json_key: z.string().min(1).nullable(),
    archive_member: z.string().min(1).nullable(),
  })
  .strict();

export const commerceDatasetManifestSchema = z
  .object({
    schema_version: z.string().min(1),
    dataset_id: z.string().min(1),
    workspace_id: z.string().min(1),
    created_at: isoDateTimeSchema,
    storage_relative_path: z.string().min(1),
    files: z.array(commerceDatasetFileSchema).min(1),
    tables: z.array(commerceDatasetTableManifestSchema).min(1),
    warnings: z.array(z.string()),
  })
  .strict();

const commerceDatasetColumnSchema = z
  .object({
    name: z.string().min(1),
    inferred_type: z.string().min(1),
    row_count: z.number().int().nonnegative(),
    non_null_count: z.number().int().nonnegative(),
    missing_count: z.number().int().nonnegative(),
    missing_rate: z.number().min(0).max(1),
    unique_count: z.number().int().nonnegative(),
    unique_rate: z.number().min(0).max(1),
    example_values: z.array(z.string()),
    numeric_min: z.string().nullable(),
    numeric_max: z.string().nullable(),
    leading_zero_count: z.number().int().nonnegative(),
    leading_zero_rate: z.number().min(0).max(1),
    is_primary_key_candidate: z.boolean(),
    is_time_candidate: z.boolean(),
  })
  .strict();

const commerceDatasetTableProfileSchema = z
  .object({
    table_name: z.string().min(1),
    row_count: z.number().int().nonnegative(),
    column_count: z.number().int().nonnegative(),
    columns: z.array(commerceDatasetColumnSchema),
    duplicate_row_count: z.number().int().nonnegative(),
    duplicate_row_rate: z.number().min(0).max(1),
    primary_key_candidates: z.array(z.string()),
    time_candidates: z.array(z.string()),
  })
  .strict();

const commerceDatasetJoinRiskSchema = z
  .object({
    left_table: z.string().min(1),
    left_column: z.string().min(1),
    right_table: z.string().min(1),
    right_column: z.string().min(1),
    cardinality: z.string().min(1),
    requires_aggregation: z.boolean(),
    reason: z.string().min(1),
  })
  .strict();

export const commerceDatasetProfileSchema = z
  .object({
    schema_version: z.string().min(1),
    dataset_id: z.string().min(1),
    workspace_id: z.string().min(1),
    tables: z.array(commerceDatasetTableProfileSchema),
    join_risks: z.array(commerceDatasetJoinRiskSchema),
  })
  .strict();

const commerceFieldMappingSchema = z
  .object({
    table_name: z.string().min(1),
    column_name: z.string().min(1),
    semantic_field: z.string().min(1),
    confidence: z.number().min(0).max(1),
    source: z.string().min(1),
    status: z.string().min(1),
    reason: z.string().min(1),
  })
  .strict();

export const commerceSemanticMappingProfileSchema = z
  .object({
    schema_version: z.string().min(1),
    dataset_id: z.string().min(1),
    workspace_id: z.string().min(1),
    mappings: z.array(commerceFieldMappingSchema),
    unresolved_columns: z.array(z.string()),
  })
  .strict();

const commerceCapabilityAssessmentSchema = z
  .object({
    name: z.string().min(1),
    path_agent: z.string().min(1),
    status: z.string().min(1),
    reason_codes: z.array(z.string()),
    available_fields: z.array(z.string()),
    missing_required_fields: z.array(z.string()),
    missing_optional_fields: z.array(z.string()),
    unmet_dependencies: z.array(z.string()),
  })
  .strict();

export const commerceCapabilityProfileSchema = z
  .object({
    schema_version: z.string().min(1),
    dataset_id: z.string().min(1),
    workspace_id: z.string().min(1),
    capabilities: z.array(commerceCapabilityAssessmentSchema),
  })
  .strict();

export const commerceSemanticConfirmationSchema = z
  .object({
    workspace_id: z.string().min(1),
    dataset_id: z.string().min(1).nullable().optional(),
    table_name: z.string().min(1),
    column_name: z.string().min(1),
    semantic_field: z.string().min(1),
    confirmed_by: z.string().min(1).nullable(),
    confirmed_at: isoDateTimeSchema,
  })
  .strict();

export const commerceDatasetFileSummarySchema = z
  .object({
    original_name: z.string().min(1),
    format: z.string().min(1),
    size_bytes: z.number().int().nonnegative(),
    sha256: z.string().regex(/^[0-9a-f]{64}$/u),
    archive_member: z.string().min(1).nullable(),
  })
  .strict();

export const commerceDatasetCheckSummarySchema = z
  .object({
    file_count: z.number().int().positive(),
    table_count: z.number().int().positive(),
    row_count: z.number().int().nonnegative(),
    confirmed_mapping_count: z.number().int().nonnegative(),
    unresolved_mapping_count: z.number().int().nonnegative(),
    available_capability_count: z.number().int().nonnegative(),
    partial_capability_count: z.number().int().nonnegative(),
    unavailable_capability_count: z.number().int().nonnegative(),
  })
  .strict();

export const commerceDatasetListItemSchema = z
  .object({
    dataset_id: z.string().min(1),
    workspace_id: z.string().min(1),
    created_at: isoDateTimeSchema,
    files: z.array(commerceDatasetFileSummarySchema),
    checks: commerceDatasetCheckSummarySchema,
    integrity_status: z.literal("verified"),
  })
  .strict();

export const commerceDatasetListResponseSchema = z
  .object({
    items: z.array(commerceDatasetListItemSchema),
    limit: z.number().int().positive(),
    offset: z.number().int().nonnegative(),
  })
  .strict();

export const commerceDatasetDetailResponseSchema = z
  .object({
    manifest: commerceDatasetManifestSchema,
    profile: commerceDatasetProfileSchema,
    mappings: commerceSemanticMappingProfileSchema,
    capabilities: commerceCapabilityProfileSchema,
    confirmations: z.array(commerceSemanticConfirmationSchema),
    checks: commerceDatasetCheckSummarySchema,
    integrity_status: z.literal("verified"),
  })
  .strict();

export const commerceDatasetIntakeResponseSchema = z
  .object({
    manifest: commerceDatasetManifestSchema,
    profile: commerceDatasetProfileSchema,
    mappings: commerceSemanticMappingProfileSchema,
    capabilities: commerceCapabilityProfileSchema,
  })
  .strict();

export const commerceMappingResumeResponseSchema = z
  .object({
    confirmations: z.array(commerceSemanticConfirmationSchema),
    mappings: commerceSemanticMappingProfileSchema,
    capabilities: commerceCapabilityProfileSchema,
    created: z.boolean(),
    replayed: z.boolean(),
  })
  .strict();

const commerceActionStatusSchema = z.enum([
  "draft",
  "validating",
  "policy_checked",
  "awaiting_approval",
  "approved",
  "rejected",
  "executing",
  "succeeded",
  "failed",
  "monitoring",
  "effective",
  "ineffective",
  "inconclusive",
  "rolling_back",
  "rolled_back",
]);

const commerceApprovalStatusSchema = z.enum([
  "not_required",
  "pending",
  "approved",
  "rejected",
  "expired",
  "revoked",
]);

const commerceRollbackPlanSchema = z
  .object({
    strategy: z.string().min(1),
    trigger: z.string().min(1),
    verification: z.string().min(1),
  })
  .strict();

const commerceApprovalRequirementSchema = z
  .object({
    required: z.boolean(),
    status: commerceApprovalStatusSchema,
    approval_id: z.string().min(1).nullable(),
    reason: z.string().min(1).nullable(),
  })
  .strict();

const commerceNoOpParametersSchema = z
  .object({
    kind: z.literal("no_op"),
    reason: z.string().min(1),
  })
  .strict();

const commerceAuditExportParametersSchema = z
  .object({
    kind: z.literal("export_audit_cohort"),
    format: z.enum(["csv", "jsonl"]),
    max_rows: z.number().int().min(1).max(5000),
    include_direct_identifiers: z.literal(false),
  })
  .strict();

const commerceInternalTaskParametersSchema = z
  .object({
    kind: z.literal("create_internal_task"),
    owner_role: z.string().min(1),
    due_days: z.number().int().min(1).max(30),
    checklist: z.array(z.string().min(1)).min(1).max(10),
  })
  .strict();

const commerceMetricMonitorParametersSchema = z
  .object({
    kind: z.literal("create_metric_monitor"),
    metric_name: z.string().min(1),
    metric_observation_ids: z.array(z.string().min(1)).min(1),
    comparison: z.enum(["less_than_or_equal", "greater_than_or_equal"]),
    threshold: z.string().min(1),
    cadence_hours: z.number().int().min(1).max(168),
    follow_up_after_days: z.number().int().min(1).max(365),
  })
  .strict();

const commerceDataRequestParametersSchema = z
  .object({
    kind: z.literal("request_missing_data"),
    missing_fields: z.array(z.string().min(1)).min(1).max(20),
    due_days: z.number().int().min(1).max(30),
  })
  .strict();

const commerceExternalMutationParametersSchema = z
  .object({
    kind: z.literal("external_mutation"),
    connector_id: z.string().min(1),
    operation: z.enum([
      "send_merchant_message",
      "update_campaign_budget",
      "update_price",
      "update_inventory",
      "pause_listing",
      "delete_listing",
      "issue_refund",
      "suspend_seller",
    ]),
    target_ref_sha256: z.string().regex(/^[0-9a-f]{64}$/u),
    reversible: z.boolean(),
    dry_run: z.boolean(),
  })
  .strict();

export const commerceActionParametersSchema = z.discriminatedUnion("kind", [
  commerceNoOpParametersSchema,
  commerceAuditExportParametersSchema,
  commerceInternalTaskParametersSchema,
  commerceMetricMonitorParametersSchema,
  commerceDataRequestParametersSchema,
  commerceExternalMutationParametersSchema,
]);

const commerceActionSchema = z
  .object({
    id: z.string().min(1),
    workspace_id: z.string().min(1),
    case_id: z.string().min(1),
    title: z.string().min(1),
    description: z.string().min(1),
    status: commerceActionStatusSchema,
    evidence_ids: z.array(z.string().min(1)).min(1),
    risk_level: z.enum(["low", "medium", "high", "critical"]),
    approval: commerceApprovalRequirementSchema,
    rollback_plan: commerceRollbackPlanSchema,
  })
  .strict();

const commerceActionDraftSchema = z
  .object({
    schema_version: z.string().min(1),
    id: z.string().min(1),
    workspace_id: z.string().min(1),
    case_id: z.string().min(1),
    title: z.string().min(1),
    description: z.string().min(1),
    evidence_ids: z.array(z.string().min(1)).min(1),
    hypothesis_ids: z.array(z.string().min(1)).min(1),
    expected_signal_metric_ids: z.array(z.string().min(1)).min(1),
    parameters: commerceActionParametersSchema,
    rollback_plan: commerceRollbackPlanSchema,
  })
  .strict();

const commerceValidatedActionSchema = z
  .object({
    schema_version: z.string().min(1),
    draft: commerceActionDraftSchema,
    validation_sha256: z.string().regex(/^[0-9a-f]{64}$/u),
  })
  .strict();

const commerceActionPolicyDecisionSchema = z
  .object({
    schema_version: z.string().min(1),
    validated: commerceValidatedActionSchema,
    level: z.enum(["L0", "L1", "L2", "L3", "L4", "L5"]),
    disposition: z.enum(["auto_execute", "approval_required", "blocked"]),
    reason_codes: z.array(z.string().min(1)).min(1),
    required_approvals: z.number().int().min(0).max(2),
    execution_tool: z.string().min(1).nullable(),
    action: commerceActionSchema,
  })
  .strict();

export const commerceActionRecordSchema = z
  .object({
    action: commerceActionSchema,
    decision: commerceActionPolicyDecisionSchema,
    created_at: isoDateTimeSchema,
    updated_at: isoDateTimeSchema,
    version: z.number().int().positive(),
  })
  .strict();

export const commerceActionRecordListResponseSchema = z
  .object({ items: z.array(commerceActionRecordSchema) })
  .strict();

export const commerceApprovalRequestSchema = z
  .object({
    schema_version: z.string().min(1),
    id: z.string().min(1),
    workspace_id: z.string().min(1),
    case_id: z.string().min(1),
    action_id: z.string().min(1),
    required_approvals: z.number().int().min(1).max(2),
    status: commerceApprovalStatusSchema,
    approved_actor_ids: z.array(z.string().min(1)),
    rejected_actor_id: z.string().min(1).nullable(),
    modified_by_actor_id: z.string().min(1).nullable(),
    replacement_draft_sha256: z
      .string()
      .regex(/^[0-9a-f]{64}$/u)
      .nullable(),
    created_at: isoDateTimeSchema,
    updated_at: isoDateTimeSchema,
    version: z.number().int().positive(),
  })
  .strict();

const commerceNoOpArtifactSchema = z
  .object({ kind: z.literal("no_op_receipt"), reason: z.string().min(1) })
  .strict();

const commerceAuditExportArtifactSchema = z
  .object({
    kind: z.literal("audit_export"),
    format: z.enum(["csv", "jsonl"]),
    relative_path: z.string().min(1),
    sha256: z.string().regex(/^[0-9a-f]{64}$/u),
    row_count: z.number().int().nonnegative(),
    include_direct_identifiers: z.literal(false),
  })
  .strict();

const commerceInternalTaskArtifactSchema = z
  .object({
    kind: z.literal("internal_task"),
    owner_role: z.string().min(1),
    due_at: isoDateTimeSchema,
    checklist: z.array(z.string().min(1)).min(1).max(10),
  })
  .strict();

const commerceMetricMonitorArtifactSchema = z
  .object({
    kind: z.literal("metric_monitor"),
    metric_name: z.string().min(1),
    metric_observation_ids: z.array(z.string().min(1)).min(1),
    comparison: z.enum(["less_than_or_equal", "greater_than_or_equal"]),
    threshold: z.string().min(1),
    cadence_hours: z.number().int().min(1).max(168),
    follow_up_after_days: z.number().int().min(1).max(365),
    next_evaluation_at: isoDateTimeSchema,
  })
  .strict();

const commerceDataRequestArtifactSchema = z
  .object({
    kind: z.literal("data_request"),
    missing_fields: z.array(z.string().min(1)).min(1).max(20),
    due_at: isoDateTimeSchema,
  })
  .strict();

const commerceActionArtifactPayloadSchema = z.discriminatedUnion("kind", [
  commerceNoOpArtifactSchema,
  commerceAuditExportArtifactSchema,
  commerceInternalTaskArtifactSchema,
  commerceMetricMonitorArtifactSchema,
  commerceDataRequestArtifactSchema,
]);

export const commerceActionExecutionArtifactSchema = z
  .object({
    schema_version: z.string().min(1),
    workspace_id: z.string().min(1),
    case_id: z.string().min(1),
    action_id: z.string().min(1),
    execution_tool: z.string().min(1),
    payload: commerceActionArtifactPayloadSchema,
    status: z.enum([
      "completed",
      "available",
      "open",
      "active",
      "cancelled",
      "disabled",
      "archived",
    ]),
    execution_input_sha256: z.string().regex(/^[0-9a-f]{64}$/u),
    verification_sha256: z.string().regex(/^[0-9a-f]{64}$/u),
    created_at: isoDateTimeSchema,
    updated_at: isoDateTimeSchema,
    version: z.number().int().positive(),
  })
  .strict();

const commerceFollowUpMetricObservationSchema = z
  .object({
    id: z.string().min(1),
    workspace_id: z.string().min(1),
    entity_id: z.string().min(1).nullable(),
    metric_name: z.string().min(1),
    semantic_status: z.enum([
      "observed",
      "derived",
      "estimated",
      "hypothesis",
      "unknown",
      "blocked",
    ]),
    value: z.union([z.string(), z.number()]).nullable(),
    unit: z.string().min(1).nullable(),
    formula_version: z.string().min(1).nullable(),
    source_fact_ids: z.array(z.string().min(1)),
    window_start: metricWindowDateTimeSchema.nullable(),
    window_end: metricWindowDateTimeSchema.nullable(),
    sample_size: z.number().int().nonnegative().nullable(),
    numerator: z.union([z.string(), z.number()]).nullable(),
    denominator: z.union([z.string(), z.number()]).nullable(),
    unknown_reason: z.string().min(1).nullable(),
  })
  .strict();

export const commerceFollowUpRecordSchema = z
  .object({
    schema_version: z.string().min(1),
    id: z.string().min(1),
    workspace_id: z.string().min(1),
    case_id: z.string().min(1),
    action_id: z.string().min(1),
    run_id: z.string().min(1),
    dataset_id: z.string().min(1),
    evaluation_window: commerceMetricWindowSchema,
    minimum_sample_size: z.number().int().positive(),
    status: z.enum(["pending", "completed"]),
    comparison_basis: z
      .enum(["metric_monitor_threshold", "no_reliable_target"])
      .nullable(),
    metric_name: z.string().min(1).nullable(),
    comparison: z
      .enum(["less_than_or_equal", "greater_than_or_equal"])
      .nullable(),
    threshold: z.string().min(1).nullable(),
    metric_observation: commerceFollowUpMetricObservationSchema.nullable(),
    signal_status: z
      .enum(["target_met", "target_missed", "unavailable"])
      .nullable(),
    attribution_method: z.enum(["none", "controlled_comparison"]),
    outcome: z
      .enum([
        "effective",
        "ineffective",
        "inconclusive",
        "resolved",
        "reopened",
        "blocked",
      ])
      .nullable(),
    assessment: z.string().min(1).nullable(),
    limitations: z.array(z.string().min(1)),
    causal_claim: z.literal(false),
    created_at: isoDateTimeSchema,
    updated_at: isoDateTimeSchema,
    version: z.number().int().positive(),
  })
  .strict();

export const commerceActionDetailResponseSchema = z
  .object({
    record: commerceActionRecordSchema,
    approval: commerceApprovalRequestSchema.nullable(),
    artifact: commerceActionExecutionArtifactSchema.nullable(),
    follow_ups: z.array(commerceFollowUpRecordSchema),
  })
  .strict();

export const commerceActionExecutionResponseSchema = z
  .object({
    run: commerceRunSchema,
    record: commerceActionRecordSchema,
    artifact: commerceActionExecutionArtifactSchema.nullable(),
    created: z.boolean(),
    replayed: z.boolean(),
    error_message: z.string().min(1).nullable(),
  })
  .strict();

const commerceApprovalDecisionCommandSchema = z
  .object({
    schema_version: z.string().min(1),
    id: z.string().min(1),
    workspace_id: z.string().min(1),
    case_id: z.string().min(1),
    action_id: z.string().min(1),
    approval_id: z.string().min(1),
    decision: z.enum(["approve", "modify", "reject"]),
    actor_id: z.string().min(1),
    idempotency_key_sha256: z.string().regex(/^[0-9a-f]{64}$/u),
    reason: z.string().min(1).nullable(),
    replacement_draft: commerceActionDraftSchema.nullable(),
    created_at: isoDateTimeSchema,
  })
  .strict();

export const commerceApprovalDecisionResponseSchema = z
  .object({
    record: commerceActionRecordSchema,
    approval: commerceApprovalRequestSchema,
    command: commerceApprovalDecisionCommandSchema,
    replayed: z.boolean(),
  })
  .strict();

export type CommerceCase = z.infer<typeof commerceCaseSchema>;
export type CommerceCaseDetail = z.infer<
  typeof commerceCaseDetailResponseSchema
>;
export type CommerceExplicitCaseResponse = z.infer<
  typeof commerceExplicitCaseResponseSchema
>;
export type CommerceDomainEvent = z.infer<typeof commerceDomainEventSchema>;
export type CommerceEvidence = z.infer<typeof commerceEvidenceSchema>;
export type CommerceHypothesis = z.infer<typeof commerceHypothesisSchema>;
export type CommerceMetricObservation = z.infer<
  typeof commerceMetricObservationSchema
>;
export type CommerceCaseAnomaly = z.infer<typeof commerceCaseAnomalySchema>;
export type CommerceCaseActionSummary = z.infer<
  typeof commerceCaseActionSummarySchema
>;
export type CommerceRun = z.infer<typeof commerceRunSchema>;
export type CommerceRunCheckpoint = z.infer<typeof commerceRunCheckpointSchema>;
export type CommerceRunDetail = z.infer<typeof commerceRunDetailResponseSchema>;
export type CommerceSkillCandidate = z.infer<
  typeof commerceSkillCandidateSchema
>;
export type CommerceSkillCandidateEvidence = z.infer<
  typeof commerceSkillCandidateEvidenceResponseSchema
>;
export type CommerceSkillCandidateTransition = z.infer<
  typeof commerceSkillCandidateTransitionResponseSchema
>;
export type CommerceDatasetDetail = z.infer<
  typeof commerceDatasetDetailResponseSchema
>;
export type CommerceDatasetListItem = z.infer<
  typeof commerceDatasetListItemSchema
>;
export type CommerceDatasetListResponse = z.infer<
  typeof commerceDatasetListResponseSchema
>;
export type CommerceDatasetIntake = z.infer<
  typeof commerceDatasetIntakeResponseSchema
>;
export type CommerceCapabilityProfile = z.infer<
  typeof commerceCapabilityProfileSchema
>;
export type CommerceMappingResumeResponse = z.infer<
  typeof commerceMappingResumeResponseSchema
>;
export type CommerceActionParameters = z.infer<
  typeof commerceActionParametersSchema
>;
export type CommerceActionRecord = z.infer<typeof commerceActionRecordSchema>;
export type CommerceActionDetail = z.infer<
  typeof commerceActionDetailResponseSchema
>;
export type CommerceActionExecutionResponse = z.infer<
  typeof commerceActionExecutionResponseSchema
>;
export type CommerceApprovalDecisionResponse = z.infer<
  typeof commerceApprovalDecisionResponseSchema
>;

export interface CommerceWorkspaceSnapshot {
  workspaceId: string;
  cases: CommerceCase[];
  selectedCase: CommerceCaseDetail | null;
  events: CommerceDomainEvent[];
  runs: CommerceRun[];
}

export interface CommerceDataInboxSnapshot {
  workspaceId: string;
  datasets: CommerceDatasetListItem[];
  selectedDataset: CommerceDatasetDetail | null;
}

export interface CommerceActionCenterSnapshot {
  workspaceId: string;
  records: CommerceActionRecord[];
  selectedDetail: CommerceActionDetail | null;
}

export interface CommerceAgentRunSnapshot {
  workspaceId: string;
  runs: CommerceRun[];
  selectedDetail: CommerceRunDetail | null;
  events: CommerceDomainEvent[];
  checkpoints: CommerceRunCheckpoint[];
}

export interface CommerceSkillsEvalsSnapshot {
  workspaceId: string;
  candidates: CommerceSkillCandidate[];
  selectedEvidence: CommerceSkillCandidateEvidence | null;
}
