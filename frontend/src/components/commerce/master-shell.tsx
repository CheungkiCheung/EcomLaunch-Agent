"use client";

import {
  ActivityIcon,
  BarChart3Icon,
  BotIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CircleAlertIcon,
  CircleCheckIcon,
  Clock3Icon,
  DatabaseIcon,
  FolderOpenIcon,
  GaugeIcon,
  InboxIcon,
  ListFilterIcon,
  MenuIcon,
  MoreHorizontalIcon,
  PaperclipIcon,
  PlayIcon,
  PlusIcon,
  RefreshCwIcon,
  SendIcon,
  SettingsIcon,
  ShieldCheckIcon,
  SparklesIcon,
  TargetIcon,
  XIcon,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  buildCommerceShellViewModel,
  CommerceApiError,
  loadCommerceWorkspaceSnapshot,
  type CommerceEvidenceInspectorViewModel,
  type CommerceShellViewModel,
  type CommerceTimelineItemViewModel,
  type CommerceWorkspaceSnapshot,
} from "@/core/commerce";
import { cn } from "@/lib/utils";

import { CommerceActionCenter } from "./action-center";
import { CommerceAgentRun } from "./agent-run";
import { CommerceCapabilityReport } from "./capability-report";
import { CommerceCaseQueue } from "./case-queue";
import { CommerceDataInbox } from "./data-inbox";
import { CommerceEvidenceExplorer } from "./evidence-explorer";
import { CommerceSkillsEvals } from "./skills-evals";

interface CommerceMasterShellProps {
  workspaceId: string | null;
  actorId?: string | null;
}

type CommerceLoadError = {
  title: string;
  description: string;
};

