export const metadata = {
  title: "Interview Simulation",
  description: "Local frontend for interview simulation"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "Segoe UI, sans-serif", margin: 24 }}>{children}</body>
    </html>
  );
}
