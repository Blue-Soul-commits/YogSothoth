import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { AdminPage } from "./pages/AdminPage";
import { RouterProvider, useRouter } from "./router";
import "./styles.css";

const rootElement = document.getElementById("root") as HTMLElement;

const Root: React.FC = () => {
  const { path } = useRouter();
  if (path.startsWith("/admin")) {
    return <AdminPage />;
  }
  return <App />;
};

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <RouterProvider>
      <Root />
    </RouterProvider>
  </React.StrictMode>
);
