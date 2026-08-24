import { Suspense } from "react";
import UpdatePortalClient from "./UpdatePortalClient";

export default function UpdatePortalPage() {
  return (
    <Suspense fallback={null}>
      <UpdatePortalClient />
    </Suspense>
  );
}
