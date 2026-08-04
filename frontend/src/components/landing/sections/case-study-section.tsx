import Link from "next/link";

import { Card } from "@/components/ui/card";

import { Section } from "../section";

export function CaseStudySection({ className }: { className?: string }) {
  const caseStudies = [
    {
      title: "OpenSKU Launch Team",
      description:
        "Ask the OpenSKU Launch Team to research a product idea and generate a 7-day Launch Validation Pack with market analysis, pricing, and content assets.",
      href: "/workspace/agents/ecom-launch/chats/new",
    },
    {
      title: "Growth Analyst",
      description:
        "Upload CSV/XLSX data to find anomalies, cohort trends, and A/B test winners — all through natural language.",
      href: "/workspace/agents/data-inspector/chats/new",
    },
    {
      title: "OpenSKU Fast",
      description:
        "Quick single-agent research with web search and PM skills. Ask a market question and get structured analysis in under a minute.",
      href: "/workspace/agents/ecom-launch/chats/new",
    },
  ];
  return (
    <Section
      className={className}
      title="What You Can Do"
      subtitle="AI-powered ecommerce product research and validation"
    >
      <div className="container-md mt-8 grid grid-cols-1 gap-4 px-4 md:grid-cols-3 md:px-20">
        {caseStudies.map((cs) => (
          <Link key={cs.title} href={cs.href}>
            <Card className="group/card hover:border-primary/50 flex h-48 flex-col justify-end p-6 transition-colors">
              <h3 className="text-lg font-semibold">{cs.title}</h3>
              <p className="text-muted-foreground mt-2 text-sm">
                {cs.description}
              </p>
            </Card>
          </Link>
        ))}
      </div>
    </Section>
  );
}
