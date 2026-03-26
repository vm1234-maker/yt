"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Bot,
  Video,
  BarChart3,
  Zap,
  Settings,
  Radio,
} from "lucide-react";
import { getSupabaseBrowser } from "@/lib/supabase";
import type { AgentRun } from "@/lib/types";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/content", label: "Content", icon: Video },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

const AGENT_NAMES = [
  { id: "strategy",   label: "Strategy"   },
  { id: "research",   label: "Research"   },
  { id: "content",    label: "Content"    },
  { id: "production", label: "Production" },
  { id: "upload",     label: "Upload"     },
  { id: "analytics",  label: "Analytics"  },
];

type AgentStatus = "running" | "success" | "error" | "idle";

function statusToColor(status: AgentStatus): string {
  if (status === "running") return "green";
  if (status === "error") return "red";
  return "idle";
}

function StatusDot({ color }: { color: string }) {
  const classes: Record<string, string> = {
    green: "bg-emerald-400 status-dot-green",
    amber: "bg-amber-400 status-dot-amber",
    red: "bg-red-400 status-dot-red",
    idle: "bg-slate-600",
  };
  return (
    <span
      className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${classes[color] ?? classes.idle}`}
    />
  );
}

export default function Nav() {
  const pathname = usePathname();

  const [agentDots, setAgentDots] = useState<Record<string, AgentStatus>>({
    strategy: "idle", research: "idle", content: "idle",
    production: "idle", upload: "idle", analytics: "idle",
  });

  useEffect(() => {
    // Initial fetch — /api/agents returns AgentRun[]
    fetch("/api/agents")
      .then(r => r.json())
      .then((runs: AgentRun[]) => {
        // Derive latest status per agent_name
        const latest: Record<string, AgentRun> = {};
        for (const run of runs) {
          const existing = latest[run.agent_name];
          if (!existing || run.started_at > existing.started_at) {
            latest[run.agent_name] = run;
          }
        }
        const dots: Record<string, AgentStatus> = {
          strategy: "idle", research: "idle", content: "idle",
          production: "idle", upload: "idle", analytics: "idle",
        };
        for (const [name, run] of Object.entries(latest)) {
          dots[name] = run.status;
        }
        setAgentDots(dots);
      })
      .catch(() => {/* keep idle defaults on error */});

    // Realtime updates
    const sb = getSupabaseBrowser();
    if (!sb) return;
    const channel = sb
      .channel("nav_agent_dots")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "agent_runs" },
        (payload) => {
          const run = payload.new as AgentRun;
          if (!run?.agent_name) return;
          setAgentDots(prev => ({ ...prev, [run.agent_name]: run.status }));
        }
      )
      .subscribe();

    return () => { sb.removeChannel(channel); };
  }, []);

  return (
    <aside
      className="w-[200px] flex-shrink-0 flex flex-col"
      style={{
        background: "var(--bg-surface)",
        borderRight: "1px solid var(--border)",
      }}
    >
      {/* Logo */}
      <div
        className="px-4 py-5 flex items-center gap-2.5"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div
          className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0"
          style={{
            background: "var(--amber-glow)",
            border: "1px solid var(--border-accent)",
          }}
        >
          <Zap size={14} style={{ color: "var(--amber)" }} />
        </div>
        <div>
          <div
            className="text-sm font-bold tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            NemoClaw
          </div>
          <div className="mono text-[9px]" style={{ color: "var(--text-muted)", letterSpacing: "0.08em" }}>
            AUTOMATION
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 flex flex-col gap-0.5 overflow-y-auto">
        <p className="section-header px-2 mt-1 mb-2">Navigation</p>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item ${isActive ? "active" : ""}`}
            >
              <Icon size={14} className="flex-shrink-0" />
              {item.label}
            </Link>
          );
        })}

        {/* Agent status section */}
        <div className="divider" />
        <p className="section-header px-2">Live Agents</p>
        <div className="px-2 flex flex-col gap-2">
          {AGENT_NAMES.map((agent) => (
            <div key={agent.id} className="flex items-center justify-between">
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                {agent.label}
              </span>
              <StatusDot color={statusToColor(agentDots[agent.id] ?? "idle")} />
            </div>
          ))}
        </div>
      </nav>

      {/* Footer */}
      <div
        className="px-4 py-3"
        style={{ borderTop: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-1.5 mb-2">
          <Radio size={10} style={{ color: "var(--green)" }} />
          <span
            className="mono text-[9px] font-bold"
            style={{ color: "var(--green)", letterSpacing: "0.1em" }}
          >
            PHASE 4 — LIVE
          </span>
        </div>
        <Link
          href="/settings"
          className="nav-item text-xs"
          style={{ padding: "6px 8px", marginLeft: "-8px" }}
        >
          <Settings size={12} className="flex-shrink-0" />
          Settings
        </Link>
      </div>
    </aside>
  );
}
