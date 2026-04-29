export default {
  // #region agent log
  ...(typeof fetch === "function"
    ? (fetch("http://127.0.0.1:7756/ingest/de1aee41-63af-490f-9fb3-c33fefe5926e", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Debug-Session-Id": "da7047",
        },
        body: JSON.stringify({
          sessionId: "da7047",
          runId: "pre-fix",
          hypothesisId: "H_cfg_loaded",
          location: "frontend/postcss.config.js:2",
          message: "PostCSS config loaded",
          data: { hasGlobalFetch: true },
          timestamp: Date.now(),
        }),
      }).catch(() => {}),
      {})
    : {}),
  // #endregion
  plugins: {
    "@tailwindcss/postcss": {},
    autoprefixer: {},
  },
};

