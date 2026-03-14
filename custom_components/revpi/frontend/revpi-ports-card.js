/**
 * Revolution Pi Ports Card
 *
 * A custom Lovelace card that shows the status of all RevPi module ports
 * and allows manipulation of outputs (digital switches, analogue values).
 */

class RevPiPortsCard extends HTMLElement {
  static get properties() {
    return {
      hass: {},
      config: {},
    };
  }

  setConfig(config) {
    if (!config.device) {
      throw new Error("Please define a 'device' (RevPi module name)");
    }
    this.config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _getEntities() {
    if (!this._hass) return { inputs: [], outputs: [] };

    const deviceName = this.config.device;
    const allStates = this._hass.states;
    const inputs = [];
    const outputs = [];

    for (const [entityId, state] of Object.entries(allStates)) {
      const attrs = state.attributes || {};
      // Match entities belonging to our RevPi device
      if (
        attrs.device_name === deviceName ||
        entityId.includes(`revpi_${deviceName.toLowerCase()}`)
      ) {
        if (
          entityId.startsWith("sensor.") &&
          !entityId.includes("_out_sensor")
        ) {
          inputs.push({ entityId, state });
        } else if (
          entityId.startsWith("switch.") ||
          entityId.startsWith("number.")
        ) {
          outputs.push({ entityId, state });
        }
      }
    }
    return { inputs, outputs };
  }

  _render() {
    if (!this.config || !this._hass) return;

    const { inputs, outputs } = this._getEntities();
    const title = this.config.title || `RevPi ${this.config.device}`;

    this.innerHTML = `
      <ha-card header="${title}">
        <div class="card-content" style="padding: 16px;">
          ${
            inputs.length > 0
              ? `
            <div class="section">
              <h3 style="margin: 0 0 8px; font-size: 14px; color: var(--secondary-text-color);">INPUTS</h3>
              <div class="port-grid">
                ${inputs.map((e) => this._renderInput(e)).join("")}
              </div>
            </div>
          `
              : ""
          }
          ${
            outputs.length > 0
              ? `
            <div class="section" style="margin-top: 16px;">
              <h3 style="margin: 0 0 8px; font-size: 14px; color: var(--secondary-text-color);">OUTPUTS</h3>
              <div class="port-grid">
                ${outputs.map((e) => this._renderOutput(e)).join("")}
              </div>
            </div>
          `
              : ""
          }
          ${
            inputs.length === 0 && outputs.length === 0
              ? '<p style="color: var(--secondary-text-color);">No ports found for this device. Check entity configuration.</p>'
              : ""
          }
        </div>
        <style>
          .port-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            gap: 8px;
          }
          .port-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 12px;
            border-radius: 8px;
            background: var(--card-background-color, #fff);
            border: 1px solid var(--divider-color, #e0e0e0);
          }
          .port-item .name {
            font-size: 12px;
            font-weight: 500;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 80px;
          }
          .port-item .value {
            font-size: 14px;
            font-weight: 600;
          }
          .port-item.on {
            border-color: var(--success-color, #4caf50);
            background: rgba(76, 175, 80, 0.1);
          }
          .port-item.off {
            border-color: var(--divider-color, #e0e0e0);
          }
          .toggle-btn {
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            border: none;
            font-size: 12px;
            font-weight: 600;
          }
          .toggle-btn.on {
            background: var(--success-color, #4caf50);
            color: white;
          }
          .toggle-btn.off {
            background: var(--divider-color, #e0e0e0);
            color: var(--primary-text-color);
          }
        </style>
      </ha-card>
    `;

    // Attach event listeners for toggle buttons
    this.querySelectorAll(".toggle-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const entityId = e.target.dataset.entity;
        const isOn = e.target.dataset.state === "on";
        this._hass.callService("switch", isOn ? "turn_off" : "turn_on", {
          entity_id: entityId,
        });
      });
    });
  }

  _renderInput(entity) {
    const { entityId, state } = entity;
    const name = state.attributes.friendly_name || entityId.split(".")[1];
    const shortName = name.replace(/^revpi_/i, "").replace(/_sensor$/, "");
    const val = state.state;
    const isOn = val === "ON" || val === "on" || val === "True";
    const isDigital = val === "ON" || val === "OFF";

    return `
      <div class="port-item ${isDigital ? (isOn ? "on" : "off") : ""}">
        <span class="name" title="${name}">${shortName}</span>
        <span class="value">${isDigital ? (isOn ? "●" : "○") : val}</span>
      </div>
    `;
  }

  _renderOutput(entity) {
    const { entityId, state } = entity;
    const name = state.attributes.friendly_name || entityId.split(".")[1];
    const shortName = name.replace(/^revpi_/i, "");

    if (entityId.startsWith("switch.")) {
      const isOn = state.state === "on";
      return `
        <div class="port-item ${isOn ? "on" : "off"}">
          <span class="name" title="${name}">${shortName}</span>
          <button class="toggle-btn ${isOn ? "on" : "off"}"
                  data-entity="${entityId}"
                  data-state="${state.state}">
            ${isOn ? "ON" : "OFF"}
          </button>
        </div>
      `;
    }

    // Number entity (analogue output)
    return `
      <div class="port-item">
        <span class="name" title="${name}">${shortName}</span>
        <span class="value">${state.state}</span>
      </div>
    `;
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("revpi-ports-card-editor");
  }

  static getStubConfig() {
    return { device: "dio01" };
  }
}

customElements.define("revpi-ports-card", RevPiPortsCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "revpi-ports-card",
  name: "Revolution Pi Ports",
  description: "Shows status and control of RevPi module ports",
});
