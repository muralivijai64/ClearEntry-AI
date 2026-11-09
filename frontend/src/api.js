
import axios from "axios";

const API_URL = "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_URL,
  timeout: 60000,
});

// Attach JWT authentication to protected API requests.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("clearentry_token");

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

// -------------------------
// FILE DOWNLOAD HELPER
// -------------------------

function downloadBlob(blob, filename) {
  const blobUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = blobUrl;
  link.download = filename;

  document.body.appendChild(link);
  link.click();
  link.remove();

  window.setTimeout(() => {
    window.URL.revokeObjectURL(blobUrl);
  }, 1000);
}

function getFilenameFromResponse(response, fallback) {
  const disposition =
    response.headers["content-disposition"] || "";

  const utf8Match = disposition.match(
    /filename\*=UTF-8''([^;]+)/i
  );

  if (utf8Match) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return fallback;
    }
  }

  const regularMatch = disposition.match(
    /filename="?([^";]+)"?/i
  );

  return regularMatch ? regularMatch[1] : fallback;
}

// -------------------------
// AUTHENTICATION
// -------------------------

export async function login(email, password) {
  const response = await api.post("/api/auth/login", {
    email,
    password,
  });

  return response.data;
}

// -------------------------
// SHIPMENTS
// -------------------------

export async function getShipments() {
  const response = await api.get("/api/shipments");
  return response.data;
}

export async function getShipment(shipmentId) {
  const response = await api.get(
    `/api/shipments/${shipmentId}`
  );

  return response.data;
}

// -------------------------
// DOCUMENT MANAGEMENT
// -------------------------

export async function getShipmentDocuments(shipmentId) {
  const response = await api.get(
    `/api/shipments/${shipmentId}/documents`
  );

  return response.data;
}

export async function uploadDocument(
  shipmentId,
  documentType,
  file
) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post(
    `/api/shipments/${shipmentId}/documents`,
    formData,
    {
      params: {
        document_type: documentType,
      },
    }
  );

  return response.data;
}

// -------------------------
// PDF PREVIEW
// -------------------------

export async function getDocumentPreviewUrl(documentId) {
  const response = await api.get(
    `/api/documents/${documentId}/download`,
    {
      responseType: "blob",
    }
  );

  const blob = new Blob([response.data], {
    type:
      response.headers["content-type"] ||
      "application/pdf",
  });

  return window.URL.createObjectURL(blob);
}

export function revokeDocumentPreviewUrl(blobUrl) {
  if (blobUrl) {
    window.URL.revokeObjectURL(blobUrl);
  }
}

// -------------------------
// OPEN PDF IN NEW TAB
// -------------------------

export async function openDocument(documentId, newTab) {
  try {
    const response = await api.get(
      `/api/documents/${documentId}/download`,
      {
        responseType: "blob",
      }
    );

    const blob = new Blob([response.data], {
      type:
        response.headers["content-type"] ||
        "application/pdf",
    });

    const blobUrl = window.URL.createObjectURL(blob);

    if (newTab && !newTab.closed) {
      newTab.location.href = blobUrl;
    } else {
      window.open(blobUrl, "_blank");
    }

    window.setTimeout(() => {
      window.URL.revokeObjectURL(blobUrl);
    }, 60000);

  } catch (error) {
    if (newTab && !newTab.closed) {
      newTab.close();
    }

    throw error;
  }
}

// -------------------------
// DOWNLOAD ORIGINAL PDF
// -------------------------

export async function downloadDocument(
  documentId,
  filename
) {
  const response = await api.get(
    `/api/documents/${documentId}/download`,
    {
      responseType: "blob",
    }
  );

  const blob = new Blob([response.data], {
    type:
      response.headers["content-type"] ||
      "application/pdf",
  });

  downloadBlob(
    blob,
    filename || `document-${documentId}.pdf`
  );
}

// -------------------------
// AI DOCUMENT EXTRACTION
// -------------------------

export async function extractDocument(documentId) {
  const response = await api.post(
    `/api/documents/${documentId}/extract`
  );

  return response.data;
}

export async function getExtraction(documentId) {
  const response = await api.get(
    `/api/documents/${documentId}/extraction`
  );

  return response.data;
}

// -------------------------
// HUMAN REVIEW AND CORRECTIONS
// -------------------------

export async function saveCorrection(
  documentId,
  fieldName,
  newValue,
  reason
) {
  const response = await api.patch(
    `/api/documents/${documentId}/review`,
    {
      field_name: fieldName,
      new_value: String(newValue),
      reason,
    }
  );

  return response.data;
}

// -------------------------
// CORRECTION HISTORY
// -------------------------

export async function getCorrectionHistory(shipmentId) {
  const response = await api.get(
    `/api/shipments/${shipmentId}/corrections`
  );

  return response.data;
}

// -------------------------
// CROSS-DOCUMENT VALIDATION
// -------------------------

export async function validateShipment(shipmentId) {
  const response = await api.post(
    `/api/shipments/${shipmentId}/validate`
  );

  return response.data;
}

// -------------------------
// MANAGER APPROVAL
// -------------------------

export async function approveShipment(shipmentId) {
  const response = await api.post(
    `/api/shipments/${shipmentId}/approve`
  );

  return response.data;
}

// -------------------------
// EXCEL EXPORT
// -------------------------

export async function exportShipment(shipmentId) {
  const response = await api.post(
    `/api/shipments/${shipmentId}/export`,
    {},
    {
      responseType: "blob",
    }
  );

  const filename = getFilenameFromResponse(
    response,
    `ClearEntry_Shipment_${shipmentId}.xlsx`
  );

  const blob = new Blob([response.data], {
    type:
      response.headers["content-type"] ||
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });

  downloadBlob(blob, filename);

  return {
    success: true,
    filename,
  };
}

// -------------------------
// EXPORT HISTORY
// -------------------------

export async function getShipmentExports(shipmentId) {
  const response = await api.get(
    `/api/shipments/${shipmentId}/exports`
  );

  return response.data;
}

// -------------------------
// DOWNLOAD PREVIOUS EXPORT
// -------------------------

export async function downloadShipmentExport(
  exportId,
  filename
) {
  const response = await api.get(
    `/api/exports/${exportId}/download`,
    {
      responseType: "blob",
    }
  );

  const downloadFilename = getFilenameFromResponse(
    response,
    filename || `ClearEntry_Export_${exportId}.xlsx`
  );

  const blob = new Blob([response.data], {
    type:
      response.headers["content-type"] ||
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });

  downloadBlob(blob, downloadFilename);

  return {
    success: true,
    filename: downloadFilename,
  };
}

// -------------------------
// DEFAULT API EXPORT
// -------------------------

export default api;
