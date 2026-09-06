import { MsalProvider } from '@azure/msal-react'
import { QueryClientProvider } from '@tanstack/react-query'
import { LazyMotion, domAnimation, MotionConfig } from 'motion/react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import { msalInstance } from './auth/config'
import './index.css'
import { queryClient } from './query-client'

/** MSAL must be initialised, and any redirect it is returning from must be consumed, *before*
 * React renders -- otherwise the first paint happens with no active account and the sign-in gate
 * bounces a user who is in fact already signed in.
 *
 * `handleRedirectPromise` is also what completes the login itself: after Entra redirects back,
 * the account only exists once this has resolved. Setting the active account here rather than in
 * a component keeps that ordering out of React's lifecycle entirely.
 */
async function start() {
  await msalInstance.initialize()
  const result = await msalInstance.handleRedirectPromise()
  const account = result?.account ?? msalInstance.getAllAccounts()[0]
  if (account) msalInstance.setActiveAccount(account)

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <MsalProvider instance={msalInstance}>
        <QueryClientProvider client={queryClient}>
          <LazyMotion features={domAnimation} strict>
            <MotionConfig reducedMotion="user">
              <BrowserRouter>
                <App />
              </BrowserRouter>
            </MotionConfig>
          </LazyMotion>
        </QueryClientProvider>
      </MsalProvider>
    </StrictMode>,
  )
}

void start()
