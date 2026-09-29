// ==========================================================================
// Service Worker & Splash Screen Loading Flow
// ==========================================================================
window.addEventListener("load", () => {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js").catch(err => {
      console.log("SW reg failed:", err);
    });
  }

  // Smoothly fade out splash screen
  const splash = document.getElementById("appSplashScreen");
  if (splash) {
    setTimeout(() => {
      splash.classList.add("fade-out");
      setTimeout(() => {
        splash.remove();
      }, 500);
    }, 400);
  }
});

// ==========================================================================
// Dark / Light Theme System
// ==========================================================================
function initTheme() {
  const currentTheme = localStorage.getItem("theme") || 
    (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  setTheme(currentTheme, false);

  document.querySelectorAll("#menuThemeToggle, #themeToggleBtn, #sidebarThemeToggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const active = document.documentElement.getAttribute("data-theme") || "light";
      const next = active === "dark" ? "light" : "dark";
      setTheme(next, true);
    });
  });
}

function setTheme(theme, save = true) {
  document.documentElement.setAttribute("data-bs-theme", theme);
  document.documentElement.setAttribute("data-theme", theme);
  if (save) localStorage.setItem("theme", theme);

  const themeMeta = document.getElementById("themeColorMeta");
  if (themeMeta) {
    themeMeta.setAttribute("content", theme === "dark" ? "#0b1120" : "#0f766e");
  }

  const badges = document.querySelectorAll(".theme-mode-badge");
  badges.forEach(el => {
    el.textContent = theme === "dark" ? "Dark 🌙" : "Light ☀️";
  });

  updateChartTheme(theme);
}

// ==========================================================================
// PWA Installation & App Mode Check
// ==========================================================================
let deferredInstallPrompt = null;

function isRunningInApp() {
  return window.matchMedia('(display-mode: standalone)').matches || 
         window.navigator.standalone === true || 
         document.referrer.includes('android-app://');
}

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
});

function triggerInstall() {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    deferredInstallPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === "accepted") {
        console.log("User installed PWA");
      }
      deferredInstallPrompt = null;
    });
  } else {
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    if (isIOS) {
      alert("iPhone par Install karne ke liye:\n1. Safari ke niche Share (⎙) button par tap karein.\n2. 'Add to Home Screen' (+) choose karein.");
    } else {
      alert("App Install karne ke liye:\nBrowser menu (⋮) me jaakar 'Install App' ya 'Add to Home screen' par tap karein.");
    }
  }
}

// ==========================================================================
// Biometric (Fingerprint / Face ID / Touch ID) Authentication Flow
// (Only active in Downloaded / Installed App)
// ==========================================================================
async function setupBiometric() {
  try {
    const credId = "ve_bio_" + Math.random().toString(36).substring(2) + Date.now();
    
    if (window.PublicKeyCredential) {
      const challenge = new Uint8Array(32);
      window.crypto.getRandomValues(challenge);
      
      const createOptions = {
        publicKey: {
          challenge: challenge,
          rp: { name: "VE-BILLING", id: window.location.hostname },
          user: {
            id: new Uint8Array([1, 2, 3, 4]),
            name: "billing_user",
            displayName: "VE Billing User"
          },
          pubKeyCredParams: [{ alg: -7, type: "public-key" }, { alg: -257, type: "public-key" }],
          authenticatorSelection: {
            authenticatorAttachment: "platform",
            userVerification: "preferred"
          },
          timeout: 60000
        }
      };

      try {
        const cred = await navigator.credentials.create(createOptions);
        if (cred) {
          const rawId = btoa(String.fromCharCode.apply(null, new Uint8Array(cred.rawId)));
          await saveBiometricCredential(rawId);
          return;
        }
      } catch (authErr) {
        console.log("Platform authenticator fallback:", authErr);
      }
    }

    await saveBiometricCredential(credId);
  } catch (err) {
    alert("Biometric setup failed: " + err.message);
  }
}

async function saveBiometricCredential(credId) {
  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || 
                 document.querySelector('input[name="csrf_token"]')?.value || "";
    
    const res = await fetch("/auth/biometric/register", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json", 
        "X-CSRFToken": csrf,
        "Accept": "application/json"
      },
      body: JSON.stringify({ credential_id: credId })
    });

    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      console.warn("Raw response:", text);
      data = { success: false, error: "Server response format error." };
    }

    if (data.success) {
      localStorage.setItem("ve_bio_credential", credId);
      alert("✅ Fingerprint / Face ID login enabled for this installed app!");
      const prompt = document.getElementById("biometricSetupPrompt");
      if (prompt) prompt.style.display = "none";
    } else {
      alert(data.error || "Failed to enable biometric login.");
    }
  } catch (err) {
    alert("Biometric setup error: " + err.message);
  }
}

