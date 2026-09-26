import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";
import { DEFAULT_AUTHENTICATED_PATH, ProtectedRoute, PublicOnlyRoute } from "./modules/auth";
import { DashboardPlaceholderPage } from "./pages/DashboardPlaceholderPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { LoginPage } from "./pages/LoginPage";
import { CategoriesPage } from "./pages/master-data/CategoriesPage";
import { LocationsPage } from "./pages/master-data/LocationsPage";
import { ProductDetailPage } from "./pages/master-data/ProductDetailPage";
import { ProductFormPage } from "./pages/master-data/ProductFormPage";
import { ProductsPage } from "./pages/master-data/ProductsPage";
import { ReorderRulesPage } from "./pages/master-data/ReorderRulesPage";
import { UnitsPage } from "./pages/master-data/UnitsPage";
import { WarehouseDetailPage } from "./pages/master-data/WarehouseDetailPage";
import { WarehousesPage } from "./pages/master-data/WarehousesPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { SignupPage } from "./pages/SignupPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to={DEFAULT_AUTHENTICATED_PATH} replace />} />

      {/* Only for signed-out users */}
      <Route element={<PublicOnlyRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
      </Route>

      {/* Requires a signed-in user. Add module pages inside this block. */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPlaceholderPage />} />
          <Route path="/profile" element={<ProfilePage />} />

          {/* Master data (products & warehouses) */}
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/products/:id" element={<ProductDetailPage />} />
          <Route path="/categories" element={<CategoriesPage />} />
          <Route path="/units" element={<UnitsPage />} />
          <Route path="/reorder-rules" element={<ReorderRulesPage />} />
          <Route path="/warehouses" element={<WarehousesPage />} />
          <Route path="/warehouses/:id" element={<WarehouseDetailPage />} />
          <Route path="/locations" element={<LocationsPage />} />
          <Route element={<ProtectedRoute roles={["INVENTORY_MANAGER"]} />}>
            <Route path="/products/new" element={<ProductFormPage />} />
            <Route path="/products/:id/edit" element={<ProductFormPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
