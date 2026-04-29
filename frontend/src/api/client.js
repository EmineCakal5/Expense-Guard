import axios from "axios";

// Backend FastAPI endpoints are mounted under /api
// - In dev: Vite proxy in vite.config.js forwards /api -> http://localhost:8000
// - In docker: VITE_API_URL can be http://backend:8000 and we call ${VITE_API_URL}/api
const BASE = import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api` : "/api";

const client = axios.create({ baseURL: BASE, timeout: 30_000 });

export const getHealth     = ()        => client.get("/health").then((r) => r.data);
export const getDashboard  = ()        => client.get("/dashboard").then((r) => r.data);
export const getAnomalies  = (params)  => client.get("/anomalies", { params }).then((r) => r.data);
export const getAnomaly    = (id)      => client.get(`/anomalies/${id}`).then((r) => r.data);
export const getDepartments= ()        => client.get("/departments").then((r) => r.data);
export const getTimeline   = (g="month") => client.get("/timeline", { params: { granularity: g } }).then((r) => r.data);
export const getMetrics    = ()        => client.get("/metrics").then((r) => r.data);
export const uploadCSV     = (file, options = {})   => {
  const fd = new FormData();
  fd.append("file", file);
  const { onUploadProgress } = options;
  return client
    .post("/upload", fd, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress,
    })
    .then((r) => r.data);
};

export default client;
