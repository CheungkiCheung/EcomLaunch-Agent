"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  buildCommerceRunTaskActivityViewModel,
  type CommerceRunTaskActivityViewModel,
} from "@/core/commerce/run-task-activity-view-model";
import {
  loadCommerceRunTaskActivityPage,
  shouldContinueCommerceTaskPolling,
  type CommerceParentRunStatus,
  type CommerceRunTaskActivity,
} from "@/core/commerce/subagent-task-api";

export interface CommerceRunTaskActivityState {
  activities: CommerceRunTaskActivity[];
  viewModel: CommerceRunTaskActivityViewModel;
  isLoading: boolean;
  isRefreshing: boolean;
  error: Error | null;
  refresh: () => void;
}

export function useCommerceRunTaskActivity({
  runId,
  runStatus,
  enabled = true,
  pollIntervalMs = 1_500,
}: {
  runId: string | null | undefined;
  runStatus?: CommerceParentRunStatus | null;
  enabled?: boolean;
  pollIntervalMs?: number;
}): CommerceRunTaskActivityState {
  const normalizedRunId = runId?.trim() ?? null;
  const [activities, setActivities] = useState<CommerceRunTaskActivity[]>([]);
  const [isLoading, setIsLoading] = useState(
    Boolean(normalizedRunId && enabled),
  );
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const activitiesRef = useRef<CommerceRunTaskActivity[]>([]);
  const activeRunIdRef = useRef<string | null>(null);

  const refresh = useCallback(() => {
    setRefreshVersion((value) => value + 1);
  }, []);

  useEffect(() => {
    if (!enabled || !normalizedRunId) {
      activeRunIdRef.current = null;
      activitiesRef.current = [];
      setActivities([]);
      setIsLoading(false);
      setIsRefreshing(false);
      setError(null);
      return;
    }

    if (activeRunIdRef.current !== normalizedRunId) {
      activeRunIdRef.current = normalizedRunId;
      activitiesRef.current = [];
      setActivities([]);
      setIsLoading(true);
      setError(null);
    } else if (activitiesRef.current.length > 0) {
      setIsRefreshing(true);
    }

    const controller = new AbortController();
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const interval = Math.max(250, pollIntervalMs);

    const poll = async () => {
      let continuePolling = true;
      try {
        const next = await loadCommerceRunTaskActivityPage({
          runId: normalizedRunId,
          previous: activitiesRef.current,
          signal: controller.signal,
        });
        if (disposed) return;
        activitiesRef.current = next;
        setActivities(next);
        setError(null);
        continuePolling = shouldContinueCommerceTaskPolling({
          runStatus,
          activities: next,
        });
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError") {
          return;
        }
        if (!disposed) {
          setError(
            caught instanceof Error
              ? caught
              : new Error("协作任务状态加载失败"),
          );
        }
      } finally {
        if (!disposed) {
          setIsLoading(false);
          setIsRefreshing(false);
          if (continuePolling) {
            timer = setTimeout(() => void poll(), interval);
          }
        }
      }
    };

    void poll();
    return () => {
      disposed = true;
      controller.abort();
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [enabled, normalizedRunId, pollIntervalMs, refreshVersion, runStatus]);

  const viewModel = useMemo(
    () => buildCommerceRunTaskActivityViewModel(activities),
    [activities],
  );

  return {
    activities,
    viewModel,
    isLoading,
    isRefreshing,
    error,
    refresh,
  };
}
