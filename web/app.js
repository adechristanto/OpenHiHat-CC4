const elements = {
  connection: document.querySelector("#connection"),
  connectionLabel: document.querySelector("#connection-label"),
  state: document.querySelector("#firmware-state"),
  raw: document.querySelector("#raw-value"),
  filtered: document.querySelector("#filtered-value"),
  cc: document.querySelector("#cc-value"),
  meter: document.querySelector("#live-meter"),
  calibration: document.querySelector("#calibration-value"),
  status: document.querySelector("#status-response"),
  commandFeedback: document.querySelector("#command-feedback"),
  midiFeedback: document.querySelector("#midi-feedback"),
  qualification: document.querySelector("#qualified-check"),
  testValue: document.querySelector("#test-value"),
  testOutput: document.querySelector("#test-value-output"),
  sendValue: document.querySelector("#send-value"),
};

let polling = false;
let commandInFlight = false;
let midiInFlight = false;
let picoConnected = false;

function readField(text, key) {
  const match = text.match(new RegExp(`(?:^|\\s)${key}=([^\\s]+)`));
  return match ? match[1] : null;
}

function setConnection(connected, label) {
  picoConnected = connected;
  elements.connection.dataset.connected = connected ? "true" : "false";
  elements.connectionLabel.textContent = label;
  setCommandButtons(commandInFlight);
}

function showUnavailable(message) {
  setConnection(false, message || "Pico unavailable");
  elements.state.textContent = "Unavailable";
  elements.state.dataset.state = "unavailable";
  elements.raw.textContent = "—";
  elements.filtered.textContent = "—";
  elements.cc.textContent = "—";
  elements.meter.style.width = "0%";
  elements.calibration.textContent = "—";
}

function renderStatus(payload) {
  if (!payload || typeof payload !== "object") {
    showUnavailable("Invalid bridge response");
    elements.status.textContent = "The local bridge returned an invalid status response.";
    return;
  }

  if (!payload.connected) {
    showUnavailable(payload.error || "Pico not connected");
    elements.status.textContent = payload.error || "No Pico connection is available.";
    return;
  }

  const statusText = typeof payload.status === "string"
    ? payload.status
    : payload.status && typeof payload.status === "object"
      ? Object.entries(payload.status).map(([key, value]) => `${key}=${value}`).join(" ")
      : "";
  const state = readField(statusText, "state") || "Connected";
  const raw = readField(statusText, "raw");
  const filtered = readField(statusText, "filtered");
  const cc = readField(statusText, "cc");
  const calibration = statusText.match(/\bcalibration=(open=\d+\s+closed=\d+|not captured)/);

  setConnection(true, "Pico connected");
  elements.state.textContent = state.replaceAll("_", " ");
  if (state === "awaiting_closed") elements.commandFeedback.textContent = "Open captured. Press the pedal fully and select Capture fully closed.";
  if (state === "running") elements.commandFeedback.textContent = "Calibration complete. Move the pedal to check CC4.";
  elements.state.dataset.state = state;
  elements.raw.textContent = raw && raw !== "None" ? raw : "—";
  elements.filtered.textContent = filtered && filtered !== "None" ? filtered : "—";
  elements.cc.textContent = cc && cc !== "None" ? cc : "—";
  elements.meter.style.width = cc && /^\d+$/.test(cc) ? `${(Math.min(127, Number(cc)) / 127) * 100}%` : "0%";
  elements.calibration.textContent = calibration ? calibration[1] : "See status response";
  elements.status.textContent = statusText || "Connected, but the bridge returned no status text.";
  if (payload.error) elements.status.textContent += `\nBridge note: ${payload.error}`;
}

