"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTheme } from "next-themes";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { FlickeringGrid } from "@/components/ui/flickering-grid";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/core/auth/AuthProvider";
import { parseAuthError } from "@/core/auth/types";

type Lang = "zh" | "en";

const T: Record<Lang, Record<string, string>> = {
  zh: {
    title: "OpenSKU",
    loginSubtitle: "登录你的账号",
    registerSubtitle: "创建新账号",
    email: "邮箱",
    emailPlaceholder: "you@example.com",
    password: "密码",
    passwordPlaceholder: "•••••••",
    signIn: "登录",
    createAccount: "创建账号",
    pleaseWait: "请稍候...",
    switchToRegister: "没有账号？注册",
    switchToLogin: "已有账号？登录",
    backHome: "← 返回首页",
    networkError: "网络错误，请重试。",
  },
  en: {
    title: "OpenSKU",
    loginSubtitle: "Sign in to your account",
    registerSubtitle: "Create a new account",
    email: "Email",
    emailPlaceholder: "you@example.com",
    password: "Password",
    passwordPlaceholder: "•••••••",
    signIn: "Sign In",
    createAccount: "Create Account",
    pleaseWait: "Please wait...",
    switchToRegister: "Don't have an account? Sign up",
    switchToLogin: "Already have an account? Sign in",
    backHome: "← Back to home",
    networkError: "Network error. Please try again.",
  },
};

function validateNextParam(next: string | null): string | null {
  if (!next) return null;
  if (!next.startsWith("/")) return null;
  if (next.startsWith("//") || next.startsWith("http://") || next.startsWith("https://")) return null;
  if (next.includes(":") && !next.startsWith("/")) return null;
  return next;
}

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated } = useAuth();
  const { theme, resolvedTheme } = useTheme();

  const [lang, setLang] = useState<Lang>("zh");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLogin, setIsLogin] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const t = T[lang]!;
  const nextParam = searchParams.get("next");
  const redirectPath = validateNextParam(nextParam) ?? "/workspace";

  useEffect(() => {
    if (isAuthenticated) router.push(redirectPath);
  }, [isAuthenticated, redirectPath, router]);

  useEffect(() => {
    let cancelled = false;
    void fetch("/api/v1/auth/setup-status")
      .then((r) => r.json())
      .then((data: { needs_setup?: boolean }) => {
        if (!cancelled && data.needs_setup) router.push("/setup");
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [router]);

  const toggleLang = useCallback(() => {
    setLang((l) => (l === "zh" ? "en" : "zh"));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const endpoint = isLogin ? "/api/v1/auth/login/local" : "/api/v1/auth/register";
      const body = isLogin
        ? `username=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`
        : JSON.stringify({ email, password });
      const headers: HeadersInit = isLogin
        ? { "Content-Type": "application/x-www-form-urlencoded" }
        : { "Content-Type": "application/json" };
      const res = await fetch(endpoint, { method: "POST", headers, body, credentials: "include" });
      if (!res.ok) {
        const data = await res.json();
        const authError = parseAuthError(data);
        setError(authError.message ?? "Login failed");
        return;
      }
      router.push(redirectPath);
    } catch {
      setError(t.networkError ?? "Network error");
    } finally {
      setLoading(false);
    }
  };

  const actualTheme = theme === "system" ? resolvedTheme : theme;

  return (
    <div className="bg-background relative flex min-h-screen items-center justify-center overflow-x-hidden overflow-y-auto">
      <FlickeringGrid
        squareSize={4}
        gridGap={4}
        color={actualTheme === "dark" ? "white" : "black"}
        maxOpacity={0.3}
        flickerChance={0.25}
      />
      <div className="border-border/20 bg-background/5 relative z-10 w-full max-w-md space-y-5 rounded-3xl border p-8 backdrop-blur-sm">
        <div className="flex justify-end">
          <button
            type="button"
            onClick={toggleLang}
            className="text-muted-foreground hover:text-foreground text-xs transition-colors"
          >
            {lang === "zh" ? "English" : "中文"}
          </button>
        </div>
        <div className="text-center">
          <h1 className="text-foreground text-3xl font-semibold">{t.title}</h1>
          <p className="text-muted-foreground mt-2 text-sm">
            {isLogin ? t.loginSubtitle : t.registerSubtitle}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="email" className="text-sm font-medium">{t.email}</label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t.emailPlaceholder} required />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="password" className="text-sm font-medium">{t.password}</label>
            <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t.passwordPlaceholder} required minLength={isLogin ? 6 : 8} />
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? t.pleaseWait : isLogin ? t.signIn : t.createAccount}
          </Button>
        </form>

        <div className="text-center text-sm">
          <button type="button" onClick={() => { setIsLogin(!isLogin); setError(""); }} className="text-blue-500 hover:underline">
            {isLogin ? t.switchToRegister : t.switchToLogin}
          </button>
        </div>

        <div className="text-muted-foreground text-center text-xs">
          <Link href="/" className="hover:underline">{t.backHome}</Link>
        </div>
      </div>
    </div>
  );
}
