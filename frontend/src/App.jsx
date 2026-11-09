
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle,
  ChevronDown,
  ClipboardList,
  Download,
  FileText,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  RefreshCw,
  Settings,
  ShieldCheck,
  Upload,
  User,
  X,
  Eye,
  Sparkles,
} from "lucide-react";

import {
  login,
  getShipments,
  getShipmentDocuments,
  uploadDocument,
  extractDocument,
  getExtraction,
  openDocument,
  downloadDocument,
  getDocumentPreviewUrl,
  revokeDocumentPreviewUrl,
  saveCorrection,
  getCorrectionHistory,
  validateShipment,
  approveShipment,
  exportShipment,
  getShipmentExports,
  downloadShipmentExport,
} from "./api";

import "./App.css";

// --------------------------------------------------
// CONSTANTS
// --------------------------------------------------

const DOCUMENT_TYPES = [
  { value: "invoice", label: "Commercial Invoice" },
  { value: "packing_list", label: "Packing List" },
  { value: "bill_of_lading", label: "Bill of Lading" },
];

const REVIEW_FIELDS = [
  { name: "document_number", label: "Document number" },
  { name: "document_date", label: "Document date" },
  { name: "currency", label: "Currency" },
  { name: "incoterm", label: "Incoterm" },
  { name: "origin_country", label: "Origin country" },
  { name: "destination_port", label: "Destination port" },
  { name: "invoice_total", label: "Invoice total" },
  { name: "package_count", label: "Package count" },
  { name: "package_type", label: "Package type" },
  { name: "gross_weight_kg", label: "Gross weight (kg)" },
  { name: "net_weight_kg", label: "Net weight (kg)" },
  { name: "measurement_cbm", label: "Measurement (CBM)" },
  { name: "bill_of_lading_number", label: "Bill of lading number" },
  { name: "vessel_name", label: "Vessel name" },
  { name: "port_of_loading", label: "Port of loading" },
  { name: "port_of_discharge", label: "Port of discharge" },
];

const REVIEW_FIELDS_BY_TYPE = {
  invoice: [
    { name: "document_number", label: "Invoice number" },
    { name: "document_date", label: "Invoice date" },
    { name: "currency", label: "Currency" },
    { name: "incoterm", label: "Incoterm" },
    { name: "origin_country", label: "Origin country" },
    { name: "destination_port", label: "Destination port" },
    { name: "invoice_total", label: "Invoice total" },
    { name: "package_count", label: "Package count" },
    { name: "package_type", label: "Package type" },
    { name: "gross_weight_kg", label: "Gross weight (kg)" },
    { name: "net_weight_kg", label: "Net weight (kg)" },
    { name: "measurement_cbm", label: "Measurement (CBM)" },
  ],

  packing_list: [
    { name: "document_number", label: "Packing list number" },
    { name: "document_date", label: "Packing list date" },
    { name: "origin_country", label: "Origin country" },
    { name: "destination_port", label: "Destination port" },
    { name: "package_count", label: "Package count" },
    { name: "package_type", label: "Package type" },
    { name: "gross_weight_kg", label: "Gross weight (kg)" },
    { name: "net_weight_kg", label: "Net weight (kg)" },
    { name: "measurement_cbm", label: "Measurement (CBM)" },
  ],

  bill_of_lading: [
    { name: "bill_of_lading_number", label: "Bill of lading number" },
    { name: "vessel_name", label: "Vessel name" },
    { name: "port_of_loading", label: "Port of loading" },
    { name: "port_of_discharge", label: "Port of discharge" },
    { name: "origin_country", label: "Origin country" },
    { name: "destination_port", label: "Destination port" },
    { name: "package_count", label: "Package count" },
    { name: "gross_weight_kg", label: "Gross weight (kg)" },
    { name: "measurement_cbm", label: "Measurement (CBM)" },
  ],
};

// --------------------------------------------------
// HELPER FUNCTIONS
// --------------------------------------------------

function normalizeExtractionResponse(response) {
  let data =
    response?.extracted_data ??
    response?.extraction ??
    response;

  if (typeof data === "string") {
    try {
      data = JSON.parse(data);
    } catch {
      return {};
    }
  }

  return data && typeof data === "object" ? data : {};
}

function getConfidenceLabel(value) {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  const confidence = Number(value);

  if (!Number.isFinite(confidence)) {
    return "Not available";
  }

  return `${Math.round(confidence * 100)}%`;
}

function getConfidenceColor(value) {
  if (value === null || value === undefined || value === "") {
    return "#64748b";
  }

  const confidence = Number(value);

  if (!Number.isFinite(confidence)) return "#64748b";
  if (confidence >= 0.85) return "#15803d";
  if (confidence >= 0.6) return "#b45309";

  return "#dc2626";
}

function getDocumentId(document) {
  return document?.id ?? document?.document_id;
}

function getDocumentName(document) {
  return (
    document?.original_filename ||
    document?.filename ||
    document?.file_name ||
    `Document ${getDocumentId(document)}`
  );
}

function getDocumentTypeLabel(type) {
  const match = DOCUMENT_TYPES.find((item) => item.value === type);
  return match?.label || type || "Document";
}

function getErrorMessage(error) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (detail !== undefined && detail !== null) {
    try {
      return JSON.stringify(detail, null, 2);
    } catch {
      return String(detail);
    }
  }

  return error?.message || "Something went wrong. Please try again.";
}

function getValidationStatusColor(status) {
  switch (String(status || "").toUpperCase()) {
    case "MATCH":
    case "CLEAR":
    case "APPROVED":
      return "#15803d";

    case "MISMATCH":
    case "REVIEW_REQUIRED":
      return "#dc2626";

    case "PENDING":
      return "#b45309";

    default:
      return "#64748b";
  }
}

