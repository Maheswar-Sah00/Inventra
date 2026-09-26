import { useEffect, useState } from "react";

import { Alert } from "../../components/ui/Alert";
import { ApiError } from "../../services/apiClient";
import { locationLabel } from "../master-data/types";
import { stockApi } from "./api";
import { formatQuantity } from "./operations";
import type { ProductStock } from "./types";

/** On-hand stock of one product, total and per location (used on the product detail page). */
export function ProductStockPanel({ productId }: { productId: number }) {
  const [stock, setStock] = useState<ProductStock | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    stockApi
      .product(productId, controller.signal)
      .then(setStock)
      .catch((err: Error) => {
        if (err.name !== "AbortError") setError(err instanceof ApiError ? err.message : "Unable to load stock.");
      });
    return () => controller.abort();
  }, [productId]);

  const unit = stock?.product.unit_of_measure.symbol;
  return (
    <section aria-label="Stock by location">
      <div className="section-header">
        <h2>Stock on hand</h2>
        {stock && <strong>{formatQuantity(stock.total_quantity, unit)}</strong>}
      </div>
      {error && <Alert variant="error">{error}</Alert>}
      {stock && stock.locations.length === 0 && <p className="muted">No stock at any location.</p>}
      {stock && stock.locations.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Location</th>
                <th className="num">Quantity</th>
              </tr>
            </thead>
            <tbody>
              {stock.locations.map((row) => (
                <tr key={row.location.id}>
                  <td>{locationLabel(row.location)}</td>
                  <td className="num">{formatQuantity(row.quantity, unit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
