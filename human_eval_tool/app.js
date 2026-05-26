const SAMPLE_SIZE = 10;
const EXPECTED_ITEMS = 30;
const STORAGE_KEY = "writerSummaryBlindHumanEval.v1";
const DEFAULT_SEED = "writer-human-eval-shared-sample-v1";
const PREFERENCE_VALUES = ["A", "B", "Tie", "Unsure"];
const REQUIRED_FIELDS = [
  "overall_preference",
  "factuality_preference",
  "coverage_preference",
];

const state = {
  items: [],
  selectedArticleKeys: [],
  answers: {},
  currentIndex: 0,
  evaluatorId: "",
  sourceName: "",
};

const elements = {
  fileInput: document.getElementById("fileInput"),
  resetButton: document.getElementById("resetButton"),
  emptyState: document.getElementById("emptyState"),
  reviewApp: document.getElementById("reviewApp"),
  evaluatorId: document.getElementById("evaluatorId"),
  progressText: document.getElementById("progressText"),
  progressBar: document.getElementById("progressBar"),
  sampleText: document.getElementById("sampleText"),
  itemList: document.getElementById("itemList"),
  jumpIncompleteButton: document.getElementById("jumpIncompleteButton"),
  exportButton: document.getElementById("exportButton"),
  saveStatus: document.getElementById("saveStatus"),
  itemCounter: document.getElementById("itemCounter"),
  reviewId: document.getElementById("reviewId"),
  prevButton: document.getElementById("prevButton"),
  nextButton: document.getElementById("nextButton"),
  articleText: document.getElementById("articleText"),
  summaryA: document.getElementById("summaryA"),
  summaryB: document.getElementById("summaryB"),
  notes: document.getElementById("notes"),
};

