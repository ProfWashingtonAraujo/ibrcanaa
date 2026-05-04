import { Users, Plus, Star, Target, Activity } from 'lucide-react';
import PageHeader from '../../components/common/PageHeader';
import Button from '../../components/ui/Button';
import StatusBadge from '../../components/ui/StatusBadge';
import { ministries } from '../../mocks/ministries';

export default function MinistriesPage() {
  return (
    <div>
      <PageHeader 
        title="Ministérios" 
        description="Acompanhe os grupos e ministérios atuantes na igreja."
        action={
          <Button className="gap-2">
            <Plus className="w-4 h-4" /> Novo Ministério
          </Button>
        }
      />

      <div className="grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 grid sm:grid-cols-2 gap-6">
          {ministries.map(ministry => (
            <div key={ministry.id} className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 flex flex-col h-full hover:shadow-md transition-shadow group">
              <div className="flex justify-between items-start mb-4">
                <div className="w-12 h-12 bg-blue-50 text-blue-900 rounded-xl flex items-center justify-center">
                  <Users className="w-6 h-6" />
                </div>
                <StatusBadge status={ministry.status} />
              </div>
              
              <h3 className="text-xl font-bold text-slate-900 mb-1">{ministry.name}</h3>
              <p className="text-sm text-slate-500 mb-6">Líder: {ministry.leader}</p>
              
              <div className="mt-auto flex items-center justify-between pt-6 border-t border-slate-100">
                <div className="flex -space-x-2">
                  {[...Array(Math.min(3, ministry.members))].map((_, i) => (
                    <img key={i} src={`https://i.pravatar.cc/150?u=${ministry.id}${i}`} className="w-8 h-8 rounded-full border-2 border-white bg-slate-200" alt="" />
                  ))}
                  {ministry.members > 3 && (
                    <div className="w-8 h-8 rounded-full border-2 border-white bg-slate-100 text-xs font-medium text-slate-600 flex items-center justify-center">
                      +{ministry.members - 3}
                    </div>
                  )}
                </div>
                <Button variant="ghost" size="sm" className="opacity-0 group-hover:opacity-100 transition-opacity">Gerenciar</Button>
              </div>
            </div>
          ))}
        </div>

        <div className="space-y-6">
          <div className="bg-slate-900 rounded-2xl p-6 text-white relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10">
              <Target className="w-32 h-32" />
            </div>
            <div className="relative z-10">
              <h3 className="text-lg font-bold mb-2">Metas Missionárias</h3>
              <p className="text-slate-400 text-sm mb-6">Nosso alvo de crescimento para o semestre atual.</p>
              
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium">Novos Voluntários</span>
                    <span>75%</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-2">
                    <div className="bg-blue-500 h-2 rounded-full" style={{ width: '75%' }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium">Células Ativas</span>
                    <span>40%</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-2">
                    <div className="bg-emerald-500 h-2 rounded-full" style={{ width: '40%' }}></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-blue-600" /> Indicadores Simulados
            </h3>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <Star className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-sm text-slate-500">Ministério Destaque</p>
                  <p className="font-bold text-slate-900">Louvor e Adoração</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center">
                  <Users className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-sm text-slate-500">Maior Crescimento</p>
                  <p className="font-bold text-slate-900">Canaã Kids (+15%)</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
