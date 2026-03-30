export default function HomePage() {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

  return (
    <main>
      <h1>Interview Simulation Frontend</h1>
      <p>Frontend Next.js actif en local.</p>
      <p>API cible: {apiBaseUrl}</p>
    </main>
  );
}
