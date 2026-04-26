import { Link } from 'react-router-dom';
import { ShieldCheck, User } from 'lucide-react';
import Logo from '../../components/common/Logo';

export default function Gateway() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center mb-10">
        <Logo className="justify-center mb-6 scale-125" />
        <h2 className="mt-6 text-center text-3xl font-extrabold text-slate-900">
          Selecione seu acesso
        </h2>
        <p className="mt-2 text-center text-sm text-slate-600">
          Como você deseja acessar o Lumen Ecclesia?
        </p>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-2xl">
        <div className="grid sm:grid-cols-2 gap-6">
          <Link 
            to="/membro" 
            className="bg-white p-8 rounded-3xl shadow-sm border border-slate-200 hover:border-blue-500 hover:shadow-md transition-all group text-center"
          >
            <div className="w-16 h-16 bg-blue-50 text-blue-900 rounded-2xl flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform">
              <User className="w-8 h-8" />
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-2">Portal do Membro</h3>
            <p className="text-slate-500 text-sm">Acesse sua jornada, contribuições e treinamentos.</p>
          </Link>

          <Link 
            to="/admin/login" 
            className="bg-white p-8 rounded-3xl shadow-sm border border-slate-200 hover:border-slate-800 hover:shadow-md transition-all group text-center"
          >
            <div className="w-16 h-16 bg-slate-100 text-slate-900 rounded-2xl flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform">
              <ShieldCheck className="w-8 h-8" />
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-2">Painel Administrativo</h3>
            <p className="text-slate-500 text-sm">Gestão de membros, financeiro e ministérios.</p>
          </Link>
        </div>
      </div>
    </div>
  );
}
