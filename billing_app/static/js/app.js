if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/service-worker.js").catch(() => {});
}

const chart = document.getElementById("salesChart");
if (chart && window.chartRows) {
  const labels = window.chartRows.map(row => `Month ${parseInt(row[0], 10)}`);
  new Chart(chart, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Sales", data: window.chartRows.map(row => Math.round(row[1] || 0)), backgroundColor: "#0f766e" },
        { label: "GST", data: window.chartRows.map(row => Math.round(row[2] || 0)), backgroundColor: "#f59e0b" }
      ]
    },
    options: { responsive: true, plugins: { legend: { position: "bottom" } } }
  });
}

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
