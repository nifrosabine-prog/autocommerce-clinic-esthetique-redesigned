import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useBranding } from '@/contexts/BrandingContext';
import { useLocation } from 'wouter';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { useTranslation } from 'react-i18next';
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarFooter,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarTrigger,
  SidebarProvider,
} from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Calendar,
  Users,
  FileText,
  Pill,
  DollarSign,
  Heart,
  Briefcase,
  MessageSquare,
  Settings,
  LogOut,
  ChevronDown,
  Menu,
  Zap,
  Activity,
  Headphones,
  BarChart,
  Mail,
  Home,
  Clock,
} from 'lucide-react';

interface NavItem {
  labelKey: string;
  href: string;
  icon: React.ReactNode;
  roles?: string[];
  children?: NavItem[];
}

const NAV_ITEMS: NavItem[] = [
  {
    labelKey: 'nav.dashboard',
    href: '/dashboard',
    icon: <Menu className="w-4 h-4" />,
  },
  {
    labelKey: 'nav.dashboard_ia',
    href: '/dashboard-ia',
    icon: <Zap className="w-4 h-4" />,
  },
  {
    labelKey: 'nav.workspace',
    href: '/workspace',
    icon: <Briefcase className="w-4 h-4" />,
    roles: ['directrice', 'medecin', 'estheticienne', 'assistante', 'prestataire', 'admin'],
  },
  {
    labelKey: 'nav.workflows',
    href: '/workflows',
    icon: <Activity className="w-4 h-4" />,
    roles: ['directrice', 'admin'],
  },
  {
    labelKey: 'nav.copilote_crm',
    href: '/copilote-crm',
    icon: <Headphones className="w-4 h-4" />,
    roles: ['directrice', 'medecin', 'admin'],
  },
  {
    labelKey: 'nav.analytics',
    href: '/analytics',
    icon: <BarChart className="w-4 h-4" />,
    roles: ['directrice', 'admin'],
  },
  {
    labelKey: 'nav.agenda',
    href: '/agenda',
    icon: <Calendar className="w-4 h-4" />,
  },
  {
    labelKey: 'nav.clinical_ops',
    href: '/clinical-ops',
    icon: <Activity className="w-4 h-4" />,
    roles: ['directrice', 'medecin', 'estheticienne', 'assistante', 'admin'],
  },
  {
    labelKey: 'nav.patients',
    href: '/patients',
    icon: <Users className="w-4 h-4" />,
  },
  {
    labelKey: 'nav.medical_file',
    href: '/medical-record',
    icon: <FileText className="w-4 h-4" />,
    roles: ['directrice', 'medecin', 'estheticienne', 'admin'],
  },
  {
    labelKey: 'nav.stock',
    href: '/stock',
    icon: <Pill className="w-4 h-4" />,
    roles: ['directrice', 'assistante', 'admin'],
  },
  {
    labelKey: 'nav.delegates',
    href: '/delegues',
    icon: <Users className="w-4 h-4" />,
    roles: ['directrice', 'medecin', 'admin'],
  },
  {
    labelKey: 'nav.invoices',
    href: '/invoices',
    icon: <DollarSign className="w-4 h-4" />,
    roles: ['directrice', 'medecin', 'estheticienne', 'assistante', 'admin'],
  },
  {
    labelKey: 'nav.commissions',
    href: '/commissions',
    icon: <DollarSign className="w-4 h-4" />,
    roles: ['directrice', 'admin', 'commercial'],
  },
  {
    labelKey: 'nav.loyalty',
    href: '/loyalty',
    icon: <Heart className="w-4 h-4" />,
  },
  {
    labelKey: 'nav.recruitment',
    href: '/recruitment',
    icon: <Briefcase className="w-4 h-4" />,
    roles: ['directrice', 'assistante', 'admin'],
  },
  {
    labelKey: 'nav.social',
    href: '/social',
    icon: <MessageSquare className="w-4 h-4" />,
  },
  {
    labelKey: 'nav.team',
    href: '/equipe',
    icon: <Mail className="w-4 h-4" />,
  },
  {
    labelKey: 'nav.team_management',
    href: '/admin/equipe',
    icon: <Users className="w-4 h-4" />,
    roles: ['directrice', 'admin'],
  },
  {
    labelKey: 'nav.rooms',
    href: '/admin/salles',
    icon: <Home className="w-4 h-4" />,
    roles: ['directrice', 'admin'],
  },
  {
    labelKey: 'nav.hr_reporting',
    href: '/admin/rh',
    icon: <Clock className="w-4 h-4" />,
    roles: ['directrice', 'admin'],
  },
  {
    labelKey: 'nav.medical_acts',
    href: '/settings/actes',
    icon: <DollarSign className="w-4 h-4" />,
    roles: ['directrice', 'admin'],
  },
  {
    labelKey: 'nav.settings',
    href: '/settings',
    icon: <Settings className="w-4 h-4" />,
    roles: ['directrice', 'admin'],
  },
];

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children }) => {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const { branding } = useBranding();
  const [location, setLocation] = useLocation();
  const [open, setOpen] = useState(false);

  // Filter nav items based on user role
  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || (user && item.roles.includes(user.role))
  );

  const isActive = (href: string) => location === href;

  return (
    <SidebarProvider>
    <div className="flex h-screen bg-background">
      <Sidebar className="clinic-sidebar">
        <SidebarHeader className="border-b border-white/10 bg-[#071a3b] px-4 py-4 text-white">
          <div className="flex items-center gap-3">
            {branding?.logo_url && (
              <img
                src={branding.logo_url}
                alt="Logo"
                className="h-8 w-8 object-contain"
              />
            )}
            <div className="flex-1 min-w-0">
              <h1 className="text-sm font-bold truncate">
                {branding?.nom_clinique || 'Clinique'}
              </h1>
              <p className="text-xs text-muted-foreground truncate">
                {user?.prenom} {user?.nom}
              </p>
            </div>
          </div>
        </SidebarHeader>

        <SidebarContent className="bg-[#071a3b] text-white">
          <SidebarMenu>
            {visibleItems.map((item) => (
              <SidebarMenuItem key={item.href}>
                <SidebarMenuButton
                  asChild
                  isActive={isActive(item.href)}
                  onClick={() => setLocation(item.href)}
                >
                  <div className="flex items-center gap-2 cursor-pointer">
                    {item.icon}
                    <span>{t(item.labelKey)}</span>
                  </div>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarContent>

        <SidebarFooter className="border-t border-white/10 bg-[#071a3b] p-4 text-white">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="w-full justify-between">
                <span className="text-xs text-muted-foreground truncate">
                  {user?.email}
                </span>
                <ChevronDown className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={logout}>
                <LogOut className="w-4 h-4 mr-2" />
                {t('common.logout')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarFooter>
      </Sidebar>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="border-b border-slate-200/80 bg-white/90 px-6 py-4 flex items-center justify-between backdrop-blur-sm">
          <SidebarTrigger />
          <div className="flex items-center gap-4">
            <LanguageSwitcher />
            <div className="text-sm text-muted-foreground">
              {t('common.role')}: <span className="font-semibold text-foreground">{t(`roles.${user?.role || 'unknown'}`)}</span>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-auto">
          <div className="p-6">
            {children}
          </div>
        </main>
      </div>
    </div>
    </SidebarProvider>
  );
};