async function loginBiometric() {
  const inApp = isRunningInApp();
  const savedCred = localStorage.getItem("ve_bio_credential");

  if (!inApp) {
    alert("📱 Note: Fingerprint Login sirf App install/download karne ke baad chalta hai.\nKripya pehle browser menu se 'Install App' ya 'Add to Home screen' karein.");
    return;
  }

  if (!savedCred) {
    alert("Biometric login is not setup yet.\nPehele password se login karein aur dashboard par 'Enable Fingerprint Login' par click karein.");
    return;
  }

  try {
    if (window.PublicKeyCredential) {
      const challenge = new Uint8Array(32);
      window.crypto.getRandomValues(challenge);
      try {
        await navigator.credentials.get({
          publicKey: {
            challenge: challenge,
            timeout: 60000,
            userVerification: "preferred"
          }
        });
      } catch (e) {
        console.log("Biometric prompt skipped or fallback used:", e);
      }
    }

    const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || 
                 document.querySelector('input[name="csrf_token"]')?.value || "";

    const res = await fetch("/auth/biometric/login", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json", 
        "X-CSRFToken": csrf,
        "Accept": "application/json"
      },
      body: JSON.stringify({ credential_id: savedCred })
    });

    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      data = { success: false, error: "Server response format error." };
    }

    if (data.success && data.redirect) {
      window.location.href = data.redirect;
    } else {
      alert(data.error || "Biometric login failed. Please log in with your password.");
    }
  } catch (err) {
    alert("Biometric login error: " + err.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();

  document.querySelectorAll("#menuInstallBtn, #pwaInstallBannerBtn, #pwaInstallHeaderBtn, #mobileMenuInstallBtn").forEach(btn => {
    btn.addEventListener("click", triggerInstall);
  });

  const inApp = isRunningInApp();
  const enableBioBtn = document.getElementById("enableBiometricBtn");
  if (enableBioBtn) enableBioBtn.addEventListener("click", setupBiometric);

  const bioPrompt = document.getElementById("biometricSetupPrompt");
  if (bioPrompt) {
    if (inApp && !localStorage.getItem("ve_bio_credential")) {
      bioPrompt.style.display = "flex";
    } else {
      bioPrompt.style.display = "none";
    }
  }

  const bioLoginBtn = document.getElementById("biometricLoginBtn");
  if (bioLoginBtn) {
    bioLoginBtn.addEventListener("click", loginBiometric);
    if (!inApp) {
      bioLoginBtn.title = "Available after adding to Home Screen / Installing App";
    }
  }
});

// ==========================================================================
// Dashboard Sales & GST Chart
// ==========================================================================
let salesChartInstance = null;

function renderChart() {
  const chartCanvas = document.getElementById("salesChart");
  if (!chartCanvas || !window.chartRows) return;

  const isDark = (document.documentElement.getAttribute("data-theme") || "light") === "dark";
  const textColor = isDark ? "#cbd5e1" : "#475569";
  const gridColor = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)";

  const labels = window.chartRows.map(row => `Month ${parseInt(row[0], 10)}`);
  
  if (salesChartInstance) {
    salesChartInstance.destroy();
  }

  salesChartInstance = new Chart(chartCanvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { 
          label: "Sales", 
          data: window.chartRows.map(row => Math.round(row[1] || 0)), 
          backgroundColor: isDark ? "#14b8a6" : "#0f766e",
          borderRadius: 6
        },
        { 
          label: "GST", 
          data: window.chartRows.map(row => Math.round(row[2] || 0)), 
          backgroundColor: "#f59e0b",
          borderRadius: 6
        }
      ]
    },
    options: { 
      responsive: true,
      plugins: { 
        legend: { 
          position: "bottom",
          labels: { color: textColor, font: { weight: "600" } }
        } 
      },
      scales: {
        x: {
          ticks: { color: textColor },
          grid: { color: gridColor }
        },
        y: {
          ticks: { color: textColor },
          grid: { color: gridColor }
        }
      }
    }
  });
}

function updateChartTheme() {
  if (salesChartInstance && window.chartRows) {
    renderChart();
  }
}

