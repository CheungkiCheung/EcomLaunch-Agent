import type { LucideIcon } from "lucide-react";

export interface Translations {
  // Locale meta
  locale: {
    localName: string;
  };

  // Common
  common: {
    home: string;
    settings: string;
    delete: string;
    edit: string;
    rename: string;
    share: string;
    openInNewWindow: string;
    close: string;
    more: string;
    search: string;
    loadMore: string;
    download: string;
    thinking: string;
    artifacts: string;
    public: string;
    custom: string;
    notAvailableInDemoMode: string;
    loading: string;
    version: string;
    lastUpdated: string;
    code: string;
    preview: string;
    cancel: string;
    save: string;
    install: string;
    create: string;
    import: string;
    export: string;
    exportAsMarkdown: string;
    exportAsJSON: string;
    exportSuccess: string;
  };

  home: {
    docs: string;
    blog: string;
  };

  // Welcome
  welcome: {
    greeting: string;
    description: string;
    createYourOwnSkill: string;
    createYourOwnSkillDescription: string;
  };

  // Clipboard
  clipboard: {
    copyToClipboard: string;
    copiedToClipboard: string;
    failedToCopyToClipboard: string;
    linkCopied: string;
  };

  // Input Box
  inputBox: {
    placeholder: string;
    createSkillPrompt: string;
    addAttachments: string;
    mode: string;
    flashMode: string;
    flashModeDescription: string;
    reasoningMode: string;
    reasoningModeDescription: string;
    proMode: string;
    proModeDescription: string;
    ultraMode: string;
    ultraModeDescription: string;
    reasoningEffort: string;
    reasoningEffortMinimal: string;
    reasoningEffortMinimalDescription: string;
    reasoningEffortLow: string;
    reasoningEffortLowDescription: string;
    reasoningEffortMedium: string;
    reasoningEffortMediumDescription: string;
    reasoningEffortHigh: string;
    reasoningEffortHighDescription: string;
    searchModels: string;
    surpriseMe: string;
    surpriseMePrompt: string;
    followupLoading: string;
    followupConfirmTitle: string;
    followupConfirmDescription: string;
    followupConfirmAppend: string;
    followupConfirmReplace: string;
    suggestions: {
      suggestion: string;
      prompt: string;
      icon: LucideIcon;
    }[];
    suggestionsCreate: (
      | {
          suggestion: string;
          prompt: string;
          icon: LucideIcon;
        }
      | {
          type: "separator";
        }
    )[];
  };

  // Sidebar
  sidebar: {
    recentChats: string;
    newChat: string;
    chats: string;
    demoChats: string;
    agents: string;
    primaryAgents: string;
    warRoom: string;
    ecomLaunch: string;
    dataInspector: string;
    openskufast: string;
  };

  // Agents
  agents: {
    title: string;
    description: string;
    newAgent: string;
    emptyTitle: string;
    emptyDescription: string;
    chat: string;
    delete: string;
    deleteConfirm: string;
    deleteSuccess: string;
    newChat: string;
    createPageTitle: string;
    createPageSubtitle: string;
    nameStepTitle: string;
    nameStepHint: string;
    nameStepPlaceholder: string;
    nameStepContinue: string;
    nameStepInvalidError: string;
    nameStepAlreadyExistsError: string;
    nameStepNetworkError: string;
    nameStepCheckError: string;
    nameStepCheckErrorWithDetail: string;
    nameStepApiDisabledError: string;
    nameStepBootstrapMessage: string;
    save: string;
    saving: string;
    saveRequested: string;
    saveHint: string;
    saveCommandMessage: string;
    agentCreatedPendingRefresh: string;
    more: string;
    agentCreated: string;
    startChatting: string;
    backToGallery: string;
    ecomLaunchName: string;
    dataInspectorName: string;
    openskufastName: string;
    ecomLaunchWelcomeDescription: string;
    dataInspectorWelcomeDescription: string;
    openskufastWelcomeDescription: string;
    ecomLaunchWelcomeBadges: string[];
    openskufastWelcomeBadges: string[];
    ecomLaunchSuggestions: {
      suggestion: string;
      prompt: string;
      icon: LucideIcon;
    }[];
    dataInspectorSuggestions: {
      suggestion: string;
      prompt: string;
      icon: LucideIcon;
    }[];
    openskufastSuggestions: {
      suggestion: string;
      prompt: string;
      icon: LucideIcon;
    }[];
  };

  // Breadcrumb
  breadcrumb: {
    workspace: string;
    chats: string;
  };

  // Workspace
  workspace: {
    officialWebsite: string;
    githubTooltip: string;
    settingsAndMore: string;
    visitGithub: string;
    reportIssue: string;
    contactUs: string;
    about: string;
    logout: string;
  };

