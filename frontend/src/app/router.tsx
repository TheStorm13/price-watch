import { Navigate, createBrowserRouter } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { CardsPage } from '../features/cards/CardsPage'
import { RunsPage } from '../features/runs/RunsPage'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: AppShell,
    children: [
      { index: true, element: <Navigate to="/cards" replace /> },
      { path: 'cards', Component: CardsPage },
      {
        path: 'cards/:cardId',
        lazy: async () => {
          const module = await import('../features/card-details/CardDetailsPage')
          return { Component: module.CardDetailsPage }
        },
      },
      { path: 'runs', Component: RunsPage },
      {
        path: 'deals',
        lazy: async () => {
          const module = await import('../features/deals/DealsPage')
          return { Component: module.DealsPage }
        },
      },
      { path: '*', element: <Navigate to="/cards" replace /> },
    ],
  },
])