function getValidationValue(value) {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

// --------------------------------------------------
// MAIN APP
// --------------------------------------------------

function App() {
  // Authentication
  const [token, setToken] = useState(() =>
    localStorage.getItem("clearentry_token")
  );

  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(
        localStorage.getItem("clearentry_user") || "null"
      );
    } catch {
      return null;
    }
  });

  const [email, setEmail] = useState("manager@clearentry.ai");
  const [password, setPassword] = useState("Manager@123");

  // Navigation
  const [activePage, setActivePage] = useState("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Shipments
  const [shipments, setShipments] = useState([]);
  const [selectedShipmentId, setSelectedShipmentId] = useState("");

  // Create shipment
  const [showCreateShipmentForm, setShowCreateShipmentForm] = useState(false);
  const [creatingShipment, setCreatingShipment] = useState(false);

  const [newShipment, setNewShipment] = useState({
    shipment_number: "",
    importer: "",
    supplier: "",
    origin_country: "",
  });

  // Documents
  const [documents, setDocuments] = useState([]);
  const [selectedDocumentType, setSelectedDocumentType] = useState("invoice");
  const [selectedFile, setSelectedFile] = useState(null);

  // Document extraction
  const [extractionResult, setExtractionResult] = useState(null);
  const [selectedExtractionDocument, setSelectedExtractionDocument] =
    useState(null);

  // Human review
  const [reviewDocumentId, setReviewDocumentId] = useState("");
  const [reviewExtraction, setReviewExtraction] = useState(null);
  const [reviewLoading, setReviewLoading] = useState(false);

  // Original PDF preview
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");

  // Corrections
  const [correctionField, setCorrectionField] = useState("");
  const [correctionValue, setCorrectionValue] = useState("");
  const [correctionReason, setCorrectionReason] = useState("");
  const [savingCorrection, setSavingCorrection] = useState(false);
  const [correctionHistory, setCorrectionHistory] = useState([]);

  // Validation and approval
  const [validationResult, setValidationResult] = useState(null);
  const [validating, setValidating] = useState(false);
  const [approving, setApproving] = useState(false);

  // Excel export and export history
  const [exporting, setExporting] = useState(false);
  const [exportHistory, setExportHistory] = useState([]);
  const [loadingExportHistory, setLoadingExportHistory] = useState(false);

  // Loading states
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [extractingDocumentId, setExtractingDocumentId] = useState(null);
  const [openingDocumentId, setOpeningDocumentId] = useState(null);
  const [downloadingDocumentId, setDownloadingDocumentId] = useState(null);

  // Notifications
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // --------------------------------------------------
  // DERIVED DATA
  // --------------------------------------------------

  const selectedShipment = useMemo(
    () =>
      shipments.find(
        (shipment) =>
          String(shipment.id) === String(selectedShipmentId)
      ),
    [shipments, selectedShipmentId]
  );

  const totalShipments = shipments.length;

  const awaitingDocuments = shipments.filter((shipment) =>
    String(shipment.status || "").toLowerCase().includes("awaiting")
  ).length;

  const underReview = shipments.filter((shipment) =>
    String(shipment.status || "").toLowerCase().includes("review")
  ).length;

  const approved = shipments.filter((shipment) =>
    String(shipment.status || "").toLowerCase().includes("approved")
  ).length;

  // --------------------------------------------------
  // EFFECTS
  // --------------------------------------------------

  useEffect(() => {
    if (token) {
      fetchShipments();
    } else {
      setShipments([]);
      setDocuments([]);
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (token && selectedShipmentId) {
      fetchDocuments(selectedShipmentId);
    } else {
      setDocuments([]);
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selectedShipmentId]);

  useEffect(() => {
    setReviewDocumentId("");
    setReviewExtraction(null);
    setCorrectionHistory([]);
    setValidationResult(null);
    setExportHistory([]);
    setCorrectionField("");
    setCorrectionValue("");
    setCorrectionReason("");
  }, [selectedShipmentId]);

  useEffect(() => {
    if (!reviewDocumentId) {
      setPreviewUrl("");
      setPreviewError("");
      setPreviewLoading(false);
      return;
    }

    let cancelled = false;
    let currentUrl = "";

    async function loadPreview() {
      setPreviewLoading(true);
      setPreviewError("");
      setPreviewUrl("");

      try {
        const url = await getDocumentPreviewUrl(reviewDocumentId);

        if (cancelled) {
          revokeDocumentPreviewUrl(url);
          return;
        }

        currentUrl = url;
        setPreviewUrl(url);
      } catch (err) {
        if (!cancelled) {
          setPreviewError(
            getErrorMessage(err) ||
              "Unable to load the original PDF."
          );
        }
      } finally {
        if (!cancelled) {
          setPreviewLoading(false);
        }
      }
    }

    loadPreview();

    return () => {
      cancelled = true;

      if (currentUrl) {
        revokeDocumentPreviewUrl(currentUrl);
      }
    };
  }, [reviewDocumentId]);

  // --------------------------------------------------
  // API FUNCTIONS
  // --------------------------------------------------

  async function fetchShipments() {
    setLoading(true);
    setError("");

    try {
      const data = await getShipments();

      const shipmentList = Array.isArray(data)
        ? data
        : data?.shipments || [];

      setShipments(shipmentList);

      if (shipmentList.length > 0) {
        setSelectedShipmentId((currentId) => {
          const stillExists = shipmentList.some(
            (shipment) =>
              String(shipment.id) === String(currentId)
          );

          if (currentId && stillExists) {
            return currentId;
          }

          return String(shipmentList[0].id);
        });
      } else {
        setSelectedShipmentId("");
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function fetchDocuments(shipmentId) {
    if (!shipmentId) {
      setDocuments([]);
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data = await getShipmentDocuments(shipmentId);

      const documentList = Array.isArray(data)
        ? data
        : data?.documents || [];

      setDocuments(documentList);
    } catch (err) {
      setDocuments([]);
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }
  // --------------------------------------------------
  // CREATE NEW SHIPMENT
  // --------------------------------------------------

  function openCreateShipmentForm() {
    setNewShipment({
      shipment_number: "",
      importer: "",
      supplier: "",
      origin_country: "",
    });

    setError("");
    setSuccess("");
    setShowCreateShipmentForm(true);
    setActivePage("shipments");
    setSidebarOpen(false);
  }

  async function handleCreateShipment(event) {
    event.preventDefault();

    const shipmentNumber = newShipment.shipment_number.trim();
    const importer = newShipment.importer.trim();

    if (!shipmentNumber) {
      setError("Please enter a shipment number.");
      return;
    }

    if (!importer) {
      setError("Please enter the importer name.");
      return;
    }

    if (!token) {
      setError("Your session has expired. Please log in again.");
      return;
    }

    const payload = {
      shipment_number: shipmentNumber.toUpperCase(),
      importer,
      supplier: newShipment.supplier.trim() || null,
      origin_country: newShipment.origin_country.trim() || null,
    };

    setCreatingShipment(true);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/shipments",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            `Shipment creation failed. HTTP ${response.status}`
        );
      }

      // Close and reset the form.
      setShowCreateShipmentForm(false);

      setNewShipment({
        shipment_number: "",
        importer: "",
        supplier: "",
        origin_country: "",
      });

      // Refresh the shipment list.
      const updatedShipments = await getShipments();

      const shipmentList = Array.isArray(updatedShipments)
        ? updatedShipments
        : updatedShipments?.shipments || [];

      setShipments(shipmentList);

      // Select the newly created shipment.
      if (data.id) {
        setSelectedShipmentId(String(data.id));
      }

      setSuccess(
        `${data.shipment_number || payload.shipment_number} created successfully.`
      );
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setCreatingShipment(false);
    }
  }
  // --------------------------------------------------
  // AUTHENTICATION
  // --------------------------------------------------

  async function handleLogin(event) {
    event.preventDefault();

    setError("");
    setSuccess("");
    setLoading(true);

    try {
      const data = await login(email, password);

      if (!data.access_token) {
        throw new Error(
          "The login response did not contain an access token."
        );
      }

      localStorage.setItem("clearentry_token", data.access_token);
      localStorage.setItem(
        "clearentry_user",
        JSON.stringify(data.user || {})
      );

      setToken(data.access_token);
      setUser(data.user || null);
      setActivePage("dashboard");
      setSuccess("Login successful.");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem("clearentry_token");
    localStorage.removeItem("clearentry_user");

    setToken(null);
    setUser(null);

    setShipments([]);
    setDocuments([]);
    setSelectedShipmentId("");

    setExtractionResult(null);
    setSelectedExtractionDocument(null);

    setReviewDocumentId("");
    setReviewExtraction(null);
    setCorrectionHistory([]);
    setValidationResult(null);
    setExportHistory([]);

    setActivePage("dashboard");
    setError("");
    setSuccess("");
  }

  // --------------------------------------------------
  // DOCUMENT UPLOAD
  // --------------------------------------------------

  async function handleUpload(event) {
    event.preventDefault();

    if (!selectedShipmentId) {
      setError("Please select a shipment first.");
      return;
    }

    if (!selectedFile) {
      setError("Please choose a PDF file to upload.");
      return;
    }

    if (selectedFile.type !== "application/pdf") {
      setError("Please upload a PDF file.");
      return;
    }

    setUploading(true);
    setError("");
    setSuccess("");

    setExtractionResult(null);
    setSelectedExtractionDocument(null);

    try {
      await uploadDocument(
        selectedShipmentId,
        selectedDocumentType,
        selectedFile
      );

      setSuccess(`${selectedFile.name} uploaded successfully.`);
      setSelectedFile(null);

      const fileInput = document.getElementById("document-file-input");

      if (fileInput) {
        fileInput.value = "";
      }

      setExportHistory([]);
      setValidationResult(null);

      await fetchDocuments(selectedShipmentId);
      await fetchShipments();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  // --------------------------------------------------
  // DOCUMENT EXTRACTION
  // --------------------------------------------------

  async function handleExtract(document) {
    const documentId = getDocumentId(document);

    if (!documentId) {
      setError("The document ID is missing.");
      return;
    }

    setExtractingDocumentId(documentId);
    setError("");
    setSuccess("");

    setExtractionResult(null);
    setSelectedExtractionDocument(document);

    try {
      const result = await extractDocument(documentId);

      setExtractionResult(result);
      setSuccess("AI extraction completed successfully.");

      const updatedDocuments = await getShipmentDocuments(
        selectedShipmentId
      );

      const documentList = Array.isArray(updatedDocuments)
        ? updatedDocuments
        : updatedDocuments?.documents || [];

      setDocuments(documentList);
      setValidationResult(null);
      setExportHistory([]);
      await fetchShipments();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setExtractingDocumentId(null);
    }
  }

  // --------------------------------------------------
  // OPEN AND DOWNLOAD DOCUMENTS
  // --------------------------------------------------

  async function handleOpenDocument(document) {
    const documentId = getDocumentId(document);

    if (!documentId) {
      setError("The document ID is missing.");
      return;
    }

    setOpeningDocumentId(documentId);
    setError("");

    try {
      await openDocument(documentId);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setOpeningDocumentId(null);
    }
  }

  async function handleDownloadDocument(document) {
    const documentId = getDocumentId(document);

    if (!documentId) {
      setError("The document ID is missing.");
      return;
    }

    setDownloadingDocumentId(documentId);
    setError("");

    try {
      await downloadDocument(
        documentId,
        getDocumentName(document)
      );

      setSuccess("Document download started.");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setDownloadingDocumentId(null);
    }
  }

  // --------------------------------------------------
  // HUMAN REVIEW
  // --------------------------------------------------

  async function loadReviewExtraction(documentId) {
    if (!documentId) {
      setError("Please select a document.");
      return;
    }

    setReviewLoading(true);
    setError("");
    setSuccess("");
    setReviewExtraction(null);

    try {
      const response = await getExtraction(documentId);
      const extracted = normalizeExtractionResponse(response);

      setReviewExtraction(extracted);
      setReviewDocumentId(String(documentId));

      setSuccess("Extracted information loaded for human review.");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setReviewLoading(false);
    }
  }

  // --------------------------------------------------
  // CORRECTION HISTORY
  // --------------------------------------------------

  async function loadCorrectionHistory() {
    if (!selectedShipmentId) {
      setError("Please select a shipment first.");
      return;
    }

    try {
      const response = await getCorrectionHistory(selectedShipmentId);

      const history = Array.isArray(response)
        ? response
        : response?.corrections || [];

      setCorrectionHistory(history);
    } catch (err) {
      setCorrectionHistory([]);
      setError(getErrorMessage(err));
    }
  }

  // --------------------------------------------------
  // SAVE HUMAN CORRECTION
  // --------------------------------------------------

  async function handleSaveCorrection(event) {
    event.preventDefault();

    if (!reviewDocumentId) {
      setError("Select a document before correcting a field.");
      return;
    }

    if (!correctionField || !correctionValue.trim()) {
      setError("Select a field and enter its corrected value.");
      return;
    }

    if (correctionReason.trim().length < 5) {
      setError(
        "Please provide a correction reason of at least 5 characters."
      );
      return;
    }

    setSavingCorrection(true);
    setError("");
    setSuccess("");

    try {
      await saveCorrection(
        reviewDocumentId,
        correctionField,
        correctionValue.trim(),
        correctionReason.trim()
      );

      setSuccess("Correction saved successfully.");

      const currentDocumentId = reviewDocumentId;

      setCorrectionField("");
      setCorrectionValue("");
      setCorrectionReason("");

      const response = await getExtraction(currentDocumentId);

      setReviewExtraction(normalizeExtractionResponse(response));

      await loadCorrectionHistory();
      await fetchShipments();

      setValidationResult(null);
      setExportHistory([]);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSavingCorrection(false);
    }
  }

  // --------------------------------------------------
  // CROSS-DOCUMENT VALIDATION
  // --------------------------------------------------

  async function handleValidateShipment() {
    if (!selectedShipmentId) {
      setError("Please select a shipment first.");
      return;
    }

    setValidating(true);
    setError("");
    setSuccess("");

    try {
      const response = await validateShipment(selectedShipmentId);
      const result = response?.validation || response;

      setValidationResult(result);

      await loadCorrectionHistory();
      await fetchShipments();

      setSuccess("Shipment validation completed.");
    } catch (err) {
      console.error("Validation error:", err);
      setError(getErrorMessage(err));
    } finally {
      setValidating(false);
    }
  }

  // --------------------------------------------------
  // MANAGER APPROVAL
  // --------------------------------------------------

  async function handleApproveShipment() {
    if (String(user?.role || "").toLowerCase() !== "manager") {
      setError("Only a manager can approve a shipment.");
      return;
    }

    if (!selectedShipmentId) {
      setError("Select a shipment before approval.");
      return;
    }

    setApproving(true);
    setError("");
    setSuccess("");

    try {
      const result = await approveShipment(selectedShipmentId);

      setSuccess(
        result?.message || "Shipment approved successfully."
      );

      setValidationResult(null);
      setExportHistory([]);

      await fetchShipments();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setApproving(false);
    }
  }

  // --------------------------------------------------
  // EXCEL EXPORT AND EXPORT HISTORY
  // --------------------------------------------------

  async function loadExportHistory() {
    if (!selectedShipmentId) {
      setError("Please select a shipment first.");
      return;
    }

    setLoadingExportHistory(true);
    setError("");

    try {
      const response = await getShipmentExports(selectedShipmentId);

      const history = Array.isArray(response)
        ? response
        : response?.exports || response?.history || [];

      setExportHistory(history);
    } catch (err) {
      setExportHistory([]);
      setError(getErrorMessage(err));
    } finally {
      setLoadingExportHistory(false);
    }
  }

  async function handleExportShipment() {
    if (!selectedShipmentId) {
      setError("Please select a shipment first.");
      return;
    }

    if (String(user?.role || "").toLowerCase() !== "manager") {
      setError("Only a manager can export a shipment.");
      return;
    }

    setExporting(true);
    setError("");
    setSuccess("");

    try {
      const result = await exportShipment(selectedShipmentId);

      setSuccess(
        `Excel export generated successfully: ${
          result?.filename || "Shipment export.xlsx"
        }`
      );

      await loadExportHistory();
      await fetchShipments();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setExporting(false);
    }
  }

  async function handleDownloadPreviousExport(item) {
    const exportId = item?.id ?? item?.export_id;

    if (!exportId) {
      setError("Export ID is missing.");
      return;
    }

    setError("");

    try {
      await downloadShipmentExport(
        exportId,
        item.filename || `ClearEntry_Export_${exportId}.xlsx`
      );

      setSuccess("Previous Excel export downloaded successfully.");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  // --------------------------------------------------
  // NAVIGATION
  // --------------------------------------------------

  function navigateTo(page) {
    setActivePage(page);
    setSidebarOpen(false);
    setError("");
    setSuccess("");
  }

  // --------------------------------------------------
  // SIDEBAR
  // --------------------------------------------------

  function renderSidebar() {
    return (
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="sidebar-brand">
          <div className="brand-icon">
            <Package size={23} />
          </div>

          <div>
            <h2>ClearEntry AI</h2>
            <span>Customs Documentation</span>
          </div>

          <button
            className="sidebar-close"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close navigation"
          >
            <X size={19} />
          </button>
        </div>

        <div className="sidebar-section-label">WORKSPACE</div>

        <nav className="sidebar-nav">
          <button
            className={activePage === "dashboard" ? "nav-item active" : "nav-item"}
            onClick={() => navigateTo("dashboard")}
          >
            <LayoutDashboard size={18} />
            <span>Dashboard</span>
          </button>

          <button
            className={activePage === "documents" ? "nav-item active" : "nav-item"}
            onClick={() => navigateTo("documents")}
          >
            <FolderOpen size={18} />
            <span>Documents</span>
          </button>

          <button
            className={activePage === "shipments" ? "nav-item active" : "nav-item"}
            onClick={() => navigateTo("shipments")}
          >
            <Package size={18} />
            <span>Shipments</span>
          </button>

          <button
            className={activePage === "review" ? "nav-item active" : "nav-item"}
            onClick={() => navigateTo("review")}
          >
            <ClipboardList size={18} />
            <span>Review Queue</span>
          </button>
        </nav>

        <div className="sidebar-section-label">SYSTEM</div>

        <nav className="sidebar-nav">
          <button
            className={activePage === "settings" ? "nav-item active" : "nav-item"}
            onClick={() => navigateTo("settings")}
          >
            <Settings size={18} />
            <span>Settings</span>
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-user">
            <div className="user-avatar">
              <User size={18} />
            </div>

            <div className="sidebar-user-info">
              <strong>{user?.name || "ClearEntry User"}</strong>
              <span>{user?.role || "User"}</span>
            </div>

            <button
              className="logout-button"
              onClick={handleLogout}
              title="Log out"
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
    );
  }

  // --------------------------------------------------
  // PAGE HEADER
  // --------------------------------------------------

  function renderHeader(title, subtitle) {
    return (
      <header className="page-header">
        <div className="page-header-left">
          <button
            className="mobile-menu-button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={21} />
          </button>

          <div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
        </div>

        <div className="header-actions">
          <div className="header-user">
            <div className="user-avatar">
              <User size={17} />
            </div>

            <span>{user?.name || "User"}</span>
            <ChevronDown size={15} />
          </div>
        </div>
      </header>
    );
  }

  // --------------------------------------------------
  // NOTIFICATIONS
  // --------------------------------------------------

  function renderNotifications() {
    return (
      <>
        {error && (
          <div className="notification error-message">
            <AlertCircle size={18} />

            <span style={{ whiteSpace: "pre-wrap" }}>
              {String(error)}
            </span>

            <button
              onClick={() => setError("")}
              aria-label="Dismiss error"
            >
              <X size={16} />
            </button>
          </div>
        )}

        {success && (
          <div className="notification success-message">
            <CheckCircle size={18} />

            <span>{success}</span>

            <button
              onClick={() => setSuccess("")}
              aria-label="Dismiss message"
            >
              <X size={16} />
            </button>
          </div>
        )}
      </>
    );
  }

  // --------------------------------------------------
  // DASHBOARD
  // --------------------------------------------------

  function renderDashboard() {
    return (
      <>
        {renderHeader(
          "Dashboard",
          "Monitor your import shipments and documentation workflow."
        )}

        {renderNotifications()}

        <main className="page-content">
          <div className="dashboard-actions">
            <div>
              <h2>Overview</h2>
              <p>Your shipment activity at a glance</p>
            </div>

            <button
              className="primary-button"
              onClick={openCreateShipmentForm}
            >
              <Package size={17} />
              New shipment
            </button>
          </div>

          <section className="stats-grid">
            <div className="stat-card">
              <div className="stat-card-top">
                <span>Total shipments</span>
                <div className="stat-icon blue"><Package size={20} /></div>
              </div>
              <strong>{totalShipments}</strong>
              <small>In your workspace</small>
            </div>

            <div className="stat-card">
              <div className="stat-card-top">
                <span>Awaiting documents</span>
                <div className="stat-icon orange"><FileText size={20} /></div>
              </div>
              <strong>{awaitingDocuments}</strong>
              <small>Documents required</small>
            </div>

            <div className="stat-card">
              <div className="stat-card-top">
                <span>Under review</span>
                <div className="stat-icon purple"><Activity size={20} /></div>
              </div>
              <strong>{underReview}</strong>
              <small>Pending verification</small>
            </div>

            <div className="stat-card">
              <div className="stat-card-top">
                <span>Approved</span>
                <div className="stat-icon green"><ShieldCheck size={20} /></div>
              </div>
              <strong>{approved}</strong>
              <small>Ready for export</small>
            </div>
          </section>

          <section className="content-card">
            <div className="section-heading">
              <div>
                <h2>Recent shipments</h2>
                <p>Your latest import shipment records</p>
              </div>

              <button
                className="secondary-button"
                onClick={fetchShipments}
                disabled={loading}
              >
                <RefreshCw size={16} />
                Refresh
              </button>
            </div>

            <div className="table-responsive">
              <table className="shipment-table">
                <thead>
                  <tr>
                    <th>SHIPMENT ID</th>
                    <th>IMPORTER</th>
                    <th>SUPPLIER</th>
                    <th>ORIGIN</th>
                    <th>STATUS</th>
                    <th>ACTION</th>
                  </tr>
                </thead>

                <tbody>
                  {shipments.map((shipment) => (
                    <tr key={shipment.id}>
                      <td><strong>{shipment.shipment_number}</strong></td>
                      <td>{shipment.importer}</td>
                      <td>{shipment.supplier || "Not specified"}</td>
                      <td>{shipment.origin_country || "Not specified"}</td>
                      <td>
                        <span className={`status-badge ${String(
                          shipment.status || ""
                        ).toLowerCase().replace(/\s+/g, "-")}`}>
                          {shipment.status}
                        </span>
                      </td>
                      <td>
                        <button
                          className="table-action"
                          onClick={() => {
                            setSelectedShipmentId(String(shipment.id));
                            navigateTo("documents");
                          }}
                        >
                          Open
                        </button>
                      </td>
                    </tr>
                  ))}

                  {shipments.length === 0 && (
                    <tr>
                      <td colSpan="6" className="empty-state">
                        {loading ? "Loading shipments..." : "No shipments found."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="table-footer">
              Showing {shipments.length} of {shipments.length} shipments
            </div>
          </section>

          <div className="workflow-banner">
            <div className="workflow-banner-icon">
              <Sparkles size={22} />
            </div>

            <div>
              <h3>AI-powered documentation workflow</h3>
              <p>
                Upload your shipment documents and let AI extract
                and cross-check important information.
              </p>
            </div>

            <button
              className="secondary-button"
              onClick={() => navigateTo("documents")}
            >
              Go to Documents
            </button>
          </div>
        </main>
      </>
    );
  }

  // --------------------------------------------------
  // DOCUMENTS PAGE
  // --------------------------------------------------

  function renderDocuments() {
    return (
      <>
        {renderHeader(
          "Documents",
          "Upload, view and extract information from your shipment documents."
        )}

        {renderNotifications()}

        <main className="page-content">
          <section className="content-card document-panel">
            <div className="section-heading">
              <div>
                <h2>Shipment documents</h2>
                <p>Select a shipment to manage its documents.</p>
              </div>

              <button
                className="secondary-button"
                onClick={() => fetchDocuments(selectedShipmentId)}
                disabled={!selectedShipmentId || loading}
              >
                <RefreshCw size={16} />
                Refresh
              </button>
            </div>

            <div className="form-field shipment-selector">
              <label htmlFor="shipment-select">Select shipment</label>

              <select
                id="shipment-select"
                value={selectedShipmentId}
                onChange={(event) => {
                  setSelectedShipmentId(event.target.value);
                  setExtractionResult(null);
                  setSelectedExtractionDocument(null);
                  setSuccess("");
                }}
              >
                <option value="">Choose a shipment</option>

                {shipments.map((shipment) => (
                  <option key={shipment.id} value={shipment.id}>
                    {shipment.shipment_number} | {shipment.importer} | {shipment.status}
                  </option>
                ))}
              </select>
            </div>

            {selectedShipment && (
              <div className="selected-shipment-summary">
                <div>
                  <span>Shipment ID</span>
                  <strong>{selectedShipment.shipment_number}</strong>
                </div>
                <div>
                  <span>Importer</span>
                  <strong>{selectedShipment.importer}</strong>
                </div>
                <div>
                  <span>Supplier</span>
                  <strong>{selectedShipment.supplier || "Not specified"}</strong>
                </div>
                <div>
                  <span>Status</span>
                  <strong>{selectedShipment.status}</strong>
                </div>
              </div>
            )}
          </section>

          <section className="content-card document-panel">
            <div className="section-heading">
              <div>
                <h2>Upload documents</h2>
                <p>Upload the invoice, packing list and Bill of Lading as PDF files.</p>
              </div>
              <div className="upload-heading-icon"><Upload size={21} /></div>
            </div>

            <form onSubmit={handleUpload} className="document-upload-form">
              <div className="form-field">
                <label htmlFor="document-type">Document type</label>
                <select
                  id="document-type"
                  value={selectedDocumentType}
                  onChange={(event) => setSelectedDocumentType(event.target.value)}
                >
                  {DOCUMENT_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label htmlFor="document-file-input">Choose PDF file</label>
                <input
                  id="document-file-input"
                  type="file"
                  accept=".pdf,application/pdf"
                  onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
                />

                {selectedFile && (
                  <small className="selected-file-name">
                    Selected: {selectedFile.name}
                  </small>
                )}
              </div>

              <button
                type="submit"
                className="primary-button upload-submit"
                disabled={uploading || !selectedShipmentId}
              >
                <Upload size={17} />
                {uploading ? "Uploading..." : "Upload document"}
              </button>
            </form>
          </section>

          <section className="content-card document-panel">
            <div className="section-heading">
              <div>
                <h2>Uploaded documents</h2>
                <p>
                  {selectedShipment
                    ? `Documents attached to ${selectedShipment.shipment_number}.`
                    : "Choose a shipment to view its uploaded documents."}
                </p>
              </div>

              <span className="document-count">
                {documents.length} document{documents.length === 1 ? "" : "s"}
              </span>
            </div>

            {!selectedShipmentId ? (
              <div className="empty-state">
                Select a shipment to view its documents.
              </div>
            ) : documents.length === 0 ? (
              <div className="empty-state">
                <FileText size={28} />
                <strong>No documents uploaded yet</strong>
                <span>Upload an invoice, packing list or Bill of Lading above.</span>
              </div>
            ) : (
              <div className="document-list">
                {documents.map((document) => {
                  const documentId = getDocumentId(document);

                  return (
                    <div className="document-item" key={documentId}>
                      <div className="document-item-icon">
                        <FileText size={22} />
                      </div>

                      <div className="document-item-info">
                        <strong>{getDocumentName(document)}</strong>
                        <span>{getDocumentTypeLabel(document.document_type)}</span>

                        {document.uploaded_at && (
                          <small>
                            Uploaded: {new Date(document.uploaded_at).toLocaleString()}
                          </small>
                        )}
                      </div>

                      <div className="document-item-actions">
                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => handleOpenDocument(document)}
                          disabled={openingDocumentId === documentId}
                          title="Open PDF in a new tab"
                        >
                          <Eye size={16} />
                          {openingDocumentId === documentId ? "Opening..." : "Open PDF"}
                        </button>

                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => handleDownloadDocument(document)}
                          disabled={downloadingDocumentId === documentId}
                          title="Download original PDF"
                        >
                          <Download size={16} />
                          {downloadingDocumentId === documentId ? "Downloading..." : "Download"}
                        </button>

                        <button
                          type="button"
                          className="primary-button"
                          onClick={() => handleExtract(document)}
                          disabled={extractingDocumentId === documentId}
                        >
                          <Sparkles size={16} />
                          {extractingDocumentId === documentId ? "Extracting..." : "Extract with AI"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {extractionResult && (
            <section className="content-card extraction-panel">
              <div className="section-heading">
                <div>
                  <h2>AI extraction result</h2>
                  <p>
                    Extracted information from {getDocumentName(selectedExtractionDocument)}.
                  </p>
                </div>

                <span className="status-badge under-review">
                  <Activity size={14} />
                  Requires human review
                </span>
              </div>

              <div className="extraction-result">
                <pre>{JSON.stringify(extractionResult, null, 2)}</pre>
              </div>

              <p className="extraction-note">
                AI-extracted values must be checked against the original
                document before approval or export.
              </p>
            </section>
          )}
        </main>
      </>
    );
  }

  // --------------------------------------------------
  // SHIPMENTS PAGE
  // --------------------------------------------------

  // --------------------------------------------------
  // SHIPMENTS PAGE
  // --------------------------------------------------

  function renderShipments() {
    return (
      <>
        {renderHeader(
          "Shipments",
          "View and manage your import shipment records."
        )}

        {renderNotifications()}

        <main className="page-content">

          {/* CREATE SHIPMENT FORM */}

          {showCreateShipmentForm && (
            <section className="content-card document-panel">
              <div className="section-heading">
                <div>
                  <h2>Create new shipment</h2>
                  <p>
                    Enter the shipment details to create a new import record.
                  </p>
                </div>

                <Package size={22} />
              </div>

              <form
                className="document-upload-form"
                onSubmit={handleCreateShipment}
              >
                <div className="form-field">
                  <label htmlFor="new-shipment-number">
                    Shipment number *
                  </label>

                  <input
                    id="new-shipment-number"
                    type="text"
                    value={newShipment.shipment_number}
                    onChange={(event) =>
                      setNewShipment((previous) => ({
                        ...previous,
                        shipment_number: event.target.value,
                      }))
                    }
                    placeholder="Example: SHP-24814"
                    required
                  />
                </div>

                <div className="form-field">
                  <label htmlFor="new-shipment-importer">
                    Importer *
                  </label>

                  <input
                    id="new-shipment-importer"
                    type="text"
                    value={newShipment.importer}
                    onChange={(event) =>
                      setNewShipment((previous) => ({
                        ...previous,
                        importer: event.target.value,
                      }))
                    }
                    placeholder="Enter importer company name"
                    required
                  />
                </div>

                <div className="form-field">
                  <label htmlFor="new-shipment-supplier">
                    Supplier
                  </label>

                  <input
                    id="new-shipment-supplier"
                    type="text"
                    value={newShipment.supplier}
                    onChange={(event) =>
                      setNewShipment((previous) => ({
                        ...previous,
                        supplier: event.target.value,
                      }))
                    }
                    placeholder="Enter supplier company name"
                  />
                </div>

                <div className="form-field">
                  <label htmlFor="new-shipment-origin">
                    Origin country
                  </label>

                  <input
                    id="new-shipment-origin"
                    type="text"
                    value={newShipment.origin_country}
                    onChange={(event) =>
                      setNewShipment((previous) => ({
                        ...previous,
                        origin_country: event.target.value,
                      }))
                    }
                    placeholder="Example: China"
                  />
                </div>

                <div
                  style={{
                    display: "flex",
                    gap: "12px",
                    flexWrap: "wrap",
                    marginTop: "10px",
                  }}
                >
                  <button
                    type="submit"
                    className="primary-button"
                    disabled={creatingShipment}
                  >
                    <Package size={17} />
                    {creatingShipment
                      ? "Creating shipment..."
                      : "Create shipment"}
                  </button>

                  <button
                    type="button"
                    className="secondary-button"
                    disabled={creatingShipment}
                    onClick={() => {
                      setShowCreateShipmentForm(false);
                      setError("");
                    }}
                  >
                    <X size={16} />
                    Cancel
                  </button>
                </div>

                <p className="extraction-note">
                  Fields marked with * are required. A new shipment
                  will initially have the status Awaiting Documents.
                </p>
              </form>
            </section>
          )}

          {/* ALL SHIPMENTS */}

          <section className="content-card">
            <div className="section-heading">
              <div>
                <h2>All shipments</h2>
                <p>Your current shipment records.</p>
              </div>

              <div
                style={{
                  display: "flex",
                  gap: "10px",
                  flexWrap: "wrap",
                }}
              >
                <button
                  className="secondary-button"
                  onClick={fetchShipments}
                  disabled={loading}
                >
                  <RefreshCw size={16} />
                  Refresh
                </button>

                <button
                  className="primary-button"
                  onClick={openCreateShipmentForm}
                >
                  <Package size={17} />
                  New shipment
                </button>
              </div>
            </div>

            <div className="table-responsive">
              <table className="shipment-table">
                <thead>
                  <tr>
                    <th>SHIPMENT ID</th>
                    <th>IMPORTER</th>
                    <th>SUPPLIER</th>
                    <th>ORIGIN</th>
                    <th>STATUS</th>
                    <th>ACTION</th>
                  </tr>
                </thead>

                <tbody>
                  {shipments.map((shipment) => (
                    <tr key={shipment.id}>
                      <td>
                        <strong>{shipment.shipment_number}</strong>
                      </td>

                      <td>{shipment.importer}</td>

                      <td>
                        {shipment.supplier || "Not specified"}
                      </td>

                      <td>
                        {shipment.origin_country || "Not specified"}
                      </td>

                      <td>
                        <span className="status-badge">
                          {shipment.status}
                        </span>
                      </td>

                      <td>
                        <button
                          className="table-action"
                          onClick={() => {
                            setSelectedShipmentId(String(shipment.id));
                            navigateTo("documents");
                          }}
                        >
                          Open
                        </button>
                      </td>
                    </tr>
                  ))}

                  {shipments.length === 0 && (
                    <tr>
                      <td colSpan="6" className="empty-state">
                        {loading
                          ? "Loading shipments..."
                          : "No shipments found. Create your first shipment."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="table-footer">
              Showing {shipments.length} of {shipments.length} shipments
            </div>
          </section>
        </main>
      </>
    );
  }

  // --------------------------------------------------
  // HUMAN REVIEW QUEUE
  // --------------------------------------------------

  function renderReviewQueue() {
    const selectedReviewDocument = documents.find(
      (document) =>
        String(getDocumentId(document)) === String(reviewDocumentId)
    );

    const reviewFields =
      REVIEW_FIELDS_BY_TYPE[selectedReviewDocument?.document_type] ||
      REVIEW_FIELDS;

    const confidence = reviewExtraction?.field_confidence || {};
    const evidence = reviewExtraction?.evidence || {};
    const verifiedFields = reviewExtraction?.human_verified_fields || [];

    const validationChecks = Array.isArray(validationResult?.checks)
      ? validationResult.checks
      : Array.isArray(validationResult?.results)
        ? validationResult.results
        : [];

    const overallStatus =
      validationResult?.overall_status ||
      validationResult?.status ||
      "NOT_VALIDATED";

    const validationSummary = validationResult?.summary || {};

    const isManager =
      String(user?.role || "").toLowerCase() === "manager";

    return (
      <>
        {renderHeader(
          "Human Review",
          "Verify AI-extracted shipment information before approval."
        )}

        {renderNotifications()}

        <main className="page-content">
          <section className="content-card document-panel">
            <div className="section-heading">
              <div>
                <h2>Select shipment and document</h2>
                <p>Choose a shipment and load its AI extraction for review.</p>
              </div>
              <ClipboardList size={22} />
            </div>

            <div className="form-field">
              <label htmlFor="review-shipment-select">Shipment</label>

              <select
                id="review-shipment-select"
                value={selectedShipmentId}
                onChange={(event) => {
                  setSelectedShipmentId(event.target.value);
                }}
              >
                <option value="">Choose a shipment</option>

                {shipments.map((shipment) => (
                  <option key={shipment.id} value={shipment.id}>
                    {shipment.shipment_number} | {shipment.importer}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label htmlFor="review-document-select">Document</label>

              <select
                id="review-document-select"
                value={reviewDocumentId}
                onChange={(event) => {
                  setReviewDocumentId(event.target.value);
                  setReviewExtraction(null);
                  setCorrectionField("");
                  setCorrectionValue("");
                  setCorrectionReason("");
                }}
              >
                <option value="">Choose a document</option>

                {documents.map((document) => (
                  <option
                    key={getDocumentId(document)}
                    value={getDocumentId(document)}
                  >
                    {getDocumentName(document)} (
                    {getDocumentTypeLabel(document.document_type)})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
              <button
                className="primary-button"
                disabled={!reviewDocumentId || reviewLoading}
                onClick={() => loadReviewExtraction(reviewDocumentId)}
              >
                <Eye size={16} />
                {reviewLoading ? "Loading..." : "Load extraction"}
              </button>

              {selectedReviewDocument && (
                <button
                  className="secondary-button"
                  onClick={() => handleOpenDocument(selectedReviewDocument)}
                  disabled={openingDocumentId === getDocumentId(selectedReviewDocument)}
                >
                  <FileText size={16} />
                  Open original PDF
                </button>
              )}

              <button
                className="secondary-button"
                disabled={!selectedShipmentId}
                onClick={loadCorrectionHistory}
              >
                <RefreshCw size={16} />
                Load correction history
              </button>
            </div>

            {selectedReviewDocument && (
              <p style={{ marginTop: "14px", color: "#64748b" }}>
                Selected: <strong>{getDocumentName(selectedReviewDocument)}</strong>
              </p>
            )}
          </section>

          {reviewExtraction && (
            <section className="content-card document-panel">
              <div className="section-heading">
                <div>
                  <h2>Extracted information</h2>
                  <p>Review the AI values against the original document.</p>
                </div>

                <span className="status-badge under-review">
                  Human verification required
                </span>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(min(100%, 420px), 1fr))",
                  gap: "20px",
                  alignItems: "start",
                }}
              >
                <div
                  style={{
                    border: "1px solid #e2e8f0",
                    borderRadius: "12px",
                    padding: "14px",
                    background: "#f8fafc",
                    minWidth: 0,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "10px",
                      marginBottom: "12px",
                    }}
                  >
                    <h3 style={{ margin: 0 }}>Original document</h3>

                    {selectedReviewDocument && (
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() =>
                          handleDownloadDocument(selectedReviewDocument)
                        }
                      >
                        <Download size={15} />
                        Download
                      </button>
                    )}
                  </div>

                  {previewLoading && (
                    <div className="empty-state">
                      <RefreshCw size={22} />
                      Loading original PDF...
                    </div>
                  )}

                  {previewError && (
                    <div className="notification error-message">
                      <AlertCircle size={17} />
                      <span>{previewError}</span>
                    </div>
                  )}

                  {!previewLoading && !previewError && previewUrl && (
                    <iframe
                      title="Original shipment document"
                      src={previewUrl}
                      style={{
                        width: "100%",
                        height: "680px",
                        border: "1px solid #cbd5e1",
                        borderRadius: "8px",
                        background: "#ffffff",
                      }}
                    />
                  )}

                  {!previewLoading && !previewError && !previewUrl && (
                    <div className="empty-state">
                      Select a document to preview its PDF.
                    </div>
                  )}
                </div>

                <div style={{ minWidth: 0 }}>
                  <h3 style={{ marginTop: 0 }}>AI-extracted fields</h3>

                  <div className="table-responsive">
                    <table className="shipment-table">
                      <thead>
                        <tr>
                          <th>FIELD</th>
                          <th>AI VALUE</th>
                          <th>CONFIDENCE</th>
                          <th>VERIFICATION</th>
                          <th>EVIDENCE</th>
                        </tr>
                      </thead>

                      <tbody>
                        {reviewFields.map((field) => {
                          const value = reviewExtraction[field.name];
                          const score = confidence[field.name];
                          const verified = verifiedFields.includes(field.name);

                          const isMissing =
                            value === null ||
                            value === undefined ||
                            value === "";

                          return (
                            <tr key={field.name}>
                              <td><strong>{field.label}</strong></td>

                              <td>
                                {isMissing
                                  ? "Not detected"
                                  : typeof value === "object"
                                    ? JSON.stringify(value)
                                    : String(value)}
                              </td>

                              <td>
                                <strong style={{ color: getConfidenceColor(score) }}>
                                  {getConfidenceLabel(score)}
                                </strong>
                              </td>

                              <td>
                                {verified ? (
                                  <span className="status-badge approved">
                                    Verified
                                  </span>
                                ) : !isMissing && Number(score) >= 0.85 ? (
                                  <span className="status-badge">
                                    AI confidence high
                                  </span>
                                ) : (
                                  <span className="status-badge under-review">
                                    Needs review
                                  </span>
                                )}
                              </td>

                              <td
                                style={{
                                  maxWidth: "250px",
                                  whiteSpace: "normal",
                                }}
                              >
                                {evidence[field.name] || "No evidence returned"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <div className="extraction-note">
                Confidence is the AI model's estimate, not proof that a
                value is correct. Always compare important values with
                the source PDF.
              </div>
            </section>
          )}

          {reviewExtraction && (
            <section className="content-card document-panel">
              <div className="section-heading">
                <div>
                  <h2>Correct an extracted field</h2>
                  <p>
                    Record the verified value and explain why it was changed.
                  </p>
                </div>
              </div>

              <form
                className="document-upload-form"
                onSubmit={handleSaveCorrection}
              >
                <div className="form-field">
                  <label htmlFor="correction-field">Field to correct</label>

                  <select
                    id="correction-field"
                    value={correctionField}
                    onChange={(event) => {
                      const fieldName = event.target.value;

                      setCorrectionField(fieldName);

                      const currentValue = reviewExtraction[fieldName];

                      setCorrectionValue(
                        currentValue === null || currentValue === undefined
                          ? ""
                          : String(currentValue)
                      );
                    }}
                    required
                  >
                    <option value="">Select a field</option>

                    {reviewFields.map((field) => (
                      <option key={field.name} value={field.name}>
                        {field.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-field">
                  <label htmlFor="correction-value">Verified value</label>

                  <input
                    id="correction-value"
                    type="text"
                    value={correctionValue}
                    onChange={(event) => setCorrectionValue(event.target.value)}
                    placeholder="Enter the verified value"
                    required
                  />
                </div>

                <div className="form-field">
                  <label htmlFor="correction-reason">Reason for correction</label>

                  <textarea
                    id="correction-reason"
                    value={correctionReason}
                    onChange={(event) => setCorrectionReason(event.target.value)}
                    placeholder="Explain how you verified this value against the source document."
                    rows={3}
                    minLength={5}
                    required
                  />
                </div>

                <button
                  type="submit"
                  className="primary-button"
                  disabled={savingCorrection}
                >
                  <CheckCircle size={16} />
                  {savingCorrection ? "Saving..." : "Save correction"}
                </button>
              </form>
            </section>
          )}

          <section className="content-card document-panel">
            <div className="section-heading">
              <div>
                <h2>Correction history</h2>
                <p>Human changes recorded for this shipment.</p>
              </div>
            </div>

            {correctionHistory.length === 0 ? (
              <div className="empty-state">
                No correction history loaded.
              </div>
            ) : (
              <div className="table-responsive">
                <table className="shipment-table">
                  <thead>
                    <tr>
                      <th>FIELD</th>
                      <th>OLD VALUE</th>
                      <th>NEW VALUE</th>
                      <th>CORRECTED BY</th>
                      <th>REASON</th>
                    </tr>
                  </thead>

                  <tbody>
                    {correctionHistory.map((item) => (
                      <tr key={item.id}>
                        <td><strong>{item.field_name}</strong></td>
                        <td>{getValidationValue(item.old_value)}</td>
                        <td>{getValidationValue(item.new_value)}</td>
                        <td>{item.corrected_by || "Not available"}</td>
                        <td style={{ whiteSpace: "normal", minWidth: "200px" }}>
                          {item.reason || "No reason provided"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="content-card document-panel">
            <div className="section-heading">
              <div>
                <h2>Cross-document validation</h2>
                <p>
                  Compare invoice, packing list and Bill of Lading information.
                </p>
              </div>
              <Activity size={22} />
            </div>

            <button
              className="primary-button"
              onClick={handleValidateShipment}
              disabled={!selectedShipmentId || validating}
            >
              <RefreshCw size={16} />
              {validating ? "Validating..." : "Validate shipment"}
            </button>

            {validationResult && (
              <div style={{ marginTop: "20px" }}>
                <h3>
                  Validation status:{" "}
                  <span style={{ color: getValidationStatusColor(overallStatus) }}>
                    {overallStatus}
                  </span>
                </h3>

                <div className="stats-grid">
                  <div className="stat-card">
                    <span>Matches</span>
                    <strong>{validationSummary.matches ?? 0}</strong>
                  </div>

                  <div className="stat-card">
                    <span>Mismatches</span>
                    <strong>{validationSummary.mismatches ?? 0}</strong>
                  </div>

                  <div className="stat-card">
                    <span>Pending</span>
                    <strong>{validationSummary.pending ?? 0}</strong>
                  </div>

                  <div className="stat-card">
                    <span>Export allowed</span>
                    <strong>{validationResult.export_allowed ? "Yes" : "No"}</strong>
                  </div>
                </div>

                {validationResult.documents_found && (
                  <div style={{ margin: "16px 0" }}>
                    <h3>Documents detected</h3>

                    <div style={{ display: "flex", flexWrap: "wrap", gap: "12px" }}>
                      {[
                        ["Invoice", "invoice"],
                        ["Packing list", "packing_list"],
                        ["Bill of Lading", "bill_of_lading"],
                      ].map(([label, key]) => (
                        <span
                          key={key}
                          className={`status-badge ${
                            validationResult.documents_found[key]
                              ? "approved"
                              : "under-review"
                          }`}
                        >
                          {label}:{" "}
                          {validationResult.documents_found[key] ? "Found" : "Missing"}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {validationChecks.length > 0 && (
                  <div className="table-responsive">
                    <table className="shipment-table">
                      <thead>
                        <tr>
                          <th>FIELD</th>
                          <th>INVOICE</th>
                          <th>PACKING LIST</th>
                          <th>BILL OF LADING</th>
                          <th>RESULT</th>
                          <th>DETAILS</th>
                        </tr>
                      </thead>

                      <tbody>
                        {validationChecks.map((check, index) => (
                          <tr
                            key={`${
                              check.field || check.field_name || "check"
                            }-${index}`}
                          >
                            <td>
                              <strong>
                                {check.field || check.field_name || "Validation"}
                              </strong>
                            </td>

                            <td>{getValidationValue(check.invoice_value)}</td>
                            <td>{getValidationValue(check.packing_list_value)}</td>
                            <td>{getValidationValue(check.bill_of_lading_value)}</td>

                            <td>
                              <span
                                className="status-badge"
                                style={{
                                  color: getValidationStatusColor(
                                    check.status || check.result
                                  ),
                                }}
                              >
                                {check.status || check.result || "Checked"}
                              </span>
                            </td>

                            <td style={{ whiteSpace: "normal", minWidth: "220px" }}>
                              {check.message || "No additional details"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {validationResult.message && (
                  <p className="extraction-note">
                    {validationResult.message}
                  </p>
                )}

                {!validationResult.export_allowed && (
                  <p style={{ color: "#b45309", marginTop: "12px" }}>
                    <AlertCircle
                      size={16}
                      style={{
                        display: "inline",
                        verticalAlign: "middle",
                        marginRight: "6px",
                      }}
                    />
                    Export is blocked until all required checks pass
                    and the shipment receives manager approval.
                  </p>
                )}
              </div>
            )}
          </section>

          <section className="content-card document-panel">
            <div className="section-heading">
              <div>
                <h2>Shipment approval</h2>
                <p>
                  Manager approval is required before a shipment can be approved for export.
                </p>
              </div>
              <ShieldCheck size={22} />
            </div>

            {isManager ? (
              <>
                <p>
                  Signed in as a manager. The backend will check validation
                  and outstanding review requirements before approving.
                </p>

                <button
                  className="primary-button"
                  onClick={handleApproveShipment}
                  disabled={!selectedShipmentId || approving}
                >
                  <ShieldCheck size={17} />
                  {approving ? "Checking approval..." : "Approve shipment"}
                </button>
              </>
            ) : (
              <p style={{ color: "#b45309" }}>
                Manager access required. Your current role is{" "}
                <strong>{user?.role || "unknown"}</strong>. You can still
                review documents and save corrections.
              </p>
            )}
          </section>

          {/* EXCEL EXPORT AND EXPORT HISTORY */}

          <section className="content-card document-panel">
            <div className="section-heading">
              <div>
                <h2>Excel export</h2>
                <p>
                  Generate the shipment filing workbook after successful
                  validation and manager approval.
                </p>
              </div>

              <Download size={22} />
            </div>

            {isManager ? (
              <>
                <div className="extraction-note">
                  Export is controlled by the backend. The shipment must
                  have all required documents, pass cross-document
                  validation, and receive manager approval.
                </div>

                <button
                  type="button"
                  className="primary-button"
                  onClick={handleExportShipment}
                  disabled={!selectedShipmentId || exporting}
                >
                  <Download size={17} />
                  {exporting
                    ? "Generating Excel..."
                    : "Generate and download Excel"}
                </button>

                <div style={{ marginTop: "24px" }}>
                  <div className="section-heading">
                    <div>
                      <h3>Export history</h3>
                      <p>
                        Previously generated Excel workbooks for this shipment.
                      </p>
                    </div>

                    <button
                      type="button"
                      className="secondary-button"
                      onClick={loadExportHistory}
                      disabled={!selectedShipmentId || loadingExportHistory}
                    >
                      <RefreshCw size={15} />
                      {loadingExportHistory ? "Loading..." : "Refresh history"}
                    </button>
                  </div>

                  {exportHistory.length === 0 ? (
                    <div className="empty-state">
                      {loadingExportHistory
                        ? "Loading export history..."
                        : "No previous exports loaded. Select Refresh history to check."}
                    </div>
                  ) : (
                    <div className="table-responsive">
                      <table className="shipment-table">
                        <thead>
                          <tr>
                            <th>FILENAME</th>
                            <th>EXPORTED BY</th>
                            <th>STATUS</th>
                            <th>DATE</th>
                            <th>ACTION</th>
                          </tr>
                        </thead>

                        <tbody>
                          {exportHistory.map((item, index) => (
                            <tr
                              key={
                                item.id ||
                                item.export_id ||
                                index
                              }
                            >
                              <td>
                                <strong>
                                  {item.filename || "Shipment export.xlsx"}
                                </strong>
                              </td>

                              <td>
                                {item.exported_by || "Not available"}
                              </td>

                              <td>
                                <span className="status-badge approved">
                                  {item.export_status || "Generated"}
                                </span>
                              </td>

                              <td>
                                {item.exported_at
                                  ? new Date(
                                      item.exported_at
                                    ).toLocaleString()
                                  : "Not available"}
                              </td>

                              <td>
                                <button
                                  type="button"
                                  className="secondary-button"
                                  onClick={() =>
                                    handleDownloadPreviousExport(item)
                                  }
                                >
                                  <Download size={15} />
                                  Download
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <p style={{ color: "#b45309" }}>
                Manager access is required to generate and download
                the filing workbook. Your current role is{" "}
                <strong>{user?.role || "unknown"}</strong>.
              </p>
            )}
          </section>
        </main>
      </>
    );
  }

  // --------------------------------------------------
  // SETTINGS PAGE
  // --------------------------------------------------

  function renderSettings() {
    return (
      <>
        {renderHeader(
          "Settings",
          "Your ClearEntry AI workspace settings."
        )}

        {renderNotifications()}

        <main className="page-content">
          <section className="content-card">
            <h2>Account information</h2>

            <div className="settings-details">
              <p><strong>Name:</strong> {user?.name || "Not available"}</p>
              <p><strong>Email:</strong> {user?.email || "Not available"}</p>
              <p><strong>Role:</strong> {user?.role || "Not available"}</p>
            </div>

            <button className="secondary-button" onClick={handleLogout}>
              <LogOut size={16} />
              Log out
            </button>
          </section>
        </main>
      </>
    );
  }

  // --------------------------------------------------
  // LOGIN SCREEN
  // --------------------------------------------------

  if (!token) {
    return (
      <div className="login-page">
        <div className="login-card">
          <div className="login-brand">
            <div className="brand-icon">
              <Package size={25} />
            </div>

            <div>
              <h1>ClearEntry AI</h1>
              <p>Intelligent Customs Documentation</p>
            </div>
          </div>

          <div className="login-heading">
            <h2>Welcome back</h2>
            <p>Sign in to access your shipment workspace.</p>
          </div>

          {renderNotifications()}

          <form onSubmit={handleLogin} className="login-form">
            <div className="form-field">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="Enter your email"
                required
              />
            </div>

            <div className="form-field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                required
              />
            </div>

            <button
              type="submit"
              className="primary-button login-submit"
              disabled={loading}
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>

          <div className="login-footer">
            AI-powered import documentation and verification
          </div>
        </div>
      </div>
    );
  }

  // --------------------------------------------------
  // MAIN APP LAYOUT
  // --------------------------------------------------

  return (
    <div className="app-shell">
      {renderSidebar()}

      {sidebarOpen && (
        <button
          className="sidebar-overlay"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close navigation overlay"
        />
      )}

      <div className="main-content">
        {activePage === "dashboard" && renderDashboard()}
        {activePage === "documents" && renderDocuments()}
        {activePage === "shipments" && renderShipments()}
        {activePage === "review" && renderReviewQueue()}
        {activePage === "settings" && renderSettings()}
      </div>
    </div>
  );
}

export default App;
