import {
  ChartNoAxesCombinedIcon,
  CompassIcon,
  GraduationCapIcon,
  ImageIcon,
  ListChecksIcon,
  MicroscopeIcon,
  PenLineIcon,
  SearchIcon,
  ShapesIcon,
  SparklesIcon,
  VideoIcon,
} from "lucide-react";

import type { Translations } from "./types";

export const enUS: Translations = {
  // Locale meta
  locale: {
    localName: "English",
  },

  // Common
  common: {
    home: "Home",
    settings: "Settings",
    delete: "Delete",
    edit: "Edit",
    rename: "Rename",
    share: "Share",
    openInNewWindow: "Open in new window",
    close: "Close",
    more: "More",
    search: "Search",
    loadMore: "Load more",
    retry: "Retry",
    download: "Download",
    thinking: "Thinking",
    artifacts: "Artifacts",
    public: "Public",
    custom: "Custom",
    notAvailableInDemoMode: "Not available in demo mode",
    loading: "Loading...",
    artifactLoadFailed: "This artifact could not be loaded.",
    version: "Version",
    lastUpdated: "Last updated",
    code: "Code",
    preview: "Preview",
    cancel: "Cancel",
    save: "Save",
    install: "Install",
    create: "Create",
    import: "Import",
    export: "Export",
    exportAsMarkdown: "Export as Markdown",
    exportAsJSON: "Export as JSON",
    exportSuccess: "Conversation exported",
    streamingStatus: {
      preparing: "Preparing a response",
      thinking: "Structuring the question and constraints",
      searching: "Searching public signals",
      reading: "Reading a public page",
      researcher: "Market Researcher is working",
      offer: "Offer Architect is working",
      assets: "Asset Studio is working",
      analyzing: "Inspecting uploaded data",
      joining: "Joining multiple data files",
      experiment: "Calculating experiment results",
      rendering: "Generating the Launch Pack",
      writing: "Writing delivery files",
      preflight: "Running deterministic preflight",
      repairing: "Repairing files from preflight observations",
      finalizing: "Preparing the final delivery",
      failed: "The run encountered an error",
    },
  },

  // Home
  home: {
    docs: "Docs",
    blog: "Blog",
  },

  // Welcome
  welcome: {
    greeting: "Hello, again!",
    description:
      "Welcome to OpenSKU, an open source super agent. With built-in and custom skills, OpenSKU helps you search on the web, analyze data, and generate artifacts like slides, web pages and do almost anything.",

    createYourOwnSkill: "Create Your Own Skill",
    createYourOwnSkillDescription:
      "Create your own skill to release the power of OpenSKU. With customized skills,\nOpenSKU can help you search on the web, analyze data, and generate\n artifacts like slides, web pages and do almost anything.",
  },

  // Clipboard
  clipboard: {
    copyToClipboard: "Copy to clipboard",
    copiedToClipboard: "Copied to clipboard",
    failedToCopyToClipboard: "Failed to copy to clipboard",
    linkCopied: "Link copied to clipboard",
  },

  // Input Box
  inputBox: {
    placeholder: "How can I assist you today?",
    createSkillPrompt:
      "We're going to build a new skill step by step with `skill-creator`. To start, what do you want this skill to do?",
    addAttachments: "Add attachments",
    mode: "Mode",
    flashMode: "Flash",
    flashModeDescription: "Fast and efficient, but may not be accurate",
    reasoningMode: "Reasoning",
    reasoningModeDescription:
      "Reasoning before action, balance between time and accuracy",
    proMode: "Pro",
    proModeDescription:
      "Reasoning, planning and executing, get more accurate results, may take more time",
    ultraMode: "Ultra",
    ultraModeDescription:
      "Pro mode with subagents to divide work; best for complex multi-step tasks",
    reasoningEffort: "Reasoning Effort",
    reasoningEffortMinimal: "Minimal",
    reasoningEffortMinimalDescription: "Retrieval + Direct Output",
    reasoningEffortLow: "Low",
    reasoningEffortLowDescription: "Simple Logic Check + Shallow Deduction",
    reasoningEffortMedium: "Medium",
    reasoningEffortMediumDescription:
      "Multi-layer Logic Analysis + Basic Verification",
    reasoningEffortHigh: "High",
    reasoningEffortHighDescription:
      "Full-dimensional Logic Deduction + Multi-path Verification + Backward Check",
    searchModels: "Search models...",
    surpriseMe: "Surprise",
    surpriseMePrompt: "Surprise me",
    followupLoading: "Generating follow-up questions...",
    followupConfirmTitle: "Send suggestion?",
    followupConfirmDescription:
      "You already have text in the input. Choose how to send it.",
    followupConfirmAppend: "Append & send",
    followupConfirmReplace: "Replace & send",
    suggestions: [
      {
        suggestion: "Write",
        prompt: "Write a blog post about the latest trends on [topic]",
        icon: PenLineIcon,
      },
      {
        suggestion: "Research",
        prompt:
          "Conduct a deep dive research on [topic], and summarize the findings.",
        icon: MicroscopeIcon,
      },
      {
        suggestion: "Collect",
        prompt: "Collect data from [source] and create a report.",
        icon: ShapesIcon,
      },
      {
        suggestion: "Learn",
        prompt: "Learn about [topic] and create a tutorial.",
        icon: GraduationCapIcon,
      },
    ],
    suggestionsCreate: [
      {
        suggestion: "Webpage",
        prompt: "Create a webpage about [topic]",
        icon: CompassIcon,
      },
      {
        suggestion: "Image",
        prompt: "Create an image about [topic]",
        icon: ImageIcon,
      },
      {
        suggestion: "Video",
        prompt: "Create a video about [topic]",
        icon: VideoIcon,
      },
      {
        type: "separator",
      },
      {
        suggestion: "Skill",
        prompt:
          "We're going to build a new skill step by step with `skill-creator`. To start, what do you want this skill to do?",
        icon: SparklesIcon,
      },
    ],
  },

  // Sidebar
  sidebar: {
    newChat: "New chat",
    chats: "Chats",
    recentChats: "Recent chats",
    demoChats: "Demo chats",
    agents: "Agents",
    primaryAgents: "Primary agents",
    warRoom: "War Room",
    ecomLaunch: "OpenSKU Launch Team",
    dataInspector: "Growth Analyst",
    openskufast: "OpenSKU Fast",
  },

  // Agents
  agents: {
    title: "Agents",
    description:
      "Create and manage custom agents with specialized prompts and capabilities.",
    newAgent: "New Agent",
    emptyTitle: "No custom agents yet",
    emptyDescription:
      "Create your first custom agent with a specialized system prompt.",
    chat: "Chat",
    delete: "Delete",
    deleteConfirm:
      "Are you sure you want to delete this agent? This action cannot be undone.",
    deleteSuccess: "Agent deleted",
    newChat: "New chat",
    createPageTitle: "Design your Agent",
    createPageSubtitle:
      "Describe the agent you want — I'll help you create it through conversation.",
    nameStepTitle: "Name your new Agent",
    nameStepHint:
      "Letters, digits, and hyphens only — stored lowercase (e.g. code-reviewer)",
    nameStepPlaceholder: "e.g. code-reviewer",
    nameStepContinue: "Continue",
    nameStepInvalidError:
      "Invalid name — use only letters, digits, and hyphens",
    nameStepAlreadyExistsError: "An agent with this name already exists",
    nameStepNetworkError:
      "Network request failed — check your network or backend connection",
    nameStepCheckError: "Could not verify name availability — please try again",
    nameStepCheckErrorWithDetail: "Name check failed: {detail}",
    nameStepApiDisabledError:
      "Custom agent management is not enabled on this server. Please contact your administrator.",
    nameStepBootstrapMessage:
      "The new custom agent name is {name}. Help me design its purpose, behavior, and SOUL.md before saving it.",
    save: "Save agent",
    saving: "Saving agent...",
    saveRequested:
      "Save requested. OpenSKU is generating and saving an initial version now.",
    saveHint:
      "You can save this agent at any time from the top-right menu, even if this is only a first draft.",
    saveCommandMessage:
      "Please save this custom agent now based on everything we have discussed so far. Treat this as my explicit confirmation to save. If some details are still missing, make reasonable assumptions, generate a concise first SOUL.md in English, and call setup_agent immediately without asking me for more confirmation.",
    agentCreatedPendingRefresh:
      "The agent was created, but OpenSKU could not load it yet. Please refresh this page in a moment.",
    more: "More actions",
    agentCreated: "Agent created!",
    startChatting: "Start chatting",
    backToGallery: "Back to Gallery",
    ecomLaunchName: "OpenSKU Launch Team",
    dataInspectorName: "Growth Analyst",
    openskufastName: "OpenSKU Fast",
    ecomLaunchWelcomeDescription:
      "Turn a rough product idea into a 7-day ecommerce launch validation pack using public signals, uploaded context, and labeled assumptions.",
    dataInspectorWelcomeDescription:
      "Upload CSV or XLSX data to find changes, anomalies, causes, and practical growth opportunities.",
    openskufastWelcomeDescription:
      "Single-agent fast product research & decisions. Uses Web Search + 22 PM skills for market analysis, positioning, pricing, and GTM advice.",
    ecomLaunchWelcomeBadges: [
      "Public signals",
      "No backend data needed",
      "Launch Crew",
      "7-day pack",
    ],
    openskufastWelcomeBadges: [
      "Single agent",
      "Web Search",
      "PM Skills",
      "Fast decisions",
    ],
    ecomLaunchSuggestions: [
      {
        suggestion: "No-data validation",
        prompt:
          "I want to launch a $15-$30 commuter coffee tumbler, but I have no store backend data. Use public signals to judge whether it is worth a 7-day lightweight validation test and output a Launch Validation Pack.",
        icon: CompassIcon,
      },
      {
        suggestion: "Category wedge",
        prompt:
          "Find a low-cost new-product opportunity in pet supplies. Start from public signals, then give me an audience wedge, offer hypotheses, and a 7-day validation plan.",
        icon: MicroscopeIcon,
      },
      {
        suggestion: "Public link",
        prompt:
          "Here is a public competitor/product link. Do not assume I have sales or conversion data; judge whether it is worth a small launch validation test only from visible public signals and page evidence:",
        icon: ShapesIcon,
      },
      {
        suggestion: "Incomplete brief",
        prompt:
          "I only have a rough new-product idea. Ask me the single most important clarifying question first; if information is still missing, continue with clearly labeled assumptions and build a lightweight validation plan.",
        icon: SparklesIcon,
      },
    ],
    dataInspectorSuggestions: [
      {
        suggestion: "Data overview",
        prompt: "Analyze this data.",
        icon: ChartNoAxesCombinedIcon,
      },
      {
        suggestion: "Find anomalies",
        prompt: "Find the most important anomalies and changes in this data.",
        icon: SearchIcon,
      },
      {
        suggestion: "Improvement areas",
        prompt: "Based on this data, what should be improved first?",
        icon: ListChecksIcon,
      },
    ],
    dataInspectorDemo: {
      title: "Choose a demo scenario",
      description: "Load real CSVs and a complete analysis prompt in one click",
      selectorLabel: "Growth Analyst demo scenarios",
      note: "Only demo attachments from this card are replaced; manual files stay. Demo data only.",
      load: "Load selected data",
      loaded: "Selected data loaded",
      scenarios: {
        experiment: {
          label: "A/B test",
          description: "3 CSVs · 200 users · conversion experiment",
          preview:
            "control 100 / 10 conversions · variant 100 / 20 conversions",
          prompt:
            "Analyze these 3 demo files end to end: inspect fields and data quality; join customers, assignments, and outcomes; compare control vs variant conversion rate, absolute difference, relative lift, p-value, 95% confidence interval, and SRM; then give a ship / extend / stop decision with next steps.",
        },
        channel: {
          label: "Channel ROI",
          description: "3 CSVs · 30 days · 4 channels · 12 campaigns",
          preview: "Xiaohongshu ROAS ≈ 3.7 · search ≈ 3.0 · display < 1",
          prompt:
            "Analyze these 3 channel-performance demo files: inspect data quality, then join ad_spend, sessions, and orders by date, channel, and campaign. Calculate CTR, visit conversion, order conversion, CAC, ROAS, refunds, and net revenue by channel and campaign; identify high-spend low-conversion traffic and recommend which budgets to increase, hold, or pause next week.",
        },
        retention: {
          label: "Retention",
          description: "3 CSVs · 12 weekly cohorts · 240 users",
          preview:
            "referral D30 40% · organic / Xiaohongshu 20% · paid display 0%",
          prompt:
            "Analyze these 3 retention demo files: inspect fields and data quality; join users, events, and subscriptions; build signup-week cohorts and calculate D1, D7, and D30 retention, purchase rate, and subscription conversion. Compare acquisition-channel quality, locate the largest drop-off, and recommend prioritized retention experiments.",
        },
        product: {
          label: "Merchandising",
          description: "3 CSVs · 8 SKUs · 240 orders",
          preview:
            "sku-001 high-volume low-margin · sku-002 high-margin low-volume · sku-008 inventory risk",
          prompt:
            "Analyze these 3 merchandising demo files: inspect fields and data quality; join products, orders, and order_items; calculate GMV, units, AOV, refunds, gross profit, gross margin, and inventory risk by SKU. Identify high-volume low-margin, high-margin low-volume, and high-inventory low-velocity products, then recommend expansion, pricing, promotion, or clearance actions.",
        },
      },
    },
    openskufastSuggestions: [
      {
        suggestion: "New product",
        prompt:
          "I want to launch a $15-$30 commuter coffee tumbler. Use public signals for market analysis, competitor scan, positioning, and pricing strategy.",
        icon: CompassIcon,
      },
      {
        suggestion: "Category scan",
        prompt:
          "In pet supplies, what new product directions are worth low-cost testing? Scan public signals and give opportunity judgment.",
        icon: MicroscopeIcon,
      },
      {
        suggestion: "Competitor teardown",
        prompt:
          "Here is a public competitor link/name. Help me break down its positioning, selling points, and possible improvement areas.",
        icon: SparklesIcon,
      },
    ],
  },

  // Breadcrumb
  breadcrumb: {
    workspace: "Workspace",
    chats: "Chats",
  },

  // Workspace
  workspace: {
    officialWebsite: "OpenSKU's official website",
    githubTooltip: "OpenSKU on Github",
    settingsAndMore: "Settings and more",
    visitGithub: "OpenSKU on GitHub",
    reportIssue: "Report a issue",
    contactUs: "Contact us",
    about: "About OpenSKU",
    logout: "Log out",
  },

  // War Room
  warRoom: {
    title: "OpenSKU War Room",
    subtitle: "Live operations for the OpenSKU Launch Team and Growth Analyst",
    refresh: "Refresh",
    allIdle: "All agents standing by",
    activeAgents: (count: number) =>
      `${count} agent${count === 1 ? "" : "s"} working`,
    switchLanguage: "Switch to Chinese",
    teamStatus: "Team status",
    switchActor: "Select an agent",
    chat: "Chat",
    task: "Task",
    output: "Output",
    runDetails: "Run details",
    currentRun: "Current run",
    running: "Running",
    completed: "Completed",
    artifacts: "Artifacts",
    blocked: "Blocked",
    expandChat: "Expand chat",
    minimizeChat: "Minimize chat",
    expand: "Expand",
    minimize: "Minimize",
    closeChat: "Close chat",
    close: "Close",
    pipeline: "Launch pipeline",
    growthPipeline: "Growth analysis pipeline",
    runMetrics: "Run metrics",
    taskQueue: "Task queue",
    artifactFiles: (count: number) =>
      `${count} artifact file${count === 1 ? "" : "s"}`,
    noArtifacts: "No artifact files yet",
    statuses: {
      idle: "Standing by",
      queued: "Queued",
      working: "Working",
      done: "Completed",
      failed: "Blocked",
    },
    activities: {
      waiting: "Waiting for a task",
      orchestrating: "Coordinating work",
      searching: "Collecting signals",
      reading: "Reading sources",
      analyzing: "Analyzing data",
      writing: "Building assets",
      reviewing: "Checking evidence",
      delivering: "Delivering results",
    },
    summaries: {
      failed: "The task is blocked. Open the failure details to investigate.",
      done: "This task is complete and its deliverables are ready to review.",
      queued: "The task is queued and waiting to start.",
      idle: "Standing by for the next real task event.",
      waiting: "Waiting for an upstream task.",
      orchestrating: "Breaking down the goal and coordinating specialist work.",
      searching: "Collecting market, customer, and public signals.",
      reading: "Reading files, pages, or data structures.",
      analyzing:
        "Comparing evidence and identifying the most important changes.",
      writing: "Turning findings into launch-ready deliverables.",
      reviewing: "Checking sources, boundaries, and delivery quality.",
      delivering: "Packaging artifacts and preparing the final handoff.",
    },
    stages: {
      init: "Understand brief",
      research: "Market research",
      offer: "Offer design",
      content: "Asset production",
      pack: "Launch pack",
      preflight: "Preflight",
      done: "Complete",
      dataIntake: "Question & files",
      dataInspect: "Inspect data",
      dataJoin: "Join and query",
      dataExperiment: "Experiment analysis",
      dataDecision: "Decision",
    },
    replay: {
      title: "Run replay",
      latestRun: "Latest real Launch run",
      live: "Live",
      start: "Play replay",
      pause: "Pause replay",
      resume: "Resume replay",
      previous: "Previous event",
      next: "Next event",
      backToLive: "Back to live",
      speed: "Replay speed",
      eventOf: (current: number, total: number) =>
        `Event ${current} of ${total}`,
      request: "Brief received",
      handoff: (actorName: string) => `Handoff to ${actorName}`,
      tool: (toolName: string) => `Tool call · ${toolName}`,
      observation: "Observation returned",
      verification: "Preflight is checking the pack",
      delivery: "Pack delivered",
      completed: "Run completed",
      failed: "Run blocked",
      launchTeam: "Launch Team",
      growthAnalyst: "Growth Analyst",
      inspectData: "Inspect uploaded data",
      queryData: "Join and query data",
      experiment: "Run deterministic experiment analysis",
      dataProfileReady: "Data profile returned",
      queryReady: "Query result returned",
      experimentReady: "Experiment result returned",
    },
    metrics: {
      llmCalls: "LLM calls",
      tokens: "Tokens",
      duration: "Duration",
      searches: "Searches",
      fetches: "Fetches",
      filesWritten: "Files written",
      queries: "Data queries",
      experiments: "Experiments",
    },
    actors: {
      "ecom-launch": {
        name: "OpenSKU Launch Team",
        shortName: "Director",
        role: "Launch Director",
        description:
          "Breaks down the brief, coordinates specialists, and assembles the final decision pack.",
      },
      "market-voc-researcher": {
        name: "Market Researcher",
        shortName: "Market",
        role: "Market & VOC Researcher",
        description:
          "Studies competitors, market signals, and real customer language.",
      },
      "offer-architect": {
        name: "Offer Architect",
        shortName: "Offer",
        role: "Offer Architect",
        description:
          "Shapes positioning, pricing hypotheses, validation tests, and launch strategy.",
      },
      "asset-studio": {
        name: "Asset Studio",
        shortName: "Assets",
        role: "Asset Studio",
        description:
          "Creates listing copy, content angles, scripts, and launch assets.",
      },
      "evidence-checker": {
        name: "Evidence Checker",
        shortName: "Evidence",
        role: "Evidence Checker",
        description:
          "Checks sources, factual boundaries, conclusions, and delivery quality.",
      },
      "data-inspector": {
        name: "Growth Analyst",
        shortName: "Growth",
        role: "Data & Growth Analyst",
        description:
          "Explains uploaded business data, anomalies, and practical growth opportunities.",
      },
    },
    canvas: {
      initializationFailed: "Scene initialization failed",
      loadFailed: (message: string) => `Could not load the office: ${message}`,
      loading: "Setting up the office…",
      controls: "WASD / arrow keys to move · E to talk",
      interactionPrompt: "E",
      viewTask: "View task",
      viewOutput: "View output",
    },
    chatPanel: {
      taskCompleted: "Completed",
      taskFailed: "Failed",
      taskRunning: "In progress",
      noTask: "No task yet",
      noOutput: "No output yet",
      history: (count: number) => `Conversation history (${count})`,
      noHistory: "No previous conversations",
      untitled: "Untitled conversation",
      startChat: (actorName: string) => `Chat with ${actorName}`,
      startChatHint: "Ask a question and watch the task update in the War Room",
      responseComplete: "Response complete · War Room state is up to date",
    },
  },

  launchCrew: {
    productName: "OpenSKU",
    title: "Launch Team",
    collaborating: "Collaborating",
    synced: "Synced",
    collaborationProgress: "Team progress",
    deliveryProgress: "Delivery progress",
    validationStage: "Validation stage",
    complete: "Complete",
    waiting: "Waiting",
    deliveryChecklist: "Delivery checklist",
    coreFilesComplete: (completed: number, total: number) =>
      `${completed}/${total} core files ready`,
    allPresent: "Complete",
    advancing: "In progress",
    missing: "Still needed",
    pendingGeneration: "Pending",
    emptyTitle: "Waiting for the first launch-validation task",
    emptyDescription:
      "Flash keeps specialist capability available without extra planning overhead. Active roles appear here only when real work is assigned.",
    packCompleteTitle: "Launch Validation Pack is ready",
    packCompleteDescription:
      "This Flash delivery was completed by the OpenSKU Launch Director and deterministic renderer. Open all seven files from the chat card or the Files control above.",
    assignedTask: "Assigned task",
    currentAction: "Current action",
    deliverables: "Deliverables",
    roles: {
      "market-voc-researcher": {
        name: "Market Researcher",
        desk: "Market and customer research",
      },
      "offer-architect": {
        name: "Offer Architect",
        desk: "Positioning and validation design",
      },
      "asset-studio": {
        name: "Asset Studio",
        desk: "Content and launch assets",
      },
    },
    deliverableLabels: {
      competitorTable: "Market signal table",
      evidenceLedger: "Evidence ledger",
      positioningBrief: "Positioning brief",
      listingPack: "Listing pack",
      contentPack: "Content pack",
      launchCalendar: "7-day plan",
      warRoomPage: "War Room page",
    },
    workflowStages: {
      brief: "Brief",
      research: "Research",
      offer: "Offer",
      assets: "Assets",
      plan: "Plan",
      audit: "Evidence",
      pack: "Delivery",
    },
    phases: {
      assign: "Assign",
      collect: "Collect",
      organize: "Build",
      return: "Return",
    },
    statuses: {
      idle: "Standing by",
      assigned: "Assigned",
      searching: "Searching",
      reading: "Reading",
      writing: "Writing",
      delivered: "Delivered",
      done: "Completed",
      failed: "Failed",
    },
    bubbles: {
      delivered: "Deliverables are ready for the Launch Director to assemble.",
      waiting: "Waiting for the Launch Director to assign work.",
      blocked: "This workflow is blocked.",
      resultReturned: "Structured findings returned to the Launch Director.",
      taskCompleted: "Subtask completed.",
      searching: "Searching public signals.",
      fetching: "Reading a public page.",
      reading: "Checking the available materials.",
      working: "Working on the assigned task.",
    },
    pixel: {
      thinking: "Thinking",
      todo: "To do",
      inProgress: "In progress",
      done: "Done",
      tasks: [
        "Clarify brief",
        "Market research",
        "Offer validation",
        "Content assets",
        "Delivery check",
      ],
      currentStage: "Current stage",
    },
  },

  launchDecision: {
    chatView: "Conversation",
    decisionView: "Decision",
    workspaceTitle: (category: string) => `${category} validation decision`,
    emptyTitle: "No Launch decision to review yet",
    emptyDescription:
      "Complete an initial product-research run in the conversation. Once OpenSKU generates a Launch Validation Pack, the recommendation, evidence gaps, and experiments will appear here.",
    returnToChat: "Return to conversation",
    currentRecommendation: "Current recommendation",
    keyRisk: "Critical risk",
    nextStep: "Next step",
    stopCondition: "Stop condition",
    noCriticalRisk: "No critical risk has been defined",
    noNextStep: "No next experiment has been scheduled",
    noStopCondition: "No stop condition has been defined",
    noRationale: "The current decision has no rationale yet.",
    awaitingReassessment: "New result awaiting review",
    openGrowthAnalyst: "Open Growth Analyst",
    returnToLaunch: "Use to update Launch decision",
    recordResult: "Record validation result",
    loadingArtifacts: "Syncing evidence and experiments",
    tabs: {
      overview: "Decision overview",
      experiments: "Experiments",
      evidence: "Evidence & assumptions",
      deliverables: "Deliverables",
    },
    decisions: {
      test_now: "Run the 7-day lightweight validation now",
      test_after_fixing_assumptions:
        "Resolve critical assumptions before testing",
      hold: "Hold validation",
      insufficient_evidence: "Insufficient evidence; collect signals first",
    },
    evidenceStates: {
      insufficient: "Insufficient evidence",
      partial: "Partially supported",
      supported: "Supported",
      conflicting: "Conflicting evidence",
    },
    evidenceLabels: {
      observed_public: "Verified public",
      uploaded_real: "Uploaded real data",
      estimated: "Estimated",
      assumption: "Assumption",
      unavailable: "Unavailable",
    },
    outcomes: {
      met: "Criterion met",
      partial: "Partially met",
      not_met: "Not met",
      inconclusive: "Inconclusive",
    },
    decisionContext: "Decision context",
    audience: "Validation audience",
    validationGoal: "Validation goal",
    notDefined: "Not defined",
    decisionDifference: "Initial / current decision",
    initial: "Initial",
    current: "Current",
    pendingReassessment:
      "A new validation result is recorded, but the Launch Team has not reviewed it. The current recommendation will not change automatically.",
    changedWithoutRationale:
      "The decision changed without a new rationale being recorded.",
    noDecisionChange: "The current conclusion matches the initial decision.",
    recordedResults: "Recorded results",
    noRecordedResults:
      "No real validation result has been recorded. Add one after an experiment is complete.",
    dateUnknown: "Date not recorded",
    sampleDefinition: "Sample definition",
    experimentPlan: "Validation experiment plan",
    experimentPlanDescription:
      "Every experiment is tied to evidence to collect, a success criterion, and a stop condition.",
    templateFallbackDescription:
      "The current plan has no structured experiments, so executable starter templates are shown below.",
    collect: "Collect",
    successCriterion: "Success criterion",
    experimentTemplatesTitle: "Validation experiment templates",
    experimentTemplates: [
      {
        name: "Customer problem interview",
        evidence: "Real scenarios, triggers, alternatives, and exact wording",
        success: "Repeated, specific problem statements emerge",
        stop: "Feedback remains generic preference",
      },
      {
        name: "Price acceptance test",
        evidence: "Price choices, rejection reasons, and buying trigger",
        success: "Budget rationale overlaps the target price",
        stop: "The target price is consistently rejected",
      },
      {
        name: "Problem-led content test",
        evidence: "Qualified comments, survey completion, and problem feedback",
        success: "At least one theme produces high-quality answers",
        stop: "Engagement appears without problem evidence",
      },
      {
        name: "Alternative and switching survey",
        evidence:
          "Current alternative, unmet scenario, and switching condition",
        success: "A clearly describable unmet scenario is found",
        stop: "No concrete switching reason exists",
      },
    ],
    keyHypotheses: "Critical assumptions",
    hypothesisLinkNotice:
      "Only explicitly linked evidence changes an assumption's status; similar wording is not auto-attributed.",
    noHypotheses:
      "The current decision has no structured critical assumptions.",
    hypothesis: "Critical assumption",
    status: "Status",
    evidence: "Direct evidence",
    decisionImpact: "Decision impact",
    awaitingLink: "To validate",
    noDirectEvidence: "Not linked",
    highImpact: "High",
    evidenceLedger: "Evidence ledger",
    noEvidence:
      "No structured evidence is available; the current state cannot be treated as supported.",
    limitation: "Limitation",
    sourceCount: (count: number) =>
      `${count} direct ${count === 1 ? "source" : "sources"}`,
    deliverablesTitle: "Launch Validation Pack",
    deliverablesDescription:
      "This list reflects files actually generated in this thread; missing files are never marked complete.",
    openArtifact: "Open",
    missingArtifact: "Pending",
    resultDialogTitle: "Record validation result",
    resultDialogDescription:
      "The result is written to this thread as a structured message for Launch Team review. It will not overwrite the current decision directly.",
    experiment: "Experiment",
    experimentPlaceholder: "For example: Price acceptance test",
    date: "Date",
    outcome: "Success criterion outcome",
    samplePlaceholder: "For example: 12 target users with a commute scenario",
    observation: "Observed result",
    observationPlaceholder:
      "Record what was actually observed, including anomalies and limitations. Do not state inference as fact.",
    cancel: "Cancel",
    submitResult: "Submit for review",
  },

  // Conversation
  conversation: {
    noMessages: "No messages yet",
    startConversation: "Start a conversation to see messages here",
  },

  // Chats
  chats: {
    searchChats: "Search chats",
  },

  // Page titles (document title)
  pages: {
    appName: "OpenSKU",
    chats: "Chats",
    newChat: "New chat",
    untitled: "Untitled",
  },

  // Tool calls
  toolCalls: {
    moreSteps: (count: number) => `${count} more step${count === 1 ? "" : "s"}`,
    lessSteps: "Less steps",
    executeCommand: "Execute command",
    presentFiles: "Present files",
    needYourHelp: "Need your help",
    useTool: (toolName: string) => `Use "${toolName}" tool`,
    searchFor: (query: string) => `Search for "${query}"`,
    searchForRelatedInfo: "Search for related information",
    searchForRelatedImages: "Search for related images",
    searchForRelatedImagesFor: (query: string) =>
      `Search for related images for "${query}"`,
    searchOnWebFor: (query: string) => `Search on the web for "${query}"`,
    viewWebPage: "View web page",
    listFolder: "List folder",
    readFile: "Read file",
    writeFile: "Write file",
    clickToViewContent: "Click to view file content",
    writeTodos: "Update to-do list",
    skillInstallTooltip: "Install skill and make it available to OpenSKU",
  },

  // Subtasks
  uploads: {
    uploading: "Uploading...",
    uploadingFiles: "Uploading files, please wait...",
  },

  subtasks: {
    subtask: "Subtask",
    executing: (count: number) =>
      `Executing ${count === 1 ? "" : count + " "}subtask${count === 1 ? "" : "s in parallel"}`,
    in_progress: "Running subtask",
    completed: "Subtask completed",
    failed: "Subtask failed",
  },

  // Token Usage
  tokenUsage: {
    title: "Token Usage",
    label: "Tokens",
    input: "Input",
    output: "Output",
    total: "Total",
    view: "Display",
    unavailable:
      "No token usage yet. Usage appears only after a successful model response when the provider returns usage_metadata.",
    unavailableShort: "No usage returned",
    note: "Header totals use persisted thread usage, plus visible in-flight usage while a run is still streaming. Per-turn and debug usage come from currently visible messages only. Totals may differ from provider billing pages.",
    presets: {
      off: "Off",
      summary: "Summary",
      perTurn: "Per turn",
      debug: "Debug",
    },
    presetDescriptions: {
      off: "Hide token usage in the header and conversation.",
      summary: "Show only the current conversation total in the header.",
      perTurn:
        "Show the header total and one token summary per assistant turn.",
      debug: "Show the header total and step-level token debugging details.",
    },
    finalAnswer: "Final answer",
    stepTotal: "Step total",
    sharedAttribution: "Shared across multiple actions in this step",
    subagent: (description: string) => `Subagent: ${description}`,
    startTodo: (content: string) => `Start To-do: ${content}`,
    completeTodo: (content: string) => `Complete To-do: ${content}`,
    updateTodo: (content: string) => `Update To-do: ${content}`,
    removeTodo: (content: string) => `Remove To-do: ${content}`,
  },

  // Shortcuts
  shortcuts: {
    searchActions: "Search actions...",
    noResults: "No results found.",
    actions: "Actions",
    keyboardShortcuts: "Keyboard Shortcuts",
    keyboardShortcutsDescription:
      "Navigate OpenSKU faster with keyboard shortcuts.",
    openCommandPalette: "Open Command Palette",
    toggleSidebar: "Toggle Sidebar",
  },

  // Settings
  settings: {
    title: "Settings",
    description: "Adjust how OpenSKU looks and behaves for you.",
    sections: {
      account: "Account",
      appearance: "Appearance",
      memory: "Memory",
      tools: "Tools",
      skills: "Skills",
      notification: "Notification",
      about: "About",
    },
    memory: {
      title: "Memory",
      description:
        "OpenSKU automatically learns from your conversations in the background. These memories help OpenSKU understand you better and deliver a more personalized experience.",
      empty: "No memory data to display.",
      rawJson: "Raw JSON",
      exportButton: "Export memory",
      exportSuccess: "Memory exported",
      importButton: "Import memory",
      importConfirmTitle: "Import memory?",
      importConfirmDescription:
        "This will overwrite your current memory with the selected JSON backup.",
      importFileLabel: "Selected file",
      importInvalidFile:
        "Failed to read the selected memory file. Please choose a valid JSON export.",
      importSuccess: "Memory imported",
      manualFactSource: "Manual",
      addFact: "Add fact",
      addFactTitle: "Add memory fact",
      editFactTitle: "Edit memory fact",
      addFactSuccess: "Fact created",
      editFactSuccess: "Fact updated",
      clearAll: "Clear all memory",
      clearAllConfirmTitle: "Clear all memory?",
      clearAllConfirmDescription:
        "This will remove all saved summaries and facts. This action cannot be undone.",
      clearAllSuccess: "All memory cleared",
      factDeleteConfirmTitle: "Delete this fact?",
      factDeleteConfirmDescription:
        "This fact will be removed from memory immediately. This action cannot be undone.",
      factDeleteSuccess: "Fact deleted",
      factContentLabel: "Content",
      factCategoryLabel: "Category",
      factConfidenceLabel: "Confidence",
      factContentPlaceholder: "Describe the memory fact you want to save",
      factCategoryPlaceholder: "context",
      factConfidenceHint: "Use a number between 0 and 1.",
      factSave: "Save fact",
      factValidationContent: "Fact content cannot be empty.",
      factValidationConfidence: "Confidence must be a number between 0 and 1.",
      noFacts: "No saved facts yet.",
      summaryReadOnly:
        "Summary sections are read-only for now. You can currently add, edit, or delete individual facts, or clear all memory.",
      memoryFullyEmpty: "No memory saved yet.",
      factPreviewLabel: "Fact to delete",
      searchPlaceholder: "Search memory",
      filterAll: "All",
      filterFacts: "Facts",
      filterSummaries: "Summaries",
      noMatches: "No matching memory found.",
      markdown: {
        overview: "Overview",
        userContext: "User context",
        work: "Work",
        personal: "Personal",
        topOfMind: "Top of mind",
        historyBackground: "History",
        recentMonths: "Recent months",
        earlierContext: "Earlier context",
        longTermBackground: "Long-term background",
        updatedAt: "Updated at",
        facts: "Facts",
        empty: "(empty)",
        table: {
          category: "Category",
          confidence: "Confidence",
          confidenceLevel: {
            veryHigh: "Very high",
            high: "High",
            normal: "Normal",
            unknown: "Unknown",
          },
          content: "Content",
          source: "Source",
          createdAt: "CreatedAt",
          view: "View",
        },
      },
    },
    appearance: {
      themeTitle: "Theme",
      themeDescription:
        "Choose how the interface follows your device or stays fixed.",
      system: "System",
      light: "Light",
      dark: "Dark",
      systemDescription: "Match the operating system preference automatically.",
      lightDescription: "Bright palette with higher contrast for daytime.",
      darkDescription: "Dim palette that reduces glare for focus.",
      languageTitle: "Language",
      languageDescription: "Switch between languages.",
    },
    tools: {
      title: "Tools",
      description: "Manage the configuration and enabled status of MCP tools.",
    },
    skills: {
      title: "Agent Skills",
      description:
        "Manage the configuration and enabled status of the agent skills.",
      createSkill: "Create skill",
      emptyTitle: "No agent skill yet",
      emptyDescription:
        "Put your agent skill folders under the `/skills/custom` folder under the root folder of OpenSKU.",
      emptyButton: "Create Your First Skill",
    },
    notification: {
      title: "Notification",
      description:
        "OpenSKU only sends a completion notification when the window is not active. This is especially useful for long-running tasks so you can switch to other work and get notified when done.",
      requestPermission: "Request notification permission",
      deniedHint:
        "Notification permission was denied. You can enable it in your browser's site settings to receive completion alerts.",
      testButton: "Send test notification",
      testTitle: "OpenSKU",
      testBody: "This is a test notification.",
      notSupported: "Your browser does not support notifications.",
      disableNotification: "Disable notification",
    },
    account: {
      profileTitle: "Profile",
      email: "Email",
      role: "Role",
      changePasswordTitle: "Change Password",
      changePasswordDescription: "Update your account password.",
      currentPassword: "Current password",
      newPassword: "New password",
      confirmNewPassword: "Confirm new password",
      passwordMismatch: "New passwords do not match",
      passwordTooShort: "Password must be at least 8 characters",
      passwordChangedSuccess: "Password changed successfully",
      networkError: "Network error. Please try again.",
      updating: "Updating...",
      updatePassword: "Update Password",
      signOut: "Sign Out",
    },
    acknowledge: {
      emptyTitle: "Acknowledgements",
      emptyDescription: "Credits and acknowledgements will show here.",
    },
  },
};
