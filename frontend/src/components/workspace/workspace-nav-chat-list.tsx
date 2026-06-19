"use client";

import {
  BotIcon,
  Gamepad2Icon,
  MessageSquareIcon,
  MessagesSquare,
  ShoppingBagIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";

export function WorkspaceNavChatList() {
  const { t } = useI18n();
  const pathname = usePathname();
  const ecomLaunchActive = pathname.startsWith("/workspace/agents/ecom-launch");
  return (
    <SidebarGroup className="pt-1">
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton isActive={pathname === "/workspace/chats"} asChild>
            <Link className="text-muted-foreground" href="/workspace/chats">
              <MessagesSquare />
              <span>{t.sidebar.chats}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton isActive={ecomLaunchActive} asChild>
            <Link
              className="text-muted-foreground"
              href="/workspace/agents/ecom-launch/chats/new"
            >
              <ShoppingBagIcon />
              <span>{t.sidebar.ecomLaunch}</span>
            </Link>
          </SidebarMenuButton>
          <SidebarMenuSub>
            <SidebarMenuSubItem>
              <SidebarMenuSubButton
                isActive={pathname.startsWith(
                  "/workspace/agents/ecom-launch/chats",
                )}
                asChild
              >
                <Link
                  className="text-muted-foreground"
                  href="/workspace/agents/ecom-launch/chats/new"
                >
                  <MessageSquareIcon />
                  <span>{t.sidebar.ecomLaunchChat}</span>
                </Link>
              </SidebarMenuSubButton>
            </SidebarMenuSubItem>
            <SidebarMenuSubItem>
              <SidebarMenuSubButton
                isActive={pathname === "/workspace/agents/ecom-launch/war-room"}
                asChild
              >
                <Link
                  className="text-muted-foreground"
                  href="/workspace/agents/ecom-launch/war-room"
                >
                  <Gamepad2Icon />
                  <span>{t.sidebar.ecomLaunchWarRoom}</span>
                </Link>
              </SidebarMenuSubButton>
            </SidebarMenuSubItem>
          </SidebarMenuSub>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={
              pathname.startsWith("/workspace/agents") && !ecomLaunchActive
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
  );
}
