/** @type {import('next').NextConfig} */

// Only fall back to localhost in development. In a production build (e.g. Vercel)
// a missing NEXT_PUBLIC_API_URL must NOT silently become "http://localhost:8000"
// — that points the user's browser at their own machine and yields "Failed to
// fetch". Leaving it empty lets the app surface a clear configuration error.
const isDev = process.env.NODE_ENV !== "production";
const apiUrl = process.env.NEXT_PUBLIC_API_URL || (isDev ? "http://localhost:8000" : "");

if (!apiUrl) {
  console.warn(
    "[config] NEXT_PUBLIC_API_URL is not set for this production build — " +
      "set it to your backend's https URL (e.g. https://your-api.onrender.com)."
  );
}

const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: apiUrl,
  },
};

module.exports = nextConfig;