export function CommerceMasterShell({
  workspaceId,
  actorId = null,
}: CommerceMasterShellProps) {
  const [snapshot, setSnapshot] = useState<CommerceWorkspaceSnapshot | null>(
    null,
  );
  const [selectedCaseId, setSelectedCaseId] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<CommerceLoadError | null>(null);

  useEffect(() => {
    if (!workspaceId) return;
    const controller = new AbortController();
    setIsRefreshing(true);
    setLoadError(null);

    void loadCommerceWorkspaceSnapshot({
      workspaceId,
      selectedCaseId,
      signal: controller.signal,
    })
      .then((nextSnapshot) => {
        setSnapshot(nextSnapshot);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setLoadError(projectLoadError(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsRefreshing(false);
      });

    return () => controller.abort();
  }, [refreshKey, selectedCaseId, workspaceId]);

  const viewModel = useMemo(
    () => (snapshot ? buildCommerceShellViewModel(snapshot) : null),
    [snapshot],
  );

  if (!workspaceId) {
    return <CommerceConfigurationState />;
  }
  if (!viewModel && loadError) {
    return (
      <CommerceFailureState
        error={loadError}
        onRetry={() => setRefreshKey((value) => value + 1)}
      />
    );
  }
  if (!viewModel) {
    return <CommerceLoadingState />;
  }

  return (
    <CommerceMasterShellView
      viewModel={viewModel}
      cases={snapshot?.cases ?? []}
      workspaceId={workspaceId}
      actorId={actorId}
      isRefreshing={isRefreshing}
      loadError={loadError}
      onRefresh={() => setRefreshKey((value) => value + 1)}
      onSelectCase={setSelectedCaseId}
    />
  );
}

interface CommerceMasterShellViewProps {
  viewModel: CommerceShellViewModel;
  cases?: CommerceWorkspaceSnapshot["cases"];
  workspaceId?: string | null;
  actorId?: string | null;
  isRefreshing: boolean;
  loadError?: CommerceLoadError | null;
  onRefresh: () => void;
  onSelectCase: (caseId: string) => void;
}

type CenterView = "overview" | "timeline" | "evidence" | "run";
type CommerceSection =
  | "case"
  | "queue"
  | "data"
  | "capability"
  | "action"
  | "runs"
  | "skills";

export function CommerceMasterShellView({
  viewModel,
  cases = [],
  workspaceId = null,
  actorId = null,
  isRefreshing,
  loadError = null,
  onRefresh,
  onSelectCase,
}: CommerceMasterShellViewProps) {
  const [centerView, setCenterView] = useState<CenterView>("overview");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [composerValue, setComposerValue] = useState("");
  const [composerNotice, setComposerNotice] = useState<string | null>(null);
  const [section, setSection] = useState<CommerceSection>("case");
  const [dataRefreshKey, setDataRefreshKey] = useState(0);
  const [preferredCasePath, setPreferredCasePath] = useState<string | null>(
    null,
  );
  const [preferredActionId, setPreferredActionId] = useState<string | null>(
    null,
  );

  const openEvidence = () => {
    if (viewModel.activeCase?.overview.evidenceInspector) {
      setInspectorOpen(true);
    } else {
      setCenterView("evidence");
    }
  };

  const reviewAction = () => {
    setPreferredActionId(viewModel.activeCase?.overview.action.id ?? null);
    setSection("action");
    setInspectorOpen(false);
  };

  const submitComposer = () => {
    if (!composerValue.trim()) return;
    setComposerNotice(
      "案例问答接口将在后续页面接入；当前内容没有发送，也没有启动新的调查。",
    );
  };

  return (
    <div
      className="h-dvh overflow-hidden bg-[#f7f7f5] text-[#20201e]"
      data-testid="commerce-master-shell"
    >
      {(sidebarOpen || inspectorOpen) && (
        <button
          type="button"
          aria-label="关闭浮动面板"
          className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[1px] lg:hidden"
          onClick={() => {
            setSidebarOpen(false);
            setInspectorOpen(false);
          }}
        />
      )}

      <div
        className={cn(
          "grid h-full grid-cols-1",
          sidebarCollapsed
            ? "lg:grid-cols-[60px_minmax(0,1fr)]"
            : "lg:grid-cols-[260px_minmax(0,1fr)]",
          inspectorOpen &&
            (sidebarCollapsed
              ? "xl:grid-cols-[60px_minmax(0,1fr)_320px]"
              : "xl:grid-cols-[260px_minmax(0,1fr)_320px]"),
        )}
      >
        <CommerceSidebar
          collapsed={sidebarCollapsed}
          open={sidebarOpen}
          viewModel={viewModel}
          activeSection={section}
          onClose={() => setSidebarOpen(false)}
          onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
          onSelectCase={(caseId) => {
            setSection("case");
            setPreferredCasePath(null);
            onSelectCase(caseId);
            setSidebarOpen(false);
            setInspectorOpen(false);
            setCenterView("overview");
          }}
          onOpenDataInbox={() => {
            setSection("data");
            setPreferredCasePath(null);
            setSidebarOpen(false);
            setInspectorOpen(false);
          }}
          onOpenCapabilityReport={() => {
            setSection("capability");
            setPreferredCasePath(null);
            setSidebarOpen(false);
            setInspectorOpen(false);
          }}
          onOpenCaseQueue={() => {
            setSection("queue");
            setPreferredCasePath(null);
            setSidebarOpen(false);
            setInspectorOpen(false);
          }}
          onOpenCreateCase={() => {
            setSection("queue");
            setPreferredCasePath("__open__");
            setPreferredActionId(null);
            setSidebarOpen(false);
            setInspectorOpen(false);
          }}
          onOpenActionCenter={() => {
            setSection("action");
            setPreferredCasePath(null);
            setPreferredActionId(null);
            setSidebarOpen(false);
            setInspectorOpen(false);
          }}
          onOpenAgentRuns={() => {
            setSection("runs");
            setPreferredCasePath(null);
            setPreferredActionId(null);
            setSidebarOpen(false);
            setInspectorOpen(false);
          }}
          onOpenSkillsEvals={() => {
            setSection("skills");
            setPreferredCasePath(null);
            setPreferredActionId(null);
            setSidebarOpen(false);
            setInspectorOpen(false);
          }}
        />

        <main className="relative flex min-w-0 flex-col overflow-hidden border-r border-black/[0.07] bg-white">
          <CommerceTopBar
            title={
              section === "data"
                ? "数据接入"
                : section === "capability"
                  ? "数据能力"
                  : section === "queue"
                    ? "案例队列"
                    : section === "action"
                      ? "行动中心"
                      : section === "runs"
                        ? "运行记录"
                        : section === "skills"
                          ? "技能与评测"
                          : (viewModel.activeCase?.title ?? "经营诊断工作区")
            }
            secondaryLabel={
              section === "data"
                ? "新数据批次"
                : section === "capability"
                  ? "订单履约数据"
                  : section === "queue"
                    ? "全部经营问题"
                    : section === "action"
                      ? "审批与执行"
                      : section === "runs"
                        ? "工程检查"
                        : section === "skills"
                          ? "演进治理"
                          : "案例详情"
            }
            isRefreshing={
              (section === "case" || section === "queue") && isRefreshing
            }
            showInspector={section === "case"}
            inspectorAvailable={
              section === "case" &&
              Boolean(viewModel.activeCase?.overview.evidenceInspector)
            }
            onOpenInspector={openEvidence}
            onOpenSidebar={() => setSidebarOpen(true)}
            onRefresh={
              section === "data" ||
              section === "capability" ||
              section === "action" ||
              section === "runs" ||
              section === "skills"
                ? () => setDataRefreshKey((value) => value + 1)
                : section === "queue"
                  ? () => {
                      onRefresh();
                      setDataRefreshKey((value) => value + 1);
                    }
                  : onRefresh
            }
          />

          {(section === "case" || section === "queue") && loadError && (
            <div
              className="mx-5 mt-4 flex items-start justify-between gap-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
              role="status"
            >
              <div>
                <p className="font-medium">{loadError.title}</p>
                <p className="mt-1 text-xs text-amber-800">
                  {loadError.description}
                </p>
              </div>
              <button
                type="button"
                className="shrink-0 rounded-lg px-2 py-1 text-xs font-medium hover:bg-amber-100 focus-visible:outline-2 focus-visible:outline-offset-2"
                onClick={onRefresh}
              >
                重试
              </button>
            </div>
          )}

          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            {section === "skills" ? (
              <CommerceSkillsEvals
                workspaceId={workspaceId}
                actorId={actorId}
                refreshSignal={dataRefreshKey}
              />
            ) : section === "runs" ? (
              <CommerceAgentRun
                workspaceId={workspaceId}
                cases={cases}
                refreshSignal={dataRefreshKey}
                onOpenCase={(caseId) => {
                  setSection("case");
                  onSelectCase(caseId);
                  setCenterView("overview");
                }}
              />
            ) : section === "action" ? (
              <CommerceActionCenter
                workspaceId={workspaceId}
                actorId={actorId}
                cases={cases}
                preferredActionId={preferredActionId}
                refreshSignal={dataRefreshKey}
                onOpenCase={(caseId) => {
                  setSection("case");
                  setPreferredActionId(null);
                  onSelectCase(caseId);
                  setCenterView("overview");
                }}
                onOpenEvidence={(caseId) => {
                  setSection("case");
                  setPreferredActionId(null);
                  onSelectCase(caseId);
                  setCenterView("evidence");
                }}
              />
            ) : section === "queue" ? (
              <CommerceCaseQueue
                workspaceId={workspaceId ?? null}
                cases={cases}
                refreshSignal={dataRefreshKey}
                preferredPath={preferredCasePath}
                onPreferredPathConsumed={() => setPreferredCasePath(null)}
                onOpenCase={(caseId) => {
                  setSection("case");
                  setPreferredCasePath(null);
                  onSelectCase(caseId);
                }}
                onOpenDataInbox={() => {
                  setSection("data");
                  setPreferredCasePath(null);
                }}
              />
            ) : section === "data" ? (
              <CommerceDataInbox
                workspaceId={workspaceId ?? null}
                actorId={actorId}
                refreshSignal={dataRefreshKey}
                onOpenCases={() => {
                  setPreferredCasePath(null);
                  setSection("queue");
                }}
              />
            ) : section === "capability" ? (
              <CommerceCapabilityReport
                workspaceId={workspaceId ?? null}
                refreshSignal={dataRefreshKey}
                onOpenDataInbox={() => {
                  setPreferredCasePath(null);
                  setSection("data");
                }}
                onOpenCases={() => {
                  setPreferredCasePath(null);
                  setSection("queue");
                }}
                onCreateCase={(path) => {
                  setPreferredCasePath(path.name);
                  setSection("queue");
                }}
              />
            ) : (
              <>
                <div className="px-5 pt-6 pb-28 sm:px-8 lg:px-9">
                  {viewModel.status === "empty" ? (
                    <CommerceEmptyState viewModel={viewModel} />
                  ) : (
                    <>
                      <CommerceCaseHeader viewModel={viewModel} />
                      <CommerceViewTabs
                        value={centerView}
                        onChange={setCenterView}
                      />
                      {centerView === "overview" && (
                        <CommerceCaseOverview
                          viewModel={viewModel}
                          onOpenEvidence={openEvidence}
                          onReviewAction={reviewAction}
                        />
                      )}
                      {centerView === "timeline" && (
                        <CommerceTimeline
                          viewModel={viewModel}
                          onReviewAction={reviewAction}
                        />
                      )}
                      {centerView === "evidence" && (
                        <CommerceEvidenceView viewModel={viewModel} />
                      )}
                      {centerView === "run" && (
                        <CommerceRunView viewModel={viewModel} />
                      )}
                    </>
                  )}
                </div>
                {centerView === "overview" && (
                  <CommerceBottomDock
                    composerNotice={composerNotice}
                    composerValue={composerValue}
                    onComposerChange={(value) => {
                      setComposerValue(value);
                      setComposerNotice(null);
                    }}
                    onSubmit={submitComposer}
                  />
                )}
              </>
            )}
          </div>
        </main>

        {inspectorOpen && viewModel.activeCase?.overview.evidenceInspector && (
          <CommerceInspector
            inspector={viewModel.activeCase.overview.evidenceInspector}
            onClose={() => setInspectorOpen(false)}
            onOpenEvidence={() => {
              setCenterView("evidence");
              setInspectorOpen(false);
            }}
          />
        )}
      </div>
    </div>
  );
}

function CommerceSidebar({
  collapsed,
  open,
  viewModel,
  activeSection,
  onClose,
  onToggleCollapsed,
  onSelectCase,
  onOpenDataInbox,
  onOpenCapabilityReport,
  onOpenCaseQueue,
  onOpenCreateCase,
  onOpenActionCenter,
  onOpenAgentRuns,
  onOpenSkillsEvals,
}: {
  collapsed: boolean;
  open: boolean;
  viewModel: CommerceShellViewModel;
  activeSection: CommerceSection;
  onClose: () => void;
  onToggleCollapsed: () => void;
  onSelectCase: (caseId: string) => void;
  onOpenDataInbox: () => void;
  onOpenCapabilityReport: () => void;
  onOpenCaseQueue: () => void;
  onOpenCreateCase: () => void;
  onOpenActionCenter: () => void;
  onOpenAgentRuns: () => void;
  onOpenSkillsEvals: () => void;
}) {
  const [moreOpen, setMoreOpen] = useState(false);
  const primaryItems: Array<{
    label: string;
    icon: LucideIcon;
    active?: boolean;
  }> = [
    { label: "新建诊断", icon: PlusIcon },
    { label: "数据接入", icon: DatabaseIcon, active: activeSection === "data" },
    { label: "案例队列", icon: InboxIcon, active: activeSection === "queue" },
    { label: "行动中心", icon: PlayIcon, active: activeSection === "action" },
  ];
  const workspaceItems: Array<{
    label: string;
    icon: LucideIcon;
    active?: boolean;
    onClick?: () => void;
  }> = [
    { label: "经营总览", icon: BarChart3Icon },
    {
      label: "数据能力",
      icon: GaugeIcon,
      active: activeSection === "capability",
      onClick: onOpenCapabilityReport,
    },
    {
      label: "运行记录",
      icon: Clock3Icon,
      active: activeSection === "runs",
      onClick: onOpenAgentRuns,
    },
    {
      label: "技能与评测",
      icon: SparklesIcon,
      active: activeSection === "skills",
      onClick: onOpenSkillsEvals,
    },
    { label: "作战室", icon: ShieldCheckIcon },
  ];

  return (
    <aside
      aria-label="电商经营诊断导航"
      className={cn(
        "fixed inset-y-0 left-0 z-50 flex w-[260px] flex-col border-r border-black/[0.07] bg-[#f7f7f5] transition-[width,transform] duration-200 motion-reduce:transition-none lg:relative lg:z-auto lg:translate-x-0",
        collapsed && "lg:w-[60px]",
        open ? "translate-x-0" : "-translate-x-full",
      )}
    >
      <div
        className={cn(
          "flex h-14 items-center justify-between px-5",
          collapsed && "lg:justify-center lg:px-2",
        )}
      >
        <div className="flex items-center gap-2.5 text-[15px] font-semibold tracking-tight">
          <div className="flex size-7 items-center justify-center rounded-lg bg-[#242421] text-white">
            <ActivityIcon className="size-4" aria-hidden="true" />
          </div>
          <span className={cn(collapsed && "lg:hidden")}>电商经营诊断</span>
        </div>
        <div className="flex items-center">
          <button
            type="button"
            aria-label={collapsed ? "展开导航" : "折叠导航"}
            className="hidden rounded-lg p-2 text-[#676761] hover:bg-black/5 focus-visible:outline-2 focus-visible:outline-offset-2 lg:inline-flex"
            onClick={onToggleCollapsed}
          >
            {collapsed ? (
              <ChevronRightIcon className="size-4" aria-hidden="true" />
            ) : (
              <ChevronDownIcon
                className="size-4 rotate-90"
                aria-hidden="true"
              />
            )}
          </button>
          <button
            type="button"
            aria-label="关闭导航"
            className="rounded-lg p-2 text-[#676761] hover:bg-black/5 focus-visible:outline-2 focus-visible:outline-offset-2 lg:hidden"
            onClick={onClose}
          >
            <XIcon className="size-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      <nav
        className={cn(
          "min-h-0 flex-1 overflow-y-auto px-3 pb-5",
          collapsed && "lg:px-2",
        )}
      >
        <div className="space-y-0.5 pt-2">
          {primaryItems.map((item) => (
            <SidebarItem
              key={item.label}
              {...item}
              collapsed={collapsed}
              onClick={
                item.label === "新建诊断"
                  ? onOpenCreateCase
                  : item.label === "数据接入"
                    ? onOpenDataInbox
                    : item.label === "案例队列"
                      ? onOpenCaseQueue
                      : item.label === "行动中心"
                        ? onOpenActionCenter
                        : undefined
              }
            />
          ))}
        </div>

        <div className={cn("mt-5", collapsed && "lg:hidden")}>
          <button
            type="button"
            aria-expanded={moreOpen}
            className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm text-[#666660] hover:bg-black/[0.035] focus-visible:outline-2 focus-visible:outline-offset-2"
            onClick={() => setMoreOpen((value) => !value)}
          >
            <span>更多</span>
            {moreOpen ? (
              <ChevronDownIcon className="size-4" aria-hidden="true" />
            ) : (
              <ChevronRightIcon className="size-4" aria-hidden="true" />
            )}
          </button>
          {moreOpen && (
            <div className="mt-1 space-y-0.5 pl-1">
              {workspaceItems.map((item) => (
                <SidebarItem
                  key={item.label}
                  {...item}
                  collapsed={false}
                  disabled={!item.onClick}
                />
              ))}
            </div>
          )}
        </div>

        <div className={cn(collapsed && "lg:hidden")}>
          <SidebarSectionLabel>当前案例</SidebarSectionLabel>
        </div>
        <div className="space-y-1">
          {viewModel.navigation.cases.length === 0 ? (
            <p
              className={cn(
                "px-3 py-2 text-xs leading-5 text-[#8a8a84]",
                collapsed && "lg:hidden",
              )}
            >
              接入数据后，新的经营案例会显示在这里。
            </p>
          ) : (
            viewModel.navigation.cases.map((item) => (
              <button
                type="button"
                key={item.id}
                aria-current={
                  activeSection === "case" && item.isActive ? "page" : undefined
                }
                className={cn(
                  "group flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 motion-reduce:transition-none",
                  collapsed && "lg:justify-center lg:px-2",
                  activeSection === "case" && item.isActive
                    ? "bg-black/[0.065] text-[#20201e]"
                    : "text-[#53534e] hover:bg-black/[0.035]",
                )}
                onClick={() => onSelectCase(item.id)}
              >
                <span
                  className={cn(
                    "mt-1.5 size-2 shrink-0 rounded-full",
                    collapsed && "lg:mt-0 lg:size-2.5",
                    item.severityLabel === "紧急" ||
                      item.severityLabel === "高风险"
                      ? "bg-red-500"
                      : item.severityLabel === "中风险"
                        ? "bg-amber-500"
                        : "bg-emerald-500",
                  )}
                />
                <span className={cn("min-w-0", collapsed && "lg:hidden")}>
                  <span className="block truncate text-sm font-medium">
                    {item.title}
                  </span>
                  <span className="mt-0.5 block text-[11px] text-[#878781]">
                    {item.statusLabel} · {item.severityLabel}
                  </span>
                </span>
              </button>
            ))
          )}
        </div>
      </nav>

      <div className="border-t border-black/[0.06] p-3">
        <SidebarItem
          label="设置"
          icon={SettingsIcon}
          collapsed={collapsed}
          disabled
        />
      </div>
    </aside>
  );
}

function SidebarItem({
  label,
  icon: Icon,
  collapsed,
  active = false,
  disabled = false,
  onClick,
}: {
  label: string;
  icon: LucideIcon;
  collapsed: boolean;
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-current={active ? "page" : undefined}
      onClick={onClick}
      title={disabled ? "将在对应页面实现后启用" : undefined}
      className={cn(
        "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-default disabled:opacity-100 motion-reduce:transition-none",
        collapsed && "lg:justify-center lg:px-2",
        active
          ? "bg-black/[0.055] font-medium text-[#20201e]"
          : "text-[#53534e] hover:bg-black/[0.035]",
      )}
    >
      <Icon className="size-[17px] stroke-[1.7]" aria-hidden="true" />
      <span className={cn(collapsed && "lg:hidden")}>{label}</span>
    </button>
  );
}

function SidebarSectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-6 mb-2 px-3 text-[11px] font-medium tracking-[0.12em] text-[#9a9a94]">
      {children}
    </div>
  );
}

function CommerceTopBar({
  title,
  secondaryLabel = "案例详情",
  isRefreshing,
  showInspector = true,
  inspectorAvailable,
  onOpenInspector,
  onOpenSidebar,
  onRefresh,
}: {
  title: string;
  secondaryLabel?: string;
  isRefreshing: boolean;
  showInspector?: boolean;
  inspectorAvailable: boolean;
  onOpenInspector: () => void;
  onOpenSidebar: () => void;
  onRefresh: () => void;
}) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-black/[0.07] bg-white/95 px-3 backdrop-blur sm:px-5">
      <div className="flex min-w-0 items-center gap-2.5">
        <button
          type="button"
          aria-label="打开导航"
          className="rounded-lg p-2 hover:bg-black/5 focus-visible:outline-2 focus-visible:outline-offset-2 lg:hidden"
          onClick={onOpenSidebar}
        >
          <MenuIcon className="size-[18px]" aria-hidden="true" />
        </button>
        <FolderOpenIcon
          className="hidden size-[18px] stroke-[1.6] sm:block"
          aria-hidden="true"
        />
        <p className="truncate text-sm font-semibold">{title}</p>
        <span className="hidden text-[#c4c4bf] sm:inline">/</span>
        <span className="hidden truncate text-xs text-[#777771] md:inline">
          {secondaryLabel}
        </span>
      </div>
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-label="刷新工作区"
          className="rounded-lg p-2 text-[#62625d] hover:bg-black/5 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50"
          disabled={isRefreshing}
          onClick={onRefresh}
        >
          <RefreshCwIcon
            className={cn("size-[17px]", isRefreshing && "animate-spin")}
            aria-hidden="true"
          />
        </button>
        <button
          type="button"
          aria-label="更多操作"
          className="rounded-lg p-2 text-[#62625d] hover:bg-black/5 focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          <MoreHorizontalIcon className="size-[18px]" aria-hidden="true" />
        </button>
        {showInspector && (
          <button
            type="button"
            aria-label="打开检查面板"
            disabled={!inspectorAvailable}
            className="inline-flex items-center gap-2 rounded-lg border border-black/[0.08] px-2.5 py-1.5 text-xs text-[#51514c] hover:bg-black/5 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-default disabled:opacity-40"
            onClick={onOpenInspector}
          >
            <ListFilterIcon className="size-[18px]" aria-hidden="true" />
            <span className="hidden sm:inline">检查面板</span>
          </button>
        )}
      </div>
    </header>
  );
}

