import { useState } from 'react';
import { Download, Plus, Search, Filter, MoreVertical, Edit2, Trash2 } from 'lucide-react';
import PageHeader from '../../components/common/PageHeader';
import Button from '../../components/ui/Button';
import StatusBadge from '../../components/ui/StatusBadge';
import ProgressBar from '../../components/ui/ProgressBar';
import { members } from '../../mocks/members';

export default function MembersPage() {
  const [filter, setFilter] = useState('Todos');
  const filters = ['Todos', 'Ativo', 'Visitante', 'Novo', 'Afastado', 'Liderança'];

  const filteredMembers = filter === 'Todos' ? members : members.filter(m => m.status === filter);

  return (
    <div>
      <PageHeader 
        title="Gestão de Membros" 
        description="Gerencie os membros, visitantes e liderança da sua igreja."
        action={
          <>
            <Button variant="outline" className="gap-2 hidden sm:flex">
              <Download className="w-4 h-4" /> Exportar
            </Button>
            <Button className="gap-2">
              <Plus className="w-4 h-4" /> Novo Membro
            </Button>
          </>
        }
      />

      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-4 sm:p-6 mb-8">
        <div className="flex flex-col md:flex-row gap-4 justify-between items-start md:items-center mb-6">
          <div className="relative w-full md:w-96">
            <Search className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input 
              type="text" 
              placeholder="Buscar por nome, email ou ministério..."
              className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
            />
          </div>
          
          <div className="flex items-center gap-2 overflow-x-auto w-full md:w-auto pb-2 md:pb-0">
            <Button variant="outline" size="sm" className="gap-2 shrink-0">
              <Filter className="w-4 h-4" /> Filtros
            </Button>
            {filters.map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                  filter === f 
                    ? 'bg-slate-900 text-white' 
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-sm font-medium text-slate-500">
                <th className="pb-4 pl-4 font-medium">Membro</th>
                <th className="pb-4 px-4 font-medium">Ministério</th>
                <th className="pb-4 px-4 font-medium">Status</th>
                <th className="pb-4 px-4 font-medium w-48">Frequência</th>
                <th className="pb-4 pr-4 font-medium text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredMembers.map(member => (
                <tr key={member.id} className="hover:bg-slate-50/50 transition-colors group">
                  <td className="py-4 pl-4">
                    <div className="flex items-center gap-3">
                      <img src={member.avatar} alt="" className="w-10 h-10 rounded-full bg-slate-200" />
                      <div>
                        <p className="font-semibold text-slate-900">{member.name}</p>
                        <p className="text-sm text-slate-500">{member.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-4 text-slate-600">{member.ministry}</td>
                  <td className="py-4 px-4">
                    <StatusBadge status={member.status} />
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-3">
                      <ProgressBar 
                        value={member.frequency} 
                        colorClass={member.frequency > 50 ? "bg-emerald-500" : "bg-amber-500"} 
                      />
                      <span className="text-xs font-medium text-slate-600 w-8">{member.frequency}%</span>
                    </div>
                  </td>
                  <td className="py-4 pr-4 text-right">
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors">
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                      <button className="p-2 text-slate-400 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors">
                        <MoreVertical className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
