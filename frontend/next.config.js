/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  // Proxy all backend requests through Next.js to avoid CORS issues.
  // Browser requests go to /api/* which Next.js rewrites server-side
  // to the actual Railway backend URLs.
  async rewrites() {
    const apiGateway = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001';
    const mlTraining = process.env.NEXT_PUBLIC_ML_TRAINING_URL || 'http://localhost:5002';
    const dataCollection = process.env.NEXT_PUBLIC_DATA_COLLECTION_URL || 'http://localhost:5008';

    return [
      // API Gateway proxy: /api/* → Railway API Gateway /*
      {
        source: '/api/:path*',
        destination: `${apiGateway}/:path*`,
      },
      // ML Training direct proxy: /ml-api/* → Railway ML Training Service /*
      {
        source: '/ml-api/:path*',
        destination: `${mlTraining}/:path*`,
      },
      // Data Collection direct proxy: /data-api/* → Railway Data Collection /*
      {
        source: '/data-api/:path*',
        destination: `${dataCollection}/:path*`,
      },
    ];
  },
}

module.exports = nextConfig
