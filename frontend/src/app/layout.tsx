import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Link from 'next/link'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Legal Citation Graph',
  description: 'AI-assisted legal citation graph visualization',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="min-h-screen bg-gray-50">
          {/* Navigation Bar */}
          <nav className="bg-white shadow-sm border-b">
            <div className="container mx-auto px-6">
              <div className="flex items-center justify-between h-16">
                <div className="flex items-center space-x-8">
                  <Link href="/" className="text-xl font-bold text-gray-900">
                    Legal Citation Graph
                  </Link>
                  <div className="flex space-x-6">
                    <Link 
                      href="/graph" 
                      className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium transition-colors"
                    >
                      Graph
                    </Link>
                    <Link 
                      href="/documents" 
                      className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium transition-colors"
                    >
                      Documents
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </nav>
          
          {/* Main Content */}
          <main>
            {children}
          </main>
        </div>
      </body>
    </html>
  )
}

