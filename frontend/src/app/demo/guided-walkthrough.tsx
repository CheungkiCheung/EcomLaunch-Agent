"use client";

import { Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

import { demoSharedCopy, type DemoLanguage } from "./demo-locales";

const STEP_DURATION_MS = 15_000;

function scrollToStep(index: number, steps: ReadonlyArray<{ id: string }>) {
  const step = steps[index];
  if (!step) {
    return;
  }
  document.getElementById(step.id)?.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

export function GuidedWalkthrough({
  scenario,
  language,
}: {
  scenario: string;
  language: DemoLanguage;
}) {
  const [activeStep, setActiveStep] = useState(-1);
  const [running, setRunning] = useState(false);
  const copy = demoSharedCopy[language].walkthrough;
  const steps = copy.steps;

  const selectStep = useCallback(
    (index: number) => {
      setActiveStep(index);
      requestAnimationFrame(() => scrollToStep(index, steps));
    },
    [steps],
  );

  useEffect(() => {
    if (!running || activeStep < 0) {
      return;
    }

    const timer = window.setTimeout(() => {
      if (activeStep >= steps.length - 1) {
        setRunning(false);
        return;
      }
      selectStep(activeStep + 1);
    }, STEP_DURATION_MS);

    return () => window.clearTimeout(timer);
  }, [activeStep, running, selectStep, steps.length]);

  useEffect(() => {
    setActiveStep(-1);
    setRunning(false);
  }, [language, scenario]);

  const active = activeStep >= 0 ? steps[activeStep] : null;
  const progress = activeStep < 0 ? 0 : ((activeStep + 1) / steps.length) * 100;

  const start = () => {
    if (activeStep >= 0 && activeStep < steps.length - 1) {
      setRunning(true);
      scrollToStep(activeStep, steps);
      return;
    }
    selectStep(0);
    setRunning(true);
  };

  const restart = () => {
    selectStep(0);
    setRunning(true);
  };

  return (
    <section
      className="sticky top-16 z-20 border-b border-stone-900/10 bg-stone-950 text-white shadow-xl"
      data-active-step={activeStep}
      data-testid="guided-walkthrough"
    >
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-3 lg:flex-row lg:items-center lg:px-8">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div className="hidden size-9 shrink-0 place-items-center rounded-xl bg-amber-300 text-stone-950 sm:grid">
            <Play className="size-4 fill-current" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-black tracking-[0.18em] text-amber-300 uppercase">
              {copy.title}
            </p>
            <p className="truncate text-sm text-stone-300" aria-live="polite">
              {active ? `${active.label}: ${active.description}` : copy.idle}
            </p>
          </div>
        </div>

        <div className="hidden items-center gap-1.5 xl:flex">
          {steps.map((step, index) => (
            <button
              key={step.id}
              type="button"
              onClick={() => {
                selectStep(index);
                setRunning(false);
              }}
              className={`rounded-full px-3 py-1.5 text-xs font-bold transition ${
                index === activeStep
                  ? "bg-amber-300 text-stone-950"
                  : "bg-white/8 text-stone-400 hover:bg-white/15 hover:text-white"
              }`}
            >
              {index + 1}. {step.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <div className="h-1.5 min-w-20 flex-1 overflow-hidden rounded-full bg-white/15 lg:w-24 lg:flex-none">
            <div
              className="h-full rounded-full bg-amber-300 transition-[width] duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          {running ? (
            <Button
              size="sm"
              variant="outline"
              className="border-white/20 bg-white/5 text-white hover:bg-white/15 hover:text-white"
              onClick={() => setRunning(false)}
            >
              <Pause />
              {copy.pause}
            </Button>
          ) : (
            <Button
              size="sm"
              className="bg-amber-300 text-stone-950 hover:bg-amber-200"
              onClick={start}
            >
              <Play className="fill-current" />
              {activeStep >= 0 && activeStep < steps.length - 1
                ? copy.resume
                : copy.start}
            </Button>
          )}
          {activeStep >= 0 ? (
            <Button
              size="icon-sm"
              variant="ghost"
              className="text-stone-400 hover:bg-white/10 hover:text-white"
              aria-label={copy.restart}
              onClick={restart}
            >
              <RotateCcw />
            </Button>
          ) : null}
        </div>
      </div>
    </section>
  );
}
