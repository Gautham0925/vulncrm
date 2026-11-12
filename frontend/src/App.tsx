import type React from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import Login from "./pages/Login";
import { Forgot, Reset } from "./pages/Password";
import Dashboard from "./pages/Dashboard";
import { CustomerDetail, CustomerList } from "./pages/Customers";
import { LeadDetail, LeadList } from "./pages/Leads";
import { DealDetail, Pipeline } from "./pages/Pipeline";
import { TicketDetail, TicketList } from "./pages/Tickets";
import { DocumentDetail, DocumentList } from "./pages/Documents";
import Reports from "./pages/Reports";
import { EmployeeDetail, EmployeeList, RoleList, TeamList } from "./pages/People";
import Integrations from "./pages/Integrations";
import OAuthApps from "./pages/OAuthApps";
import { Audit, OrgSettings, Platform, Sso } from "./pages/Admin";
import Profile from "./pages/Profile";
import TestLibrary from "./pages/TestLibrary";
import DevMailbox from "./pages/DevMailbox";

function Guard({ perm, children }: { perm?: string; children: React.ReactElement }) {
  const { me, can, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Spinner />;
  if (!me) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (perm && !can(perm)) return <div className="py-24 text-center"><h1 className="text-xl font-semibold">Access denied</h1><p className="mt-2 text-sm text-ink-500">Your role does not include access to this area.</p></div>;
  return children;
}

export default function App() {
  const g = (perm: string | undefined, el: React.ReactElement) => <Guard perm={perm}>{el}</Guard>;
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<Forgot />} />
      <Route path="/reset-password" element={<Reset />} />
      <Route path="/dev/mailbox" element={<DevMailbox />} />
      <Route element={<Guard><Layout /></Guard>}>
        <Route index element={<Dashboard />} />
        <Route path="customers" element={g("customers.read", <CustomerList />)} />
        <Route path="customers/:id" element={g("customers.read", <CustomerDetail />)} />
        <Route path="leads" element={g("leads.read", <LeadList />)} />
        <Route path="leads/:id" element={g("leads.read", <LeadDetail />)} />
        <Route path="pipeline" element={g("opportunities.read", <Pipeline />)} />
        <Route path="pipeline/deal/:id" element={g("opportunities.read", <DealDetail />)} />
        <Route path="opportunities/:id" element={g("opportunities.read", <DealDetail />)} />
        <Route path="tickets" element={g("tickets.read", <TicketList />)} />
        <Route path="tickets/:id" element={g("tickets.read", <TicketDetail />)} />
        <Route path="documents" element={g("documents.read", <DocumentList />)} />
        <Route path="documents/:id" element={g("documents.read", <DocumentDetail />)} />
        <Route path="reports" element={g("reports.read", <Reports />)} />
        <Route path="employees" element={g("employees.read", <EmployeeList />)} />
        <Route path="employees/:id" element={g("employees.read", <EmployeeDetail />)} />
        <Route path="teams" element={g("employees.read", <TeamList />)} />
        <Route path="roles" element={g("roles.manage", <RoleList />)} />
        <Route path="integrations" element={g("integrations.manage", <Integrations />)} />
        <Route path="oauth-apps" element={g("oauth.manage", <OAuthApps />)} />
        <Route path="sso" element={g("sso.manage", <Sso />)} />
        <Route path="audit" element={g("audit.read", <Audit />)} />
        <Route path="admin" element={g("org.manage", <OrgSettings />)} />
        <Route path="platform" element={g("platform.manage", <Platform />)} />
        <Route path="test-library" element={g("testlib.read", <TestLibrary />)} />
        <Route path="profile" element={<Profile />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
