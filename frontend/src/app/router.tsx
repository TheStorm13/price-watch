import { Navigate, createBrowserRouter } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { CardsPage } from '../features/cards/CardsPage'

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
      { path: 'runs', element: <Navigate to="/cards" replace /> },
      { path: '*', element: <Navigate to="/cards" replace /> },
    ],
  },
])
