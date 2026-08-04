"use client";

import { RadioTowerIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";

export function WarRoomNavItem() {
  const { t } = useI18n();
  const pathname = usePathname();
  return (
    <SidebarGroup className="pt-1 pb-0">
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            size="lg"
            tooltip={t.sidebar.warRoom}
            isActive={pathname.startsWith("/workspace/war-room")}
            className="border border-orange-200/70 bg-gradient-to-r from-orange-50 to-rose-50 text-orange-800 shadow-sm hover:from-orange-100 hover:to-rose-100 data-[active=true]:border-orange-300 data-[active=true]:bg-orange-100"
            asChild
          >
            <Link href="/workspace/war-room">
              <RadioTowerIcon />
              <span className="font-medium">{t.sidebar.warRoom}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroup>
  );
}