  // War Room
  warRoom: {
    title: string;
    subtitle: string;
    refresh: string;
    allIdle: string;
    activeAgents: (count: number) => string;
    switchLanguage: string;
    teamStatus: string;
    switchActor: string;
    chat: string;
    task: string;
    output: string;
    runDetails: string;
    currentRun: string;
    running: string;
    completed: string;
    artifacts: string;
    blocked: string;
    expandChat: string;
    minimizeChat: string;
    expand: string;
    minimize: string;
    closeChat: string;
    close: string;
    pipeline: string;
    runMetrics: string;
    taskQueue: string;
    artifactFiles: (count: number) => string;
    noArtifacts: string;
    statuses: {
      idle: string;
      queued: string;
      working: string;
      done: string;
      failed: string;
    };
    activities: {
      waiting: string;
      orchestrating: string;
      searching: string;
      reading: string;
      analyzing: string;
      writing: string;
      reviewing: string;
      delivering: string;
    };
    summaries: {
      failed: string;
      done: string;
      queued: string;
      idle: string;
      waiting: string;
      orchestrating: string;
      searching: string;
      reading: string;
      analyzing: string;
      writing: string;
      reviewing: string;
      delivering: string;
    };
    stages: {
      init: string;
      research: string;
      offer: string;
      content: string;
      pack: string;
      done: string;
    };
    metrics: {
      llmCalls: string;
      tokens: string;
      duration: string;
      searches: string;
      fetches: string;
      filesWritten: string;
    };
    actors: {
      "ecom-launch": {
        name: string;
        shortName: string;
        role: string;
        description: string;
      };
      "market-voc-researcher": {
        name: string;
        shortName: string;
        role: string;
        description: string;
      };
      "offer-architect": {
        name: string;
        shortName: string;
        role: string;
        description: string;
      };
      "asset-studio": {
        name: string;
        shortName: string;
        role: string;
        description: string;
      };
      "evidence-checker": {
        name: string;
        shortName: string;
        role: string;
        description: string;
      };
      "data-inspector": {
        name: string;
        shortName: string;
        role: string;
        description: string;
      };
    };
    canvas: {
      initializationFailed: string;
      loadFailed: (message: string) => string;
      loading: string;
      controls: string;
      interactionPrompt: string;
      viewTask: string;
      viewOutput: string;
    };
    chatPanel: {
      taskCompleted: string;
      taskFailed: string;
      taskRunning: string;
      noTask: string;
      noOutput: string;
      history: (count: number) => string;
      noHistory: string;
      untitled: string;
      startChat: (actorName: string) => string;
      startChatHint: string;
      responseComplete: string;
    };
  };

  // OpenSKU Launch Team side panel
  launchCrew: {
    productName: string;
    title: string;
    collaborating: string;
    synced: string;
    collaborationProgress: string;
    validationStage: string;
    complete: string;
    waiting: string;
    deliveryChecklist: string;
    coreFilesComplete: (completed: number, total: number) => string;
    allPresent: string;
    advancing: string;
    missing: string;
    pendingGeneration: string;
    emptyTitle: string;
    emptyDescription: string;
    assignedTask: string;
    currentAction: string;
    deliverables: string;
    roles: {
      "market-voc-researcher": { name: string; desk: string };
      "offer-architect": { name: string; desk: string };
      "asset-studio": { name: string; desk: string };
    };
    deliverableLabels: {
      competitorTable: string;
      evidenceLedger: string;
      positioningBrief: string;
      listingPack: string;
      contentPack: string;
      launchCalendar: string;
      warRoomPage: string;
    };
    workflowStages: {
      brief: string;
      research: string;
      offer: string;
      assets: string;
      plan: string;
      audit: string;
      pack: string;
    };
    phases: {
      assign: string;
      collect: string;
      organize: string;
      return: string;
    };
    statuses: {
      idle: string;
      assigned: string;
      searching: string;
      reading: string;
      writing: string;
      delivered: string;
      done: string;
      failed: string;
    };
    bubbles: {
      delivered: string;
      waiting: string;
      blocked: string;
      resultReturned: string;
      taskCompleted: string;
      searching: string;
      fetching: string;
      reading: string;
      working: string;
    };
    pixel: {
      thinking: string;
      todo: string;
      inProgress: string;
      done: string;
      tasks: string[];
      currentStage: string;
    };
  };

  // Conversation
  conversation: {
    noMessages: string;
    startConversation: string;
  };

  // Chats
  chats: {
    searchChats: string;
  };

  // Page titles (document title)
  pages: {
    appName: string;
    chats: string;
    newChat: string;
    untitled: string;
  };