async function refreshStatus() {
  if (polling) return;
  polling = true;
  try {
    const response = await fetch("/api/status", { headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Status request failed (${response.status})`);
    renderStatus(payload);
  } catch (error) {
    showUnavailable("Local bridge unavailable");
    elements.status.textContent = error.message || "Could not reach the local bridge.";
  } finally {
    polling = false;
  }
}

async function postJson(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || payload.response || `Request failed (${response.status})`);
  return payload;
}

async function sendCommand(command) {
  if (commandInFlight) return;
  if (command.startsWith("calibrate ") && !elements.qualification.checked) {
    elements.commandFeedback.textContent = "Confirm the hardware qualification check before calibration.";
    return;
  }
  commandInFlight = true;
  elements.commandFeedback.textContent = `Sending “${command}”…`;
  setCommandButtons(true);
  try {
    const payload = await postJson("/api/command", { command });
    elements.commandFeedback.textContent = payload.response || "Command sent.";
    await refreshStatus();
  } catch (error) {
    elements.commandFeedback.textContent = `Command failed: ${error.message}`;
  } finally {
    commandInFlight = false;
    setCommandButtons(false);
  }
}

function setCommandButtons(busy) {
  const qualified = elements.qualification.checked && picoConnected;
  document.querySelector("#open-calibration").disabled = busy || !qualified;
  document.querySelector("#closed-calibration").disabled = busy || !qualified;
  document.querySelector("#cancel-calibration").disabled = busy || !qualified;
}

async function sendMidi(value) {
  if (midiInFlight) return;
  midiInFlight = true;
  const numericValue = Math.max(0, Math.min(127, Number(value)));
  elements.midiFeedback.textContent = `Sending synthetic CC4 ${numericValue} from OpenHiHat Test…`;
  document.querySelector("#send-test").disabled = true;
  document.querySelectorAll("[data-midi-value]").forEach((button) => { button.disabled = true; });
  try {
    const payload = await postJson("/api/test-midi", { value: numericValue });
    elements.midiFeedback.textContent = payload.response || `Synthetic CC4 ${numericValue} sent from OpenHiHat Test.`;
  } catch (error) {
    elements.midiFeedback.textContent = `Synthetic MIDI send failed: ${error.message}`;
  } finally {
    midiInFlight = false;
    document.querySelector("#send-test").disabled = false;
    document.querySelectorAll("[data-midi-value]").forEach((button) => { button.disabled = false; });
  }
}

elements.qualification.addEventListener("change", () => {
  setCommandButtons(false);
  elements.commandFeedback.textContent = elements.qualification.checked
    ? "Hardware check confirmed. Capture at each fully held endpoint."
    : "Calibration controls are locked until the hardware check is confirmed.";
});

document.querySelector("#refresh-button").addEventListener("click", refreshStatus);
document.querySelector("#open-calibration").addEventListener("click", () => sendCommand("calibrate open"));
document.querySelector("#closed-calibration").addEventListener("click", () => sendCommand("calibrate closed"));
document.querySelector("#cancel-calibration").addEventListener("click", () => sendCommand("cancel"));
elements.testValue.addEventListener("input", () => {
  elements.testOutput.value = elements.testValue.value;
  elements.sendValue.textContent = elements.testValue.value;
});
document.querySelector("#send-test").addEventListener("click", () => sendMidi(elements.testValue.value));
document.querySelectorAll("[data-midi-value]").forEach((button) => {
  button.addEventListener("click", () => {
    const value = button.dataset.midiValue;
    elements.testValue.value = value;
    elements.testOutput.value = value;
    elements.sendValue.textContent = value;
    sendMidi(value);
  });
});

setCommandButtons(false);
async function playPad(number) {
  const note = Number(document.querySelector(`#pad-note-${number}`).value);
  const velocity = Number(document.querySelector("#pad-velocity").value);
  const feedback = document.querySelector("#pad-feedback");
  if (!Number.isInteger(note) || note < 0 || note > 127 || !Number.isInteger(velocity) || velocity < 1 || velocity > 127) {
    feedback.textContent = "Choose a note from 0 to 127 and velocity from 1 to 127.";
    return;
  }
  try {
    const result = await postJson("/api/pad", { note, velocity });
    feedback.textContent = result.response + " from OpenHiHat Test.";
  } catch (error) { feedback.textContent = `Pad failed: ${error.message}`; }
}
document.querySelector("#pad-1").addEventListener("click", () => playPad(1));
document.querySelector("#pad-2").addEventListener("click", () => playPad(2));
document.addEventListener("keydown", (event) => {
  if (event.repeat || event.ctrlKey || event.metaKey || event.altKey || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
  if (event.key.toLowerCase() === "a") playPad(1);
  if (event.key.toLowerCase() === "s") playPad(2);
});
refreshStatus();
window.setInterval(refreshStatus, 250);
