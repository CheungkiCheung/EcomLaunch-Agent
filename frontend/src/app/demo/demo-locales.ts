export type DemoLanguage = "en" | "zh";
export type DemoScenario = "launch" | "growth";

export type VerificationLoopContent = {
  title: string;
  budget: string;
  firstRound: {
    label: string;
    actionLabel: string;
    action: string;
    observationLabel: string;
    result: string;
    violations: string[];
  };
  decision: {
    label: string;
    title: string;
    basis: string;
    filesLabel: string;
    files: string[];
    toolsLabel: string;
    tools: string[];
    unchanged: string;
  };
  rerun: {
    label: string;
    action: string;
  };
  secondRound: {
    label: string;
    actionLabel: string;
    action: string;
    observationLabel: string;
    result: string;
    checks: string[];
  };
  stop: {
    label: string;
    title: string;
    reason: string;
    metrics: string[];
  };
};

export type ScenarioTranslation = {
  label: string;
  navDescription: string;
  eyebrow: string;
  title: string;
  description: string;
  decision: string;
  briefTitle: string;
  briefFields: Array<{ label: string; value: string }>;
  notice: string;
  warRoomEyebrow: string;
  warRoomTitle: string;
  replayLabel: string;
  replayDescription: string;
  participants: Record<string, { name: string; activity: string }>;
  pipelineTitle: string;
  pipeline: Array<{ label: string; detail: string; kind: string }>;
  stats: Array<{ value: string; label: string }>;
  verificationEyebrow: string;
  verificationTitle: string;
  verificationDescription: string;
  verificationSteps: Array<{
    label: string;
    title: string;
    detail: string;
  }>;
  verificationLoop?: VerificationLoopContent;
  deliverablesTitle: string;
  deliverablesDescription: string;
  deliverables: Array<{
    title: string;
    description: string;
    href: string;
    label: string;
  }>;
  alternateLabel: string;
};

export const demoSharedCopy = {
  en: {
    metadataTitle: "OpenSKU Interview Demo — No API Key Required",
    metadataDescription:
      "Explore recorded OpenSKU launch-validation and growth-analysis scenarios with deterministic sample data and inspectable outputs.",
    brandSubtitle: "Interview demo",
    sampleOutputs: "Sample outputs",
    languageLabel: "Language",
    languageEnglish: "EN",
    languageChinese: "中文",
    scenariosAriaLabel: "Recorded demo scenarios",
    exploreRuntime: "Explore the runtime",
    readDecision: "Read the decision",
    sampleBrief: "Sample brief",
    recordedTitle: "Recorded sample — no live agents are running",
    zeroKeys: "0 keys required",
    agentStatus: "Agent status",
    activeInScenario: (count: number) =>
      `${count} active in this recorded scenario`,
    done: "Done",
    notUsed: "Not used",
    status: {
      passed: "passed",
      blocked: "blocked",
      revised: "revised",
    },
    deliverablesEyebrow: "03 · Inspect the output",
    inspectableFiles: "inspectable files",
    liveApiCalls: "live API calls",
    openFile: "Open file",
    continueEyebrow: "Continue the interview walkthrough",
    continueTitle: "Show both sides of the OpenSKU runtime.",
    continueDescription:
      "Switch scenarios to demonstrate specialist orchestration and a separate, deterministic data-analysis path without waiting for a live model call.",
    quickStart: "Open Quick Start",
    footerRecorded: "Recorded, deterministic, and credential-free.",
    footerClaims: "No live claims are implied by demo fixtures.",
    walkthrough: {
      title: "60-second interview walkthrough",
      idle: "Start once, then explain each highlighted section as the page advances.",
      pause: "Pause",
      resume: "Resume",
      start: "Start tour",
      restart: "Restart walkthrough",
      steps: [
        {
          id: "demo-brief",
          label: "Brief",
          description: "Frame the business question and bounded inputs.",
        },
        {
          id: "war-room",
          label: "Runtime",
          description:
            "Show which agents run and which deterministic tools support them.",
        },
        {
          id: "verification",
          label: "Verification",
          description:
            "Explain the failure gate, minimal revision, and deterministic checks.",
        },
        {
          id: "deliverables",
          label: "Outputs",
          description: "Open the decision and one evidence-bearing artifact.",
        },
      ],
    },
  },
  zh: {
    metadataTitle: "OpenSKU 中文面试 Demo — 无需 API Key",
    metadataDescription:
      "使用确定性样例数据体验 OpenSKU 的上新验证与增长分析场景，并检查真实可打开的交付物。",
    brandSubtitle: "面试演示",
    sampleOutputs: "样例产物",
    languageLabel: "语言",
    languageEnglish: "EN",
    languageChinese: "中文",
    scenariosAriaLabel: "录制式演示场景",
    exploreRuntime: "查看运行过程",
    readDecision: "阅读决策",
    sampleBrief: "样例 Brief",
    recordedTitle: "录制式样例 — 当前没有实时 Agent 在运行",
    zeroKeys: "无需密钥",
    agentStatus: "Agent 状态",
    activeInScenario: (count: number) => `本录制场景中有 ${count} 个活跃 Agent`,
    done: "已完成",
    notUsed: "未使用",
    status: {
      passed: "已通过",
      blocked: "已拦截",
      revised: "已修订",
    },
    deliverablesEyebrow: "03 · 检查交付物",
    inspectableFiles: "份可检查文件",
    liveApiCalls: "次实时 API 调用",
    openFile: "打开文件",
    continueEyebrow: "继续面试演示",
    continueTitle: "展示 OpenSKU 运行时的两条业务路径。",
    continueDescription:
      "切换场景即可分别展示专家协作和确定性数据分析，无需在面试现场等待模型实时生成。",
    quickStart: "查看快速开始",
    footerRecorded: "录制式、确定性、无需凭据。",
    footerClaims: "Demo 样例不代表任何实时业务结论。",
    walkthrough: {
      title: "60 秒面试引导演示",
      idle: "点击一次开始，然后跟随页面自动切换的部分进行讲解。",
      pause: "暂停",
      resume: "继续",
      start: "开始演示",
      restart: "重新开始引导",
      steps: [
        {
          id: "demo-brief",
          label: "输入",
          description: "说明业务问题、输入条件和决策边界。",
        },
        {
          id: "war-room",
          label: "运行时",
          description: "展示实际运行的 Agent 以及提供支持的确定性工具。",
        },
        {
          id: "verification",
          label: "校验",
          description: "说明失败拦截、最小修订和重新验收。",
        },
        {
          id: "deliverables",
          label: "交付物",
          description: "打开最终决策和一份带证据或计算过程的产物。",
        },
      ],
    },
  },
} as const;

