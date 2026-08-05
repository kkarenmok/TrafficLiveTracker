(() => {
  "use strict";

  const config = window.TRAFFIC_TRACKER_CONFIG || {};
  const apiBase = String(config.API_BASE_URL || "").replace(/\/$/, "");
  const elements = {
    form: document.querySelector("#stop-form"),
    input: document.querySelector("#stop-search"),
    mode: document.querySelector("#mode-select"),
    results: document.querySelector("#search-results"),
    spinner: document.querySelector("#search-spinner"),
    add: document.querySelector("#add-stop"),
    searchStatus: document.querySelector("#search-status"),
    dashboardStatus: document.querySelector("#dashboard-status"),
    grid: document.querySelector("#stop-grid"),
    updated: document.querySelector("#updated-at"),
    refresh: document.querySelector("#refresh"),
    toast: document.querySelector("#toast"),
    toastMessage: document.querySelector("#toast-message"),
    undo: document.querySelector("#undo-remove")
  };

  let configuredIds = new Set();
  let searchResults = [];
  let selectedStop = null;
  let activeIndex = -1;
  let searchTimer = null;
  let searchController = null;
  let refreshTimer = null;
  let toastTimer = null;
  let removedStop = null;

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body) headers["Content-Type"] = "application/json";
    const response = await fetch(`${apiBase}${path}`, {
      ...options,
      headers
    });
    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try { message = (await response.json()).detail || message; } catch (_) { /* no JSON */ }
      throw new Error(message);
    }
    return response.json();
  }

  function setSearchLoading(loading) {
    elements.spinner.classList.toggle("is-hidden", !loading);
  }

  function closeResults() {
    elements.results.classList.add("is-hidden");
    elements.input.setAttribute("aria-expanded", "false");
    activeIndex = -1;
  }

  function selectResult(index) {
    const stop = searchResults[index];
    if (!stop || configuredIds.has(stop.id)) return;
    selectedStop = stop;
    activeIndex = index;
    elements.input.value = `${stop.name}${stop.indicator ? ` · ${stop.indicator}` : ""}`;
    elements.add.disabled = false;
    elements.searchStatus.textContent = `Selected ${elements.input.value}`;
    closeResults();
  }

  function renderResults() {
    elements.results.replaceChildren();
    if (!searchResults.length) {
      const empty = document.createElement("div");
      empty.className = "no-arrivals";
      empty.textContent = "No matching bus stops found.";
      elements.results.append(empty);
    } else {
      searchResults.forEach((stop, index) => {
        const option = document.createElement("button");
        const alreadyAdded = configuredIds.has(stop.id);
        option.type = "button";
        option.className = `result-option${index === activeIndex ? " is-active" : ""}`;
        option.role = "option";
        option.id = `search-option-${index}`;
        option.disabled = alreadyAdded;
        option.setAttribute("aria-selected", String(index === activeIndex));

        const copy = document.createElement("span");
        copy.className = "result-copy";
        const name = document.createElement("span");
        name.className = "result-name";
        name.textContent = stop.name;
        const meta = document.createElement("span");
        meta.className = "result-meta";
        meta.textContent = alreadyAdded ? "Already added" : (stop.routes.length ? `Routes ${stop.routes.join(", ")}` : stop.id);
        copy.append(name, meta);
        const letter = document.createElement("span");
        letter.className = "stop-letter";
        letter.textContent = stop.indicator || "Bus stop";
        option.append(copy, letter);
        option.addEventListener("click", () => selectResult(index));
        elements.results.append(option);
      });
    }
    elements.results.classList.remove("is-hidden");
    elements.input.setAttribute("aria-expanded", "true");
  }

  async function runSearch(query) {
    if (searchController) searchController.abort();
    searchController = new AbortController();
    setSearchLoading(true);
    elements.searchStatus.textContent = "";
    try {
      const mode = (elements.mode && elements.mode.value) || "bus";
      searchResults = await api(`/stops/search?q=${encodeURIComponent(query)}&modes=${encodeURIComponent(mode)}`, { signal: searchController.signal });
      renderResults();
    } catch (error) {
      if (error.name !== "AbortError") elements.searchStatus.textContent = `Search unavailable: ${error.message}`;
    } finally {
      setSearchLoading(false);
    }
  }

  elements.input.addEventListener("input", () => {
    clearTimeout(searchTimer);
    selectedStop = null;
    elements.add.disabled = true;
    const query = elements.input.value.trim();
    if (query.length < 2) {
      closeResults();
      elements.searchStatus.textContent = query ? "Enter at least two characters." : "";
      return;
    }
    searchTimer = setTimeout(() => runSearch(query), 280);
  });

  elements.input.addEventListener("keydown", (event) => {
    if (elements.results.classList.contains("is-hidden") || !searchResults.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const direction = event.key === "ArrowDown" ? 1 : -1;
      const available = searchResults
        .map((_, index) => index)
        .filter((index) => !configuredIds.has(searchResults[index].id));
      if (!available.length) return;
      const current = available.indexOf(activeIndex);
      activeIndex = available[(current + direction + available.length) % available.length];
      elements.input.setAttribute("aria-activedescendant", `search-option-${activeIndex}`);
      renderResults();
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      selectResult(activeIndex);
    } else if (event.key === "Escape") {
      closeResults();
    }
  });

  document.addEventListener("click", (event) => {
    if (!elements.results.contains(event.target) && event.target !== elements.input) closeResults();
  });

  elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!selectedStop) return;
    elements.add.disabled = true;
    elements.searchStatus.textContent = "Adding stop…";
    try {
      await api("/stops", { method: "POST", body: JSON.stringify({ id: selectedStop.id }) });
      elements.input.value = "";
      selectedStop = null;
      elements.searchStatus.textContent = "Stop added.";
      await loadDashboard();
    } catch (error) {
      elements.searchStatus.textContent = `Could not add stop: ${error.message}`;
      elements.add.disabled = false;
    }
  });

  function arrivalRow(arrival) {
    const item = document.createElement("li");
    item.className = "arrival";
    const route = document.createElement("span");
    route.className = "route";
    route.textContent = arrival.route;
    const copy = document.createElement("div");
    const destination = document.createElement("div");
    destination.className = "destination";
    destination.textContent = arrival.destination;
    copy.append(destination);
    if (arrival.platform_name) {
      const platform = document.createElement("div");
      platform.className = "platform";
      platform.textContent = arrival.platform_name;
      copy.append(platform);
    }
    const minutes = document.createElement("div");
    minutes.className = "minutes";
    minutes.append(Object.assign(document.createElement("strong"), { textContent: arrival.minutes_until_arrival }));
    minutes.append(document.createTextNode(arrival.minutes_until_arrival === 1 ? " min" : " mins"));
    item.append(route, copy, minutes);
    return item;
  }

  function stopCard(entry) {
    const card = document.createElement("article");
    card.className = "stop-card";
    const header = document.createElement("header");
    header.className = "card-header";
    const copy = document.createElement("div");
    const title = document.createElement("h3");
    title.className = "stop-title";
    title.textContent = entry.stop.name;
    const id = document.createElement("p");
    id.className = "stop-id";
    id.textContent = entry.stop.id;
    copy.append(title, id);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-button";
    remove.textContent = "×";
    remove.title = `Remove ${entry.stop.name}`;
    remove.setAttribute("aria-label", remove.title);
    remove.addEventListener("click", () => removeStop(entry.stop));
    header.append(copy, remove);
    card.append(header);
    if (!entry.arrivals.length) {
      const empty = document.createElement("div");
      empty.className = "no-arrivals";
      empty.textContent = "No live arrivals available.";
      card.append(empty);
    } else {
      const list = document.createElement("ul");
      list.className = "arrival-list";
      entry.arrivals.slice(0, 5).forEach((arrival) => list.append(arrivalRow(arrival)));
      card.append(list);
    }
    return card;
  }

  async function loadDashboard() {
    clearTimeout(refreshTimer);
    elements.refresh.disabled = true;
    if (!elements.grid.children.length) {
      elements.dashboardStatus.classList.remove("is-hidden");
      elements.dashboardStatus.textContent = "Loading live arrivals…";
    }
    try {
      const dashboard = await api("/dashboard");
      configuredIds = new Set(dashboard.stops.map((entry) => entry.stop.id));
      elements.grid.replaceChildren(...dashboard.stops.map(stopCard));
      elements.dashboardStatus.classList.toggle("is-hidden", dashboard.stops.length > 0);
      if (!dashboard.stops.length) elements.dashboardStatus.textContent = "No stops yet. Search above to add one.";
      elements.updated.textContent = `Updated ${new Date(dashboard.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
      refreshTimer = setTimeout(loadDashboard, Math.max(5, dashboard.refresh_seconds) * 1000);
    } catch (error) {
      elements.dashboardStatus.classList.remove("is-hidden");
      elements.dashboardStatus.textContent = `Live arrivals are unavailable. ${error.message}`;
      elements.updated.textContent = "Update failed";
      refreshTimer = setTimeout(loadDashboard, 30000);
    } finally {
      elements.refresh.disabled = false;
    }
  }

  async function removeStop(stop) {
    try {
      await api(`/stops/${encodeURIComponent(stop.id)}`, { method: "DELETE" });
      removedStop = stop;
      showToast(`${stop.name} removed.`);
      await loadDashboard();
    } catch (error) {
      elements.dashboardStatus.classList.remove("is-hidden");
      elements.dashboardStatus.textContent = `Could not remove stop: ${error.message}`;
    }
  }

  function showToast(message) {
    clearTimeout(toastTimer);
    elements.toastMessage.textContent = message;
    elements.toast.classList.remove("is-hidden");
    toastTimer = setTimeout(() => {
      elements.toast.classList.add("is-hidden");
      removedStop = null;
    }, 5000);
  }

  elements.undo.addEventListener("click", async () => {
    if (!removedStop) return;
    const stop = removedStop;
    clearTimeout(toastTimer);
    elements.undo.disabled = true;
    try {
      await api("/stops", { method: "POST", body: JSON.stringify({ id: stop.id }) });
      elements.toast.classList.add("is-hidden");
      removedStop = null;
      await loadDashboard();
    } catch (error) {
      showToast(`Undo failed: ${error.message}`);
    } finally {
      elements.undo.disabled = false;
    }
  });

  elements.refresh.addEventListener("click", loadDashboard);
  loadDashboard();
})();
