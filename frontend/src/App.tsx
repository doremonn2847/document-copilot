import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import ChatLayout from '@/pages/ChatLayout'
import NewChatPage from '@/pages/NewChatPage'
import ChatThreadPage from '@/pages/ChatThreadPage'
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
        <Route path="/" element={<AccessGate access="approved"><Navigate to="/chats" replace /></AccessGate>} />
        <Route path="/chats" element={<AccessGate access="approved"><ChatLayout /></AccessGate>}>
          <Route index element={<NewChatPage />} />
          <Route path=":threadId" element={<ChatThreadPage />} />
        </Route>
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
