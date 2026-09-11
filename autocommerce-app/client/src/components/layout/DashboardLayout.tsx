import React from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useBranding } from '@/contexts/BrandingContext';
import { useLocation } from 'wouter';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Activity,
  BarChart3,
  Bot,
  CalendarDays,
  ChevronDown,
  ClipboardList,
  DollarSign,
  FileHeart,
  HeartHandshake,
  LayoutDashboard,
  LogOut,
  Mail,
  MessageSquare,
  Package,
  Settings,
  ShieldCheck,
  Users,
  WandSparkles,
} from 'lucide-react';

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  roles?: string[];
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Clinique',
    items: [
      { label: 'Dashboard', href: '/dashboard', icon: <LayoutDashboard className="h-4 w-4" /> },
      { label: 'Agenda', href: '/agenda', icon: <CalendarDays className="h-4 w-4" /> },
      { label: 'Patients', href: '/patients', icon: <Users className="h-4 w-4" /> },
      { label: 'Dossiers cliniques', href: '/dossiers', icon: <FileHeart className="h-4 w-4" />, roles: ['directrice', 'medecin', 'estheticienne', 'admin'] },
      { label: 'Suivi des soins', href: '/clinical-ops', icon: <Activity className="h-4 w-4" />, roles: ['directrice', 'medecin', 'estheticienne', 'assistante', 'admin'] },
    ],
  },
  {
    label: 'Gestion',
    items: [
      { label: 'Facturation', href: '/invoices', icon: <DollarSign className="h-4 w-4" /> },
      { label: 'Stocks', href: '/stock', icon: <Package className="h-4 w-4" /> },
      { label: 'Commissions', href: '/commissions', icon: <DollarSign className="h-4 w-4" />, roles: ['directrice', 'admin', 'commercial'] },
      { label: 'Délégués & labos', href: '/delegues', icon: <Users className="h-4 w-4" />, roles: ['directrice', 'medecin', 'admin'] },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { label: 'Copilote IA', href: '/dashboard-ia', icon: <WandSparkles className="h-4 w-4" /> },
      { label: 'Copilote relation', href: '/copilote-crm', icon: <Bot className="h-4 w-4" />, roles: ['directrice', 'medecin', 'admin'] },
      { label: 'Automatisations', href: '/workflows', icon: <ClipboardList className="h-4 w-4" />, roles: ['directrice', 'admin'] },
      { label: 'Rapports', href: '/analytics', icon: <BarChart3 className="h-4 w-4" />, roles: ['directrice', 'admin'] },
    ],
  },
  {
    label: 'Relation patient',
    items: [
      { label: 'Messagerie & social', href: '/social', icon: <MessageSquare className="h-4 w-4" />, roles: ['directrice', 'assistante', 'commercial', 'admin'] },
      { label: 'Fidélité', href: '/loyalty', icon: <HeartHandshake className="h-4 w-4" />, roles: ['directrice', 'assistante', 'admin'] },
      { label: 'Équipe', href: '/equipe', icon: <Mail className="h-4 w-4" /> },
    ],
  },
  {
    label: 'Administration',
    items: [
      { label: 'Équipe & accès', href: '/admin/equipe', icon: <Users className="h-4 w-4" />, roles: ['directrice', 'admin'] },
      { label: 'Tarification', href: '/settings/actes', icon: <DollarSign className="h-4 w-4" />, roles: ['directrice', 'admin'] },
      { label: 'Paramètres', href: '/settings', icon: <Settings className="h-4 w-4" />, roles: ['directrice', 'admin'] },
      { label: 'Sécurité MFA', href: '/settings/mfa', icon: <ShieldCheck className="h-4 w-4" />, roles: ['directrice', 'admin'] },
    ],
  },
];

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children }) => {
  const { user, logout } = useAuth();
  const { branding } = useBranding();
  const [location, setLocation] = useLocation();

  const isVisible = (item: NavItem) => !item.roles || Boolean(user && item.roles.includes(user.role));
  const isActive = (href: string) => location === href || (href !== '/dashboard' && location.startsWith(`${href}/`));

  return (
    <SidebarProvider>
      <div className="flex h-dvh w-full overflow-hidden bg-slate-50 text-slate-900">
        <Sidebar className="border-r-0 bg-[#071a3b] text-slate-100">
          <SidebarHeader className="border-b border-white/10 bg-[#071a3b] px-4 py-5">
            <button type="button" onClick={() => setLocation('/dashboard')} className="flex w-full items-center gap-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-300">
              <div className="grid h-9 w-9 shrink-0 place-items-center overflow-hidden rounded-xl bg-teal-400/15 text-teal-200 ring-1 ring-teal-300/20">
                {branding?.logo_url ? <img src={branding.logo_url} alt="" className="h-full w-full object-contain p-1" /> : <FileHeart className="h-5 w-5" />}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold tracking-tight text-white">{branding?.nom_clinique || 'Clinic Esthétique'}</p>
                <p className="truncate text-xs text-slate-300">Espace opérationnel</p>
              </div>
            </button>
          </SidebarHeader>

          <SidebarContent className="bg-[#071a3b] px-2 py-3">
            {NAV_GROUPS.map((group) => {
              const items = group.items.filter(isVisible);
              if (items.length === 0) return null;
              return (
                <section key={group.label} className="mb-4 last:mb-0">
                  <p className="px-3 pb-1.5 pt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{group.label}</p>
                  <SidebarMenu>
                    {items.map((item) => (
                      <SidebarMenuItem key={item.href}>
                        <SidebarMenuButton asChild isActive={isActive(item.href)}>
                          <button
                            type="button"
                            onClick={() => setLocation(item.href)}
                            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-300 ${
                              isActive(item.href) ? 'bg-white/12 font-medium text-white shadow-sm' : 'text-slate-300 hover:bg-white/8 hover:text-white'
                            }`}
                          >
                            <span className={isActive(item.href) ? 'text-teal-200' : 'text-slate-400'}>{item.icon}</span>
                            <span>{item.label}</span>
                          </button>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </section>
              );
            })}
          </SidebarContent>

          <SidebarFooter className="border-t border-white/10 bg-[#071a3b] p-3">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="h-auto w-full justify-between rounded-xl px-2 py-2 text-left text-slate-200 hover:bg-white/10 hover:text-white">
                  <span className="min-w-0">
                    <span className="block truncate text-xs font-medium">{user?.prenom} {user?.nom}</span>
                    <span className="block truncate text-[11px] text-slate-400">{user?.email}</span>
                  </span>
                  <ChevronDown className="h-4 w-4 shrink-0" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuItem onClick={logout}><LogOut className="mr-2 h-4 w-4" /> Déconnexion</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarFooter>
        </Sidebar>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <header className="flex min-h-16 shrink-0 items-center justify-between border-b border-slate-200/80 bg-white px-4 shadow-[0_1px_0_rgba(15,23,42,0.02)] sm:px-6">
            <div className="flex items-center gap-3">
              <SidebarTrigger className="text-slate-700 hover:bg-slate-100" />
              <div className="hidden border-l border-slate-200 pl-3 sm:block">
                <p className="text-xs font-medium text-slate-500">Connecté en tant que</p>
                <p className="text-sm font-semibold capitalize text-slate-800">{user?.role?.replace('_', ' ')}</p>
              </div>
            </div>
            <div className="flex items-center gap-2"><LanguageSwitcher /></div>
          </header>
          <main className="flex-1 overflow-auto"><div className="p-4 sm:p-6 lg:p-8">{children}</div></main>
        </div>
      </div>
    </SidebarProvider>
  );
};
