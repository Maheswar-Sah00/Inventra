import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";
import { DEFAULT_AUTHENTICATED_PATH, ProtectedRoute, PublicOnlyRoute } from "./modules/auth";
import { OPERATIONS } from "./modules/inventory/operations";
import { DashboardPage } from "./pages/dashboard/DashboardPage";
import { MoveHistoryPage } from "./pages/dashboard/MoveHistoryPage";
import { StockAvailabilityPage } from "./pages/dashboard/StockAvailabilityPage";
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
import { OperationDetailPage } from "./pages/operations/OperationDetailPage";
import { OperationFormPage } from "./pages/operations/OperationFormPage";
import { OperationListPage } from "./pages/operations/OperationListPage";
import { StockPage } from "./pages/operations/StockPage";
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
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/stock-availability" element={<StockAvailabilityPage />} />
          <Route path="/move-history" element={<MoveHistoryPage />} />
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

          {/* Inventory operations (open to every signed-in user). key= remounts pages per operation. */}
          <Route path="/stock" element={<StockPage />} />
          {Object.values(OPERATIONS).map((config) => [
            <Route key={`${config.kind}-list`} path={`/${config.kind}`} element={<OperationListPage key={config.kind} config={config} />} />,
            <Route key={`${config.kind}-new`} path={`/${config.kind}/new`} element={<OperationFormPage key={`${config.kind}-new`} config={config} />} />,
            <Route key={`${config.kind}-detail`} path={`/${config.kind}/:id`} element={<OperationDetailPage key={config.kind} config={config} />} />,
            <Route key={`${config.kind}-edit`} path={`/${config.kind}/:id/edit`} element={<OperationFormPage key={`${config.kind}-edit`} config={config} />} />,
          ])}
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
