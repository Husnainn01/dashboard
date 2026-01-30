self.__BUILD_MANIFEST = {
  "/": [
    "static/chunks/pages/index.js"
  ],
  "/_error": [
    "static/chunks/pages/_error.js"
  ],
  "__rewrites": {
    "afterFiles": [
      {
        "source": "/api/:path*"
      },
      {
        "source": "/ml-api/:path*"
      },
      {
        "source": "/data-api/:path*"
      }
    ],
    "beforeFiles": [],
    "fallback": []
  },
  "sortedPages": [
    "/",
    "/_app",
    "/_error"
  ]
};self.__BUILD_MANIFEST_CB && self.__BUILD_MANIFEST_CB()