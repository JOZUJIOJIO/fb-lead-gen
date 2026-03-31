import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Campaigns from './pages/Campaigns';
import NewCampaign from './pages/NewCampaign';
import CampaignDetail from './pages/CampaignDetail';
import Leads from './pages/Leads';
import Personas from './pages/Personas';
import Settings from './pages/Settings';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-[#f5f5f7]">
        <Sidebar />
        <main className="flex-1 overflow-auto p-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/campaigns" element={<Campaigns />} />
            <Route path="/campaigns/new" element={<NewCampaign />} />
            <Route path="/campaigns/:id" element={<CampaignDetail />} />
            <Route path="/leads" element={<Leads />} />
            <Route path="/personas" element={<Personas />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
