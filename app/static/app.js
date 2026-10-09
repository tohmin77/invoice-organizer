const COLS = [
  { key: "purchaser", label: "Purchaser", required: true },
  { key: "seller", label: "Seller", required: true },
  { key: "items", label: "Items / services" },
  { key: "amount", label: "Amount", num: true, required: true },
  { key: "gst", label: "GST", num: true },
  { key: "date", label: "Date", required: true, placeholder: "YYYY-MM-DD" },
];

const rows = document.getElementById("rows");
const statusEl = document.getElementById("status");
const errorsEl = document.getElementById("errors");
const emptyEl = document.getElementById("empty");
const reviewOnly = document.getElementById("review-only");
const reviewCount = document.getElementById("review-count");

function showError(msg) {
  const li = document.createElement("li");
  li.textContent = msg;
  errorsEl.appendChild(li);
}

function isBlank(v) {
  return v === null || v === undefined || v === "";
}

function cellProblem(inv, col) {
  if (col.required && isBlank(inv[col.key])) return "missing";
  if (col.key === "gst" && typeof inv.gst === "number" && typeof inv.amount === "number" && inv.gst > inv.amount) {
    return "suspect";
  }
  return null;
}

function needsReview(inv) {
  return COLS.some((c) => cellProblem(inv, c));
}

function applyFlags(tr, inv) {
  for (const col of COLS) {
    const td = tr.querySelector(`td[data-key="${col.key}"]`);
    td.classList.remove("missing", "suspect");
    const problem = cellProblem(inv, col);
    if (problem) td.classList.add(problem);
    td.title = problem === "missing" ? "Missing — please fill in" : problem === "suspect" ? "GST is larger than the amount" : "";
  }
  tr.classList.toggle("review", needsReview(inv));
}

function updateReviewState() {
  let count = 0;
  for (const tr of rows.children) {
    if (tr.classList.contains("review")) count++;
    tr.hidden = reviewOnly.checked && !tr.classList.contains("review");
  }
  reviewCount.textContent = count ? `${count} need review` : "";
  emptyEl.hidden = rows.children.length > 0;
}

function renderRow(inv) {
  const tr = document.createElement("tr");
  const file = document.createElement("td");
  file.className = "file";
  file.textContent = inv.filename;
  file.title = inv.filename;
  tr.appendChild(file);

  for (const col of COLS) {
    const td = document.createElement("td");
    td.dataset.key = col.key;
    td.dataset.label = col.label;
    if (col.num) td.className = "num";
    const input = document.createElement("input");
    input.value = inv[col.key] ?? "";
    if (col.num) input.inputMode = "decimal";
    if (col.key === "date") input.inputMode = "numeric";
    input.setAttribute("aria-label", col.label);
    input.placeholder = col.placeholder ?? (col.required ? "missing" : "");
    input.addEventListener("change", () => saveCell(inv, col, input, tr, td));
    td.appendChild(input);
    tr.appendChild(td);
  }

  const actions = document.createElement("td");
  const del = document.createElement("button");
  del.className = "danger";
  del.textContent = "Delete";
  del.addEventListener("click", async () => {
    if (!confirm("Delete this invoice?")) return;
    const res = await fetch(`/api/invoices/${inv.id}`, { method: "DELETE" });
    if (res.ok) {
      tr.remove();
      updateReviewState();
    } else {
      showError("Could not delete invoice.");
    }
  });
  actions.appendChild(del);
  tr.appendChild(actions);
  applyFlags(tr, inv);
  return tr;
}

async function saveCell(inv, col, input, tr, td) {
  const raw = input.value.trim();
  let value = raw === "" ? null : raw;
  if (col.num && value !== null) {
    value = Number(value.replace(/[$,\s]/g, ""));
    if (Number.isNaN(value)) {
      showError(`${col.key} must be a number.`);
      input.value = inv[col.key] ?? "";
      return;
    }
  }
  const res = await fetch(`/api/invoices/${inv.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ [col.key]: value }),
  });
  if (!res.ok) {
    showError(res.status === 422 ? `Invalid ${col.key} (dates must be YYYY-MM-DD).` : "Could not save change.");
    input.value = inv[col.key] ?? "";
    return;
  }
  Object.assign(inv, await res.json());
  input.value = inv[col.key] ?? "";
  applyFlags(tr, inv);
  td.classList.add("saved");
  setTimeout(() => td.classList.remove("saved"), 1200);
  updateReviewState();
}

async function loadInvoices() {
  const res = await fetch("/api/invoices");
  const invoices = await res.json();
  rows.replaceChildren(...invoices.map(renderRow));
  updateReviewState();
}

reviewOnly.addEventListener("change", updateReviewState);

document.getElementById("add-btn").addEventListener("click", async () => {
  const res = await fetch("/api/invoices", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  if (!res.ok) return showError("Could not add invoice.");
  const tr = renderRow(await res.json());
  rows.prepend(tr);
  tr.querySelector("input").focus();
  reviewOnly.checked = false;
  updateReviewState();
  tr.querySelector("input").focus();
});

document.getElementById("upload-btn").addEventListener("click", async (e) => {
  const picker = document.getElementById("files");
  if (!picker.files.length) return;
  const form = new FormData();
  for (const f of picker.files) form.append("files", f);
  const btn = e.currentTarget;
  btn.disabled = true;
  errorsEl.replaceChildren();
  statusEl.textContent = "Extracting… this can take a little while.";
  try {
    const res = await fetch("/api/upload", { method: "POST", body: form });
    if (!res.ok) throw new Error(`Upload failed (${res.status})`);
    const results = await res.json();
    for (const r of results) if (r.error) showError(`${r.filename}: ${r.error}`);
    const ok = results.filter((r) => r.invoice).length;
    statusEl.textContent = `${ok} of ${results.length} processed.`;
    picker.value = "";
    await loadInvoices();
  } catch (err) {
    statusEl.textContent = "";
    showError(err.message);
  } finally {
    btn.disabled = false;
  }
});

loadInvoices();