function CommerceCaseHeader({
  viewModel,
}: {
  viewModel: CommerceShellViewModel;
}) {
  const activeCase = viewModel.activeCase;
  if (!activeCase) return null;
  return (
    <section className="mx-auto w-full max-w-[880px]">
      <p className="mb-3 text-xs font-medium text-[#777771]">案例详情</p>
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <h1 className="text-[26px] leading-tight font-semibold tracking-[-0.025em] sm:text-[30px]">
            {activeCase.title}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#666660]">
            {activeCase.subtitle}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <StatusPill tone="danger">{activeCase.severityLabel}</StatusPill>
          <StatusPill>{activeCase.statusLabel}</StatusPill>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#777771]">
        <span>{activeCase.overview.periodLabel}</span>
        <span aria-hidden="true">·</span>
        <span>{activeCase.overview.updatedLabel}</span>
        <span aria-hidden="true">·</span>
        <span>{activeCase.overview.evidenceCountLabel}</span>
      </div>
    </section>
  );
}

function StatusPill({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "danger";
}) {
  return (
    <span
      className={cn(
        "inline-flex h-7 items-center rounded-full border px-3 text-xs font-medium",
        tone === "danger"
          ? "border-red-200 bg-red-50 text-red-700"
          : "border-black/[0.08] bg-[#f5f5f3] text-[#555550]",
      )}
    >
      {children}
    </span>
  );
}

