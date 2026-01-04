/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://127.0.0.1:8000/v1/:path*', // Proxy to FastAPI
      },
    ];
  },
};

export default nextConfig;