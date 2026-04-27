import { Users, UserPlus, Calendar, Wallet } from 'lucide-react';
import PageHeader from '../../components/common/PageHeader';
import StatCard from '../../components/common/StatCard';
import { events } from '../../mocks/events';
import { members } from '../../mocks/members';

export default function AdminDashboard() {
  const recentEvents = events.slice(0, 3);
  const recentMembers = members.slice(-3).reverse();

  return (
    <div>
      <PageHeader 
        title="Dashboard" 
        description="Bem-vindo ao painel administrativo da Igreja Batista Regular Canaã."
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard title="Total de Membros" value="2.450" icon={Users} trend={{ isPositive: true, value: 5.2 }} />
        <StatCard title="Novos (Este mês)" value="45" icon={UserPlus} trend={{ isPositive: true, value: 12.5 }} />
        <StatCard title="Eventos Ativos" value="12" icon={Calendar} />
        <StatCard title="Saldo em Caixa" value="R$ 15.450,00" icon={Wallet} trend={{ isPositive: false, value: 2.1 }} />
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
          <h3 className="text-lg font-bold text-slate-900 mb-6">Crescimento e Frequência</h3>
          <div className="h-64 flex items-end justify-between gap-2">
            {[40, 65, 45, 80, 55, 90, 75].map((height, i) => (
              <div key={i} className="w-full bg-slate-50 rounded-t-lg relative group">
                <div 
                  className="absolute bottom-0 w-full bg-blue-900 rounded-t-lg transition-all duration-500 group-hover:bg-blue-800"
                  style={{ height: `${height}%` }}
                ></div>
              </div>
            ))}
          </div>
          <div className="flex justify-between mt-4 text-xs font-medium text-slate-400">
            <span>Jan</span><span>Fev</span><span>Mar</span><span>Abr</span><span>Mai</span><span>Jun</span><span>Jul</span>
          </div>
        </div>

        <div className="space-y-8">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-4">Próximos Eventos</h3>
            <div className="space-y-4">
              {recentEvents.map(event => (
                <div key={event.id} className="flex items-center gap-4 p-3 rounded-xl hover:bg-slate-50 transition-colors">
                  <div className="w-12 h-12 bg-blue-50 text-blue-900 rounded-xl flex items-center justify-center shrink-0 font-bold text-sm">
                    {new Date(event.date).getDate()}
                  </div>
                  <div>
                    <h4 className="font-semibold text-slate-900">{event.title}</h4>
                    <p className="text-sm text-slate-500">{event.location}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-4">Últimos Cadastros</h3>
            <div className="space-y-4">
              {recentMembers.map(member => (
                <div key={member.id} className="flex items-center gap-4 p-3 rounded-xl hover:bg-slate-50 transition-colors">
                  <img src={member.avatar} alt={member.name} className="w-10 h-10 rounded-full bg-slate-200" />
                  <div>
                    <h4 className="font-semibold text-slate-900">{member.name}</h4>
                    <p className="text-sm text-slate-500">{member.status}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
