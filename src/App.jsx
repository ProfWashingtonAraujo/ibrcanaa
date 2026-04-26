import { BrowserRouter, Routes, Route } from 'react-router-dom';
import DashboardLayout from './layouts/DashboardLayout';

// Pages
import LandingPage from './pages/LandingPage';
import Gateway from './pages/auth/Gateway';
import LoginAdmin from './pages/auth/LoginAdmin';
import AdminDashboard from './pages/admin/AdminDashboard';
import MembersPage from './pages/admin/MembersPage';
import FinancePage from './pages/admin/FinancePage';
import MinistriesPage from './pages/admin/MinistriesPage';
import EventsPage from './pages/admin/EventsPage';
import SettingsPage from './pages/admin/SettingsPage';
import MemberDashboard from './pages/member/MemberDashboard';
import MemberProfile from './pages/member/MemberProfile';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<Gateway />} />
        <Route path="/admin/login" element={<LoginAdmin />} />
        
        {/* Admin Routes */}
        <Route path="/admin" element={<DashboardLayout isAdmin />}>
          <Route index element={<AdminDashboard />} />
          <Route path="membros" element={<MembersPage />} />
          <Route path="financeiro" element={<FinancePage />} />
          <Route path="ministerios" element={<MinistriesPage />} />
          <Route path="eventos" element={<EventsPage />} />
          <Route path="configuracoes" element={<SettingsPage />} />
        </Route>

        {/* Member Routes */}
        <Route path="/membro" element={<DashboardLayout isAdmin={false} />}>
          <Route index element={<MemberDashboard />} />
          <Route path="perfil" element={<MemberProfile />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
