import "./globals.css";

export const metadata = {
  title: "Everest Textile Manufacturing - Plant Operations Terminal",
  description: "Worker and Floor Management Operations Terminal",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