  // Tool calls
  toolCalls: {
    moreSteps: (count: number) => string;
    lessSteps: string;
    executeCommand: string;
    presentFiles: string;
    needYourHelp: string;
    useTool: (toolName: string) => string;
    searchForRelatedInfo: string;
    searchForRelatedImages: string;
    searchFor: (query: string) => string;
    searchForRelatedImagesFor: (query: string) => string;
    searchOnWebFor: (query: string) => string;
    viewWebPage: string;
    listFolder: string;
    readFile: string;
    writeFile: string;
    clickToViewContent: string;
    writeTodos: string;
    skillInstallTooltip: string;
  };

  // Uploads
  uploads: {
    uploading: string;
    uploadingFiles: string;
  };

  // Subtasks
  subtasks: {
    subtask: string;
    executing: (count: number) => string;
    in_progress: string;
    completed: string;
    failed: string;
  };

  // Token Usage
  tokenUsage: {
    title: string;
    label: string;
    input: string;
    output: string;
    total: string;
    view: string;
    unavailable: string;
    unavailableShort: string;
    note: string;
    presets: {
      off: string;
      summary: string;
      perTurn: string;
      debug: string;
    };
    presetDescriptions: {
      off: string;
      summary: string;
      perTurn: string;
      debug: string;
    };
    finalAnswer: string;
    stepTotal: string;
    sharedAttribution: string;
    subagent: (description: string) => string;
    startTodo: (content: string) => string;
    completeTodo: (content: string) => string;
    updateTodo: (content: string) => string;
    removeTodo: (content: string) => string;
  };

  // Shortcuts
  shortcuts: {
    searchActions: string;
    noResults: string;
    actions: string;
    keyboardShortcuts: string;
    keyboardShortcutsDescription: string;
    openCommandPalette: string;
    toggleSidebar: string;
  };

  // Settings
  settings: {
    title: string;
    description: string;
    sections: {
      account: string;
      appearance: string;
      memory: string;
      tools: string;
      skills: string;
      notification: string;
      about: string;
    };
    memory: {
      title: string;
      description: string;
      empty: string;
      rawJson: string;
      exportButton: string;
      exportSuccess: string;
      importButton: string;
      importConfirmTitle: string;
      importConfirmDescription: string;
      importFileLabel: string;
      importInvalidFile: string;
      importSuccess: string;
      manualFactSource: string;
      addFact: string;
      addFactTitle: string;
      editFactTitle: string;
      addFactSuccess: string;
      editFactSuccess: string;
      clearAll: string;
      clearAllConfirmTitle: string;
      clearAllConfirmDescription: string;
      clearAllSuccess: string;
      factDeleteConfirmTitle: string;
      factDeleteConfirmDescription: string;
      factDeleteSuccess: string;
      factContentLabel: string;
      factCategoryLabel: string;
      factConfidenceLabel: string;
      factContentPlaceholder: string;
      factCategoryPlaceholder: string;
      factConfidenceHint: string;
      factSave: string;
      factValidationContent: string;
      factValidationConfidence: string;
      noFacts: string;
      summaryReadOnly: string;
      memoryFullyEmpty: string;
      factPreviewLabel: string;
      searchPlaceholder: string;
      filterAll: string;
      filterFacts: string;
      filterSummaries: string;
      noMatches: string;
      markdown: {
        overview: string;
        userContext: string;
        work: string;
        personal: string;
        topOfMind: string;
        historyBackground: string;
        recentMonths: string;
        earlierContext: string;
        longTermBackground: string;
        updatedAt: string;
        facts: string;
        empty: string;
        table: {
          category: string;
          confidence: string;
          confidenceLevel: {
            veryHigh: string;
            high: string;
            normal: string;
            unknown: string;
          };
          content: string;
          source: string;
          createdAt: string;
          view: string;
        };
      };
    };
    appearance: {
      themeTitle: string;
      themeDescription: string;
      system: string;
      light: string;
      dark: string;
      systemDescription: string;
      lightDescription: string;
      darkDescription: string;
      languageTitle: string;
      languageDescription: string;
    };
    tools: {
      title: string;
      description: string;
    };
    skills: {
      title: string;
      description: string;
      createSkill: string;
      emptyTitle: string;
      emptyDescription: string;
      emptyButton: string;
    };
    notification: {
      title: string;
      description: string;
      requestPermission: string;
      deniedHint: string;
      testButton: string;
      testTitle: string;
      testBody: string;
      notSupported: string;
      disableNotification: string;
    };
    account: {
      profileTitle: string;
      email: string;
      role: string;
      changePasswordTitle: string;
      changePasswordDescription: string;
      currentPassword: string;
      newPassword: string;
      confirmNewPassword: string;
      passwordMismatch: string;
      passwordTooShort: string;
      passwordChangedSuccess: string;
      networkError: string;
      updating: string;
      updatePassword: string;
      signOut: string;
    };
    acknowledge: {
      emptyTitle: string;
      emptyDescription: string;
    };
  };
}
