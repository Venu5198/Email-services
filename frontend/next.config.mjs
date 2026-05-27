/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enables minimal standalone server output for Docker (copies only required files)
  // This makes the production image ~50MB instead of ~1GB
  output: 'standalone',

  // Proxy /api/* and /track/* and /unsubscribe requests to the FastAPI backend
  // This avoids CORS issues when both services run in the same Docker network
  async rewrites() {
    const apiBase = process.env.INTERNAL_API_URL || 'http://api:8000'
    return [
      { source: '/api/:path*',         destination: `${apiBase}/api/:path*` },
      { source: '/track/:path*',       destination: `${apiBase}/track/:path*` },
      { source: '/unsubscribe',        destination: `${apiBase}/unsubscribe` },
      { source: '/health',             destination: `${apiBase}/health` },
    ]
  },
}

export default nextConfig