function CommerceViewTabs({
  value,
  onChange,
}: {
  value: CenterView;
  onChange: (value: CenterView) => void;
}) {
  const tabs: Array<{ value: CenterView; label: string }> = [
    { value: "overview", label: "概览" },
    { value: "timeline", label: "调查记录" },
    { value: "evidence", label: "证据" },
    { value: "run", label: "运行" },
  ];
  return (
    <div className="mx-auto mt-7 flex w-full max-w-[880px] overflow-x-auto border-b border-black/[0.08]">
      {tabs.map((tab) => (
        <button
          type="button"
          key={tab.value}
          className={cn(
            "relative shrink-0 px-4 py-3 text-sm font-medium text-[#74746e] transition-colors hover:text-[#20201e] focus-visible:outline-2 focus-visible:outline-offset-2 motion-reduce:transition-none",
            value === tab.value && "text-[#20201e]",
          )}
          onClick={() => onChange(tab.value)}
        >
          {tab.label}
          {value === tab.value && (
            <span className="absolute right-2 bottom-0 left-2 h-0.5 rounded-full bg-[#20201e]" />
          )}
        </button>
      ))}
    </div>
  );
}

function CommerceCaseOverview({
  viewModel,
  onOpenEvidence,
  onReviewAction,
}: {
  viewModel: CommerceShellViewModel;
  onOpenEvidence: () => void;
  onReviewAction: () => void;
}) {
  const activeCase = viewModel.activeCase;
  if (!activeCase) return null;
  const overview = activeCase.overview;
  return (
    <section className="mx-auto w-full max-w-[880px] py-5">
      <div className="border-b border-black/[0.08] pb-5">
        <h2 className="text-base font-semibold">发生了什么</h2>
        <p className="mt-2 text-sm leading-6 text-[#65655f]">
          {overview.problemStatement}
        </p>
        {overview.comparison ? (
          <div className="mt-4 grid items-center gap-3 rounded-xl border border-black/[0.09] px-4 py-3 text-sm sm:grid-cols-[1fr_auto_1fr_auto]">
            <div>
              <p className="text-[11px] text-[#898983]">上一周期</p>
              <p className="mt-1 font-medium tabular-nums">
                {overview.comparison.baselineValueLabel}
              </p>
            </div>
            <ChevronRightIcon
              className="hidden size-4 text-[#8a8a84] sm:block"
              aria-hidden="true"
            />
            <div>
              <p className="text-[11px] text-[#898983]">当前周期</p>
              <p className="mt-1 font-medium tabular-nums">
                {overview.comparison.currentValueLabel}
              </p>
            </div>
            <p className="text-xs font-medium text-red-600 tabular-nums sm:text-right">
              {overview.comparison.changeLabel}
            </p>
          </div>
        ) : (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900">
            {overview.analysisUnavailableLabel ?? "当前没有可复算的指标对比。"}
          </div>
        )}
      </div>

      <div className="border-b border-black/[0.08] py-5">
        <h2 className="text-base font-semibold">当前判断</h2>
        <div className="mt-3 flex items-start gap-3 rounded-xl border border-black/[0.08] bg-[#fafaf8] px-4 py-3.5">
          {overview.conclusion.verified ? (
            <CircleCheckIcon
              className="mt-0.5 size-5 shrink-0 text-emerald-700"
              aria-hidden="true"
            />
          ) : (
            <CircleAlertIcon
              className="mt-0.5 size-5 shrink-0 text-amber-700"
              aria-hidden="true"
            />
          )}
          <div>
            <p className="text-sm leading-6 text-[#44443f]">
              {overview.conclusion.description}
            </p>
            <p className="mt-1 text-xs text-[#777771]">
              {overview.conclusion.verificationLabel}
            </p>
          </div>
        </div>
      </div>

      <div className="border-b border-black/[0.08] py-5">
        <h2 className="text-base font-semibold">证据边界</h2>
        <div className="mt-3 flex flex-col gap-3 rounded-xl border border-black/[0.08] px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-medium">
              {overview.evidenceBoundary.summary}
            </p>
            <p className="mt-1 text-xs leading-5 text-[#73736d]">
              {overview.evidenceBoundary.unknownSummary}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            {overview.evidenceBoundary.contradictingCount > 0 && (
              <span className="text-xs text-amber-700">
                {overview.evidenceBoundary.contradictingCount} 条矛盾
              </span>
            )}
            <button
              type="button"
              disabled={!overview.evidenceBoundary.primaryEvidenceId}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-black/[0.09] px-3 text-sm font-medium hover:bg-black/[0.035] focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-default disabled:opacity-40"
              onClick={onOpenEvidence}
            >
              查看证据
              <ChevronRightIcon className="size-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>

      <div className="py-5">
        <h2 className="text-base font-semibold">下一步</h2>
        <div className="mt-3 flex flex-col gap-3 rounded-xl border border-black/[0.08] px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <TargetIcon
              className="mt-0.5 size-4 shrink-0 text-[#555550]"
              aria-hidden="true"
            />
            <div className="min-w-0">
              <p className="text-sm font-medium">{overview.action.title}</p>
              <p className="mt-1 text-xs text-[#73736d]">
                {overview.action.statusLabel}
              </p>
            </div>
          </div>
          <button
            type="button"
            disabled={!overview.action.available}
            className="inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-black/[0.09] px-3 text-sm font-medium hover:bg-black/[0.035] focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-default disabled:opacity-40"
            onClick={onReviewAction}
          >
            {overview.action.available ? "查看行动" : "等待行动"}
            <ChevronRightIcon className="size-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </section>
  );
}

