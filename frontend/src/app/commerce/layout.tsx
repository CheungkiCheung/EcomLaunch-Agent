import { type Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { AuthProvider } from "@/core/auth/AuthProvider";
import { getServerSideUser } from "@/core/auth/server";
import { assertNever } from "@/core/auth/types";
import { featureFlags } from "@/core/config/feature-flags";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "电商经营诊断",
  description: "面向电商运营的可追溯异常诊断、行动与跟进工作区。",
};

export default async function CommerceLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  if (!featureFlags.commerceCaseAgent) notFound();

  const result = await getServerSideUser();
  switch (result.tag) {
    case "authenticated":
      return <AuthProvider initialUser={result.user}>{children}</AuthProvider>;
    case "needs_setup":
    case "system_setup_required":
      redirect("/setup");
    case "unauthenticated":
      redirect("/login?next=%2Fcommerce");
    case "gateway_unavailable":
      return <CommerceGatewayUnavailable />;
    case "config_error":
      throw new Error(result.message);
    default:
      assertNever(result);
  }
}

function CommerceGatewayUnavailable() {
  return (
    <div className="flex h-dvh items-center justify-center bg-[#f7f7f5] px-6 text-[#20201e]">
      <div className="max-w-md rounded-2xl border border-black/[0.08] bg-white p-7 text-center shadow-sm">
        <h1 className="text-lg font-semibold">服务暂时不可用</h1>
        <p className="mt-2 text-sm leading-6 text-[#6f6f69]">
          登录网关可能正在重启。请稍后重试，页面不会在身份不可确认时读取经营案例。
        </p>
        <div className="mt-5 flex justify-center gap-3">
          <Link
            href="/commerce"
            className="rounded-lg bg-[#252522] px-4 py-2 text-sm font-medium text-white hover:bg-black"
          >
            重新加载
          </Link>
          <form action="/api/v1/auth/logout" method="post">
            <button
              type="submit"
              className="rounded-lg border border-black/[0.1] px-4 py-2 text-sm text-[#5f5f59] hover:bg-black/[0.03]"
            >
              退出登录
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
