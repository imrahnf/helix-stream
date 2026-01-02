/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  async rewrites() {
    return [
      { source: '/api/v1/:path*', destination: 'http://127.0.0.1:8000/v1/:path*' },
      { source: '/api/health', destination: 'http://127.0.0.1:8000/health' },
    ];
  },
};

export default nextConfig;