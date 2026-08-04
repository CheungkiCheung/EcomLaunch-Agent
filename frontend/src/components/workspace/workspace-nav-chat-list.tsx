"use client";

import {
  BotIcon,
  DatabaseIcon,
  MessagesSquare,
  ShoppingBagIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";

export function WorkspaceNavChatList() {
  const { t } = useI18n();
  const pathname = usePathname();
  const ecomLaunchActive = pathname.startsWith("/workspace/agents/ecom-launch");
  const dataInspectorActive = pathname.startsWith(
    "/workspace/agents/data-inspector",
  );
  return (
    <>
      <SidebarGroup className="pt-1 pb-1">
        <SidebarGroupLabel>{t.sidebar.primaryAgents}</SidebarGroupLabel>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              tooltip={t.sidebar.ecomLaunch}
              isActive={ecomLaunchActive}
              asChild
            >
              <Link
                className="text-muted-foreground"
                href="/workspace/agents/ecom-launch/chats/new"
              >
                <ShoppingBagIcon />
                <span>{t.sidebar.ecomLaunch}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              tooltip={t.sidebar.dataInspector}
              isActive={dataInspectorActive}
              asChild
            >
              <Link
                className="text-muted-foreground"
                href="/workspace/agents/data-inspector/chats/new"
              >
                <DatabaseIcon />
                <span>{t.sidebar.dataInspector}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroup>
      <SidebarGroup className="pt-0">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip={t.sidebar.chats}
              isActive={pathname === "/workspace/chats"}
              asChild
            >
              <Link className="text-muted-foreground" href="/workspace/chats">
                <MessagesSquare />
                <span>{t.sidebar.chats}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip={t.sidebar.agents}
              isActive={
                pathname.startsWith("/workspace/agents") &&
                !ecomLaunchActive &&
                !dataInspectorActive
              }
              asChild
            >
              <Link className="text-muted-foreground" href="/workspace/agents">
                <BotIcon />
                <span>{t.sidebar.agents}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroup>
    </>
  );
}
