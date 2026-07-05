import { MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'TripWise',
    short_name: 'TripWise',
    description: 'Manage trip expenses and settle debts easily.',
    start_url: '/',
    id: '/',
    display: 'standalone',
    display_override: ['window-controls-overlay', 'standalone', 'minimal-ui'],
    background_color: '#07090e',
    theme_color: '#07090e',
    orientation: 'any',
    scope: '/',
    lang: 'en',
    dir: 'ltr',
    categories: ['finance', 'travel', 'productivity'],
    related_applications: [],
    prefer_related_applications: false,
    icons: [
      {
        src: '/icon-192x192.png',
        sizes: '192x192',
        type: 'image/png',
        purpose: 'maskable',
      },
      {
        src: '/icon-512x512.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'maskable',
      },
      {
        src: '/icon',
        sizes: 'any',
        type: 'image/png',
      },
    ],
    screenshots: [
      {
        src: '/screenshot-desktop.png',
        sizes: '1280x720',
        type: 'image/png',
        form_factor: 'wide',
      },
      {
        src: '/screenshot-mobile.png',
        sizes: '750x1334',
        type: 'image/png',
        form_factor: 'narrow',
      },
    ] as any,
    shortcuts: [
      {
        name: 'Dashboard',
        short_name: 'Dashboard',
        description: 'Go to your dashboard',
        url: '/dashboard',
      },
    ],
  }
}
