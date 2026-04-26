import { Link, useNavigate } from 'react-router-dom';
import Logo from '../../components/common/Logo';
import Button from '../../components/ui/Button';

export default function LoginAdmin() {
  const navigate = useNavigate();

  const handleLogin = (e) => {
    e.preventDefault();
    navigate('/admin');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <Logo className="justify-center mb-8" />
        <div className="bg-white py-8 px-4 shadow-sm sm:rounded-3xl sm:px-10 border border-slate-100">
          <div className="mb-6 text-center">
            <h2 className="text-2xl font-bold text-slate-900">Acesse o painel</h2>
            <p className="text-sm text-slate-500 mt-1">Área restrita à liderança</p>
          </div>

          <form className="space-y-6" onSubmit={handleLogin}>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                E-mail
              </label>
              <div className="mt-1">
                <input
                  type="email"
                  defaultValue="admin@lumen.com"
                  className="appearance-none block w-full px-3 py-2 border border-slate-300 rounded-xl shadow-sm placeholder-slate-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">
                Senha
              </label>
              <div className="mt-1">
                <input
                  type="password"
                  defaultValue="123456"
                  className="appearance-none block w-full px-3 py-2 border border-slate-300 rounded-xl shadow-sm placeholder-slate-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm transition-colors"
                />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <input
                  id="remember-me"
                  name="remember-me"
                  type="checkbox"
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-slate-300 rounded"
                />
                <label htmlFor="remember-me" className="ml-2 block text-sm text-slate-900">
                  Lembrar acesso
                </label>
              </div>

              <div className="text-sm">
                <a href="#" className="font-medium text-blue-600 hover:text-blue-500">
                  Esqueci minha senha
                </a>
              </div>
            </div>

            <div>
              <Button type="submit" className="w-full">
                Entrar
              </Button>
            </div>
          </form>
          
          <div className="mt-6 text-center">
            <Link to="/login" className="text-sm text-slate-500 hover:text-slate-900">
              Voltar para seleção
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