function CommerceTimeline({
  viewModel,
  onReviewAction,
}: {
  viewModel: CommerceShellViewModel;
  onReviewAction: () => void;
}) {
  const activeCase = viewModel.activeCase;
  return (
    <section className="mx-auto w-full max-w-[880px] py-5">
      {viewModel.timeline.wasReordered && (
        <div className="mb-4 rounded-xl border border-sky-100 bg-sky-50 px-4 py-3 text-xs leading-5 text-sky-900">
          接收到的事件顺序不一致，界面已按权威案例序号重新排序。
        </div>
      )}
      {viewModel.timeline.items.length === 0 ? (
        <InlineEmptyState
          icon={Clock3Icon}
          title="还没有调查记录"
          description="当前案例尚未产生结构化调查事件。"
        />
      ) : (
        <ol className="relative ml-3 border-l border-black/[0.13]">
          {viewModel.timeline.items.map((item) => (
            <CommerceTimelineItem
              key={item.id}
              item={item}
              evidence={
                item.title.endsWith("分析已完成")
                  ? activeCase?.evidence.slice(0, 2)
                  : undefined
              }
            />
          ))}
        </ol>
      )}

      {activeCase && (
        <div className="mt-5 flex flex-col gap-4 rounded-xl border border-black/[0.09] bg-[#fafaf8] px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold">
              {activeCase.actionState.label}
            </h3>
            <p className="mt-1 text-xs leading-5 text-[#72726c]">
              {activeCase.actionState.description}
            </p>
          </div>
          <button
            type="button"
            disabled={!activeCase.actionState.available}
            className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-lg bg-[#252522] px-4 text-sm font-medium text-white hover:bg-black focus-visible:outline-2 focus-visible:outline-offset-2 disabled:bg-[#ddddda] disabled:text-[#85857f]"
            onClick={onReviewAction}
          >
            {activeCase.actionState.available ? "查看行动" : "等待行动"}
            <ChevronRightIcon className="size-4" aria-hidden="true" />
          </button>
        </div>
      )}
    </section>
  );
}

function CommerceTimelineItem({
  item,
  evidence,
}: {
  item: CommerceTimelineItemViewModel;
  evidence?: NonNullable<CommerceShellViewModel["activeCase"]>["evidence"];
}) {
  const Icon = timelineIcon(item);
  return (
    <li className="relative ml-8 pb-6 last:pb-1">
      <span
        className={cn(
          "absolute top-0 -left-[45px] flex size-7 items-center justify-center rounded-full border bg-white",
          item.state === "completed" && "border-emerald-200 text-emerald-700",
          item.state === "running" && "border-amber-200 text-amber-700",
          item.state === "blocked" && "border-red-200 text-red-700",
          item.state === "neutral" && "border-black/10 text-[#777771]",
        )}
      >
        <Icon className="size-3.5" aria-hidden="true" />
      </span>
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <div>
          <h3 className="text-sm font-semibold">{item.title}</h3>
          <p className="mt-1 text-xs leading-5 text-[#71716b]">
            {item.description}
          </p>
        </div>
        <time className="shrink-0 text-[11px] text-[#8b8b85] tabular-nums">
          {item.timeLabel}
        </time>
      </div>
      {evidence && evidence.length > 0 && (
        <div className="mt-4 rounded-xl border border-black/[0.08] bg-[#fafaf8] p-3">
          <h4 className="mb-2 text-xs font-semibold">关键发现</h4>
          <div className="space-y-1.5">
            {evidence.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-3 rounded-lg border border-black/[0.06] bg-white px-3 py-2 text-xs"
              >
                <span className="rounded-md border border-black/[0.08] bg-[#f8f8f6] px-2 py-0.5 text-[10px] text-[#686862]">
                  {item.typeLabel}
                </span>
                <span className="min-w-0 flex-1 text-[#4b4b46]">
                  {item.summary}
                </span>
                <span
                  className={cn(
                    "shrink-0 text-[10px] font-medium",
                    item.relation === "contradicts"
                      ? "text-amber-700"
                      : "text-emerald-700",
                  )}
                >
                  {item.statusLabel}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </li>
  );
}

function CommerceEvidenceView({
  viewModel,
}: {
  viewModel: CommerceShellViewModel;
}) {
  const activeCase = viewModel.activeCase;
  return activeCase ? (
    <CommerceEvidenceExplorer viewModel={activeCase.evidenceExplorer} />
  ) : null;
}

function CommerceRunView({ viewModel }: { viewModel: CommerceShellViewModel }) {
  return (
    <section className="mx-auto w-full max-w-[880px] py-6">
      {viewModel.subagents.length === 0 ? (
        <InlineEmptyState
          icon={BotIcon}
          title="还没有子智能体运行记录"
          description="系统只有在数据能力满足路径要求时才会启动相应分析。"
        />
      ) : (
        <div className="rounded-xl border border-black/[0.08] bg-[#fafaf8] p-5">
          <div className="flex items-center gap-3 rounded-xl border border-black/[0.08] bg-white px-4 py-3">
            <TargetIcon className="size-4 text-[#60605a]" aria-hidden="true" />
            <div>
              <p className="text-sm font-semibold">目标循环</p>
              <p className="mt-0.5 text-xs text-[#777771]">
                {viewModel.runtime.stateLabel}
              </p>
            </div>
          </div>
          <div className="mx-7 h-5 border-l border-black/[0.12]" />
          <div className="grid gap-2 sm:grid-cols-3">
            {viewModel.subagents.map((item) => (
              <div
                key={item.pathType}
                className="rounded-xl border border-black/[0.08] bg-white px-4 py-3"
              >
                <p className="text-sm font-semibold">{item.label}</p>
                <p
                  className={cn(
                    "mt-1 text-xs",
                    item.status === "completed"
                      ? "text-emerald-700"
                      : item.status === "blocked"
                        ? "text-red-700"
                        : "text-amber-700",
                  )}
                >
                  {item.statusLabel}
                </p>
              </div>
            ))}
          </div>
          <div className="mx-7 h-5 border-l border-black/[0.12]" />
          <div className="flex items-center gap-3 rounded-xl border border-black/[0.08] bg-white px-4 py-3">
            <ShieldCheckIcon
              className="size-4 text-emerald-700"
              aria-hidden="true"
            />
            <div>
              <p className="text-sm font-semibold">独立验证</p>
              <p className="mt-0.5 text-xs text-[#777771]">
                {viewModel.runtime.modelLabel} · {viewModel.runtime.retryLabel}
              </p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function CommerceInspector({
  inspector,
  onClose,
  onOpenEvidence,
}: {
  inspector: CommerceEvidenceInspectorViewModel;
  onClose: () => void;
  onOpenEvidence: () => void;
}) {
  return (
    <aside
      aria-label="证据详情"
      className="fixed inset-y-0 right-0 z-50 flex w-[min(88vw,340px)] flex-col bg-[#fbfbfa] shadow-[-18px_0_50px_rgba(0,0,0,0.08)] xl:relative xl:inset-auto xl:z-auto xl:mt-[72px] xl:mr-4 xl:mb-4 xl:ml-3 xl:h-[calc(100%-88px)] xl:w-auto xl:overflow-hidden xl:rounded-2xl xl:border xl:border-black/[0.08] xl:shadow-[0_10px_35px_rgba(0,0,0,0.07)]"
    >
      <div className="flex h-14 items-center justify-between border-b border-black/[0.07] px-5">
        <h2 className="text-sm font-semibold">证据详情</h2>
        <button
          type="button"
          aria-label="关闭检查面板"
          className="rounded-lg p-2 text-[#696963] hover:bg-black/5 focus-visible:outline-2 focus-visible:outline-offset-2"
          onClick={onClose}
        >
          <XIcon className="size-4" aria-hidden="true" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <div className="border-b border-black/[0.07] pb-4">
          <h3 className="text-sm font-semibold">{inspector.title}</h3>
          <span className="mt-2 inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700">
            {inspector.statusLabel}
          </span>
        </div>

        <InspectorSection title="证据属性">
          <InspectorRow label="类型" value={inspector.typeLabel} />
          <InspectorRow
            label="关系"
            value={inspector.relationLabel}
            tone="positive"
          />
          <InspectorRow label="分析周期" value={inspector.periodLabel} />
        </InspectorSection>

        <InspectorSection title="数值">
          <InspectorRow label="上一周期" value={inspector.baselineValueLabel} />
          <InspectorRow label="当前周期" value={inspector.currentValueLabel} />
          <InspectorRow
            label="变化"
            value={inspector.changeLabel}
            tone="danger"
          />
        </InspectorSection>

        <InspectorSection title="来源与口径">
          <InspectorRow label="数据来源" value={inspector.sourceLabel} />
          <InspectorRow label="计算口径" value={inspector.formulaLabel} />
          <InspectorRow
            label="数据血缘"
            value={inspector.lineageLabel}
            tone="positive"
          />
        </InspectorSection>

        <button
          type="button"
          className="flex h-10 w-full items-center justify-center rounded-lg border border-black/[0.09] text-sm font-medium hover:bg-black/[0.035] focus-visible:outline-2 focus-visible:outline-offset-2"
          onClick={onOpenEvidence}
        >
          查看数据血缘
        </button>
      </div>
    </aside>
  );
}

function InspectorRow({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "positive" | "danger";
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-black/[0.05] px-1 py-2.5 last:border-b-0">
      <span className="shrink-0 text-xs text-[#777771]">{label}</span>
      <span
        className={cn(
          "text-right text-xs leading-5 font-medium",
          tone === "positive" && "text-emerald-700",
          tone === "danger" && "text-red-600",
        )}
      >
        {value}
      </span>
    </div>
  );
}

function InspectorSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-5">
      <h3 className="mb-2 px-1 text-xs font-semibold">{title}</h3>
      {children}
    </section>
  );
}

function CommerceBottomDock({
  composerNotice,
  composerValue,
  onComposerChange,
  onSubmit,
}: {
  composerNotice: string | null;
  composerValue: string;
  onComposerChange: (value: string) => void;
  onSubmit: () => void;
}) {
  const [focused, setFocused] = useState(false);
  const expanded =
    focused || Boolean(composerValue.trim()) || Boolean(composerNotice);
  return (
    <div className="pointer-events-none absolute right-3 bottom-3 left-3 z-20 sm:right-5 sm:left-5">
      <div className="pointer-events-auto mx-auto max-w-[880px]">
        <div className="rounded-2xl border border-black/[0.09] bg-white p-2 shadow-[0_14px_38px_rgba(0,0,0,0.1)]">
          <label htmlFor="commerce-case-composer" className="sr-only">
            继续询问当前案例
          </label>
          <div className="flex items-end gap-2">
            <button
              type="button"
              disabled
              aria-label="添加电商数据"
              title="将在数据接入页面实现后启用"
              className="flex size-9 shrink-0 items-center justify-center rounded-full border border-black/[0.08] text-[#686862] disabled:cursor-default"
            >
              <PaperclipIcon className="size-4" aria-hidden="true" />
            </button>
            <span className="hidden h-9 shrink-0 items-center gap-2 rounded-lg border border-black/[0.08] bg-[#fafaf8] px-3 text-xs text-[#5f5f59] sm:inline-flex">
              <FolderOpenIcon className="size-3.5" aria-hidden="true" />
              当前案例
            </span>
            <textarea
              id="commerce-case-composer"
              rows={expanded ? 2 : 1}
              value={composerValue}
              placeholder="继续询问当前案例，或添加新的数据……"
              className={cn(
                "min-h-9 flex-1 resize-none border-0 bg-transparent px-2 py-1.5 text-sm leading-6 outline-none placeholder:text-[#9b9b95]",
                expanded && "min-h-[58px]",
              )}
              onBlur={() => setFocused(false)}
              onChange={(event) => onComposerChange(event.target.value)}
              onFocus={() => setFocused(true)}
            />
            <button
              type="button"
              aria-label="发送案例问题"
              disabled={!composerValue.trim()}
              className="flex size-9 shrink-0 items-center justify-center rounded-full bg-[#242421] text-white hover:bg-black focus-visible:outline-2 focus-visible:outline-offset-2 disabled:bg-[#ddddda] disabled:text-[#8c8c86]"
              onClick={onSubmit}
            >
              <SendIcon className="size-4" aria-hidden="true" />
            </button>
          </div>
          {composerNotice && (
            <p
              className="mx-2 mt-2 border-t border-black/[0.06] px-1 pt-2 pb-1 text-[11px] leading-5 text-amber-800"
              role="status"
            >
              {composerNotice}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function CommerceEmptyState({
  viewModel,
}: {
  viewModel: CommerceShellViewModel;
}) {
  const emptyState = viewModel.emptyState;
  if (!emptyState) return null;
  return (
    <div className="mx-auto flex min-h-[60vh] w-full max-w-[760px] flex-col items-center justify-center text-center">
      <div className="flex size-12 items-center justify-center rounded-2xl border border-black/[0.08] bg-[#f6f6f3]">
        <InboxIcon className="size-5 text-[#666660]" aria-hidden="true" />
      </div>
      <h2 className="mt-5 text-xl font-semibold">{emptyState.title}</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-[#70706a]">
        {emptyState.description}
      </p>
      <button
        type="button"
        disabled
        title="将在数据接入页面实现后启用"
        className="mt-5 rounded-lg bg-[#252522] px-4 py-2 text-sm font-medium text-white disabled:cursor-default"
      >
        {emptyState.actionLabel}
      </button>
      <p className="mt-8 text-xs text-[#8a8a84]">
        {viewModel.runtime.stateLabel}
      </p>
    </div>
  );
}

function InlineEmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <div className="flex min-h-52 flex-col items-center justify-center rounded-xl border border-dashed border-black/[0.12] px-6 text-center">
      <Icon className="size-5 text-[#7b7b75]" aria-hidden="true" />
      <h3 className="mt-3 text-sm font-semibold">{title}</h3>
      <p className="mt-1 max-w-sm text-xs leading-5 text-[#7b7b75]">
        {description}
      </p>
    </div>
  );
}

function CommerceLoadingState() {
  return (
    <div className="flex h-dvh items-center justify-center bg-[#f7f7f5] text-[#20201e]">
      <div className="text-center" role="status">
        <RefreshCwIcon
          className="mx-auto size-5 animate-spin text-[#73736d] motion-reduce:animate-none"
          aria-hidden="true"
        />
        <p className="mt-3 text-sm font-medium">正在加载经营工作区</p>
        <p className="mt-1 text-xs text-[#777771]">
          当前只读取案例、证据、运行和结构化事件。
        </p>
      </div>
    </div>
  );
}

function CommerceConfigurationState() {
  return (
    <div className="flex h-dvh items-center justify-center bg-[#f7f7f5] px-6 text-[#20201e]">
      <div className="max-w-md rounded-2xl border border-black/[0.08] bg-white p-7 text-center shadow-sm">
        <CircleAlertIcon
          className="mx-auto size-6 text-amber-600"
          aria-hidden="true"
        />
        <h1 className="mt-4 text-lg font-semibold">尚未配置经营工作区</h1>
        <p className="mt-2 text-sm leading-6 text-[#6f6f69]">
          请为前端配置一个有效的经营工作区标识。系统不会猜测工作区，也不会跨工作区读取案例。
        </p>
      </div>
    </div>
  );
}

function CommerceFailureState({
  error,
  onRetry,
}: {
  error: CommerceLoadError;
  onRetry: () => void;
}) {
  return (
    <div className="flex h-dvh items-center justify-center bg-[#f7f7f5] px-6 text-[#20201e]">
      <div className="max-w-md rounded-2xl border border-black/[0.08] bg-white p-7 text-center shadow-sm">
        <CircleAlertIcon
          className="mx-auto size-6 text-red-600"
          aria-hidden="true"
        />
        <h1 className="mt-4 text-lg font-semibold">{error.title}</h1>
        <p className="mt-2 text-sm leading-6 text-[#6f6f69]">
          {error.description}
        </p>
        <button
          type="button"
          className="mt-5 inline-flex h-9 items-center gap-2 rounded-lg bg-[#252522] px-4 text-sm font-medium text-white hover:bg-black focus-visible:outline-2 focus-visible:outline-offset-2"
          onClick={onRetry}
        >
          <RefreshCwIcon className="size-4" aria-hidden="true" />
          重新加载
        </button>
      </div>
    </div>
  );
}

function timelineIcon(item: CommerceTimelineItemViewModel): LucideIcon {
  if (item.state === "completed") return CircleCheckIcon;
  if (item.state === "running") return Clock3Icon;
  if (item.state === "blocked") return CircleAlertIcon;
  return ActivityIcon;
}

function projectLoadError(error: unknown): CommerceLoadError {
  if (error instanceof CommerceApiError) {
    if (error.code === "invalid_response") {
      return {
        title: "经营数据合同不兼容",
        description:
          "后端响应没有通过前端合同校验。界面已停止渲染，避免猜测或伪造状态。",
      };
    }
    if (error.status === 404) {
      return {
        title: "经营案例不存在",
        description: "当前案例可能已被删除，或不属于已配置的工作区。",
      };
    }
    if (error.status === 503) {
      return {
        title: "经营数据服务暂不可用",
        description: "持久化服务尚未初始化或正在恢复，请稍后重试。",
      };
    }
  }
  return {
    title: "无法加载经营工作区",
    description: "请检查后端服务、功能开关和工作区配置后重试。",
  };
}
