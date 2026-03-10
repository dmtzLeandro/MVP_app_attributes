import { Navigate, Route, Routes } from "react-router-dom";
import { isAuthed } from "./api/client";

import Dashboard from "./pages/dashboard";
import Preview from "./pages/preview";
import ProductEditor from "./pages/productEditor";
import Products from "./pages/products";
import LoginPage from "./pages/login";

function PrivateRoute({ children }: { children: JSX.Element }) {
  if (!isAuthed()) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/"
        element={
          <PrivateRoute>
            <Navigate to="/productos" replace />
          </PrivateRoute>
        }
      />

      <Route
        path="/dashboard"
        element={
          <PrivateRoute>
            <Dashboard />
          </PrivateRoute>
        }
      />

      <Route
        path="/productos"
        element={
          <PrivateRoute>
            <Products />
          </PrivateRoute>
        }
      />

      <Route
        path="/productos/:id"
        element={
          <PrivateRoute>
            <ProductEditor />
          </PrivateRoute>
        }
      />

      <Route
        path="/preview"
        element={
          <PrivateRoute>
            <Preview />
          </PrivateRoute>
        }
      />

      <Route path="*" element={<Navigate to="/productos" replace />} />
    </Routes>
  );
}