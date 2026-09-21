import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import FlagQueue from "./pages/FlagQueue";
import FlagDetail from "./pages/FlagDetail";
import Layout from "./components/Layout";
import { AuthProvider, useAuth } from "./lib/auth";
import Login from "./pages/Login";

function Placeholder({ title }: { title: string }) {
  return <h2 className="text-lg font-medium">{title}</h2>;
}

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
        <Route path="/assistant" element={<Placeholder title="Assistant" />} />
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