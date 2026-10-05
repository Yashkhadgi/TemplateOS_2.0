import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute, PublicOnlyRoute } from "./components/protected-route";
import { DashboardLayout } from "./layouts/dashboard-layout";
import { DashboardPage } from "./pages/dashboard-page";
import { LoginPage } from "./pages/login-page";
import { ProfilePage } from "./pages/profile-page";
import { UploadTemplatePage } from "./pages/upload-template-page";
import { SignupPage } from "./pages/signup-page";
import { TemplateLibraryPage } from "./pages/template-library-page";
import { TemplateDetailPage } from "./pages/template-detail-page";
import { PlaceholderReviewPage } from "./pages/placeholder-review-page";
import { TemplateCleaningPage } from "./pages/template-cleaning-page";
import { FieldSetupPage } from "./pages/field-setup-page";
import { CreateDocumentPage } from "./pages/create-document-page";
import { EditDocumentPage } from "./pages/edit-document-page";

export function App() {
  return (
    <Routes>
      <Route element={<PublicOnlyRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route element={<DashboardLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/upload-template" element={<UploadTemplatePage />} />
          <Route path="/templates" element={<TemplateLibraryPage />} />
          <Route path="/templates/:id" element={<TemplateDetailPage />} />
          <Route path="/templates/:id/placeholders" element={<PlaceholderReviewPage />} />
          <Route path="/templates/:id/clean" element={<TemplateCleaningPage />} />
          <Route path="/templates/:id/fields" element={<FieldSetupPage />} />
          <Route path="/documents/create/:id" element={<CreateDocumentPage />} />
          <Route path="/documents/:id/edit" element={<EditDocumentPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
