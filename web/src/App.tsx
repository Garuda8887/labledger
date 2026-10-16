import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { UnlockScreen } from "./components/Unlock";
import { AppProvider, useApp } from "./lib/store";
import Analysis from "./pages/Analysis";
import Biomarker from "./pages/Biomarker";
import Compare from "./pages/Compare";
import Documents from "./pages/Documents";
import Matrix from "./pages/Matrix";
import Overview from "./pages/Overview";
import Print from "./pages/Print";
import Profiles, { Onboarding } from "./pages/Profiles";
import Review from "./pages/Review";
import { PageSkeleton } from "./components/ui";

function Gate({ children }: { children: React.ReactNode }) {
  const { profiles, needsUnlock, completeUnlock } = useApp();
  if (needsUnlock === null || (needsUnlock === false && profiles === null)) {
    return <div className="mx-auto max-w-6xl px-4 py-10"><PageSkeleton /></div>;
  }
  if (needsUnlock) {
    return <UnlockScreen onUnlocked={completeUnlock} />;
  }
  if (!profiles!.length) return <div className="mx-auto max-w-6xl px-4 py-10"><Onboarding first /></div>;
  return <>{children}</>;
}

export default function App() {
  return (
    <AppProvider>
      <Gate>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="biomarker/:id" element={<Biomarker />} />
            <Route path="analysis" element={<Analysis />} />
            <Route path="matrix"element={<Matrix />} />
            <Route path="compare" element={<Compare />} />
            <Route path="documents" element={<Documents />} />
            <Route path="review/:id" element={<Review />} />
            <Route path="print" element={<Print />} />
            <Route path="profiles" element={<Profiles />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Gate>
    </AppProvider>
  );
}
