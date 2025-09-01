/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: process.env.NODE_ENV === 'production' 
          ? '/v1/:path*'  // Use relative path in production
          : 'http://localhost:8000/v1/:path*',  // Use localhost in development
      },
    ]
  },
}

module.exports = nextConfig
