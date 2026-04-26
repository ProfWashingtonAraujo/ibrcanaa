import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Users, HeartHandshake, Wallet, Calendar, Settings, LogOut, Home, Compass, Award, User } from 'lucide-react';
import Logo from '../common/Logo';
import { cn } from '../ui/Button';

export default function Sidebar({ isAdmin = true, isMobileOpen, onClose }) {
  const adminLinks = [
    { to: '/admin', icon: LayoutDashboard, label: 'Dashboard', end: true },
    { to: '/admin/membros', icon: Users, label: 'Membros' },
    { to: '/admin/ministerios', icon: HeartHandshake, label: 'Ministérios' },
    { to: '/admin/financeiro', icon: Wallet, label: 'Financeiro' },
    { to: '/admin/eventos', icon: Calendar, label: 'Eventos' },
    { to: '/admin/configuracoes', icon: Settings, label: 'Configurações' },
  ];

  const memberLinks = [
    { to: '/membro', icon: Home, label: 'Início', end: true },
    { to: '/membro/jornada', icon: Compass, label: 'Jornada de Fé' },
    { to: '/membro/contribuicoes', icon: Wallet, label: 'Contribuições' },
    { to: '/membro/perfil', icon: User, label: 'Meu Perfil' },
  ];

  const links = isAdmin ? adminLinks : memberLinks;

  return (
    <>
      {/* Mobile overlay */}
      {isMobileOpen && (
        <div 
          className="fixed inset-0 z-40 bg-slate-900/50 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside className={cn(
        "fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-slate-200 flex flex-col transition-transform duration-300 lg:translate-x-0 lg:static",
        isMobileOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="h-16 flex items-center px-6 border-b border-slate-100">
          <Logo />
        </div>

        <div className="flex-1 overflow-y-auto py-6 px-4">
          <nav className="space-y-1">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                onClick={onClose}
                className={({ isActive }) => cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-xl font-medium transition-colors",
                  isActive 
                    ? "bg-blue-50 text-blue-900" 
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                )}
              >
                <link.icon className="w-5 h-5" />
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="p-4 border-t border-slate-100">
          <div className="bg-slate-50 p-4 rounded-xl mb-4">
            <h4 className="text-sm font-semibold text-slate-900">Modo Demonstrativo</h4>
            <p className="text-xs text-slate-500 mt-1">Lumen Ecclesia - v1.0.0</p>
          </div>
          <NavLink
            to="/login"
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl font-medium text-red-600 hover:bg-red-50 transition-colors"
          >
            <LogOut className="w-5 h-5" />
            Sair
          </NavLink>
        </div>
      </aside>
    </>
  );
}
