"use client";

import {
  CheckCircle2Icon,
  ChevronDownIcon,
  ChevronRightIcon,
  CircleAlertIcon,
  DatabaseIcon,
  FileCheck2Icon,
  FileUpIcon,
  FolderOpenIcon,
  HashIcon,
  LoaderCircleIcon,
  ShieldCheckIcon,
  UploadCloudIcon,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  buildCommerceDataInboxViewModel,
  CommerceApiError,
  loadCommerceDataInboxSnapshot,
  resumeCommerceDatasetMapping,
  uploadCommerceDataset,
  type CommerceDataInboxSnapshot,
  type CommerceDataInboxViewModel,
} from "@/core/commerce";
import { cn } from "@/lib/utils";

interface CommerceDataInboxProps {
  workspaceId: string | null;
  actorId?: string | null;
  refreshSignal?: number;
  onOpenCases?: () => void;
}

type InboxError = {
  title: string;
  description: string;
};

export function CommerceDataInbox({
  workspaceId,
  actorId,
  refreshSignal = 0,
  onOpenCases,
}: CommerceDataInboxProps) {
  const [snapshot, setSnapshot] = useState<CommerceDataInboxSnapshot | null>(
    null,
  );
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [error, setError] = useState<InboxError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!workspaceId) return;
    const controller = new AbortController();
    setError(null);
    void loadCommerceDataInboxSnapshot({
      workspaceId,
      selectedDatasetId,
      signal: controller.signal,
    })
      .then((nextSnapshot) => setSnapshot(nextSnapshot))
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === "AbortError") {
          return;
        }
        setError(projectInboxError(cause));
      });
    return () => controller.abort();
  }, [refreshKey, refreshSignal, selectedDatasetId, workspaceId]);

  const viewModel = useMemo(
    () =>
      buildCommerceDataInboxViewModel(
        snapshot ?? {
          workspaceId: workspaceId ?? "",
          datasets: [],
          selectedDataset: null,
        },
      ),
    [snapshot, workspaceId],
  );

  if (!workspaceId) {
    return (
      <CommerceDataInboxView
        viewModel={viewModel}
        isUploading={false}
        isConfirming={false}
        error={{
          title: "尚未配置工作区",
          description:
            "需要先配置 Commerce Workspace ID，才能安全读取数据批次。",
        }}
        notice={null}
        actorConfigured={Boolean(actorId)}
        onChooseFiles={() => undefined}
        onDropFiles={() => undefined}
        onRefresh={() => undefined}
        onSelectDataset={() => undefined}
        onConfirm={() => undefined}
        onDefer={() => undefined}
        onContinue={() => undefined}
        onOpenCases={onOpenCases}
      />
    );
  }

  const chooseFiles = async (files: File[]) => {
    if (files.length === 0) return;
    setNotice(null);
    setError(null);
    setIsUploading(true);
    try {
      const intake = await uploadCommerceDataset({ workspaceId, files });
      setSelectedDatasetId(intake.manifest.dataset_id);
      setRefreshKey((value) => value + 1);
      setNotice("数据已安全接收，正在确认字段语义和可分析范围。");
    } catch (cause: unknown) {
      setError(projectInboxError(cause, "数据接收失败"));
    } finally {
      setIsUploading(false);
    }
  };

  const confirmMapping = async () => {
    const pending = viewModel.pendingConfirmation;
    const datasetId = viewModel.selectedDataset?.manifest.dataset_id;
    if (!pending || !datasetId) return;
    if (!actorId?.trim()) {
      setError({
        title: "无法记录确认人",
        description: "当前页面没有配置操作人标识，确认不会被提交。",
      });
      return;
    }
    setIsConfirming(true);
    setError(null);
    setNotice(null);
    try {
      await resumeCommerceDatasetMapping({
        workspaceId,
        datasetId,
        actorId,
        tableName: pending.tableName,
        columnName: pending.columnName,
        semanticField: pending.semanticField,
        idempotencyKey: `mapping-resume-${Date.now()}`,
      });
      setRefreshKey((value) => value + 1);
      setNotice("字段含义已记录，数据能力检查可以继续。");
    } catch (cause: unknown) {
      setError(projectInboxError(cause, "字段确认失败"));
    } finally {
      setIsConfirming(false);
    }
  };

  return (
    <CommerceDataInboxView
      viewModel={viewModel}
      isUploading={isUploading}
      isConfirming={isConfirming}
      error={error}
      notice={notice}
      actorConfigured={Boolean(actorId?.trim())}
      onChooseFiles={chooseFiles}
      onDropFiles={chooseFiles}
      onRefresh={() => setRefreshKey((value) => value + 1)}
      onSelectDataset={(datasetId) => setSelectedDatasetId(datasetId)}
      onConfirm={confirmMapping}
      onDefer={() => setNotice("已保留当前批次；未确认字段不会被推断为零。")}
      onContinue={() =>
        setNotice(
          "数据能力报告将在下一步接入；当前页面不会创建案例或启动调查。",
        )
      }
      onOpenCases={onOpenCases}
    />
  );
}