// ==========================================================================
// Customer Autocomplete & Live Document Calculations
// ==========================================================================
function calculateLiveTotals() {
  const rows = document.querySelectorAll(".item-card-row, .item-row");
  let totalTaxable = 0;
  let totalGST = 0;

  rows.forEach(row => {
    const qty = parseFloat(row.querySelector(".item-qty, input[name='quantity[]']")?.value) || 0;
    const rate = parseFloat(row.querySelector(".item-rate, input[name='rate[]']")?.value) || 0;
    const disc = parseFloat(row.querySelector(".item-disc, input[name='discount[]']")?.value) || 0;
    const gstRate = parseFloat(row.querySelector(".item-gst, select[name='gst_rate[]']")?.value) || 0;

    const base = Math.max(0, (qty * rate) - disc);
    const gst = base * (gstRate / 100);
    const lineTotal = base + gst;

    const lineTotalEl = row.querySelector(".item-line-total");
    if (lineTotalEl) {
      lineTotalEl.textContent = "₹" + lineTotal.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    totalTaxable += base;
    totalGST += gst;
  });

  const grandTotal = totalTaxable + totalGST;

  const liveTaxable = document.getElementById("liveTaxable");
  const liveGST = document.getElementById("liveGST");
  const liveGrandTotal = document.getElementById("liveGrandTotal");

  if (liveTaxable) liveTaxable.textContent = "₹" + totalTaxable.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (liveGST) liveGST.textContent = "₹" + totalGST.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (liveGrandTotal) liveGrandTotal.textContent = "₹" + grandTotal.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

document.addEventListener("DOMContentLoaded", () => {
  renderChart();

  const customerPicker = document.querySelector(".customer-picker");
  if (customerPicker) {
    const options = Array.from(document.querySelectorAll("#saved_customers option"));
    const fields = {
      id: document.getElementById("customer_id"),
      company: document.getElementById("customer_company"),
      ship: document.getElementById("customer_ship"),
      gstin: document.getElementById("customer_gstin"),
      phone: document.getElementById("customer_phone"),
      email: document.getElementById("customer_email"),
      address: document.getElementById("customer_address")
    };

    customerPicker.addEventListener("input", () => {
      const selected = options.find(option => option.value === customerPicker.value);
      if (!selected) {
        if (fields.id) fields.id.value = "";
        return;
      }
      fields.id.value = selected.dataset.id || "";
      fields.company.value = selected.dataset.company || "";
      fields.ship.value = selected.dataset.ship || "";
      fields.gstin.value = selected.dataset.gstin || "";
      fields.phone.value = selected.dataset.phone || "";
      fields.email.value = selected.dataset.email || "";
      fields.address.value = selected.dataset.address || "";
    });
  }

  const itemRows = document.getElementById("itemRows");
  const addItemRow = document.getElementById("addItemRow");
  const addItemRowBottom = document.getElementById("addItemRowBottom");

  if (itemRows) {
    const refreshItemRows = () => {
      const allRows = itemRows.querySelectorAll(".item-card-row, .item-row");
      allRows.forEach((row, index) => {
        const badge = row.querySelector(".row-badge");
        if (badge) badge.textContent = `Item #${index + 1}`;
        const num = row.querySelector(".row-number");
        if (num) num.textContent = index + 1;
        const remove = row.querySelector(".remove-item-row");
        if (remove) remove.disabled = allRows.length === 1;
      });
      calculateLiveTotals();
    };

    const blankCard = () => {
      const first = itemRows.querySelector(".item-card-row, .item-row");
      const clone = first.cloneNode(true);
      clone.querySelectorAll("input, textarea").forEach(input => {
        if (input.name === "quantity[]") input.value = "1";
        else if (input.name === "unit[]") input.value = "Nos";
        else if (input.name === "rate[]" || input.name === "discount[]") input.value = "0";
        else input.value = "";
      });
      clone.querySelectorAll("select").forEach(select => { select.value = "18"; });
      return clone;
    };

    const handleAdd = () => {
      itemRows.appendChild(blankCard());
      refreshItemRows();
    };

    if (addItemRow) addItemRow.addEventListener("click", handleAdd);
    if (addItemRowBottom) addItemRowBottom.addEventListener("click", handleAdd);

    itemRows.addEventListener("click", event => {
      if (!event.target.classList.contains("remove-item-row")) return;
      const allRows = itemRows.querySelectorAll(".item-card-row, .item-row");
      if (allRows.length === 1) return;
      event.target.closest(".item-card-row, .item-row").remove();
      refreshItemRows();
    });

    itemRows.addEventListener("input", () => {
      calculateLiveTotals();
    });

    refreshItemRows();
  }
});