function hashString(value) {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function seededRandom(seedText) {
  let seed = hashString(seedText) || 1;
  return () => {
    seed = Math.imul(1664525, seed) + 1013904223;
    return (seed >>> 0) / 4294967296;
  };
}

function shuffledCopy(values, seedText) {
  const random = seededRandom(seedText);
  const copy = [...values];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function normalizeText(value) {
  return String(value ?? "").trim();
}

function articleKey(article) {
  return hashString(normalizeText(article)).toString(16).padStart(8, "0");
}

function groupByArticle(items) {
  const groups = new Map();
  for (const item of items) {
    const article = normalizeText(item.article);
    if (!article) {
      continue;
    }
    const key = articleKey(article);
    if (!groups.has(key)) {
      groups.set(key, { key, article, items: [] });
    }
    groups.get(key).items.push(item);
  }
  return [...groups.values()];
}

function sampleItems(inputItems) {
  const groups = groupByArticle(inputItems);
  if (groups.length < SAMPLE_SIZE) {
    throw new Error(`Expected at least ${SAMPLE_SIZE} unique articles, found ${groups.length}.`);
  }
  const selectedGroups = shuffledCopy(groups, DEFAULT_SEED).slice(0, SAMPLE_SIZE);
  const selectedArticleKeys = selectedGroups.map((group) => group.key);
  const selectedItems = selectedGroups.flatMap((group) => group.items);
  return { selectedArticleKeys, selectedItems };
}

function makeEmptyAnswer(item) {
  return {
    overall_preference: validPreference(item.overall_preference) ? item.overall_preference : "",
    factuality_preference: validPreference(item.factuality_preference) ? item.factuality_preference : "",
    coverage_preference: validPreference(item.coverage_preference) ? item.coverage_preference : "",
    notes: item.notes ?? "",
  };
}

function validPreference(value) {
  return PREFERENCE_VALUES.includes(value);
}

function isComplete(item) {
  const answer = state.answers[item.review_id] || {};
  return REQUIRED_FIELDS.every((field) => validPreference(answer[field]));
}

function completedCount() {
  return state.items.filter(isComplete).length;
}

function saveState() {
  const payload = {
    items: state.items,
    selectedArticleKeys: state.selectedArticleKeys,
    answers: state.answers,
    currentIndex: state.currentIndex,
    evaluatorId: state.evaluatorId,
    sourceName: state.sourceName,
    savedAt: new Date().toISOString(),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  elements.saveStatus.textContent = `Autosaved ${new Date().toLocaleTimeString()}.`;
}

function loadSavedState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return false;
  }
  try {
    const saved = JSON.parse(raw);
    if (!Array.isArray(saved.items) || !saved.items.length || !saved.answers) {
      return false;
    }
    state.items = saved.items;
    state.selectedArticleKeys = saved.selectedArticleKeys || [];
    state.answers = saved.answers;
    state.currentIndex = Math.min(saved.currentIndex || 0, state.items.length - 1);
    state.evaluatorId = saved.evaluatorId || "";
    state.sourceName = saved.sourceName || "saved browser session";
    return true;
  } catch (error) {
    console.warn("Could not load saved evaluation state.", error);
    return false;
  }
}

function renderChoiceControls() {
  document.querySelectorAll(".choice-row").forEach((container) => {
    const field = container.dataset.field;
    container.innerHTML = "";
    for (const value of PREFERENCE_VALUES) {
      const id = `${field}_${value}`;
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = field;
      input.value = value;
      input.id = id;
      input.addEventListener("change", () => updateAnswer(field, value));
      label.append(input, document.createTextNode(value));
      container.append(label);
    }
  });
}

function renderApp() {
  const hasItems = state.items.length > 0;
  elements.emptyState.classList.toggle("hidden", hasItems);
  elements.reviewApp.classList.toggle("hidden", !hasItems);
  if (!hasItems) {
    return;
  }

  elements.evaluatorId.value = state.evaluatorId;
  renderItemList();
  renderCurrentItem();
  renderProgress();
}

function renderProgress() {
  const complete = completedCount();
  const total = state.items.length;
  const percent = total ? Math.round((complete / total) * 100) : 0;
  elements.progressText.textContent = `${complete} / ${total}`;
  elements.progressBar.style.width = `${percent}%`;
  const articleCount = state.selectedArticleKeys.length || groupByArticle(state.items).length;
  const warning = total === EXPECTED_ITEMS ? "" : ` Expected ${EXPECTED_ITEMS}; sampled ${total}.`;
  elements.sampleText.textContent = `${articleCount} articles selected from ${state.sourceName || "loaded JSON"}.${warning}`;
}

function renderItemList() {
  elements.itemList.innerHTML = "";
  state.items.forEach((item, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = String(index + 1);
    button.title = `${item.review_id}${isComplete(item) ? " complete" : " incomplete"}`;
    button.classList.toggle("active", index === state.currentIndex);
    button.classList.toggle("complete", isComplete(item));
    button.addEventListener("click", () => {
      state.currentIndex = index;
      saveState();
      renderApp();
    });
    elements.itemList.append(button);
  });
}

function renderCurrentItem() {
  const item = state.items[state.currentIndex];
  const answer = state.answers[item.review_id] || makeEmptyAnswer(item);
  state.answers[item.review_id] = answer;

  elements.itemCounter.textContent = `Item ${state.currentIndex + 1} / ${state.items.length}`;
  elements.reviewId.textContent = item.review_id;
  elements.articleText.textContent = item.article || "";
  elements.summaryA.textContent = item.summary_a || "";
  elements.summaryB.textContent = item.summary_b || "";
  elements.notes.value = answer.notes || "";
  elements.prevButton.disabled = state.currentIndex === 0;
  elements.nextButton.disabled = state.currentIndex === state.items.length - 1;

  for (const field of REQUIRED_FIELDS) {
    document.querySelectorAll(`input[name="${field}"]`).forEach((input) => {
      input.checked = input.value === answer[field];
    });
  }
}

function updateAnswer(field, value) {
  const item = state.items[state.currentIndex];
  state.answers[item.review_id] = state.answers[item.review_id] || makeEmptyAnswer(item);
  state.answers[item.review_id][field] = value;
  saveState();
  renderItemList();
  renderProgress();
}

function updateNotes(value) {
  const item = state.items[state.currentIndex];
  state.answers[item.review_id] = state.answers[item.review_id] || makeEmptyAnswer(item);
  state.answers[item.review_id].notes = value;
  saveState();
}

function importItems(inputItems, sourceName) {
  if (!Array.isArray(inputItems)) {
    throw new Error("The selected JSON must be an array of review items.");
  }
  for (const [index, item] of inputItems.entries()) {
    for (const field of ["review_id", "article", "summary_a", "summary_b"]) {
      if (!Object.prototype.hasOwnProperty.call(item, field)) {
        throw new Error(`Item ${index + 1} is missing required field "${field}".`);
      }
    }
  }

  const sampled = sampleItems(inputItems);
  state.items = sampled.selectedItems;
  state.selectedArticleKeys = sampled.selectedArticleKeys;
  state.answers = Object.fromEntries(state.items.map((item) => [item.review_id, makeEmptyAnswer(item)]));
  state.currentIndex = 0;
  state.sourceName = sourceName;
  saveState();
  renderApp();
}

function buildExportItems() {
  return state.items.map((item) => {
    const answer = state.answers[item.review_id] || makeEmptyAnswer(item);
    return {
      review_id: item.review_id,
      article: item.article,
      summary_a: item.summary_a,
      summary_b: item.summary_b,
      overall_preference: answer.overall_preference || null,
      factuality_preference: answer.factuality_preference || null,
      coverage_preference: answer.coverage_preference || null,
      notes: answer.notes ? answer.notes : null,
    };
  });
}

function exportResults() {
  const incomplete = state.items.filter((item) => !isComplete(item));
  if (incomplete.length) {
    const proceed = window.confirm(
      `${incomplete.length} review items still have blank required preference fields. Export anyway?`
    );
    if (!proceed) {
      return;
    }
  }

  const evaluator = (state.evaluatorId || "evaluator").trim().replace(/[^a-z0-9_-]+/gi, "_");
  const filename = `human_eval_completed_${evaluator || "evaluator"}.json`;
  const blob = new Blob([JSON.stringify(buildExportItems(), null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function resetProgress() {
  const proceed = window.confirm("Clear saved sample and answers from this browser?");
  if (!proceed) {
    return;
  }
  localStorage.removeItem(STORAGE_KEY);
  state.items = [];
  state.selectedArticleKeys = [];
  state.answers = {};
  state.currentIndex = 0;
  state.evaluatorId = "";
  state.sourceName = "";
  elements.fileInput.value = "";
  renderApp();
}

elements.fileInput.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) {
    return;
  }
  try {
    const text = await file.text();
    importItems(JSON.parse(text), file.name);
  } catch (error) {
    window.alert(`Could not load evaluation JSON: ${error.message}`);
  }
});

elements.evaluatorId.addEventListener("input", (event) => {
  state.evaluatorId = event.target.value;
  saveState();
});

elements.notes.addEventListener("input", (event) => updateNotes(event.target.value));

elements.prevButton.addEventListener("click", () => {
  state.currentIndex = Math.max(0, state.currentIndex - 1);
  saveState();
  renderApp();
});

elements.nextButton.addEventListener("click", () => {
  state.currentIndex = Math.min(state.items.length - 1, state.currentIndex + 1);
  saveState();
  renderApp();
});

elements.jumpIncompleteButton.addEventListener("click", () => {
  const index = state.items.findIndex((item) => !isComplete(item));
  if (index === -1) {
    window.alert("All review items are complete.");
    return;
  }
  state.currentIndex = index;
  saveState();
  renderApp();
});

elements.exportButton.addEventListener("click", exportResults);
elements.resetButton.addEventListener("click", resetProgress);

renderChoiceControls();
loadSavedState();
renderApp();