interface CommerceDataInboxViewProps {
  viewModel: CommerceDataInboxViewModel;
  isUploading: boolean;
  isConfirming: boolean;
  error: InboxError | null;
  notice: string | null;
  actorConfigured: boolean;
  onChooseFiles: (files: File[]) => void;
  onDropFiles: (files: File[]) => void;
  onRefresh: () => void;
  onSelectDataset: (datasetId: string) => void;
  onConfirm: () => void;
  onDefer: () => void;
  onContinue: () => void;
  onOpenCases?: () => void;
}

export function CommerceDataInboxView({
  viewModel,
  isUploading,
  isConfirming,
  error,
  notice,
  actorConfigured,
  onChooseFiles,
  onDropFiles,
  onRefresh,
  onSelectDataset,
  onConfirm,
  onDefer,
  onContinue,
  onOpenCases,
}: CommerceDataInboxViewProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showAllFiles, setShowAllFiles] = useState(false);

  const files = showAllFiles ? viewModel.files : viewModel.files.slice(0, 3);
  const hasMoreFiles = viewModel.files.length > 3;

  return (
    <div className="min-h-full bg-white px-5 pt-6 pb-16 sm:px-8 lg:px-9">
      <div className="mx-auto max-w-[900px]">
        <div>
          <p className="text-[11px] font-semibold tracking-[0.16em] text-[#8a8a82] uppercase">
            数据接入
          </p>
          <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.035em] text-[#242421] sm:text-[32px]">
            {viewModel.title}
          </h1>
          <p className="mt-2 max-w-[700px] text-sm leading-6 text-[#6f6f69]">
            {viewModel.subtitle}
          </p>
          {viewModel.metadataLabel && (
            <p className="mt-3 text-xs text-[#878780]">
              {viewModel.metadataLabel}
            </p>
          )}
        </div>

        {error && (
          <div
            className="mt-5 flex items-start justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-950"
            role="alert"
          >
            <div>
              <p className="font-medium">{error.title}</p>
              <p className="mt-1 text-xs leading-5 text-red-800">
                {error.description}
              </p>
            </div>
            <button
              type="button"
              className="shrink-0 rounded-lg px-2 py-1 text-xs font-medium hover:bg-red-100 focus-visible:outline-2 focus-visible:outline-offset-2"
              onClick={onRefresh}
            >
              重试
            </button>
          </div>
        )}

        {notice && (
          <div
            className="mt-5 rounded-xl border border-[#dce5dc] bg-[#f5faf5] px-4 py-3 text-sm text-[#315338]"
            role="status"
          >
            {notice}
          </div>
        )}

        {viewModel.status === "empty" ? (
          <CommerceDataInboxEmpty
            isUploading={isUploading}
            isDragging={isDragging}
            inputRef={inputRef}
            onDragEnter={() => setIsDragging(true)}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setIsDragging(false);
              onDropFiles(Array.from(event.dataTransfer.files));
            }}
            onChoose={() => inputRef.current?.click()}
            onInput={(event) => {
              onChooseFiles(Array.from(event.target.files ?? []));
              event.target.value = "";
            }}
            recentDatasets={viewModel.recentDatasets}
            onSelectDataset={onSelectDataset}
          />
        ) : (
          <>
            <section className="mt-8" aria-labelledby="dataset-batch-heading">
              <div className="flex items-center justify-between gap-4">
                <h2
                  id="dataset-batch-heading"
                  className="text-sm font-semibold text-[#2d2d29]"
                >
                  本次数据批次
                </h2>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-[#dce8dc] bg-[#f5faf5] px-2.5 py-1 text-xs font-medium text-[#3d6a43]">
                  <ShieldCheckIcon className="size-3.5" aria-hidden="true" />
                  已安全接收
                </span>
              </div>
              <div className="mt-3 divide-y divide-black/[0.06] rounded-xl border border-black/[0.08] bg-white">
                {files.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center gap-3 px-4 py-3 text-sm"
                  >
                    <FileCheck2Icon
                      className="size-4 shrink-0 text-[#4f7754]"
                      aria-hidden="true"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-[#30302c]">
                        {file.filename}
                      </p>
                      <p className="mt-0.5 text-xs text-[#85857e]">
                        {file.roleLabel} · {file.rowLabel}
                      </p>
                    </div>
                    <span className="shrink-0 text-xs font-medium text-[#4f7754]">
                      {file.statusLabel}
                    </span>
                  </div>
                ))}
                {hasMoreFiles && (
                  <button
                    type="button"
                    className="flex w-full items-center justify-center gap-1 px-4 py-3 text-xs font-medium text-[#686862] hover:bg-black/[0.025] focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
                    onClick={() => setShowAllFiles((value) => !value)}
                  >
                    {showAllFiles
                      ? "收起文件"
                      : `查看全部 ${viewModel.files.length} 个文件`}
                    {showAllFiles ? (
                      <ChevronDownIcon
                        className="size-3.5"
                        aria-hidden="true"
                      />
                    ) : (
                      <ChevronRightIcon
                        className="size-3.5"
                        aria-hidden="true"
                      />
                    )}
                  </button>
                )}
              </div>
            </section>

            <section className="mt-8" aria-labelledby="dataset-check-heading">
              <h2
                id="dataset-check-heading"
                className="text-sm font-semibold text-[#2d2d29]"
              >
                自动检查
              </h2>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {viewModel.checks.map((check) => (
                  <CheckRow key={check.label} check={check} />
                ))}
              </div>
            </section>

            {viewModel.pendingConfirmation ? (
              <section
                className="mt-8"
                aria-labelledby="dataset-confirm-heading"
              >
                <h2
                  id="dataset-confirm-heading"
                  className="text-sm font-semibold text-[#2d2d29]"
                >
                  需要你确认
                </h2>
                <div className="mt-3 rounded-xl border border-[#ead9b2] bg-[#fffaf0] p-4 sm:p-5">
                  <div className="flex items-start gap-3">
                    <CircleAlertIcon
                      className="mt-0.5 size-4 shrink-0 text-[#a8751d]"
                      aria-hidden="true"
                    />
                    <div className="min-w-0">
                      <h3 className="text-sm font-semibold text-[#634916]">
                        {viewModel.pendingConfirmation.title}
                      </h3>
                      <p className="mt-2 text-sm leading-6 text-[#775b25]">
                        {viewModel.pendingConfirmation.description}
                      </p>
                      <div className="mt-3 inline-flex max-w-full items-center rounded-lg border border-[#e7d6ae] bg-white/70 px-3 py-2 font-mono text-xs text-[#66512a]">
                        <span className="truncate">
                          {viewModel.pendingConfirmation.tableName}.
                          {viewModel.pendingConfirmation.columnName}
                        </span>
                        <span className="mx-2 text-[#bcae8d]">→</span>
                        <span className="truncate font-sans">
                          {viewModel.pendingConfirmation.semanticLabel}
                        </span>
                      </div>
                      <p className="mt-3 text-xs text-[#927744]">
                        确认只影响当前工作区的数据语义，不会修改原始文件。
                      </p>
                      {!actorConfigured && (
                        <p className="mt-2 text-xs font-medium text-[#9a5f17]">
                          当前未配置操作人，暂不能提交确认。
                        </p>
                      )}
                      <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:items-center">
                        <button
                          type="button"
                          className="min-h-11 rounded-lg border border-[#e0cfaa] px-3 text-sm font-medium text-[#795d27] hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-2"
                          onClick={onDefer}
                        >
                          暂不确认
                        </button>
                        <button
                          type="button"
                          disabled={!actorConfigured || isConfirming}
                          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[#2f5435] px-4 text-sm font-medium text-white hover:bg-[#26452b] focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-45"
                          onClick={onConfirm}
                        >
                          {isConfirming && (
                            <LoaderCircleIcon
                              className="size-4 animate-spin"
                              aria-hidden="true"
                            />
                          )}
                          确认字段含义
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            ) : (
              <section className="mt-8 rounded-xl border border-[#dce8dc] bg-[#f5faf5] p-4 text-sm text-[#315338]">
                <div className="flex items-center gap-2 font-medium">
                  <CheckCircle2Icon className="size-4" aria-hidden="true" />
                  字段语义已确认
                </div>
                <p className="mt-1.5 text-xs leading-5 text-[#55735a]">
                  当前批次没有待人工确认的字段，下一步可以检查数据能力。
                </p>
              </section>
            )}

            <section className="mt-8" aria-labelledby="dataset-range-heading">
              <h2
                id="dataset-range-heading"
                className="text-sm font-semibold text-[#2d2d29]"
              >
                当前可识别范围
              </h2>
              <div className="mt-3 rounded-xl border border-black/[0.08] bg-[#fafaf8] p-4 text-sm leading-7 text-[#5f5f58]">
                <p>
                  <span className="font-medium text-[#3f6544]">已识别：</span>
                  {viewModel.recognizedLabels.length > 0
                    ? viewModel.recognizedLabels.join("、")
                    : "当前没有可确认的经营语义"}
                </p>
                <p>
                  <span className="font-medium text-[#7c6a45]">未观察：</span>
                  {viewModel.notObservedLabels.join("、")}
                </p>
                <p className="mt-2 text-xs leading-5 text-[#85857e]">
                  未观察字段不会被推断为零，也不会生成对应经营结论。
                </p>
              </div>
            </section>

            <div className="mt-9 flex flex-col-reverse gap-3 border-t border-black/[0.07] pt-5 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="button"
                className="inline-flex min-h-11 items-center justify-center rounded-lg border border-black/[0.1] px-4 text-sm font-medium text-[#5e5e58] hover:bg-black/[0.03] focus-visible:outline-2 focus-visible:outline-offset-2"
                onClick={() => inputRef.current?.click()}
              >
                返回添加文件
              </button>
              <button
                type="button"
                className="inline-flex min-h-11 items-center justify-center rounded-lg bg-[#252522] px-4 text-sm font-medium text-white hover:bg-black focus-visible:outline-2 focus-visible:outline-offset-2"
                onClick={onContinue}
              >
                继续检查数据能力
              </button>
            </div>
            <input
              ref={inputRef}
              className="hidden"
              type="file"
              multiple
              accept=".csv,.xlsx,.json,.zip"
              onChange={(event) => {
                onChooseFiles(Array.from(event.target.files ?? []));
                event.target.value = "";
              }}
            />
          </>
        )}

        {onOpenCases && (
          <button
            type="button"
            className="mt-8 text-xs font-medium text-[#707069] underline decoration-black/20 underline-offset-4 hover:text-[#252522]"
            onClick={onOpenCases}
          >
            返回案例队列
          </button>
        )}
      </div>
    </div>
  );
}

