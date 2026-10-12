import { BrowserRouter, Route, Routes } from 'react-router-dom'
import HomePage from '@/pages/HomePage'
import AuthPage from '@/pages/AuthPage'
import AuthCallbackPage from '@/pages/AuthCallbackPage'
import PendingApprovalPage from '@/pages/PendingApprovalPage'
import AuthProvider from '@/components/AuthProvider'
import AccessGate from '@/components/AccessGate'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
      <Routes>
        <Route path="/" element={<AccessGate access="approved"><HomePage /></AccessGate>} />
        <Route path="/login" element={<AccessGate access="public"><AuthPage key="login" mode="login" /></AccessGate>} />
        <Route path="/signup" element={<AccessGate access="public"><AuthPage key="signup" mode="signup" /></AccessGate>} />
        <Route path="/pending-approval" element={<AccessGate access="pending"><PendingApprovalPage /></AccessGate>} />
        <Route path="/auth/callback" element={<AuthCallbackPage />} />
        <Route path="*" element={<main className="p-8">Page not found. <a className="underline" href="/">Return home</a></main>} />
      </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
