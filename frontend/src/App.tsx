import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import { AuthProvider, useAuth } from "./lib/auth";
import Assistant from "./pages/Assistant";
import FlagDetail from "./pages/FlagDetail";
import FlagQueue from "./pages/FlagQueue";
import LiveFeed from "./pages/LiveFeed";
import Login from "./pages/Login";

function Shell() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="p-8 text-slate-400">Loading...</div>;
  }

  if (!user) {
    return <Login />;
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/flags" element={<FlagQueue />} />
        <Route path="/flags/:flagId" element={<FlagDetail />} />
        <Route path="/live" element={<LiveFeed />} />
        <Route path="/assistant" element={<Assistant />} />
        <Route path="*" element={<Navigate to="/flags" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </AuthProvider>
  );
}