function CommerceDataInboxEmpty({
  isUploading,
  isDragging,
  inputRef,
  onDragEnter,
  onDragLeave,
  onDrop,
  onChoose,
  onInput,
  recentDatasets,
  onSelectDataset,
}: {
  isUploading: boolean;
  isDragging: boolean;
  inputRef: React.RefObject<HTMLInputElement | null>;
  onDragEnter: () => void;
  onDragLeave: () => void;
  onDrop: (event: React.DragEvent<HTMLDivElement>) => void;
  onChoose: () => void;
  onInput: (event: React.ChangeEvent<HTMLInputElement>) => void;
  recentDatasets: CommerceDataInboxSnapshot["datasets"];
  onSelectDataset: (datasetId: string) => void;
}) {
  return (
    <>
      <section className="mt-8" aria-labelledby="dataset-upload-heading">
        <h2
          id="dataset-upload-heading"
          className="text-sm font-semibold text-[#2d2d29]"
        >
          添加数据
        </h2>
        <div
          className={cn(
            "mt-3 rounded-2xl border border-dashed p-6 text-center transition-colors sm:p-8",
            isDragging
              ? "border-[#5c8061] bg-[#f3f8f3]"
              : "border-black/[0.16] bg-[#fafaf8] hover:border-black/[0.28]",
          )}
          onDragEnter={(event) => {
            event.preventDefault();
            onDragEnter();
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            if (event.currentTarget === event.target) onDragLeave();
          }}
          onDrop={onDrop}
        >
          <div className="mx-auto flex size-11 items-center justify-center rounded-xl border border-black/[0.08] bg-white text-[#5c5c55] shadow-sm">
            {isUploading ? (
              <LoaderCircleIcon
                className="size-5 animate-spin"
                aria-hidden="true"
              />
            ) : (
              <UploadCloudIcon className="size-5" aria-hidden="true" />
            )}
          </div>
          <p className="mt-4 text-sm font-medium text-[#353530]">
            {isUploading ? "正在安全接收文件" : "拖入文件或文件夹"}
          </p>
          <p className="mt-1.5 text-xs leading-5 text-[#85857e]">
            支持 CSV、XLSX、JSON 和 ZIP；单批次最多 20 个文件
          </p>
          <button
            type="button"
            disabled={isUploading}
            className="mt-5 inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[#252522] px-4 text-sm font-medium text-white hover:bg-black focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-wait disabled:opacity-60"
            onClick={onChoose}
          >
            <FolderOpenIcon className="size-4" aria-hidden="true" />
            选择文件
          </button>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[11px] text-[#8b8b83]">
            <span className="inline-flex items-center gap-1">
              <ShieldCheckIcon className="size-3.5" aria-hidden="true" />
              只读存储
            </span>
            <span className="inline-flex items-center gap-1">
              <HashIcon className="size-3.5" aria-hidden="true" />
              计算文件哈希
            </span>
            <span className="inline-flex items-center gap-1">
              <FileUpIcon className="size-3.5" aria-hidden="true" />
              保留来源记录
            </span>
          </div>
          <input
            ref={inputRef}
            className="hidden"
            type="file"
            multiple
            accept=".csv,.xlsx,.json,.zip"
            onChange={onInput}
          />
        </div>
      </section>

      <section className="mt-8" aria-labelledby="dataset-checks-heading">
        <h2
          id="dataset-checks-heading"
          className="text-sm font-semibold text-[#2d2d29]"
        >
          系统会检查
        </h2>
        <div className="mt-3 divide-y divide-black/[0.06] rounded-xl border border-black/[0.08] bg-white">
          {[
            ["文件完整性", "检查格式、大小和重复文件"],
            ["表结构", "识别订单、商品、卖家、评价等数据表"],
            ["字段语义", "自动映射，歧义字段需要人工确认"],
            ["数据能力", "明确能分析、部分可分析和无法判断的范围"],
          ].map(([label, detail]) => (
            <div key={label} className="flex items-center gap-3 px-4 py-3">
              <DatabaseIcon
                className="size-4 shrink-0 text-[#77776e]"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-[#3b3b36]">{label}</p>
                <p className="mt-0.5 text-xs text-[#85857e]">{detail}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8" aria-labelledby="recent-datasets-heading">
        <h2
          id="recent-datasets-heading"
          className="text-sm font-semibold text-[#2d2d29]"
        >
          最近的数据批次
        </h2>
        {recentDatasets.length === 0 ? (
          <div className="mt-3 rounded-xl border border-black/[0.08] bg-[#fafaf8] px-4 py-4 text-sm text-[#77776f]">
            <p>还没有导入记录</p>
            <p className="mt-1 text-xs text-[#999991]">
              完成首次上传后，可在这里查看处理状态和来源。
            </p>
          </div>
        ) : (
          <div className="mt-3 divide-y divide-black/[0.06] rounded-xl border border-black/[0.08] bg-white">
            {recentDatasets.slice(0, 3).map((dataset) => (
              <button
                key={dataset.dataset_id}
                type="button"
                className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-black/[0.025] focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
                onClick={() => onSelectDataset(dataset.dataset_id)}
              >
                <FileCheck2Icon
                  className="size-4 text-[#4f7754]"
                  aria-hidden="true"
                />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-[#3b3b36]">
                    {dataset.files[0]?.original_name ?? "数据批次"}
                  </p>
                  <p className="mt-0.5 text-xs text-[#85857e]">
                    {dataset.checks.file_count} 个文件 ·{" "}
                    {dataset.checks.row_count.toLocaleString("zh-CN")} 行
                  </p>
                </div>
                <span className="text-xs font-medium text-[#4f7754]">
                  已验证
                </span>
              </button>
            ))}
          </div>
        )}
      </section>

      <div className="mt-9 flex flex-col items-end border-t border-black/[0.07] pt-5">
        <button
          type="button"
          disabled
          className="min-h-11 rounded-lg bg-[#252522] px-4 text-sm font-medium text-white opacity-35"
        >
          继续检查数据能力
        </button>
        <p className="mt-2 text-xs text-[#999991]">添加数据后可继续</p>
      </div>
    </>
  );
}

function CheckRow({
  check,
}: {
  check: CommerceDataInboxViewModel["checks"][number];
}) {
  const verified = check.state === "verified";
  const review = check.state === "review";
  return (
    <div className="flex items-center gap-3 rounded-xl border border-black/[0.08] bg-white px-4 py-3">
      {verified ? (
        <CheckCircle2Icon
          className="size-4 shrink-0 text-[#4f7754]"
          aria-hidden="true"
        />
      ) : review ? (
        <CircleAlertIcon
          className="size-4 shrink-0 text-[#a8751d]"
          aria-hidden="true"
        />
      ) : (
        <CircleAlertIcon
          className="size-4 shrink-0 text-[#85857e]"
          aria-hidden="true"
        />
      )}
      <span className="min-w-0 flex-1 text-sm text-[#45453f]">
        {check.label}
      </span>
      <span
        className={cn(
          "text-xs font-medium",
          verified && "text-[#4f7754]",
          review && "text-[#a8751d]",
          !verified && !review && "text-[#85857e]",
        )}
      >
        {check.detail}
      </span>
    </div>
  );
}

function projectInboxError(
  cause: unknown,
  fallbackTitle = "数据批次暂时无法读取",
): InboxError {
  if (cause instanceof CommerceApiError) {
    if (cause.status === 409) {
      return {
        title: "数据批次需要重新检查",
        description:
          "存储中的来源或清单校验未通过，系统没有继续推断。请修复来源后重试。",
      };
    }
    if (cause.status === 404) {
      return {
        title: "数据批次不存在",
        description: "当前工作区找不到这个批次，可能已经被移除或尚未完成接收。",
      };
    }
  }
  return {
    title: fallbackTitle,
    description: "系统没有把不完整的数据当作可分析结果。请检查服务连接后重试。",
  };
}
