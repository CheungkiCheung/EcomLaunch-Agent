"use client";

import {
  ChevronRightIcon,
  RocketIcon,
  SearchIcon,
  ShieldCheckIcon,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import Galaxy from "@/components/ui/galaxy";
import { cn } from "@/lib/utils";

export function Hero({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex size-full flex-col items-center justify-center",
        className,
      )}
    >
      <div className="absolute inset-0 z-0 bg-black/40">
        <Galaxy
          mouseRepulsion={false}
          starSpeed={0.2}
          density={0.6}
          glowIntensity={0.35}
          twinkleIntensity={0.3}
          speed={0.5}
        />
      </div>
      <div className="container-md relative z-10 mx-auto flex h-screen flex-col items-center justify-center">
        <div className="flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-4 py-1.5 text-sm text-white/70 backdrop-blur">
          <RocketIcon className="size-4 text-amber-300" />
          AI Agent 驱动的电商新品验证与增长决策
        </div>
        <h1 className="mt-6 flex items-center gap-2 text-4xl font-bold text-white md:text-6xl">
          <div>从产品想法到</div>
        </h1>
        <h1 className="flex items-center gap-2 text-4xl font-bold md:text-6xl">
          <span className="bg-gradient-to-r from-amber-300 via-orange-400 to-rose-400 bg-clip-text text-transparent">
            数据支撑的上市决策
          </span>
        </h1>
        <p className="text-muted-foreground mt-8 max-w-2xl text-center text-lg text-white/70">
          OpenSKU 基于 LangGraph 多智能体编排，用公开信号做市场研究、
          方案设计与内容生成。闪速模式 30 秒给结论，Ultra 模式生成 七件套 Launch
          Validation Pack，每条结论附证据来源。
        </p>
        <div className="mt-8 flex items-center gap-3">
          <Link href="/workspace/agents/ecom-launch/chats/new">
            <Button
              size="lg"
              className="bg-gradient-to-r from-amber-400 to-orange-500 text-white shadow-lg shadow-orange-500/25 hover:from-amber-500 hover:to-orange-600"
            >
              <span>开始验证你的产品</span>
              <ChevronRightIcon className="size-4" />
            </Button>
          </Link>
          <Link href="/workspace">
            <Button
              size="lg"
              variant="outline"
              className="border-white/25 bg-transparent text-white hover:bg-white/10"
            >
              进入工作区
            </Button>
          </Link>
          <Link href="/demo?lang=zh">
            <Button
              size="lg"
              variant="outline"
              className="border-amber-300/40 bg-amber-300/10 text-amber-100 hover:bg-amber-300/20 hover:text-white"
            >
              查看中英文 Demo
            </Button>
          </Link>
        </div>
        <div className="mt-10 flex items-center gap-6 text-xs text-white/50">
          <span className="flex items-center gap-1.5">
            <SearchIcon className="size-3.5 text-amber-300" />
            公开信号研究
          </span>
          <span className="flex items-center gap-1.5">
            <RocketIcon className="size-3.5 text-amber-300" />
            三专家流水线
          </span>
          <span className="flex items-center gap-1.5">
            <ShieldCheckIcon className="size-3.5 text-amber-300" />
            证据治理
          </span>
        </div>
      </div>
    </div>
  );
}
