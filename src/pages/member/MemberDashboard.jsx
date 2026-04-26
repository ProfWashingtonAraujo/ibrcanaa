import { PlayCircle, Target, Award, HeartHandshake } from 'lucide-react';
import PageHeader from '../../components/common/PageHeader';
import ProgressBar from '../../components/ui/ProgressBar';
import Button from '../../components/ui/Button';

export default function MemberDashboard() {
  return (
    <div>
      <PageHeader 
        title="Olá, João!" 
        description="Bem-vindo ao seu portal do membro. Aqui você acompanha sua jornada de fé."
      />

      <div className="grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Target className="w-5 h-5 text-blue-600" /> Maturidade Espiritual
              </h3>
              <span className="text-sm font-medium text-slate-500">Nível 3</span>
            </div>
            <p className="text-sm text-slate-500 mb-4">Você está progredindo muito bem na sua jornada com Cristo.</p>
            <ProgressBar value={65} colorClass="bg-blue-600" />
            <div className="mt-2 text-right text-xs text-slate-400 font-medium">350 / 500 XP</div>
          </div>

          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <h3 className="text-lg font-bold text-slate-900 mb-6 flex items-center gap-2">
              <PlayCircle className="w-5 h-5 text-blue-600" /> Treinamentos e Cursos
            </h3>
            
            <div className="space-y-6">
              <div className="group">
                <div className="flex justify-between items-center mb-2">
                  <div>
                    <h4 className="font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">Fundamentos da Fé</h4>
                    <p className="text-sm text-slate-500">Módulo 2: Oração e Palavra</p>
                  </div>
                  <Button variant="ghost" size="sm">Continuar</Button>
                </div>
                <ProgressBar value={40} colorClass="bg-emerald-500" />
              </div>

              <div className="group">
                <div className="flex justify-between items-center mb-2">
                  <div>
                    <h4 className="font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">Liderança com Propósito</h4>
                    <p className="text-sm text-slate-500">Introdução</p>
                  </div>
                  <Button variant="ghost" size="sm">Iniciar</Button>
                </div>
                <ProgressBar value={0} colorClass="bg-slate-300" />
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-8">
          <div className="bg-slate-900 p-6 rounded-2xl text-white relative overflow-hidden">
            <div className="absolute -top-10 -right-10 opacity-20">
              <Award className="w-48 h-48" />
            </div>
            <div className="relative z-10">
              <span className="px-2 py-1 bg-blue-600 rounded-md text-xs font-bold uppercase tracking-wider mb-4 inline-block">Novidade</span>
              <h3 className="text-xl font-bold mb-2">Mentoria de Liderança</h3>
              <p className="text-slate-400 text-sm mb-6">Inscreva-se na nova turma de mentoria pastoral e prepare-se para liderar.</p>
              <Button className="w-full bg-white text-slate-900 hover:bg-slate-100">Saiba Mais</Button>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <HeartHandshake className="w-5 h-5 text-blue-600" /> Meus Ministérios
            </h3>
            <div className="flex items-center gap-4 p-4 rounded-xl border border-slate-100 bg-slate-50">
              <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-sm text-2xl">
                🎵
              </div>
              <div>
                <h4 className="font-bold text-slate-900">Louvor</h4>
                <p className="text-sm text-slate-500">Voluntário Ativo</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
