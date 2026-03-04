import { Link, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/dashboard";
import Products from "./pages/products";
import ProductEditor from "./pages/productEditor";
import Preview from "./pages/preview";

export default function App() {
  return (
    <div>
      <nav style={{ padding: 12, borderBottom: "1px solid #ddd", display: "flex", gap: 12 }}>
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/productos">Productos</Link>
        <Link to="/preview">Preview</Link>
      </nav>

      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/productos" element={<Products />} />
        <Route path="/productos/:id" element={<ProductEditor />} />
        <Route path="/preview" element={<Preview />} />
      </Routes>
    </div>
  );
}