export const chineseScenarioTranslations: Record<
  DemoScenario,
  ScenarioTranslation
> = {
  launch: {
    label: "上新验证",
    navDescription: "商品 Brief → 专家协作 → 验证后的决策包",
    eyebrow: "中文样例 · 无需 API Key",
    title: "一份商品 Brief，生成一套可决策的上新包。",
    description:
      "这个确定性演示以一款面向美国市场的便携旅行咖啡杯为例，展示真实的三专家拓扑、交付前 Preflight 门禁，以及可以直接打开检查的样例文件。",
    decision: "验证",
    briefTitle: "便携旅行咖啡杯",
    briefFields: [
      { label: "市场", value: "美国" },
      { label: "人群", value: "通勤者与高频旅行者" },
      { label: "价格测试", value: "24–34 美元假设" },
      { label: "约束", value: "防漏且重量低于 350 克" },
    ],
    notice:
      "市场结论均为确定性演示数据，不是当前实时调研。Agent 拓扑与实际 Ultra 配置一致；验收被表示为系统门禁，而不是额外 Agent。",
    warRoomEyebrow: "01 · 多 Agent 运行时",
    warRoomTitle: "4 个活跃 Agent，1 个确定性门禁。",
    replayLabel: "回放完成",
    replayDescription: "便携旅行咖啡杯验证",
    participants: {
      "ecom-launch": {
        name: "启动总监",
        activity: "决策包组装完成",
      },
      "market-voc-researcher": {
        name: "市场研究员",
        activity: "样例市场信号图已完成",
      },
      "offer-architect": {
        name: "方案架构师",
        activity: "定位假设已形成",
      },
      "asset-studio": {
        name: "素材工作室",
        activity: "商品页与内容素材已生成",
      },
      "data-inspector": {
        name: "增长分析师",
        activity: "本 Brief 未提供店铺数据",
      },
    },
    pipelineTitle: "依赖顺序",
    pipeline: [
      {
        label: "研究",
        detail: "市场信号与消费者语言",
        kind: "AGENT",
      },
      {
        label: "方案",
        detail: "定位、定价与验证假设",
        kind: "AGENT",
      },
      {
        label: "素材",
        detail: "商品页文案、内容钩子与脚本",
        kind: "AGENT",
      },
      {
        label: "Preflight",
        detail: "7 件套、证据、JSON/CSV 与声明检查",
        kind: "系统",
      },
    ],
    stats: [
      { value: "3", label: "类专家" },
      { value: "7/7", label: "必需文件" },
      { value: "0", label: "次实时 API 调用" },
    ],
    verificationEyebrow: "02 · 校验闭环",
    verificationTitle: "模型不能批准自己的交付。",
    verificationDescription:
      "确定性 Preflight 会拦截文件缺失、结构化数据错误、证据边界不清和不受支持的实体商品声明。系统只修订失败的产物，再重新执行验收。",
    verificationSteps: [
      {
        label: "生成",
        title: "7 件套已组装",
        detail: "主 Agent 将三个专家的输出组装为完整交付合同。",
      },
      {
        label: "Preflight",
        title: "样例缺陷被拦截",
        detail: "一条证据缺少 URL，并出现未经支持的“完全防漏”声明。",
      },
      {
        label: "修订",
        title: "仅编辑两份产物",
        detail: "失败 Observation 只开放受限文件编辑工具，执行最小修订。",
      },
      {
        label: "复检",
        title: "7/7 合同通过",
        detail: "文件、证据标签、URL、结构化数据和声明边界全部通过。",
      },
    ],
    verificationLoop: {
      title: "有界 Agent-Environment 验证闭环",
      budget: "已使用 2 / 5 轮",
      firstRound: {
        label: "Loop 01 / 05",
        actionLabel: "Agent Action",
        action: "present_files(7 artifacts)",
        observationLabel: "Environment Observation",
        result: "已拦截 · 2 个违规项",
        violations: [
          "evidence-ledger.json · observed_public 条目缺少 source_url",
          "listing-pack.md · 出现未经支持的“完全防漏”商品声明",
        ],
      },
      decision: {
        label: "Agent Decision",
        title: "根据 Observation 选择最小修订",
        basis:
          "失败列表动态决定下一步修改的文件与工具，另外 5 份产物保持不变。",
        filesLabel: "选中文件 · 2 / 7",
        files: ["evidence-ledger.json", "listing-pack.md"],
        toolsLabel: "开放工具",
        tools: ["str_replace", "write_file"],
        unchanged: "未修改产物：5 份 · 跳过整包重新生成",
      },
      rerun: {
        label: "下一步由环境反馈决定",
        action: "修复两份失败产物，然后再次调用 present_files。",
      },
      secondRound: {
        label: "Loop 02 / 05",
        actionLabel: "Agent Action",
        action: "present_files(7 artifacts)",
        observationLabel: "新的 Environment Observation",
        result: "已通过 · 7 / 7",
        checks: [
          "必需文件 7/7",
          "缺失来源 URL 0",
          "违规声明 0",
          "无效 JSON/CSV 0",
        ],
      },
      stop: {
        label: "Stop Condition",
        title: "成功条件满足",
        reason:
          "环境返回干净的交付合同，因此 Agent 直接停止，不继续消耗剩余 Loop Budget。",
        metrics: [
          "已使用轮次 2/5",
          "修订范围 2/7 份文件",
          "未触发 Run Budget",
          "未触发重复工具调用保护",
        ],
      },
    },
    deliverablesTitle: "不只是一个聊天回答。",
    deliverablesDescription:
      "打开文件即可检查决策结构、证据边界、可编辑的上新素材和明确的停止条件。",
    deliverables: [
      {
        title: "上新决策",
        description: "带明确门槛的“先验证、再投入”建议。",
        href: "/demo/opensku-coffee-mug/launch-decision.zh-CN.md",
        label: "决策",
      },
      {
        title: "证据台账",
        description: "明确区分样例观察、估算和待验证假设。",
        href: "/demo/opensku-coffee-mug/evidence-ledger.zh-CN.md",
        label: "证据",
      },
      {
        title: "商品页素材包",
        description: "可继续编辑的定位、卖点、异议处理和内容方向。",
        href: "/demo/opensku-coffee-mug/listing-pack.zh-CN.md",
        label: "素材",
      },
      {
        title: "7 天验证计划",
        description: "带阈值和停止条件的低成本测试顺序。",
        href: "/demo/opensku-coffee-mug/seven-day-validation-plan.zh-CN.md",
        label: "计划",
      },
    ],
    alternateLabel: "查看增长分析师",
  },
  growth: {
    label: "增长实验",
    navDescription: "CSV/XLSX → 只读分析 → Ship / Extend / Stop",
    eyebrow: "确定性分析 · 无需 API Key",
    title: "三份业务文件，形成一项实验决策。",
    description:
      "这个录制式 Growth Analyst 场景会关联访客、实验分组和订单数据，执行确定性的双比例检验与 SRM 检查，并将结论写入受限的业务 Memory 快照。",
    decision: "上线",
    briefTitle: "结账页社会证明实验",
    briefFields: [
      { label: "输入", value: "访客 + 分组 + 订单" },
      { label: "样本", value: "2,380 名已分组访客" },
      { label: "主指标", value: "购买转化率" },
      { label: "问题", value: "实验版本是否应该上线？" },
    ],
    notice:
      "所有数据行和指标都是确定性样例。不包含用户上传数据，不调用模型；SQL 和统计结果都可以根据页面展示的样本数复算。",
    warRoomEyebrow: "01 · 有界分析运行时",
    warRoomTitle: "1 个分析师，4 个确定性阶段。",
    replayLabel: "分析完成",
    replayDescription: "结账页实验决策",
    participants: {
      "data-inspector": {
        name: "增长分析师",
        activity: "已记录 SHIP 决策",
      },
      "ecom-launch": {
        name: "启动总监",
        activity: "本场景没有上新 Brief",
      },
    },
    pipelineTitle: "确定性分析阶段",
    pipeline: [
      {
        label: "检查",
        detail: "CSV/XLSX 类型、Schema 与行数检查",
        kind: "工具",
      },
      {
        label: "关联",
        detail: "对三份已注册文件执行只读 DuckDB 查询",
        kind: "SQL",
      },
      {
        label: "检验",
        detail: "双比例 z-test、置信区间与 SRM",
        kind: "统计",
      },
      {
        label: "记忆",
        detail: "将决策和指标上下文写入业务 Memory",
        kind: "记忆",
      },
    ],
    stats: [
      { value: "+31.4%", label: "相对提升" },
      { value: "0.0346", label: "p-value" },
      { value: "0.682", label: "SRM p-value" },
    ],
    verificationEyebrow: "02 · 确定性分析",
    verificationTitle: "建议背后有可以检查的计算过程。",
    verificationDescription:
      "录制样例使用对照组 96/1,200 和实验组 124/1,180 的购买数据。结果通过预先设定的 5% 显著性阈值，分流通过 SRM 检查，绝对提升的置信区间也保持在零以上。",
    verificationSteps: [
      {
        label: "检查",
        title: "已注册三份文件",
        detail: "允许的表格格式和必需 Join Key 均通过 Schema 检查。",
      },
      {
        label: "关联",
        title: "2,380 名访客完成核对",
        detail: "受限 SELECT 在无外部访问的条件下关联分组、访客和订单。",
      },
      {
        label: "检验",
        title: "绝对提升 +2.51 个百分点",
        detail: "p = 0.0346；95% CI = +0.18 到 +4.84 个百分点；SRM p = 0.682。",
      },
      {
        label: "决策",
        title: "上线并持续监控",
        detail: "分阶段放量，并监控退款率、客单价、结账延迟和转化提升。",
      },
    ],
    deliverablesTitle: "一项可以审计的增长决策。",
    deliverablesDescription:
      "检查最终建议、统计计算、Cohort 快照，以及会带入下一次对话的受限 Memory 条目。",
    deliverables: [
      {
        title: "增长决策",
        description: "带阈值和放量保护条件的 Ship / Extend / Stop 建议。",
        href: "/demo/opensku-growth-experiment/growth-decision.zh-CN.md",
        label: "决策",
      },
      {
        title: "实验分析",
        description: "Join 计数、转化率、z-test、置信区间和 SRM 明细。",
        href: "/demo/opensku-growth-experiment/experiment-analysis.zh-CN.md",
        label: "实验",
      },
      {
        title: "Cohort 留存",
        description: "展示获客 Cohort 和第 4 周留存的紧凑 CSV 样例。",
        href: "/demo/opensku-growth-experiment/cohort-retention.zh-CN.csv",
        label: "留存",
      },
      {
        title: "Memory 快照",
        description: "供后续会话调用的指标上下文与实验结论。",
        href: "/demo/opensku-growth-experiment/memory-snapshot.zh-CN.md",
        label: "记忆",
      },
    ],
    alternateLabel: "查看上新验证",
  },
};
