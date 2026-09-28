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
// PWA Installation Flow
// ==========================================================================
let deferredInstallPrompt = null;

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

document.addEventListener("DOMContentLoaded", () => {
  initTheme();

  document.querySelectorAll("#menuInstallBtn, #pwaInstallBannerBtn, #pwaInstallHeaderBtn, #mobileMenuInstallBtn").forEach(btn => {
    btn.addEventListener("click", triggerInstall);
  });
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
// Customer Autocomplete & Item Rows
// ==========================================================================
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
  if (itemRows && addItemRow) {
    const refreshItemRows = () => {
      itemRows.querySelectorAll(".item-row").forEach((row, index) => {
        row.querySelector(".row-number").textContent = index + 1;
        const remove = row.querySelector(".remove-item-row");
        if (remove) remove.disabled = itemRows.querySelectorAll(".item-row").length === 1;
      });
    };

    const blankRow = () => {
      const first = itemRows.querySelector(".item-row");
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

    addItemRow.addEventListener("click", () => {
      itemRows.appendChild(blankRow());
      refreshItemRows();
    });

    itemRows.addEventListener("click", event => {
      if (!event.target.classList.contains("remove-item-row")) return;
      if (itemRows.querySelectorAll(".item-row").length === 1) return;
      event.target.closest(".item-row").remove();
      refreshItemRows();
    });

    refreshItemRows();
  }
});
