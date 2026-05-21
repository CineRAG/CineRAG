# CineRAG Frontend

## Backend-App Nuvolos Launch

Run this frontend from a separate terminal in the same Nuvolos Backend application as FastAPI. Frontend API calls stay on the frontend origin, including Nuvolos `/proxy/<port>` paths, and Vite proxies those requests to `http://127.0.0.1:8000`.

Create the environment once:

```bash
cd /files/CineRAG/frontend
conda create -n cinerag_frontend -c conda-forge nodejs=20 -y
conda activate cinerag_frontend
npm ci
```

Launch the frontend after the backend is already running on port `8000`:

```bash
cd /files/CineRAG/frontend
conda activate cinerag_frontend
unset VITE_API_BASE_URL
npm run build
npm run preview -- --host 0.0.0.0 --port 3000
```
